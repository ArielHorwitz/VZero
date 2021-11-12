import numpy as np

def center_position(pos, size):
    r = list(np.array(pos) - (np.array(size) / 2))
    assert len(r) == 2
    return cc_int(r)


def cc_int(pos):
    return int(pos[0]), int(pos[1])
