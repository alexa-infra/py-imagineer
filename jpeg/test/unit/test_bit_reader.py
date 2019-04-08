from io import BytesIO
from jpeg.scan_decode import BitReader


def test_bit_reader():
    b = BytesIO(b'\xa0')
    r = BitReader(b)
    bits = tuple(r)
    assert bits == (1, 0, 1, 0, 0, 0, 0, 0)

def test_bit_reader2():
    b = BytesIO(b'\xa0\x0f')
    r = BitReader(b)
    bits = tuple(r)
    assert bits == (1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1)

def test_bit_reader_ff00():
    b = BytesIO(b'\xff\x00\xa0')
    r = BitReader(b)
    bits = tuple(r)
    assert bits == (1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0)
