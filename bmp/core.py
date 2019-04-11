import struct
from jpeg.core import safe_read
from jpeg.scan_decode import clamp

def mime_check(fp):
    data = safe_read(fp, 2)
    return data == b'BM'

def read_header(self, fp):
    data = safe_read(fp, 2)
    if data != b'BM':
        raise SyntaxError('Invalid header')
    filesize, _, data_offset = struct.unpack('<III', safe_read(fp, 12))
    self.filesize = filesize
    self.data_offset = data_offset

int_clamp = lambda x: int(clamp(x))

def write_bmp(fp, fmt, w, h, pixels):

    padding = (w * 3) % 4
    padding = 0 if padding == 0 else (4 - padding)
    filesize = 14 + 40 + (w * 3 + padding) * h

    fp.write(b'BM')
    fp.write(struct.pack('<III', filesize, 0, 14+40))

    fp.write(struct.pack('<III', 40, w, h))
    fp.write(struct.pack('HH', 1, 24))
    fp.write(struct.pack('<I', 0) * 6)

    padding_bytes = b'\x00' * padding
    for y in range(h-1, -1, -1):
        for x in range(0, w):
            coord = w * y + x
            r, g, b = 0, 0, 0
            if fmt == 'YCbCr':
                c = coord * 3
                Y, cb, cr = pixels[c:c+3]
                Y, cb, cr = Y - 128, cb - 128, cr - 128
                # c_red = 0.299
                # c_green = 0.587
                # c_blue = 0.114
                # r = cr * (2 - 2*c_red) + y
                # b = cb * (2 - 2*c_blue) + y
                # g = (y - c_blue*b - c_red*r) / c_green
                r = int_clamp(Y + 1.402 * cr)
                b = int_clamp(Y + 1.772 * cb)
                g = int_clamp(Y - 0.34414 * cb - 0.71414 * cr)
            elif fmt == 'RGB':
                c = coord * 3
                r, g, b = pixels[c:c+3]
            elif fmt == 'L':
                L = pixels[coord]
                r, g, b = L, L, L
            else:
                assert False
            fp.write(struct.pack('BBB', b, g, r))
        fp.write(padding_bytes)
