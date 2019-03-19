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

def test_bits_to_byte():
    assert bits_to_byte((1, 0)) == 0b10
    assert bits_to_byte((1, 0, 1)) == 0b101
    assert bits_to_byte((1, 0, 1, 1)) == 0b1011

def byte_to_bits(byte, length=8):
    return tuple(1 if byte & (1 << i) else 0 for i in rev_range(length))

def test_byte_to_bits():
    assert byte_to_bits(0b10, 2) == (1, 0)
    assert byte_to_bits(0b10, 3) == (0, 1, 0)
    assert byte_to_bits(0b110, 3) == (1, 1, 0)
    assert byte_to_bits(0b1011, 4) == (1, 0, 1, 1)
