import sys
from jpeg import JpegImage
from PIL import Image


def main(filename):
    with open(filename, 'rb') as f:
        img = JpegImage(f)
        img.prescan()
        img.process()

        frame = img.frame

        print('Size:', frame.w, frame.h)
        for idx, c in enumerate(frame.components):
            print('Component sampling {}: {}'.format(idx, c.sampling))

        data = img.get_linearized_data()
        fmt = img.get_format()

        dimg = Image.frombytes(fmt, (frame.w, frame.h), data.tobytes())
        dimg.show()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('1 argument, jpeg image path, is required')
        sys.exit(1)
    main(sys.argv[1])
