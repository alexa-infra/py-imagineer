from ..utils import byte_to_bits, bits_to_byte


def test_bits_to_byte():
    assert bits_to_byte((1, 0, 0)) == 0b100
    assert bits_to_byte((1, 1, 0, 0)) == 0b1100


def test_byte_to_bits():
    assert byte_to_bits(0b100, 3) == (1, 0, 0)
    assert byte_to_bits(0b100, 4) == (0, 1, 0, 0)
    assert byte_to_bits(0b01, 2) == (0, 1)
    assert byte_to_bits(0b1100) == (0, 0, 0, 0, 1, 1, 0, 0)
