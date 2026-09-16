"""Coverage unmixing: explain every source pixel as one yarn color or a mix of two."""

import numpy as np
from scipy import ndimage

from .cleanup import EIGHT
from .color import sq_dist


def unmix(lab, pal_lab, margin=3.0, reach=0):
    """Coverage fractions (h, w, K) of the palette colors for every pixel.

    A pixel is explained either as one pure color or as a mix of two colors
    (the Lab segment between them that passes closest to the pixel). Pure wins
    unless a mix fits better by more than `margin` delta E, so pixels inside a
    wide area of an in-between color stay that color.

    With `reach` > 0 a pair is only allowed where both colors occur (as the
    nearest pure color) within `reach` px: with many yarns some segment
    between two unrelated colors passes through almost any color (a slightly
    desaturated magenta line is exactly 30% purple + 70% orange), and only
    neighbours can blur into a pixel.
    """
    h, w, _ = lab.shape
    k = len(pal_lab)
    px = lab.reshape(-1, 3)
    pairs = [(a, b) for a in range(k) for b in range(a + 1, k)]
    alpha = np.zeros((len(px), k), dtype=np.float32)
    near = None
    if reach > 0:
        nearest = sq_dist(px, pal_lab).argmin(1).reshape(h, w)
        near = [ndimage.maximum_filter(nearest == c, size=2 * reach + 1).ravel()
                for c in range(k)]
    step = 1_000_000
    for s0 in range(0, len(px), step):
        p = px[s0:s0 + step]
        d = np.sqrt(np.maximum(sq_dist(p, pal_lab), 0))
        best_off = d.min(1) - margin
        best_pair = np.full(len(p), -1, dtype=np.int16)
        best_s = np.zeros(len(p), dtype=np.float32)
        for i, (a, b) in enumerate(pairs):
            dv = pal_lab[b] - pal_lab[a]
            s = np.clip((p - pal_lab[a]) @ dv / (dv @ dv), 0, 1)
            off = np.linalg.norm(p - (pal_lab[a] + s[:, None] * dv), axis=1)
            hit = off < best_off
            if near is not None:
                hit &= near[a][s0:s0 + step] & near[b][s0:s0 + step]
            best_off[hit], best_pair[hit], best_s[hit] = off[hit], i, s[hit]
        out = alpha[s0:s0 + step]
        pure = best_pair < 0
        out[np.nonzero(pure)[0], d.argmin(1)[pure]] = 1.0
        for i, (a, b) in enumerate(pairs):
            sel = best_pair == i
            out[sel, a] = 1.0 - best_s[sel]
            out[sel, b] = best_s[sel]
    return alpha.reshape(h, w, k)


def blend_pairs(palette, max_off=0.15):
    """{k: [(a, b), ...]} for palette colors k lying between colors a and b in RGB.

    E.g. grey sits on the line between blue and cream, so a blurred blue/cream
    edge looks grey even though the design has no grey there.
    """
    pal = palette.astype(np.float32)
    out = {}
    for k in range(len(pal)):
        for a in range(len(pal)):
            for b in range(a + 1, len(pal)):
                if k in (a, b):
                    continue
                d = pal[b] - pal[a]
                s = (pal[k] - pal[a]) @ d / (d @ d)
                off = np.linalg.norm(pal[k] - (pal[a] + s * d))
                if 0.15 < s < 0.85 and off < max_off * np.linalg.norm(d):
                    out.setdefault(k, []).append((a, b))
    return out


def unmix_thin_blends(alpha, lab, palette, pal_lab, reach=7):
    """Unmix thin strips of an in-between color into the two colors it blends.

    A blurred blue/cream edge and a blurred 1px blue line both look grey. So a
    thin strip of grey (removed by a 3x3 opening) is unmixed into blue/cream
    when it is not attached to a wide grey area and one of the two colors is
    nearby, or when it touches both colors. Wide areas of grey and the thin
    edges/tips of those areas are kept. Modifies `alpha` in place and returns
    the number of pixels changed.
    """
    labels = alpha.argmax(-1)
    changed = 0
    for k, pairs in blend_pairs(palette).items():
        mask = labels == k
        wide = ndimage.binary_opening(mask, structure=EIGHT)
        thin = mask & ~wide
        if not thin.any():
            continue
        comp, n = ndimage.label(mask, structure=EIGHT)
        attached = np.zeros(n + 1, dtype=bool)
        attached[np.unique(comp[wide])] = True
        # a dense cluster of thin strips is hatching, not a blurred line
        dense = ndimage.uniform_filter(thin.astype(np.float32), size=15) > 0.25
        isolated = thin & ~attached[comp] & ~dense
        best = np.full(labels.shape, np.inf, dtype=np.float32)
        for a, b in pairs:
            near_a = ndimage.maximum_filter(labels == a, size=reach)
            near_b = ndimage.maximum_filter(labels == b, size=reach)
            ok = thin & ((near_a & near_b) | (isolated & (near_a | near_b)))
            if not ok.any():
                continue
            dv = pal_lab[b] - pal_lab[a]
            s = np.clip((lab - pal_lab[a]) @ dv / (dv @ dv), 0, 1)
            off = np.linalg.norm(lab - (pal_lab[a] + s[..., None] * dv), axis=-1)
            hit = ok & (off < best)
            best[hit] = off[hit]
            alpha[hit] = 0.0
            alpha[hit, a] = 1.0 - s[hit]
            alpha[hit, b] = s[hit]
            changed += int(hit.sum())
    return changed
