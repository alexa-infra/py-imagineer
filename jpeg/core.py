import sys
import struct
import math
from array import array
from io import BytesIO
from itertools import islice, repeat

import huffman
from .scan_decode import decode_baseline


class EOF(Exception):
    pass

class BadMarker(Exception):
    pass

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

def get_marker(f, throw=True):
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

def DRI(self, marker):
    data, length = read_block(self.fp)

    if length < 2:
        raise SyntaxError('bad DRI block')
    self.restart_interval = read_u16(data)

def DHT(self, marker):
    data, length = read_block(self.fp)

    self.dht = True
    while data.tell() < length:
        q = read_u8(data)
        tc = (q >> 4) & 15
        th = (q     ) & 15
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


def DQT(self, marker):
    data, length = read_block(self.fp)

    while data.tell() < length:
        if length - data.tell() < 65:
            raise SyntaxError('bad quantization table size')
        q = read_u8(data)
        qt = (v >> 4) & 15
        qc = (v     ) & 15
        if qt > 0:
            raise SyntaxError('only 8-bit quantization tables are supported')
        self.quantization[qc] = array('B', data.read(64))

def DNL(self, marker):
    data, length = read_block(self.fp)

    if length < 2:
        raise SyntaxError('bad DNL block')
    self.dnl_num_lines = read_u16(data)

def APP(self, marker):
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
            version = data.read(1)
            flag1 = data.read(2)
            flag2 = data.read(2)
            self.adobe_color_transform = read_u8(data)

SOF_names = {
    0xFFC0: 'Baseline',
    0xFFC1: 'Extended sequential, Huffman',
    0xFFC2: 'Progressive, Huffman',
    0xFFC3: 'Lossless, Huffman',
    # 0xFFC4 is DHT
    0xFFC5: 'Differential sequential, Huffman',
    0xFFC6: 'Differential progressive, Huffman',
    0xFFC7: 'Differential loseless, Huffman',
    # 0xFFC8 reserved for JPG Extensions
    0xFFC9: 'Extended sequential, arithmetic',
    0xFFCA: 'Progressive, arithmetic',
    0xFFCB: 'Lossless, arithmetic',
    # 0xFFCC is DAC
    0xFFCD: 'Differential sequential, arithmetic',
    0xFFCE: 'Differential progressive, arithmetic',
    0xFFCF: 'Differential loseless, arithmetic',
}

# Hierarchical, storing multiple images of different sizes
# nonexistent in the world, thus not supported
SOF_differential = (
    0xFFC5,
    0xFFC6,
    0xFFC7,
    0xFFCD,
    0xFFCE,
    0xFFCF,
)

SOF_baseline = (
    0xFFC0,
)

SOF_sequential = (
    0xFFC1,
    0xFFC5,
    0xFFC9,
    0xFFCD,
)

SOF_progressive = (
    0xFFC2,
    0xFFC6,
    0xFFCA,
    0xFFCE,
)

# Loseless are known, but not widely used, thus not supported
SOF_loseless = (
    0xFFC3,
    0xFFC7,
    0xFFCB,
    0xFFCF,
)

SOF_huffman = (
    0xFFC0,
    0xFFC1,
    0xFFC2,
    0xFFC3,
    0xFFC5,
    0xFFC6,
    0xFFC7,
)

# better alternative to huffman, but not widely used
# and proprietar, thus not supported
SOF_arithmetic = (
    0xFFC9,
    0xFFCA,
    0xFFCB,
    0xFFCD,
    0xFFCE,
    0xFFCF,
)

SOF_supported = (
    0xFFC0,
    0xFFC1,
    0xFFC2,
)

def SOF(self, marker):
    self.sof = True

    name = SOF_names[marker]
    print('Found SOF {}'.format(name))
    if marker in SOF_differential:
        raise SyntaxError('Differential is not supported')
    if marker in SOF_arithmetic:
        raise SyntaxError('Arithmetic is not supported')
    if marker in SOF_loseless:
        raise SyntaxError('Loseless is not supported')

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

    for i in range(cc):
        id, q, tq = struct.unpack('3B', data.read(3))
        h = (q >> 4) & 15
        v = (q     ) & 15
        comp = frame.add_component(id, h, v)
        comp.quantization = self.quantization[tq]
    frame.prepare()

def DAC(self, marker):
    """ Define arithmetic coding condition
    """
    data, length = read_block(self.fp)

    raise SyntaxError('DAC is not implemented')

def DHP(self, marker):
    """ Define hierarchical progression
    """
    data, length = read_block(self.fp)

    raise SyntaxError('DHP is not implemented')

def EXP(self, marker):
    """ Expand reference component
    """
    data, length = read_block(self.fp)

    raise SyntaxError('EXP is not implemented')


def COM(self, marker):
    read_block(self.fp)


def SOS(self, marker):
    self.sos = True
    if not self.sof:
        raise SyntaxError('No SOF before SOS')
    frame = self.frame
    if frame.huffman and not self.dht:
        raise SyntaxError('No DHT')

    data, length = read_block(self.fp)

    n = read_u8(data)
    if length != n * 2 + 4 or n > 4:
        raise SyntaxError('SOS bad length')
    if n == 0 and not frame.progressive:
        raise SyntaxError('SOS bad length')

    components = []
    for i in range(n):
        id, c = struct.unpack('BB', data.read(2))
        if id not in frame.components_ids:
            raise SyntaxError('Bad component id')
        comp = frame.components_ids[id]
        dc_id = (c >> 4) & 15
        ac_id = (c     ) & 15
        comp.huffman_dc = self.huffman_dc[dc_id]
        comp.huffman_ac = self.huffman_ac[ac_id]
        components.append(comp)

    spectral_start = read_u8(data)
    spectral_end = read_u8(data)
    successive_approx = read_u8(data)
    successive_prev = (c >> 4) & 15
    successive      = (c     ) & 15

    decode_baseline(self, components)


def SOI(self, marker):
    raise SyntaxError('duplicate SOI')


def EOI(self, marker):
    self.eoi = True


def RST(self, marker):
    pass


def parse_marker(marker):
    #print('Found marker {0:X}'.format(marker))

    if marker == 0xFFC4: # DHT - Define huffman table
        return DHT

    if marker == 0xFFCC: # DAC - Define arithmetic coding condition
        return DAC

    if 0xFFC0 <= marker <= 0xFFCF: # SOF - Start of frame
        return SOF

    if 0xFFD0 <= marker <= 0xFFD7: # Restarts
        return RST

    if marker == 0xFFD8: # SOI - Start of image
        return SOI

    if marker == 0xFFD9: # EOI - End of image
        return EOI

    if marker == 0xFFDA: # SOS - Start of scan
        return SOS

    #if 0xFFDB <= marker <= 0xFFDF:
    if marker == 0xFFDB: # DQT - Define quantization table
        return DQT

    if marker == 0xFFDC: # DNL - Define number of lines
        return DNL

    if marker == 0xFFDD: # DRI - Define restart interval
        return DRI

    if marker == 0xFFDE: # DHP - Define hierarchical progression
        return DHP

    if marker == 0xFFDF: # EXP - Expand reference component
        return EXP

    if 0xFFE0 <= marker <= 0xFFEF: # APP
        return APP

    if marker == 0xFFFE: # COM - Comment
        return COM

    raise SyntaxError('unknown marker 0x{0:X}'.format(marker))

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
        print('buffer_size', buffer_size // 1024, 'KB')
        self.data = make_array('h', buffer_size)

class Frame:
    def __init__(self, marker, w, h, cc):
        self.extended = marker in SOF_sequential
        self.progressive = marker in SOF_progressive
        self.huffman = marker in SOF_huffman
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

        self.sof = False
        self.sos = False
        self.eoi = False
        self.dht = False

        self.frame = None

    def prescan(self):
        skip_till_marker = False
        while True:
            try:
                if skip_till_marker:
                    marker = None
                    while marker is None or marker == 0xFF00:
                        marker = get_marker(self.fp, throw=False)
                    skip_till_marker = False
                else:
                    marker = get_marker(self.fp)

                handler = parse_marker(marker)
                print('Marker 0x{0:X} {1}'.format(marker, handler))

                if handler not in (EOI, SOI, RST):
                    read_block(self.fp)

                if handler is SOS:
                    skip_till_marker = True
            except BadMarker:
                print('Bad marker')
                break
            except EOF:
                print('EOF')
                break


    def read_exif(self):
        marker = get_marker(self.fp)
        handler = parse_marker(marker)
        if handler is not SOI: # SOI - start of image
            raise SyntaxError('no SOI')

        while self.fp and not self.sos and not self.eoi:
            marker = get_marker(self.fp)
            handler = parse_marker(marker)
            if handler is not None:
                handler(self, marker)

        if not self.sos:
            raise SyntaxError('No SOS')


        if self.frame.huffman and not self.dht:
            raise SyntaxError('No DHT')

        print('Good!', 'w h = {} {}'.format(self.frame.w, self.frame.h))
