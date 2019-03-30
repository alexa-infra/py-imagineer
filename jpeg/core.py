import struct
import math
from array import array
from io import BytesIO

import huffman
from huffman.decoding import BitDecoder
from .scan_decode import decode, decode_finish
from .zigzag import dezigzag
from . import sof_types
from .utils import high_low4, make_array


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
    def __init__(self, byte):
        super().__init__()
        self.msg = 'unknown marker 0x{0:X}'.format(byte)

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
            raise BadMarker(m)
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
    if self.frame:
        self.frame.restart_interval = self.restart_interval

def parse_DHT(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    while data.tell() < length:
        tc, th = high_low4(read_u8(data))
        if tc > 1 or th > 3:
            raise SyntaxError('bad DHT table')
        is_dc = tc == 0
        maxsymbol = 15 if is_dc else 255

        codes = huffman.decode_table(data)
        for code, _ in codes.items():
            if code < 0 or code > maxsymbol:
                raise SyntaxError('bad Huffman table')

        if is_dc:
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
        dqt = array('B', data.read(64))
        self.quantization[qc] = dequant = make_array('B', 64)
        for i, z in enumerate(dezigzag):
            dequant[z] = dqt[i]

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
    if cc not in (1, 3, 4): # L, YCbCr, CMYK
        raise SyntaxError('bad component count')
    if length < 6 + 3 * cc:
        raise SyntaxError('bad SOF length')

    frame = self.frame = Frame(marker, w, h)
    frame.restart_interval = self.restart_interval
    frame.quantization = self.quantization

    for _ in range(cc):
        idx, q, tq = struct.unpack('3B', data.read(3))
        h, v = high_low4(q)
        frame.add_component(idx, h, v, tq)

class Scan:
    def __init__(self, frame):
        self.position = None
        self.frame = frame
        self.components = []
        self.huffman_dc = {}
        self.huffman_ac = {}
        self.spectral_start = 0
        self.spectral_end = 0
        self.approx_high = 0
        self.approx_low = 0
        self.prog_state = None

    @property
    def is_refine(self):
        return self.approx_high != 0

    @property
    def is_dc(self):
        return self.spectral_start == 0

    @property
    def is_ac(self):
        return self.spectral_start != 0

    @property
    def is_interleaved(self):
        return len(self.components) > 1

def parse_SOS(self, *args): # pylint: disable=unused-argument
    data, length = read_block(self.fp)

    frame = self.frame

    n = read_u8(data)
    if length != n * 2 + 4 or n > 4 or n == 0:
        raise SyntaxError('SOS bad length')

    scan = Scan(frame)

    for _ in range(n):
        idx, c = struct.unpack('2B', data.read(2))
        if idx not in frame.components_ids:
            raise SyntaxError('Bad component id')
        comp = frame.components_ids[idx]
        dc_id, ac_id = high_low4(c)

        scan.huffman_dc[idx] = self.get_dc_decoder(dc_id)
        scan.huffman_ac[idx] = self.get_ac_decoder(ac_id)

        scan.components.append(comp)

    k, e, approx = struct.unpack('3B', data.read(3))
    scan.spectral_start = k
    scan.spectral_end = e
    scan.approx_high, scan.approx_low = high_low4(approx)
    if frame.progressive:
        if scan.is_ac and not n == 1:
            raise SyntaxError('Progressive AC scan has {} components'.format(n))
    else:
        if not (k == 0 and e == 63 and approx == 0):
            raise SyntaxError('Invalid scan values for baseline')
        if not len(frame.components) == n:
            raise SyntaxError('Baseline scan has not enough components')

    scan.position = self.fp.tell()
    self.scans.append(scan)


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

parsers = {
    DHT: parse_DHT,
    DQT: parse_DQT,
    DRI: parse_DRI,
    DNL: parse_DNL,
    APP: parse_APP,
    SOF: parse_SOF,
    SOS: parse_SOS,
}

class Component:
    def __init__(self, idx, h, v, qc):
        self.id = idx
        self.sampling = (h, v)
        self.scale = (0, 0)
        self.qc = qc

        self.size = (0, 0) # effective pixels, non-iterleaved MCU
        self.data = None
        self.blocks_size = (0, 0)
        self.blocks = None

        self.last_dc = 0

    def prepare(self, frame):
        h, v = self.sampling
        self.scale = (frame.max_h // h, frame.max_v // v)

        w2 = math.ceil(frame.w * h / frame.max_h)
        h2 = math.ceil(frame.h * v / frame.max_v)
        self.size = (w2, h2)
        self.data = make_array('h', w2 * h2)

        width = math.ceil(w2 / 8)
        height = math.ceil(h2 / 8)
        self.blocks_size = (width, height)
        self.blocks = [make_array('h', 64) for _ in range(width * height)]

class Frame:
    def __init__(self, marker, w, h):
        self.baseline = marker in sof_types.baseline
        self.extended = marker in sof_types.sequential
        self.progressive = marker in sof_types.progressive
        self.h = h
        self.w = w
        self.components = []
        self.components_ids = {}
        self.restart_interval = None
        self.quantization = None

        self.max_h = 0
        self.max_v = 0
        self.blocks_size = (0, 0)

    def add_component(self, idx, h, v, qc):
        comp = Component(idx, h, v, qc)
        self.components.append(comp)
        self.components_ids[idx] = comp
        self.max_h = max(h, self.max_h)
        self.max_v = max(v, self.max_v)
        return comp

    def prepare(self):
        blocks_x = math.ceil(self.w / (8 * self.max_h))
        blocks_y = math.ceil(self.h / (8 * self.max_v))
        self.blocks_size = blocks_x, blocks_y
        for component in self.components:
            component.prepare(self)

class JpegImage:

    def __init__(self, fp):
        self.fp = fp
        self.is_valid = None

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
        self.scans = []
        self.marker_codes = []

    def get_dc_decoder(self, dc_id):
        huffman_dc = self.huffman_dc.get(dc_id)
        return BitDecoder(huffman_dc) if huffman_dc else None

    def get_ac_decoder(self, ac_id):
        huffman_ac = self.huffman_ac.get(ac_id)
        return BitDecoder(huffman_ac) if huffman_ac else None

    @classmethod
    def is_jpeg(cls, fp):
        try:
            pos = fp.tell()
            data = safe_read(fp, 3)
            return data == b'\xFF\xD8\xFF'
        except EOF:
            return False
        finally:
            fp.seek(pos)

    def read_markers(self):
        self.marker_codes = marker_codes = []

        skip_till_marker = False
        while True:
            if skip_till_marker:
                code = None
                while code is None or code == 0xFF00:
                    code = get_marker_code(self.fp, throw=False)
                skip_till_marker = False
            else:
                code = get_marker_code(self.fp)

            try:
                marker = marker_map[code]
            except KeyError:
                raise BadMarker(code)

            pos = self.fp.tell()
            marker_codes.append((code, marker, pos))

            if marker not in (EOI, SOI, RST):
                read_block(self.fp)

            if marker in (SOS, RST):
                skip_till_marker = True

            if marker == EOI:
                break

    def print_info(self):
        frame = self.frame
        scans = self.scans

        for code, marker, pos in self.marker_codes:
            name = marker_names[marker]
            print('Marker 0x{0:X} {1} {2}'.format(code, name, pos))

        print('Size:', frame.w, frame.h)
        for idx, c in enumerate(frame.components):
            print('Component sampling {}: {}'.format(idx, c.sampling))

        if frame.progressive:
            print('Progressive')
            print('{} scans'.format(len(scans)))
            for scan_i, scan in enumerate(scans):
                scan_type = 'DC' if scan.is_dc else 'AC'
                cids = [str(c.id) for c in scan.components]
                print(' {} scan: {}, isRefine={}, nComp={} ({}), Indexes: {}->{}'.format(
                    scan_i+1, scan_type, scan.is_refine, len(cids),
                    ','.join(cids), scan.spectral_start, scan.spectral_end))
        else:
            print('Baseline')

    def validate_markers(self):
        marker_codes = self.marker_codes
        markers = [m for c, m, p in marker_codes]

        if SOI not in markers:
            raise SyntaxError('SOI not found')
        if not markers.count(SOI) == 1:
            raise SyntaxError('SOI found {} times'.format(markers.count(SOI)))
        if not markers[0] == SOI:
            raise SyntaxError('SOI is not the first market')

        if SOF not in markers:
            raise SyntaxError('SOF not found')
        if not markers.count(SOF) == 1:
            raise SyntaxError('SOF found {} times'.format(markers.count(SOF)))

        SOF_marker = next(c for c, m, p in marker_codes if m == SOF)
        if SOF_marker in sof_types.differential:
            raise SyntaxError('Differential is not supported')
        if SOF_marker in sof_types.loseless:
            raise SyntaxError('Loseless is not supported')
        if SOF_marker in sof_types.arithmetic:
            raise SyntaxError('Arithmetic is not supported')

        if SOS not in markers:
            raise SyntaxError('SOS not found')

        progressive = SOF_marker in sof_types.progressive
        if progressive:
            if markers.count(SOS) == 1:
                raise SyntaxError('Progressive should contain more than one SOS')
        else:
            if not markers.count(SOS) == 1:
                raise SyntaxError('Baseline should contain one SOS')

        SOS_position = markers.index(SOS)
        if SOF not in markers[:SOS_position]:
            raise SyntaxError('SOF should be before SOS')

        if DRI in markers:
            if not markers.count(DRI) == 1:
                raise SyntaxError('DRI found {} times'.format(markers.count(DRI)))
            if RST not in markers:
                raise SyntaxError('Found DRI and no RST')
        else:
            if RST in markers:
                raise SyntaxError('Found RST and no DRI')

        if DHT not in markers:
            raise SyntaxError('DHT is not found')
        if DQT not in markers:
            raise SyntaxError('DQT is not found')

        unsupported = (DAC, DHP, EXP, JPG)
        for marker in unsupported:
            if marker in markers:
                name = marker_names[marker]
                raise SyntaxError('Unsupported 0x{0:X} {1} marker'.format(marker, name))

        if progressive:
            if EOI in markers:
                if not markers.count(EOI) == 1:
                    raise SyntaxError('EOI found {} times'.format(markers.count(EOI)))
                if not markers[-1] == EOI:
                    raise SyntaxError('EOI is not the last market')
        else:
            if EOI not in markers:
                raise SyntaxError('EOI not found')
            if not markers.count(EOI) == 1:
                raise SyntaxError('EOI found {} times'.format(markers.count(EOI)))
            if not markers[-1] == EOI:
                raise SyntaxError('EOI is not the last market')

        if DNL in markers:
            if not markers.count(DNL) == 1:
                raise SyntaxError('DNL found {} times'.format(markers.count(DNL)))
            DNL_position = markers.index(DNL)
            if not DNL_position == SOS_position + 1:
                raise SyntaxError('DNL does not follow first SOS')

    def parse_marker_blocks(self):
        for code, marker, pos in self.marker_codes:
            parser = parsers.get(marker)
            if not parser:
                continue
            self.fp.seek(pos)
            parser(self, code)

    def decode(self):
        self.frame.prepare()

        n_scans = len(self.scans)
        for n, scan in enumerate(self.scans):
            self.fp.seek(scan.position)
            print('Scan {}/{}'.format(n, n_scans))
            decode(self.fp, scan)

        print('Decode finishing..')
        decode_finish(self.frame)

    def process(self):
        try:
            is_valid = False
            self.read_markers()
            self.validate_markers()
            self.parse_marker_blocks()
            self.print_info()
            self.decode()
            is_valid = True
        except EOF:
            print('Unexpected End-of-file')
        except BadMarker as e:
            print('Invalid JPEG structure:', e.msg)
        except SyntaxError as e:
            print('Invalid JPEG data:', e.msg)
        finally:
            self.is_valid = is_valid

    def get_format(self):
        n = len(self.frame.components)
        if n == 4:
            return 'CMYK'
        if n == 3:
            return 'YCbCr'
        if n == 1:
            return 'L'
        return None

    def get_linearized_data(self):
        frame = self.frame
        n = len(frame.components)

        r = make_array('B', frame.w * frame.h * n)
        for row in range(frame.h):
            for col in range(frame.w):
                coord = row * frame.w + col
                for idx, c in enumerate(frame.components):
                    scalex, scaley = c.scale
                    width, _ = c.size

                    coord1 = (row // scaley) * width + (col // scalex)
                    r[coord * n + idx] = c.data[coord1]
        return r
