import numpy as np
from scipy import fftpack


def idct_2d(block):
    nblock = np.array(block)
    nblock = nblock.reshape(8, 8)
    res = fftpack.idct(fftpack.idct(nblock.T, norm='ortho').T, norm='ortho')
    res = res.astype(int)
    res = res + 128
    res = res.clip(0, 255)
    return res.flatten().tolist()
