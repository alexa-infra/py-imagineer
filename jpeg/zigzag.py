from itertools import repeat, chain


# mapping from row-major 8x8 matrix to position in the zigzag stream
# pylint: disable=bad-whitespace,bad-continuation
zigzag = (
     0,  1,  5,  6, 14, 15, 27, 28,
     2,  4,  7, 13, 16, 26, 29, 42,
     3,  8, 12, 17, 25, 30, 41, 43,
     9, 11, 18, 24, 31, 40, 44, 53,
    10, 19, 23, 32, 39, 45, 52, 54,
    20, 22, 33, 38, 46, 51, 55, 60,
    21, 34, 37, 47, 50, 56, 59, 61,
    35, 36, 48, 49, 57, 58, 62, 63,
)
# pylint: enable=bad-whitespace,bad-continuation

def make_zigzag(n):
    z = list()
    for i in range(n):
        z.append(list(repeat(0, n)))
    x, y = 0, 0
    up = True
    for i in range(0, n * n):
        z[y][x] = i
        if up:
            if x + 1 < n and y - 1 >= 0:
                x += 1
                y -= 1
            else:
                if x + 1 < n:
                    x += 1
                else:
                    y += 1
                up = False
        else:
            if x - 1 >= 0 and y + 1 < n:
                x -= 1
                y += 1
            else:
                if y + 1 < n:
                    y += 1
                else:
                    x += 1
                up = True
    #for row in z:
    #    for col in row:
    #        print('{:2}'.format(col), end=' ')
    #    print()
    return z

def test_zigzag():
    z = make_zigzag(8)
    zz = list(chain(*z))
    for i, v in enumerate(zz):
        assert zigzag[i] == v

# mapping from the zigzag stream to position in the 8x8 row-major matrix
# pylint: disable=bad-whitespace,bad-continuation
dezigzag = (
     0,  1,  8, 16,  9,  2,  3, 10,
    17, 24, 32, 25, 18, 11,  4,  5,
    12, 19, 26, 33, 40, 48, 41, 34,
    27, 20, 13,  6,  7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36,
    29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46,
    53, 60, 61, 54, 47, 55, 62, 63,
)
# pylint: enable=bad-whitespace,bad-continuation

def test_dezigzag():
    z = make_zigzag(8)
    zz = list(chain(*z))
    for i, v in enumerate(zz):
        assert dezigzag[v] == i
