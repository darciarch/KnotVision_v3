"""Coverage vote: from per-pixel coverage fractions to one yarn per knot."""

import numpy as np
from PIL import Image
from scipy import ndimage

from .symmetry import mirror_average

DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))  # 0, 90, 45, 135 degrees as (dy, dx)


def resize_alpha(alpha, size):
    """Area-average coverage maps (h, w, K) onto the knot grid (W, H) -> (H, W, K).

    BOX resampling is an exact area average, so a knot's value is the
    fraction of its area covered by that color (bilinear blurred 2 px lines
    into their 2 px gaps)."""
    out = np.empty((size[1], size[0], alpha.shape[-1]), dtype=np.float32)
    for k in range(alpha.shape[-1]):
        im = Image.fromarray(np.ascontiguousarray(alpha[..., k]), "F")
        out[..., k] = np.asarray(im.resize(size, Image.Resampling.BOX))
    return out


def shifted(a, dy, dx):
    """`a` shifted by (dy, dx) with edge replication."""
    r = max(abs(dy), abs(dx))
    p = np.pad(a, r, mode="edge")
    h, w = a.shape
    return p[r + dy:r + dy + h, r + dx:r + dx + w]


def directional_mean(cov, length=9):
    """Mean coverage along the orientation in which it varies least, per knot.

    Returns (mean (h, w, K), orientation index into DIRECTIONS). Along a
    straight edge or a thin line the coverage is constant in the direction of
    the edge/line, so that orientation is chosen and its mean describes the
    structure the knot lies on rather than the knot's own noisy value.
    """
    h, w, k = cov.shape
    r = length // 2
    best_var = np.full((h, w), np.inf, dtype=np.float32)
    best = cov.copy()
    ori = np.zeros((h, w), dtype=np.int8)
    for o, (dy, dx) in enumerate(DIRECTIONS):
        m = np.zeros_like(cov)
        m2 = np.zeros_like(cov)
        for i in range(-r, r + 1):
            sh = np.stack([shifted(cov[..., c], i * dy, i * dx) for c in range(k)], -1)
            m += sh
            m2 += sh * sh
        m /= length
        var = (m2 / length - m * m).sum(-1)
        hit = var < best_var
        best_var[hit] = var[hit]
        best[hit] = m[hit]
        ori[hit] = o
    return best, ori


def straighten_runs(labels, soft, hard, thr=0.6, own=0.85, length=9, min_run=15):
    """Decide straight, half-covered runs of knots as a whole instead of knot by knot.

    Where a band edge or a thin line straddles a row of knots, every knot on
    that row is covered about half by two colors (`soft` coverage, the area
    fraction). The per-knot argmax is then decided by noise and a perfectly
    straight edge comes out jagged; averaging over a short window does not
    help because the mean itself sits near the tie and flips from segment to
    segment. So knots whose `directional_mean` is undecided (max < `thr`,
    own coverage < `own` so clean dots and strokes are never touched) are
    grouped into runs along their orientation, and each run of at least
    `min_run` knots takes one color: the majority of the source pixel labels
    over the run (`hard` coverage; the soft mean would tie on a line that
    straddles two rows evenly). Short runs (curved edges, small shapes) keep
    their per-knot decision. On the real design min_run 9 costs twice as many
    knots as 15; a source's border band edge becomes one row with either.
    Returns (knots changed, runs decided).
    """
    d, ori = directional_mean(soft, length)
    amb = (d.max(-1) < thr) & (soft.max(-1) < own)
    changed = 0
    runs = 0
    for o, (dy, dx) in enumerate(DIRECTIONS):
        st = np.zeros((3, 3), dtype=bool)
        st[1, 1] = st[1 + dy, 1 + dx] = st[1 - dy, 1 - dx] = True
        comp, n = ndimage.label(amb & (ori == o), structure=st)
        if n == 0:
            continue
        sizes = np.bincount(comp.ravel())
        ids = np.nonzero(sizes[1:] >= min_run)[0] + 1
        if len(ids) == 0:
            continue
        means = np.stack([ndimage.mean(hard[..., c], comp, ids) for c in range(hard.shape[-1])], -1)
        lut = np.full(n + 1, -1, dtype=np.int16)
        lut[ids] = means.argmax(1)
        new = lut[comp]
        sel = new >= 0
        changed += int((labels[sel] != new[sel]).sum())
        labels[sel] = new[sel].astype(labels.dtype)
        runs += len(ids)
    return changed, runs


def vote_knots(alpha, knot_size, sym_lr, sym_tb):
    """Label map (H, W) uint8 on the knot grid from source coverage fractions.

    Every knot takes the color covering most of its area ("soft" coverage:
    the per-pixel fractions area-averaged onto the knot; it beats the majority
    of one-hot pixel labels on the real design). Symmetric halves are averaged
    with their mirror first. The
    one-hot majority ("hard") is only used by `straighten_runs`.
    """
    n = alpha.shape[-1]
    onehot = np.stack([(alpha.argmax(-1) == k).astype(np.float32) for k in range(n)], -1)
    hard = mirror_average(resize_alpha(onehot, knot_size), sym_lr, sym_tb)
    del onehot
    soft = mirror_average(resize_alpha(alpha, knot_size), sym_lr, sym_tb)
    labels = soft.argmax(-1).astype(np.uint8)
    changed, runs = straighten_runs(labels, soft, hard)
    print(f"straight runs: {runs} half-covered runs decided as a whole, "
          f"{changed} knots changed", flush=True)
    return labels
