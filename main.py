import sys
from jpeg import JpegImage
from PIL import Image


def main(filename):
    with open(filename, 'rb') as f:
        img = JpegImage(f)
        img.process()
        if not img.is_valid:
            return

        frame = img.frame
        data = img.get_linearized_data()
        fmt = img.get_format()

        dimg = Image.frombytes(fmt, (frame.w, frame.h), data.tobytes())
        dimg.show()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('1 argument, jpeg image path, is required')
        sys.exit(1)
    main(sys.argv[1])
