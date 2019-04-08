from ..core import Node, iter_nodes, iter_leafs, get_frequences
from ..core import get_huffman_table, check_huffman_table


def test_iter_nodes():
    root = Node(1,
                Node(2,
                     Node(4, None, None),
                     Node(5, None, None)),
                Node(3, None, None))
    expected = [4, 2, 5, 1, 3]
    assert list(x.cargo for x in iter_nodes(root)) == expected


def test_iter_leafs():
    root = Node(1,
                Node(2,
                     Node(4, None, None),
                     Node(5, None, None)),
                Node(3, None, None))
    expected = [4, 5, 3]
    assert list(x for x, _ in iter_leafs(root)) == expected


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

