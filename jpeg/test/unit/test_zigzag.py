from itertools import repeat, chain
from jpeg.zigzag import zigzag, dezigzag


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

def test_dezigzag():
    z = make_zigzag(8)
    zz = list(chain(*z))
    for i, v in enumerate(zz):
        assert dezigzag[v] == i
