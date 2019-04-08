import math
import struct
from itertools import zip_longest

from .core import get_frequences
from .core import get_huffman_table
from .utils import bits_to_byte


write8 = lambda out, val: out.write(struct.pack('B', val))
write16 = lambda out, val: out.write(struct.pack('<H', val))


def get_encoded_length(freq, codes):
    return sum(freq[ch] * len(code) for ch, code in codes.items())


def grouper(iterable, n, fillvalue=None):
    """
        Collect data into fixed-length chunks or blocks
        grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    """
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def iter_codes(text, codes):
    for ch in text:
        code = codes[ch]
        for c in code:
            yield c


def encode_table(codes, output):
    sizes = [0 for x in range(16)]
    for v in codes.values():
        sizes[len(v) - 1] += 1
    for s in sizes:
        write8(output, s)
    acodes = list(codes.items())
    acodes.sort(key=lambda x: len(x[1]))
    for k, v in acodes:
        write8(output, k)


def encode_iterator(data, codes):
    iterable = iter_codes(data, codes)
    for bits in grouper(iterable, 8, 0):
        yield bits


def encode_bin(data, codes, output):
    for bits in encode_iterator(data, codes):
        byte = bits_to_byte(bits)
        write8(output, byte)


def encode(data, output):
    freq = get_frequences(data)
    codes = get_huffman_table(freq)
    encode_table(codes, output)

    write16(output, len(data))
    length = get_encoded_length(freq, codes)
    write16(output, math.ceil(length / 8))

    encode_bin(data, codes, output)
