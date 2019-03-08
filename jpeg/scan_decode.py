import math
from io import BytesIO
from array import array
import struct
from huffman.decoding import bit_decoder
from huffman.utils import byte_to_bits
from .zigzag import dezigzag


def bit_reader(data):
    bits = None
    bit_counter = 0

    while True:
        if not bits or bit_counter >= 8:
            byte = data.read(1)
            if not byte:
                return # EOF
            byte = struct.unpack('B', byte)[0]
            if byte == 0xFF:
                next_byte = data.read(1)
                if not next_byte:
                    return
                next_byte = struct.unpack('B', next_byte)[0]
                if 0xD0 <= next_byte <= 0xD7:
                    yield None # signals decoder to reset bit counter
                    # TODO: reset DC
                    continue
                elif next_byte == 0x00:
                    pass # 0xFF00 is encoded 0xFF
                else:
                    raise SyntaxError('found 0xFF{0:X} marker'.format(next_byte))
            bits = byte_to_bits(byte)
            bit_counter = 0

        yield bits[bit_counter]
        bit_counter += 1

def test_bit_reader():
    b = BytesIO(b'\xa0')
    r = bit_reader(b)
    bits = tuple(r)
    assert bits == (1, 0, 1, 0, 0, 0, 0, 0)

def test_bit_reader2():
    b = BytesIO(b'\xa0\x0f')
    r = bit_reader(b)
    bits = tuple(r)
    assert bits == (1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1)

def test_bit_reader_ff00():
    b = BytesIO(b'\xff\x00\xa0')
    r = bit_reader(b)
    bits = tuple(r)
    assert bits == (1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0)

def receive(r, length):
    n = 0
    while length:
        n = (n << 1) | next(r)
        length -= 1
    return n

_bias = lambda n: (-1 << n) + 1
bias = [_bias(n) for n in range(16)]

_bmask = lambda n: (1 << n) - 1
bmask = [_bmask(n) for n in range(17)]

def dc_table(n, length):
    """
    length=0                        -> 0
    length=1 0b0, 0b1               -> -1, 1
    length=2 0b00, 0b01, 0b10, 0b11 -> -3, -2, 2, 3
    length=3 0b000, ..., 0b111      -> -7, -6, -5, -4, 4, 5, 6, 7
    ....
    """
    if length == 0:
        return 0
    if n <= bmask[length - 1]: # if most sign bit is not set
        return n + bias[length]
    return n

def test_dc_table():
    assert dc_table(0, 0) == 0
    assert dc_table(0b0, 1) == -1
    assert dc_table(0b1, 1) == 1
    assert dc_table(0b00, 2) == -3
    assert dc_table(0b01, 2) == -2
    assert dc_table(0b10, 2) == 2
    assert dc_table(0b11, 2) == 3
    assert dc_table(0b000, 3) == -7
    assert dc_table(0b111, 3) == 7

def receive_and_extend(reader, length):
    n = receive(reader, length)
    return dc_table(n, length)

def read_huffman(reader, decoder):
    for bit in reader:
        ch = decoder(bit)
        if ch is not None:
            return ch

def read_dc(reader, decoder):
    s = read_huffman(reader, decoder)
    return receive_and_extend(reader, s)

def test_read_dc():
    hh = {
        10: (1, 1, 1, 1, 1, 1, 0)
    }
    decoder = bit_decoder(hh)
    b = BytesIO(b'\xfc\xff\x00\xe2\xaf')
    reader = bit_reader(b)
    value = read_dc(reader, decoder)
    assert value == -512

def read_ac(reader, decoder):
    k = 1
    while k < 64:
        rs = read_huffman(reader, decoder)
        r = (rs >> 4) & 15
        s = (rs     ) & 15
        if s == 0:
            if r < 15:
                return
            k += 16
            continue
        k += r
        value = receive_and_extend(reader, s)
        yield k, value
        k += 1

def read_baseline(reader, component, offset):
    dc_decoder = bit_decoder(component.huffman_dc)
    ac_decoder = bit_decoder(component.huffman_ac)
    block_data = component.data
    qt = component.quantization

    last_dc = component.last_dc

    dc = read_dc(reader, dc_decoder)
    dc += last_dc
    block_data[offset] *= qt[0]
    for z, ac in read_ac(reader, ac_decoder):
        pos = dezigzag[z]
        block_data[pos] = ac * qt[pos]

    component.last_dc = last_dc

def decode_baseline(self, components):
    frame = self.frame
    w = frame.w // (8 * frame.max_h)
    h = frame.h // (8 * frame.max_v)
    reader = bit_reader(self.fp)
    for row in range(h):
        for col in range(w):
            for comp in components:
                a, b = comp.sampling
                w2 = math.ceil(w // 8 * a / frame.max_h)
                for i in range(a):
                    block_row = row * a + i
                    for j in range(b):
                        block_col = col * b + j
                        offset = 64 * (w2 * block_row + block_col)
                        read_baseline(reader, comp, offset)
