# pylint: disable=missing-docstring

def rev_range(size):
    return range(size-1, -1, -1)


def rev_dict(dictionary):
    return {v: k for k, v in dictionary.items()}


def bits_to_byte(bits):
    byte = 0
    for pos, value in enumerate(reversed(bits)):
        if value == 1:
            byte = (1 << pos) | byte
    return byte


def byte_to_bits(byte, length=8):
    return tuple(1 if byte & (1 << i) else 0 for i in rev_range(length))
