"""Coverage vote: from per-pixel coverage fractions to one yarn per knot."""

import math

import numpy as np
from scipy import ndimage

from .symmetry import mirror_average

DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))  # 0, 90, 45, 135 degrees as (dy, dx)


def box_coeffs(n_out, scale, first, crop, in_size):
    """PIL's BOX resampling coefficients (Resample.c, precompute_coeffs) for
    the `n_out` knots starting at knot `first` of a grid laid over `in_size`
    source px with `scale` px per knot, as (index (n_out, taps) into a crop
    starting at source px `crop`, weight (n_out, taps)). Knot j takes the
    source pixels whose centre lies within +-scale/2 of its own centre
    (j + 0.5) * scale, each weighted 1 / count, computed with PIL's own
    double arithmetic; unused taps have weight 0 and a valid index."""
    support = 0.5 * scale
    ss = 1.0 / scale
    taps = int(math.ceil(support)) * 2 + 1
    j = np.arange(n_out, dtype=np.int64)
    center = (first + j + 0.5) * scale
    xmin = np.maximum((center - support + 0.5).astype(np.int64), 0)
    xmax = np.minimum((center + support + 0.5).astype(np.int64), in_size)
    x = xmin[:, None] + np.arange(taps)[None, :]
    w = ((x.astype(np.float64) - center[:, None] + 0.5) * ss)
    k = np.where((w > -0.5) & (w <= 0.5) & (x < xmax[:, None]), 1.0, 0.0)
    ww = k.sum(1)
    k = np.where(ww[:, None] != 0.0, k / np.where(ww[:, None] != 0.0, ww[:, None], 1.0), k)
    idx = np.clip(x - crop, 0, None)
    return idx, k


def _pass(a, idx, k, axis):
    """One resampling pass along `axis` (1 = columns, 0 = rows): double
    accumulation over the taps in ascending order, stored as float32, like
    PIL's 32 bit float path."""
    n_out, taps = idx.shape
    shape = list(a.shape)
    shape[axis] = n_out
    acc = np.zeros(shape, dtype=np.float64)
    for t in range(taps):
        take = np.take(a, np.minimum(idx[:, t], a.shape[axis] - 1), axis=axis)
        wt = k[:, t] if axis == 1 else k[:, t][:, None]
        acc += take * wt
    return acc.astype(np.float32)


def resize_alpha(alpha, size, scale=None, first=(0, 0), crop=(0, 0), in_size=None):
    """Area-average coverage maps (h, w, K) onto knots (W, H) -> (H, W, K).

    Bit-identical to PIL's BOX resize of the whole source (exact area
    average of pixel centres; bilinear blurred 2 px lines into their 2 px
    gaps), re-implemented so that a crop of the source gives the same
    values as the whole: `alpha` is the crop starting at source px `crop`
    of a source of `in_size` px, `scale` = (sx, sy) source px per knot of
    the whole grid and `first` = (x, y) the whole-grid index of the first
    knot. PIL itself takes a resize box in single precision, which moves a
    fractional box end by an ulp and flips exact 50/50 ties (the real
    design's dashed border, straddling two knot rows every 250 rows).
    Defaults: the whole map onto `size`."""
    h, w = alpha.shape[:2]
    if scale is None:
        scale = (w / size[0], h / size[1])
    if in_size is None:
        in_size = (w, h)
    ix, kx = box_coeffs(size[0], scale[0], first[0], crop[0], in_size[0])
    iy, ky = box_coeffs(size[1], scale[1], first[1], crop[1], in_size[1])
    out = np.empty((size[1], size[0], alpha.shape[-1]), dtype=np.float32)
    for c in range(alpha.shape[-1]):
        out[..., c] = _pass(_pass(alpha[..., c], ix, kx, 1), iy, ky, 0)
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


def straighten_runs(labels, soft, hard, thr=0.6, own=0.85, length=9, min_run=15, count=None):
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
    `count` (bool (h, w)) restricts the majority to those knots (the output
    part, not the pad beyond a mirror axis): the part and its mirror make up
    the run in the whole image, so the part alone has the same majority,
    while a pad of any size can tip a near-tie run (a band edge across the
    real design). A run with no counted knot keeps its own majority.
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
        if count is not None:
            w = count.astype(np.float32)
            num = ndimage.sum(w, comp, ids)
            part = np.stack([ndimage.sum(hard[..., c] * w, comp, ids) for c in range(hard.shape[-1])], -1)
            counted = num > 0
            means[counted] = part[counted] / num[counted, None]
        lut = np.full(n + 1, -1, dtype=np.int16)
        lut[ids] = means.argmax(1)
        new = lut[comp]
        sel = new >= 0
        changed += int((labels[sel] != new[sel]).sum())
        labels[sel] = new[sel].astype(labels.dtype)
        runs += len(ids)
    return changed, runs


def vote_knots(alpha, knot_size, sym_lr, sym_tb, geometry=None, count=None):
    """Label map (H, W) uint8 on the knot grid from source coverage fractions.

    Every knot takes the color covering most of its area ("soft" coverage:
    the per-pixel fractions area-averaged onto the knot; it beats the majority
    of one-hot pixel labels on the real design). Symmetric halves (`sym_lr` /
    `sym_tb`: the grid holds both halves of that axis) are averaged with
    their mirror first. The one-hot majority ("hard") is only used by
    `straighten_runs`. `geometry` = (scale, first, crop, in_size) as in
    `resize_alpha` (the map is a crop of the source), `count` as in
    `straighten_runs`.
    """
    geo = geometry or ()
    n = alpha.shape[-1]
    onehot = np.stack([(alpha.argmax(-1) == k).astype(np.float32) for k in range(n)], -1)
    hard = mirror_average(resize_alpha(onehot, knot_size, *geo), sym_lr, sym_tb)
    del onehot
    soft = mirror_average(resize_alpha(alpha, knot_size, *geo), sym_lr, sym_tb)
    labels = soft.argmax(-1).astype(np.uint8)
    changed, runs = straighten_runs(labels, soft, hard, count=count)
    print(f"straight runs: {runs} half-covered runs decided as a whole, "
          f"{changed} knots changed", flush=True)
    return labels
