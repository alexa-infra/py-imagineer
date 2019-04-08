from jpeg.scan_decode import ext_table, ext_table_pos


def test_ext_table():
    assert ext_table(0, 0) == 0
    assert ext_table(0b0, 1) == -1
    assert ext_table(0b1, 1) == 1
    assert ext_table(0b00, 2) == -3
    assert ext_table(0b01, 2) == -2
    assert ext_table(0b10, 2) == 2
    assert ext_table(0b11, 2) == 3
    assert ext_table(0b000, 3) == -7
    assert ext_table(0b111, 3) == 7

def test_ext_table_pos():
    assert ext_table_pos(0, 0) == 1
    assert ext_table_pos(0b0, 1) == 2
    assert ext_table_pos(0b1, 1) == 3
    assert ext_table_pos(0b00, 2) == 4
    assert ext_table_pos(0b01, 2) == 5
    assert ext_table_pos(0b10, 2) == 6
    assert ext_table_pos(0b000, 3) == 8
    assert ext_table_pos(0b111, 3) == 15
