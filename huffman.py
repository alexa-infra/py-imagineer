import math
from collections import defaultdict, namedtuple
from itertools import zip_longest, chain
from io import BytesIO
import heapq
import struct


Node = namedtuple('Node', ['cargo', 'left', 'right'])

def rev_range(n):
    return range(n-1, -1, -1)


def rev_dict(d):
    return {v: k for k, v in d.items()}

def node_is_leaf(node):
    return not node.left and not node.right

def iter_nodes(node):
    """ Depth-first, left-to-right binary tree traversal
    """
    stack = list()
    while stack or node:
        if node:
            stack.append(node)
            node = node.left
        else:
            node = stack.pop()
            yield node
            node = node.right

def test_iter_nodes():
    root = Node(1,
                Node(2,
                     Node(4, None, None),
                     Node(5, None, None)),
                Node(3, None, None))
    expected = [4, 2, 5, 1, 3]
    assert list(x.cargo for x in iter_nodes(root)) == expected


def iter_leafs(root):
    parents = dict()
    leafs = list()
    for node in iter_nodes(root):
        if node_is_leaf(node):
            leafs.append(node)
        else:
            parents[node.left] = (node, 0)
            parents[node.right] = (node, 1)
    for node in leafs:
        cargo = node.cargo
        path = list()
        while node in parents:
            node, c = parents[node]
            path.append(c)
        path.reverse()
        yield cargo, tuple(path)


def test_iter_leafs():
    root = Node(1,
                Node(2,
                     Node(4, None, None),
                     Node(5, None, None)),
                Node(3, None, None))
    expected = [4, 5, 3]
    assert list(x for x, _ in iter_leafs(root)) == expected



def get_frequences(text):
    freq = defaultdict(int)
    for ch in text:
        freq[ch] += 1
    return freq


def bits_to_byte(bits):
    byte = 0
    for pos, value in enumerate(reversed(bits)):
        if value == 1:
            byte = (1 << pos) | byte
    return byte


def test_bits_to_byte():
    assert bits_to_byte((1, 0, 0)) == 0b100
    assert bits_to_byte((1, 1, 0, 0)) == 0b1100


def byte_to_bits(byte, length=8):
    return tuple(1 if byte & (1 << i) else 0 for i in rev_range(length))


def test_byte_to_bits():
    assert byte_to_bits(0b100, 3) == (1, 0, 0)
    assert byte_to_bits(0b100, 4) == (0, 1, 0, 0)
    assert byte_to_bits(0b01, 2) == (0, 1)
    assert byte_to_bits(0b1100) == (0, 0, 0, 0, 1, 1, 0, 0)


def check_huffman_table(codes):
    code = 0
    revcodes = rev_dict(codes)
    codeslist = list(codes.values())
    codeslist.sort(key=len)
    p = 0
    for v in codeslist:
        l = len(v)
        if l != p:
            code = code << 1
            p = l
        bits = byte_to_bits(code, l)
        if bits not in revcodes:
            return False
        code += 1
    return True


def make_huffman_tree(freq):
    """
    Note: we sort at first by number of nodes in subtree and then by weight
    """
    nodes = {k: Node(k, None, None) for k, v in freq.items()}
    heap = [(0, v, nodes[k]) for k, v in freq.items()]
    heapq.heapify(heap)
    while len(heap) > 1:
        n1, weight1, node1 = heapq.heappop(heap)
        n2, weight2, node2 = heapq.heappop(heap)
        ttype = type(node1.cargo)
        node = Node(ttype(), node1, node2)
        heapq.heappush(heap, (n1+n2+2, weight1+weight2, node))
    _, _, root = heap[0]
    return root


def get_huffman_table(freq):
    root = make_huffman_tree(freq)
    codes = {ch: path for ch, path in iter_leafs(root)}
    return codes


def test_huffman_table():
    freq = get_frequences('A_DEAD_DAD_CEDED_A_BAD_BABE_A_BEADED_ABACA_BED')
    h = get_huffman_table(freq)
    assert check_huffman_table(h)


def test_huffman_table2():
    freq = get_frequences('hello world')
    h = get_huffman_table(freq)
    assert check_huffman_table(h)

def test_huffman_table3():
    freq = get_frequences('hello фыва')
    h = get_huffman_table(freq)
    assert check_huffman_table(h)

def test_huffman_table4():
    freq = get_frequences('hello фыва'.encode('utf-8'))
    h = get_huffman_table(freq)
    assert check_huffman_table(h)


def get_encoded_length(freq, codes):
    return sum(freq[ch] * len(code) for ch, code in codes.items())


def grouper(iterable, n, fillvalue=None):
    """
        Collect data into fixed-length chunks or blocks
        grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    """
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def iter_codes(text, codes):
    for ch in text:
        code = codes[ch]
        for c in code:
            yield c


write8 = lambda out, val: out.write(struct.pack('B', val))
write16 = lambda out, val: out.write(struct.pack('<H', val))
read8 = lambda inp: struct.unpack('B', inp.read(1))[0]
read16 = lambda inp: struct.unpack('<H', inp.read(2))[0]


def encode_table(codes, output):
    sizes = [0 for x in range(16)]
    for v in codes.values():
        sizes[len(v)] += 1
    for s in sizes:
        write8(output, s)
    acodes = list(codes.items())
    acodes.sort(key=lambda x: len(x[1]))
    for k, v in acodes:
        write8(output, k)


def encode_iterator(data, codes):
    iterable = iter_codes(data, codes)
    for bits in grouper(iterable, 8, 0):
        yield bits


def encode(data, output):
    freq = get_frequences(data)
    codes = get_huffman_table(freq)
    encode_table(codes, output)

    write16(output, len(data))
    length = get_encoded_length(freq, codes)
    write16(output, math.ceil(length / 8))

    for bits in encode_iterator(data, codes):
        byte = bits_to_byte(bits)
        write8(output, byte)
        #print(it, '{0:X}'.format(byte))


def encode_bin(data, codes, output):
    for bits in encode_iterator(data, codes):
        byte = bits_to_byte(bits)
        write8(output, byte)


def decode_iterator(data, codes, length):
    revcodes = rev_dict(codes)
    seq = list()
    bitdata = chain(*map(byte_to_bits, data))
    r = 0
    while r < length:
        bit = next(bitdata, None)
        if bit is None:
            return
        seq.append(bit)
        t = tuple(seq)
        if t in revcodes:
            yield revcodes[t]
            seq.clear()
            r += 1


def decode_text(data, codes, length):
    return ''.join(decode_iterator(data, codes, length))


def decode_bin(data, codes, length):
    return bytearray(decode_iterator(data, codes, length))


def decode_table(inp):
    sizes = struct.unpack('16B', inp.read(16))

    codes = dict()
    code = 0
    for l, s in enumerate(sizes):
        code = code << 1
        for _ in range(s):
            k = struct.unpack('B', inp.read(1))[0]
            codes[k] = byte_to_bits(code, l)
            code += 1
    return codes

def decode(inp):
    codes = decode_table(inp)
    nsymbols = read16(inp)
    nbytes = read16(inp)
    data = inp.read(nbytes)

    return decode_bin(data, codes, nsymbols)


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
    print(dtext)
    result = dtext.decode('utf-8')
    assert result == text


def main(text):
    print(text)
    b = BytesIO()
    encode(text.encode('utf-8'), b)
    print(b.getvalue())
    b.seek(0)
    dtext = decode(b)
    print(dtext.decode('utf-8'))

if __name__ == '__main__':
    main('hello world')
