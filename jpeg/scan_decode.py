from io import BytesIO
from array import array
from itertools import product
from .zigzag import dezigzag
from .idct import idct_2d
from .utils import high_low4

CHUNK_LEN = 10 * 1024

class BitReader:
    def __init__(self, data):
        self.data = data
        self.byte = None
        self.bit_counter = 8
        self.chunk = None
        self.chunk_it = 0
        self.chunk_len = 0
        self._next_chunk()

    def __iter__(self):
        return self

    def __next__(self):
        if self.bit_counter >= 8:
            self.byte = self.get_next_byte()
            self.bit_counter = 0

        n = 8 - self.bit_counter - 1
        vbit = self.byte & bias2[n]
        self.bit_counter += 1
        return 1 if vbit else 0

    def reset(self):
        self.byte = None
        self.bit_counter = 8

    def _next_chunk(self):
        self.chunk = array('B', self.data.read(CHUNK_LEN))
        self.chunk_it = 0
        self.chunk_len = len(self.chunk)

    def read_byte(self):
        if self.chunk_it >= CHUNK_LEN:
            self._next_chunk()
        if self.chunk_it >= self.chunk_len:
            raise StopIteration
        byte = self.chunk[self.chunk_it]
        self.chunk_it += 1
        return byte

    def get_next_byte(self):
        byte = self.read_byte()
        if byte == 0xFF:
            next_byte = self.read_byte()
            if next_byte == 0x00:
                return byte
            raise SyntaxError('found 0xFF{0:X} marker'.format(next_byte))
        return byte

def receive(r, length):
    n = 0
    while length:
        #n = (n << 1) | next(r)
        bit = next(r)
        if bit:
            n = n | bias2[length-1]
        length -= 1
    return n

_bias = lambda n: (-1 << n) + 1
bias = [_bias(n) for n in range(16)]

_bmask = lambda n: (1 << n) - 1
bmask = [_bmask(n) for n in range(17)]

def ext_table(n, length):
    """
    length=0                        -> 0
    length=1 0b0, 0b1               -> -1, 1
    length=2 0b00, 0b01, 0b10, 0b11 -> -3, -2, 2, 3
    length=3 0b000, ..., 0b111      -> -7, -6, -5, -4, 4, 5, 6, 7
    ....
    """
    if length == 0:
        return 0
    if n <= bmask[length - 1]: # if most sign bit is not set
        return n + bias[length]
    return n

def receive_and_extend(reader, length):
    n = receive(reader, length)
    return ext_table(n, length)

_bias2 = lambda n: 1 << n
bias2 = [_bias2(n) for n in range(16)]

def ext_table_pos(n, length):
    """
    Table G.1. - EOBn code run length extensions
    length=0                        -> 1
    length=1 0b0, 0b1               -> 2, 3
    length=2 0b00, 0b01, 0b10, 0b11 -> 4, 5, 6, 7
    length=3 0b000, ..., 0b111      -> 8, 9, 10, 11, 12, 13, 14, 15
    ....
    """
    return n + bias2[length]

def receive_and_extend_pos(reader, length):
    n = receive(reader, length)
    return ext_table_pos(n, length)

def read_huffman(reader, decoder):
    for bit in reader:
        ch = decoder(bit)
        if ch is not None:
            return ch
    return None

def read_ac_prog_first(reader, decoder, block_data, scan, component):
    if not scan.prog_state:
        scan.prog_state = ProgState()
    state = scan.prog_state

    if state.eobrun > 0:
        # G.1.2.2 - this AC block contains all zeros
        state.eobrun -= 1
        return
    k = scan.spectral_start
    while k <= scan.spectral_end:
        rs = read_huffman(reader, decoder)
        r, s = high_low4(rs)
        if s == 0:
            if r < 15:
                # G.1.2.2 - End-of-Bands
                # the rest of this block contains all zeros
                # and EOBRUN next blocks are all zeros too
                state.eobrun = receive_and_extend_pos(reader, r)
                state.eobrun -= 1
                break
            k += 15
        else:
            k += r
            assert k <= scan.spectral_end
            value = receive_and_extend(reader, s)
            value = value << scan.approx_low
            z = dezigzag[k]
            block_data[z] = value
        k += 1

def read_ac_prog_refine(reader, decoder, block_data, scan, component):
    if not scan.prog_state:
        scan.prog_state = ProgState()
    state = scan.prog_state

    assert state.ac_state in (0, 4)
    k = scan.spectral_start
    e = scan.spectral_end
    r = 0
    while k <= e:
        z = dezigzag[k]
        sign = -1 if block_data[z] < 0 else 1
        # if AC has non-zero history, then we will refine its value
        has_prev_value = block_data[z] != 0

        if state.ac_state == 0:
            # initial state, we read encoded RRRRSSSS Huffman value
            # R is the number of zero values before current value
            # S is the amplitude of refine (should be 1)
            rs = read_huffman(reader, decoder)
            r, s = high_low4(rs)
            if s == 0:
                if r < 15:
                    # EOB, we should skip all next zero values and
                    # refine non-zero values till the end of block
                    # For the next EOBRUN-1 blocks we do the same
                    state.eobrun = receive_and_extend_pos(reader, r)
                    state.ac_state = 4
                else:
                    # We skip next 16 zero values and refine all
                    # non-zero values between them
                    r = 16
                    state.ac_state = 1
            elif s == 1:
                # We skip next R zero values and refine non-zero
                # values between them, after that we set current
                # value to ac_next_value
                state.ac_next_value = receive_and_extend(reader, s)
                state.ac_state = 2 if r else 3
            else:
                raise SyntaxError('invalid s value')

        if state.ac_state == 1 or state.ac_state == 2:
            if has_prev_value:
                value = next(reader) << scan.approx_low
                block_data[z] += sign * value
            else:
                r -= 1
                if r == 0:
                    state.ac_state = 3 if state.ac_state == 2 else 0

        elif state.ac_state == 3:
            if has_prev_value:
                value = next(reader) << scan.approx_low
                block_data[z] += sign * value
            else:
                block_data[z] = state.ac_next_value << scan.approx_low
                state.ac_state = 0

        elif state.ac_state == 4:
            if has_prev_value:
                value = next(reader) << scan.approx_low
                block_data[z] += sign * value
        k += 1
    if state.ac_state == 4:
        state.eobrun -= 1
        if state.eobrun == 0:
            state.ac_state = 0

def read_baseline(reader, component, block_data, scan):
    dc_decoder = scan.huffman_dc[component.id]

    s = read_huffman(reader, dc_decoder)
    dc = receive_and_extend(reader, s)

    dc += component.last_dc
    component.last_dc = dc
    block_data[0] = dc

    ac_decoder = scan.huffman_ac[component.id]
    k = 1
    while k <= 63:
        rs = read_huffman(reader, ac_decoder)
        r, s = high_low4(rs)
        if s == 0:
            if r < 15:
                break
            k += 15
        else:
            k += r
            ac = receive_and_extend(reader, s)
            z = dezigzag[k]
            block_data[z] = ac
        k += 1

def read_progressive(reader, component, block_data, scan):
    # progressive scan contains either AC or DC values
    # DC might be interleaved, AC is only non-interleaved
    if not scan.is_refine:
        if scan.is_dc:
            read_fn = read_dc_prog_first
        else:
            read_fn = read_ac_prog_first
    else:
        if scan.is_dc:
            read_fn = read_dc_prog_refine
        else:
            read_fn = read_ac_prog_refine
    if scan.is_dc:
        decoder = scan.huffman_dc[component.id]
    else:
        decoder = scan.huffman_ac[component.id]
    read_fn(reader, decoder, block_data, scan, component)

def read_dc_prog_first(reader, decoder, block_data, scan, component):
    s = read_huffman(reader, decoder)
    dc = receive_and_extend(reader, s)

    dc += component.last_dc
    component.last_dc = dc
    block_data[0] = dc << scan.approx_low

def read_dc_prog_refine(reader, decoder, block_data, scan, component):
    bit = next(reader)
    value = bit << scan.approx_low
    block_data[0] |= value

class ProgState:
    def __init__(self):
        self.eobrun = 0
        self.ac_state = 0
        self.ac_next_value = None

def set_block(data, block_data, row, col, width):
    offset = row * width + col
    for i in range(8):
        for j in range(8):
            c = 8 * i + j
            data[offset + i * width + j] = block_data[c]

def iter_block_samples(component, row, col):
    h, v = component.sampling
    w, _ = component.blocks_size
    blocks = component.blocks

    for i in range(v):
        sub_row = row * v + i
        for j in range(h):
            sub_col = col * h + j
            yield blocks[sub_row * w + sub_col]

def decode(fp, scan):
    reader = BitReader(fp)
    frame = scan.frame
    components = scan.components
    restart_interval = frame.restart_interval
    non_interleaved = not scan.is_interleaved

    if frame.progressive:
        decode_fn = lambda c, b: read_progressive(reader, c, b, scan)
    else:
        decode_fn = lambda c, b: read_baseline(reader, c, b, scan)

    n = 0
    restart = 0

    if non_interleaved:
        component = components[0]
        blocks_x, blocks_y = component.blocks_size
    else:
        blocks_x, blocks_y = frame.blocks_size

    for block_row, block_col in product(range(blocks_y), range(blocks_x)):
        if non_interleaved:
            component = components[0]
            block = component.blocks[block_row * blocks_x + block_col]
            decode_fn(component, block)
        else:
            # interleaved
            for component in components:
                for block in iter_block_samples(component, block_row, block_col):
                    decode_fn(component, block)
        if restart_interval:
            n += 1
            if n < blocks_x * blocks_y and n % restart_interval == 0:
                byte1 = reader.read_byte()
                byte2 = reader.read_byte()
                assert byte1 == 0xFF, '0x{0:X}'.format(byte1)
                assert 0xD0 <= byte2 <= 0xD7, '0xFF{0:X}'.format(byte2)
                assert byte2 == 0xD0 + restart
                restart = (restart + 1) % 8
                reader.reset()
                for component in components:
                    component.last_dc = 0
                for huff_decoder in scan.huffman_dc.values():
                    if huff_decoder:
                        huff_decoder.reset()
                for huff_decoder in scan.huffman_ac.values():
                    if huff_decoder:
                        huff_decoder.reset()
                scan.prog_state = None

def clamp(x):
    if x < -128:
        return 0
    if x > 127:
        return 255
    return x + 128

def decode_prog_block_finish(component, block_data, qt):
    for c in range(64):
        block_data[c] *= qt[c]
    idct_2d(block_data)
    for c in range(64):
        block_data[c] = clamp(block_data[c])

def decode_finish(frame):
    for comp in frame.components:
        data = comp.data
        blocks = comp.blocks
        w, h = comp.blocks_size
        qt = frame.quantization[comp.qc]
        for row in range(h):
            for col in range(w):
                block = blocks[row * w + col]
                decode_prog_block_finish(comp, block, qt)
                set_block(data, block, row * 8, col * 8, w * 8)
