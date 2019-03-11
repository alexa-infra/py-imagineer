from io import BytesIO
import struct
from huffman.decoding import bit_decoder
from huffman.utils import byte_to_bits
from .zigzag import dezigzag
from .idct import idct_2d
from .utils import high_low4, make_array


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

def ext_table(n, length):
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

def test_ext_table():
    assert ext_table(0, 0) == 0
    assert ext_table(0b0, 1) == -1
    assert ext_table(0b1, 1) == 1
    assert ext_table(0b00, 2) == -3
    assert ext_table(0b01, 2) == -2
    assert ext_table(0b10, 2) == 2
    assert ext_table(0b11, 2) == 3
    assert ext_table(0b000, 3) == -7
    assert ext_table(0b111, 3) == 7

def receive_and_extend(reader, length):
    n = receive(reader, length)
    return ext_table(n, length)

def read_huffman(reader, decoder):
    for bit in reader:
        ch = decoder(bit)
        if ch is not None:
            return ch
    return None

def read_dc(reader, decoder, scan):
    s = read_huffman(reader, decoder)
    value = receive_and_extend(reader, s)
    if scan.approx_low:
        value = value << scan.approx_low
    return value

def test_read_dc():
    hh = {
        10: (1, 1, 1, 1, 1, 1, 0)
    }
    decoder = bit_decoder(hh)
    b = BytesIO(b'\xfc\xff\x00\xe2\xaf')
    reader = bit_reader(b)
    value = read_dc(reader, decoder)
    assert value == -512

def read_ac(reader, decoder, scan):
    k = 1 if scan.spectral_start == 0 else scan.spectral_start
    while k <= scan.spectral_end:
        rs = read_huffman(reader, decoder)
        r, s = high_low4(rs)
        if s == 0:
            if r < 15:
                break
            k += 16
            continue
        k += r
        value = receive_and_extend(reader, s)
        if scan.approx_low:
            value = value << scan.approx_low
        yield k, value
        k += 1

def read_baseline(reader, component, block_data, scan):
    qt = component.quantization

    dc_decoder = bit_decoder(component.huffman_dc)
    dc = read_dc(reader, dc_decoder, scan)
    dc += component.last_dc
    component.last_dc = dc
    block_data[0] = dc * qt[0]

    ac_decoder = bit_decoder(component.huffman_ac)
    for z, ac in read_ac(reader, ac_decoder, scan):
        pos = dezigzag[z]
        block_data[pos] = ac * qt[pos]

    idct_2d(block_data)

def get_block(data, block_data, row, col, width):
    offset = row * width + col
    for i in range(8):
        for j in range(8):
            c = 8 * i + j
            block_data[c] = data[offset + i * width + j]

def set_block(data, block_data, row, col, width):
    offset = row * width + col
    for i in range(8):
        for j in range(8):
            c = 8 * i + j
            data[offset + i * width + j] = block_data[c]

def decode_baseline(fp, frame, scan):
    blocks_x = frame.w // (8 * frame.max_h)
    blocks_y = frame.h // (8 * frame.max_v)
    reader = bit_reader(fp)
    tmp = make_array('h', 64)
    n = 0
    components = scan.components
    for block_row in range(blocks_y):
        for block_col in range(blocks_x):
            for comp in components:
                data = comp.data
                h, v = comp.sampling
                w, _ = comp.size
                for i in range(v):
                    for j in range(h):
                        row = 8 * (block_row * v + i)
                        col = 8 * (block_col * h + j)
                        get_block(data, tmp, row, col, w)
                        read_baseline(reader, comp, tmp, scan)
                        set_block(data, tmp, row, col, w)
            n += 1
            if frame.restart_interval and n % frame.restart_interval == 0:
                for c in components:
                    c.last_dc = 0
