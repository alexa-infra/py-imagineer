from io import BytesIO

from huffman.core import get_frequences, get_huffman_table
from huffman.encoding import encode, encode_bin
from huffman.decoding import decode, decode_text


def test_main():
    text = 'hello world'

    b = BytesIO()
    encode(text.encode('utf-8'), b)
    b.seek(0)

    dtext = decode(b)
    result = dtext.decode('utf-8')
    assert result == text


def test_main2():
    text = 'hello world'

    freq = get_frequences(text)
    codes = get_huffman_table(freq)

    b = BytesIO()
    encode_bin(text, codes, b)

    result = decode_text(b.getbuffer(), codes, len(text))
    assert result == text


def test_main3():
    text = 'hello фыва'

    b = BytesIO()
    encode(text.encode('utf-8'), b)
    b.seek(0)

    dtext = decode(b)
    result = dtext.decode('utf-8')
    assert result == text
