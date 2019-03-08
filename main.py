import sys
from jpeg import JpegImage
from jpeg.core import make_array
from PIL import Image
from array import array


def main(filename):
    with open(filename, 'rb') as f:
        img = JpegImage(f)
        img.prescan()
        img.process()

        frame = img.frame
        n = len(frame.components)

        print('Size:', frame.w, frame.h)
        for idx, c in enumerate(frame.components):
            print('Component sampling {}: {}'.format(idx, c.sampling))

        r = make_array('B', frame.w * frame.h * n)
        for row in range(frame.h):
            for col in range(frame.w):
                coord = row * frame.w + col
                for idx, c in enumerate(frame.components):
                    h, v = c.sampling
                    scalex, scaley = frame.max_h // h, frame.max_v // v
                    width, _ = c.size

                    coord1 = (row // scalex) * width + (col // scaley)
                    r[coord * n + idx] = c.data[coord1]
        fmt = None
        if n == 3:
            fmt = 'YCbCr'
        elif n == 1:
            fmt = 'L'
        dimg = Image.frombytes(fmt, (frame.w, frame.h), r.tobytes())
        dimg.show()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('1 argument, jpeg image path, is required')
        sys.exit(1)
    main(sys.argv[1])
