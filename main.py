import sys
from tempfile import NamedTemporaryFile
import subprocess
from jpeg import JpegImage
from bmp.core import write_bmp


def main(infile):
    with open(infile, 'rb') as f:
        img = JpegImage(f)
        img.process()
        if not img.is_valid:
            return

        frame = img.frame
        data = img.get_linearized_data()
        fmt = img.get_format()

    # from PIL import Image
    # dimg = Image.frombytes(fmt, (frame.w, frame.h), data.tobytes())
    # dimg.show()

    with NamedTemporaryFile() as f:
        write_bmp(f, fmt, frame.w, frame.h, data)
        f.flush()
        subprocess.run(['display', f.name])


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('1 argument, jpeg image path, is required')
        sys.exit(1)
    main(sys.argv[1])
