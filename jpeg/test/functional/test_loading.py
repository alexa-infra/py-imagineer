import os
import pytest
from collections import namedtuple
from jpeg import JpegImage


ImgData = namedtuple('ImgData', 'filename, format, size, sampling')

testdata = [
    ImgData("divine-flux.jpg", 'YCbCr', (128, 128), ((1, 1), (1, 1), (1, 1))),
    ImgData("divine-flux2.jpg", 'YCbCr', (128, 128), ((2, 2), (1, 1), (1, 1))),
    ImgData("divine-flux3.jpg", 'L', (128, 128), ((1, 1),)),
    ImgData("divine-flux4.jpg", 'YCbCr', (128, 128), ((1, 1), (1, 1), (1, 1))),
    ImgData("divine-flux5.jpg", 'YCbCr', (128, 128), ((2, 1), (1, 1), (1, 1))),
    ImgData("divine-flux6.jpg", 'YCbCr', (128, 128), ((1, 2), (1, 1), (1, 1))),
    ImgData("divine-flux7.jpg", 'YCbCr', (128, 128), ((2, 2), (1, 1), (1, 1))),
]

def get_path(filename):
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'data', filename)

@pytest.fixture(params=testdata)
def img_data(request):
    return request.param

def raw_loading(filename):
    path = get_path(filename)
    with open(path, 'rb') as f:
        img = JpegImage(f)
        img.process()
        return img

def test_loading(img_data):
    img = raw_loading(img_data.filename)
    assert img.is_valid
    assert img.get_format() == img_data.format
    frame = img.frame
    size = (frame.w, frame.h)
    sampling = tuple(c.sampling for c in frame.components)
    assert size == img_data.size
    assert sampling == img_data.sampling
    data = img.get_linearized_data()
    assert data

def test_loading_failed():
    img = raw_loading('divine-flux.png')
    assert not img.is_valid

def test_is_jpeg():
    path = get_path('divine-flux.jpg')
    with open(path, 'rb') as f:
        assert JpegImage.is_jpeg(f)

def test_is_not_jpeg():
    path = get_path('divine-flux.png')
    with open(path, 'rb') as f:
        assert not JpegImage.is_jpeg(f)
