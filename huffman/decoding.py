import struct
from itertools import chain

from .utils import rev_dict
from .utils import byte_to_bits


read8 = lambda inp: struct.unpack('B', inp.read(1))[0]
read16 = lambda inp: struct.unpack('<H', inp.read(2))[0]


def bit_decoder(codes):
    revcodes = rev_dict(codes)
    bits = list()

    def push(bit):
        bits.append(bit)
        if len(bits) > 16:
            raise SyntaxError('broken huffman code')
        t = tuple(bits)
        if t in revcodes:
            bits.clear()
            return revcodes[t]
        return None
    return push

def byte_decoder(codes):
    decoder = bit_decoder(codes)

    def push(byte):
        bits = byte_to_bits(byte)
        for bit in bits:
            ch = decoder(bit)
            if ch is not None:
                yield ch
    return push


def decode_iterator(data, codes, length):
    decoder = bit_decoder(codes)
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
