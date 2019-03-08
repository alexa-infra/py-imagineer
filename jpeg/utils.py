from array import array
from itertools import repeat


high_low4 = lambda x: ((x >> 4) & 15, x & 15)

def make_array(typecode, n):
    initializer = repeat(0, n)
    return array(typecode, initializer)
