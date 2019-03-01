
baseline = (
    0xFFC0,
)


sequential = (
    0xFFC1,
    0xFFC5,
    0xFFC9,
    0xFFCD,
)


progressive = (
    0xFFC2,
    0xFFC6,
    0xFFCA,
    0xFFCE,
)


# Loseless are known, but not widely used, thus not supported
loseless = (
    0xFFC3,
    0xFFC7,
    0xFFCB,
    0xFFCF,
)


possible = baseline + sequential + progressive + loseless


# Hierarchical, storing multiple images of different sizes
# nonexistent in the world, thus not supported
differential = (
    0xFFC5,
    0xFFC6,
    0xFFC7,
    0xFFCD,
    0xFFCE,
    0xFFCF,
)


huffman = (
    0xFFC0,
    0xFFC1,
    0xFFC2,
    0xFFC3,
    0xFFC5,
    0xFFC6,
    0xFFC7,
)


# better alternative to huffman, but not widely used
# and proprietar, thus not supported
arithmetic = (
    0xFFC9,
    0xFFCA,
    0xFFCB,
    0xFFCD,
    0xFFCE,
    0xFFCF,
)

unsupported = tuple(set(differential) | set(loseless) | set(arithmetic))
supported = tuple(set(possible) - set(unsupported))
