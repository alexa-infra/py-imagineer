import struct
from itertools import chain, repeat

from .utils import byte_to_bits, bits_to_byte


read8 = lambda inp: struct.unpack('B', inp.read(1))[0]
read16 = lambda inp: struct.unpack('<H', inp.read(2))[0]


class BitDecoder:
    def __init__(self, codes):
        self.rcodes = dict()
        self.lcodes = list(repeat(0, 17))
        self.bits_len = 0
        self.cached = 0
        for code, bits in codes.items():
            length = len(bits)
            val = bits_to_byte(bits)
            self.rcodes[(length, val)] = code
            self.lcodes[length] += 1

    def __call__(self, bit):
        assert bit in (0, 1)
        if self.bits_len + 1 > 16:
            raise SyntaxError('broken huffman code')

        self.bits_len += 1
        self.cached = (self.cached << 1) | bit

        if not self.lcodes[self.bits_len]:
            return None

        key = (self.bits_len, self.cached)

        code = self.rcodes.get(key)
        if code is None:
            return None

        self.bits_len = 0
        self.cached = 0
        return code

    def reset(self):
        self.bits_len = 0
        self.cached = 0

def byte_decoder(codes):
    decoder = BitDecoder(codes)

    def push(byte):
        bits = byte_to_bits(byte)
        for bit in bits:
            ch = decoder(bit)
            if ch is not None:
                yield ch
    return push


def decode_iterator(data, codes, length):
    decoder = BitDecoder(codes)
    bitdata = chain(*map(byte_to_bits, data))
    r = 0
    while r < length:
        bit = next(bitdata, None)
        if bit is None:
            return
        ch = decoder(bit)
        if not ch:
            continue
        r += 1
        yield ch


def decode_text(data, codes, length):
    return ''.join(decode_iterator(data, codes, length))


def decode_bin(data, codes, length):
    return bytearray(decode_iterator(data, codes, length))


def decode_table(inp):
    sizes = struct.unpack('16B', inp.read(16))

    codes = dict()
    code = 0
    for l, s in enumerate(sizes):
        code = code << 1
        for _ in range(s):
            k = struct.unpack('B', inp.read(1))[0]
            codes[k] = byte_to_bits(code, l + 1)
            code += 1
    return codes

def decode(inp):
    codes = decode_table(inp)
    nsymbols = read16(inp)
    nbytes = read16(inp)
    data = inp.read(nbytes)

    return decode_bin(data, codes, nsymbols)
