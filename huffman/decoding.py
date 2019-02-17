import struct
from itertools import chain

from .utils import rev_dict
from .utils import byte_to_bits


read8 = lambda inp: struct.unpack('B', inp.read(1))[0]
read16 = lambda inp: struct.unpack('<H', inp.read(2))[0]


def decode_iterator(data, codes, length):
    revcodes = rev_dict(codes)
    seq = list()
    bitdata = chain(*map(byte_to_bits, data))
    r = 0
    while r < length:
        bit = next(bitdata, None)
        if bit is None:
            return
        seq.append(bit)
        t = tuple(seq)
        if t in revcodes:
            yield revcodes[t]
            seq.clear()
            r += 1


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
            codes[k] = byte_to_bits(code, l)
            code += 1
    return codes

def decode(inp):
    codes = decode_table(inp)
    nsymbols = read16(inp)
    nbytes = read16(inp)
    data = inp.read(nbytes)

    return decode_bin(data, codes, nsymbols)
