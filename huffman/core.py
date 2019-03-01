""" Huffman table
"""
from collections import defaultdict
from collections import namedtuple
import heapq

from .utils import byte_to_bits
from .utils import rev_dict


Node = namedtuple('Node', ['cargo', 'left', 'right'])


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


def iter_leafs(root):
    """ Iterate throw leafs in binary tree
    For each leaf returns its value (cargo) and the path from root node to
    the leaf. Path is represented by (1, 0, 1) tuple, where 0 is left,
    1 is right.
    """
    parents = dict()
    leafs = list()
    node_is_leaf = lambda node: not node.left and not node.right
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
            node, left_or_right = parents[node]
            path.append(left_or_right)
        path.reverse()
        yield cargo, tuple(path)


def get_frequences(array):
    """ Get frequency of each element of array
    Returns dictionary where key is unique element of the array,
    value is the number of occurances of the element
    """
    frequences = defaultdict(int)
    for element in array:
        frequences[element] += 1
    return frequences


def make_huffman_tree(freq):
    """ Make a binary-tree from array-element frequences,
    where left node is more probable than right node. So more frequent
    element will have shorter path from the root.

    Note: we sort at first by number of nodes in subtree and then by weight
    In this case leafs on n-th raw will have no gaps. It give us an advantage
    in more optimal size of resulting table. In general case this doesn't
    matter, so we can simply use only weight (frequency).
    """
    nodes = {k: Node(k, None, None) for k, v in freq.items()}
    heap = [(0, v, nodes[k]) for k, v in freq.items()]
    heapq.heapify(heap)
    while len(heap) > 1:
        num1, weight1, node1 = heapq.heappop(heap)
        num2, weight2, node2 = heapq.heappop(heap)
        ttype = type(node1.cargo)
        node = Node(ttype(), node1, node2)
        heapq.heappush(heap, (num1+num2+2, weight1+weight2, node))
    _, _, root = heap[0]
    return root


def get_huffman_table(freq):
    """ Gives Huffman encoding table, by making a binary tree from frequences
    and then building a path of each node from the root.
    Returns a dictionary, where key is element, value is (1, 0, 1) tuple
    """
    root = make_huffman_tree(freq)
    codes = {ch: path for ch, path in iter_leafs(root)}
    return codes


def check_huffman_table(codes):
    """ Check huffman table for validity
    """
    code = 0
    revcodes = rev_dict(codes)
    codeslist = list(codes.values())
    codeslist.sort(key=len)
    last_size = 0
    for value in codeslist:
        size = len(value)
        if size != last_size:
            code = code << 1
            last_size = size
        bits = byte_to_bits(code, size)
        if bits not in revcodes:
            return False
        code += 1
    for i, value in enumerate(codeslist):
        size = len(value)
        for value2 in codeslist[i+1:]:
            if value == value2[:size]:
                return False
    return True
