"""Cleanup on the knot grid: islands."""

import numpy as np
from scipy import ndimage

EIGHT = np.ones((3, 3), dtype=bool)  # 8-connectivity


def remove_islands(labels, n, min_area, max_passes=5):
    """Repaint connected areas smaller than min_area with their dominant neighbor color."""
    h, w = labels.shape
    total = 0
    for _ in range(max_passes):
        changed = 0
        for k in range(n):
            comp, count = ndimage.label(labels == k, structure=EIGHT)
            if count == 0:
                continue
            sizes = np.bincount(comp.ravel())
            small = np.nonzero(sizes[1:] < min_area)[0] + 1
            if len(small) == 0:
                continue
            objects = ndimage.find_objects(comp)
            for i in small:
                ys, xs = objects[i - 1]
                ys = slice(max(ys.start - 1, 0), min(ys.stop + 1, h))
                xs = slice(max(xs.start - 1, 0), min(xs.stop + 1, w))
                region = labels[ys, xs]
                inside = comp[ys, xs] == i
                ring = ndimage.binary_dilation(inside, structure=EIGHT) & ~inside
                neighbors = region[ring]
                if neighbors.size == 0:
                    continue
                region[inside] = np.bincount(neighbors, minlength=n).argmax()
                changed += int(sizes[i])
        total += changed
        if changed == 0:
            break
    return total
