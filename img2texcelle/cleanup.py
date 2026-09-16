"""Cleanup on the knot grid: islands and shading slivers."""

import numpy as np
from scipy import ndimage

from .color import rgb_to_lab

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


def remove_shading_specks(labels, palette, n, max_area, ring_dom=0.8, hue_tol=25.0,
                          neutral=8.0, max_passes=5):
    """Repaint small islands that are a shade of the one color enclosing them.

    A shaded render (bevels, drop shadows, highlights) leaves 1-knot slivers
    of dark brown inside tan or cream inside tan. Such a component below
    `max_area` knots whose 1-knot ring is at least `ring_dom` one color, and
    whose color has the same Lab hue as that color (within `hue_tol` deg, or
    one of them is nearly neutral: chroma < `neutral`), takes the enclosing
    color. A cream dot on dark red (different hue) is kept. This also erases
    real same-hue details (about 1% of the knots on a real Texcelle design),
    so it is opt-in (--specks). Returns the number of knots repainted.
    """
    lab = rgb_to_lab(np.asarray(palette, dtype=np.uint8))
    hue = np.arctan2(lab[:, 2], lab[:, 1])
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    h, w = labels.shape
    total = 0
    for _ in range(max_passes):
        changed = 0
        for k in range(n):
            comp, count = ndimage.label(labels == k, structure=EIGHT)
            if count == 0:
                continue
            sizes = np.bincount(comp.ravel())
            small = np.nonzero(sizes[1:] < max_area)[0] + 1
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
                votes = np.bincount(region[ring], minlength=n)
                if votes.sum() == 0:
                    continue
                j = int(votes.argmax())
                if j == k or votes[j] < ring_dom * votes.sum():
                    continue
                d_hue = abs((hue[j] - hue[k] + np.pi) % (2 * np.pi) - np.pi)
                if d_hue < np.deg2rad(hue_tol) or min(chroma[j], chroma[k]) < neutral:
                    region[inside] = j
                    changed += int(sizes[i])
        total += changed
        if changed == 0:
            break
    return total
