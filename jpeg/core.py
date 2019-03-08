import struct
import math
from array import array
from io import BytesIO
from itertools import islice, repeat

import huffman
from .scan_decode import decode_baseline
from . import sof_types


SOF, DHT, DAC, JPG, RST, SOI, EOI, SOS, DQT, DNL, DRI, DHP, EXP, APP, COM = tuple(range(15))

marker_names = {
    SOF: 'SOF',
    DHT: 'DHT',
    DAC: 'DAC',
    JPG: 'JPG',
    RST: 'RST',
    SOI: 'SOI',
    EOI: 'EOI',
    SOS: 'SOS',
    DQT: 'DQT',
    DNL: 'DNL',
    DRI: 'DRI',
    DHP: 'DHP',
    EXP: 'EXP',
    APP: 'APP',
    COM: 'COM',
}

class EOF(Exception):
    pass

class BadMarker(Exception):
    pass

high_low4 = lambda x: ((x >> 4) & 15, x & 15)

def make_array(typecode, n):
    initializer = islice(repeat(0), n)
    return array(typecode, initializer)

def safe_read(f, n):
    data = f.read(n)
    if not data or len(data) != n:
        raise EOF()
    return data

def read_u8(f):
    data = safe_read(f, 1)
    return struct.unpack('B', data)[0]

def read_u16(f):
    """ big-endian """
    data = safe_read(f, 2)
    return struct.unpack('>H', data)[0]

def get_marker_code(f, throw=True):
    m = read_u8(f)
    if m != 0xFF:
        if throw:
            raise BadMarker()
        return None
    n = read_u8(f)
    return (m << 8) | n

def read_block(f):
    length = read_u16(f) - 2
    if length < 0:
        raise SyntaxError('Bad block size')
    data = safe_read(f, length)
    return BytesIO(data), length

def parse_DRI(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    if length < 2:
        raise SyntaxError('bad DRI block')
    self.restart_interval = read_u16(data)

def parse_DHT(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    while data.tell() < length:
        tc, th = high_low4(read_u8(data))
        if tc > 1 or th > 3:
            raise SyntaxError('bad DHT table')
        isDC = tc == 0
        maxsymbol = 15 if isDC else 255

        codes = huffman.decode_table(data)
        for code, _ in codes.items():
            if code < 0 or code > maxsymbol:
                raise SyntaxError('bad Huffman table')

        if isDC:
            self.huffman_dc[th] = codes
        else:
            self.huffman_ac[th] = codes


def parse_DQT(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    while data.tell() < length:
        if length - data.tell() < 65:
            raise SyntaxError('bad quantization table size')
        qt, qc = high_low4(read_u8(data))
        if qt > 0:
            raise SyntaxError('only 8-bit quantization tables are supported')
        self.quantization[qc] = array('B', data.read(64))

def parse_DNL(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    if length < 2:
        raise SyntaxError('bad DNL block')
    self.dnl_num_lines = read_u16(data)

def parse_APP(self, marker, *args): # pylint: disable=unused-argument
    data, _ = read_block(self.fp)

    if marker == 0xFFE0:
        header = data.read(5)

        if header == b'JFIF\x00':
            self.jfif = True

        if header == b'JFXX\x00':
            self.jfxx = True

    if marker == 0xFFE1:
        header = data.read(5)

        if header == b'Exif\x00':
            self.exif = True

    if marker == 0xFFEE:
        header = data.read(6)

        if header == b'Adobe\x00':
            self.adobe = True
            data.read(5)
            self.adobe_color_transform = read_u8(data)


def parse_SOF(self, marker, *args): # pylint: disable=unused-argument

    data, length = read_block(self.fp)

    if length < 6:
        raise SyntaxError('bad SOF length')
    num_bits, sof_num_lines, w, cc = struct.unpack('>BHHB', data.read(6))

    h = self.dnl_num_lines if self.dnl_num_lines else sof_num_lines

    if num_bits != 8:
        raise SyntaxError('only 8-bit is supported')
    if w == 0 or h == 0:
        raise SyntaxError('0 width or height')
    if cc not in (1, 3, 4): # L, RGB, CMYK
        raise SyntaxError('bad component count')
    if length < 6 + 3 * cc:
        raise SyntaxError('bad SOF length')

    frame = self.frame = Frame(marker, w, h, cc)

    for _ in range(cc):
        idx, q, tq = struct.unpack('3B', data.read(3))
        h, v = high_low4(q)
        comp = frame.add_component(idx, h, v)
        comp.quantization = self.quantization[tq]
    frame.prepare()

def parse_SOS(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    frame = self.frame

    n = read_u8(data)
    if length != n * 2 + 4 or n > 4:
        raise SyntaxError('SOS bad length')
    if n == 0 and not frame.progressive:
        raise SyntaxError('SOS bad length')

    components = []
    for _ in range(n):
        idx, c = struct.unpack('BB', data.read(2))
        if idx not in frame.components_ids:
            raise SyntaxError('Bad component id')
        comp = frame.components_ids[idx]
        dc_id, ac_id = high_low4(c)
        comp.huffman_dc = self.huffman_dc[dc_id]
        comp.huffman_ac = self.huffman_ac[ac_id]
        components.append(comp)

    # pylint: disable=unused-variable
    spectral_start = read_u8(data)
    spectral_end = read_u8(data)
    successive_prev, successive = high_low4(read_u8(data))
    # pylint: enable=unused-variable

    decode_baseline(self, components)

marker_map = {
    0xFFC0: SOF, # SOF - Start of frame
    0xFFC1: SOF,
    0xFFC2: SOF,
    0xFFC3: SOF,
    0xFFC4: DHT, # DHT - Define huffman table
    0xFFC5: SOF,
    0xFFC6: SOF,
    0xFFC7: SOF,
    0xFFC8: JPG, # Reserved for extensions
    0xFFC9: SOF,
    0xFFCA: SOF,
    0xFFCB: SOF,
    0xFFCC: DAC, # DAC - Define arithmetic coding condition
    0xFFCE: SOF,
    0xFFCF: SOF,

    0xFFD0: RST, # Restarts
    0xFFD1: RST,
    0xFFD2: RST,
    0xFFD3: RST,
    0xFFD4: RST,
    0xFFD5: RST,
    0xFFD6: RST,
    0xFFD7: RST,

    0xFFD8: SOI, # SOI - Start of image
    0xFFD9: EOI, # EOI - End of image
    0xFFDA: SOS, # SOS - Start of scan
    0xFFDB: DQT, # DQT - Define quantization table
    0xFFDC: DNL, # DNL - Define number of lines
    0xFFDD: DRI, # DRI - Define restart interval
    0xFFDE: DHP, # DHP - Define hierarchical progression
    0xFFDF: EXP, # EXP - Expand reference component

    0xFFE0: APP, # APP - Application marker
    0xFFE1: APP,
    0xFFE2: APP,
    0xFFE3: APP,
    0xFFE4: APP,
    0xFFE5: APP,
    0xFFE6: APP,
    0xFFE7: APP,
    0xFFE8: APP,
    0xFFE9: APP,
    0xFFEA: APP,
    0xFFEB: APP,
    0xFFEC: APP,
    0xFFED: APP,
    0xFFEE: APP,
    0xFFEF: APP,
    0xFFFE: COM, # COM - Comment
}

def parse_marker_code(marker):

    if marker not in marker_map:
        raise BadMarker('unknown marker 0x{0:X}'.format(marker))
    return marker_map[marker]

class Component:
    def __init__(self, idx, h, v):
        self.id = idx
        self.sampling = (h, v)
        self.quantization = None
        self.huffman_dc = None
        self.huffman_ac = None

        self.size = (0, 0) # effective pixels, non-iterleaved MCU
        self.data = None

        self.last_dc = 0

    @property
    def mcu_size(self):
        h, v = self.sampling
        return h * 8, v * 8

    def prepare(self, frame):
        h, v = self.sampling
        w2 = math.ceil(frame.w * h / frame.max_h)
        h2 = math.ceil(frame.h * v / frame.max_v)
        self.size = (w2, h2)
        buffer_size = w2 * h2
        #print('buffer_size', buffer_size // 1024, 'KB')
        self.data = make_array('h', buffer_size)

class Frame:
    def __init__(self, marker, w, h, cc):
        self.baseline = marker in sof_types.baseline
        self.extended = marker in sof_types.sequential
        self.progressive = marker in sof_types.progressive
        self.h = h
        self.w = w
        self.num_components = cc
        self.components = []
        self.components_ids = {}

        self.max_h = 0
        self.max_v = 0

    def add_component(self, idx, h, v):
        assert len(self.components) + 1 <= self.num_components
        comp = Component(idx, h, v)
        self.components.append(comp)
        self.components_ids[idx] = comp
        self.max_h = max(h, self.max_h)
        self.max_v = max(v, self.max_v)
        return comp

    def prepare(self):
        for component in self.components:
            component.prepare(self)

class JpegImage:

    def __init__(self, fp):
        self.fp = fp

        self.huffman_dc = {}
        self.huffman_ac = {}
        self.quantization = {}
        self.restart_interval = None
        self.dnl_num_lines = None

        self.jfif = None
        self.jfxx = None
        self.adobe = None
        self.adobe_color_transform = None

        self.frame = None
        self.marker_codes = []

    def prescan(self):
        self.marker_codes = marker_codes = []

        skip_till_marker = False
        while True:
            try:
                if skip_till_marker:
                    code = None
                    while code is None or code == 0xFF00:
                        code = get_marker_code(self.fp, throw=False)
                    skip_till_marker = False
                else:
                    code = get_marker_code(self.fp)

                marker = parse_marker_code(code)
                pos = self.fp.tell()
                marker_codes.append((code, marker, pos))

                if marker not in (EOI, SOI, RST):
                    read_block(self.fp)

                if marker in (SOS, RST):
                    skip_till_marker = True
            except BadMarker:
                print('Bad marker')
                break
            except EOF:
                break

        for code, marker, pos in marker_codes:
            name = marker_names[marker]
            print('Marker 0x{0:X} {1} {2}'.format(code, name, pos))

        markers = [m for c, m, p in marker_codes]
        assert markers.count(SOI) == 1 and markers[0] == SOI
        assert markers.count(EOI) == 1 and markers[-1] == EOI

        assert markers.count(SOF) == 1
        SOF_marker = next(c for c, m, p in marker_codes if m == SOF)
        assert SOF_marker not in sof_types.differential
        assert SOF_marker not in sof_types.loseless
        assert SOF_marker not in sof_types.arithmetic

        assert SOS in markers

        if DRI in markers:
            assert markers.count(DRI) == 1
            assert RST in markers
        else:
            assert RST not in markers

        assert DHT in markers
        assert DQT in markers

        assert DAC not in markers
        assert DHP not in markers
        assert EXP not in markers
        assert JPG not in markers

    def process(self):

        def iter_markers(marker):
            for c, m, p in self.marker_codes:
                if m == marker:
                    yield c, p

        def process_marker(marker, parse_func):
            for code, pos in iter_markers(marker):
                self.fp.seek(pos)
                parse_func(self, code)

        process_marker(DHT, parse_DHT)
        process_marker(DQT, parse_DQT)
        process_marker(DRI, parse_DRI)
        process_marker(DNL, parse_DNL)
        process_marker(APP, parse_APP)
        process_marker(SOF, parse_SOF)
        print('Good!', 'w h = {} {}'.format(self.frame.w, self.frame.h))
        process_marker(SOS, parse_SOS)
