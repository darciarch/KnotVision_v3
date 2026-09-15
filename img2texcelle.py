#!/usr/bin/env python3
"""
img2texcelle.py - convert a ready design image (jpg/png) into a Texcelle-compatible
indexed TIFF.

The design is treated as regions + thin lines, not as independent pixels:

  1. rotate image 90 deg if its orientation differs from the carpet
  2. optional denoise at source resolution (median filter, off by default)
  3. pick yarn palette (auto k-means in Lab on flat areas, or --palette);
     --outline adds colors that only occur as thin contour lines
  4. unmix every source pixel into coverage fractions of (at most) two yarn
     colors, so a blurred edge or a blurred 1px line is "60% brown / 40% cream"
     instead of a wrong in-between color; thin strips of an in-between color
     (e.g. grey on a blue/cream edge) are unmixed into their neighbours
  5. resize the coverage maps (not the RGB image) to the knot grid
  6. regions: every knot takes the color with the largest coverage; parts
     thinner than 3 knots are dropped and refilled from their surroundings
  7. lines: a ridge detector on each color's coverage map follows thin lines
     even where they are blurred below 50%, so they stay continuous; every
     connected line gets one color, decided from its mean color against its
     background (a blurred blue line looks grey/dark pixel by pixel); dark
     contour lines (--outline) are erased or drawn as an extra yarn; the
     centerlines are redrawn with their measured width (or --line-width)
  8. cleanup: areas below --min-area take the dominant surrounding color, 1px
     bumps and notches are smoothed
  9. save as 8-bit palette TIFF + palette text file

Usage:
  python img2texcelle.py design.jpg --width 200 --height 300 --points 1000000 --colors 8
  python img2texcelle.py design.jpg --width 200 --height 300 --reed 1000 --density 1200 --colors 8
  python img2texcelle.py design.jpg --width 200 --height 300 --points 1000000 \\
      --palette "#F9F6E8,#5D757C,#6A5C4E,#B1B3AA" --outline "#5F5F58" --outline-mode keep

Point definition:
  --points   : points per m^2, assumed square (same density in both directions)
  --reed/--density : horizontal points per m / vertical points per m (overrides --points)
"""

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from skimage.feature import hessian_matrix, hessian_matrix_eigvals
from skimage.morphology import skeletonize

EIGHT = np.ones((3, 3), dtype=bool)


def compute_pixels(width_cm, height_cm, points=None, reed=None, density=None):
    """Return (px_w, px_h) for the design."""
    if reed and density:
        ppm_x, ppm_y = reed, density
    elif points:
        # square assumption: same points per meter in both directions
        ppm_x = ppm_y = math.sqrt(points)
    else:
        raise ValueError("give --points or --reed and --density")
    px_w = round(width_cm / 100.0 * ppm_x)
    px_h = round(height_cm / 100.0 * ppm_y)
    return px_w, px_h


def rgb_to_lab(rgb):
    """sRGB uint8 array (..., 3) -> CIE Lab float32 (..., 3), D65."""
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]], dtype=np.float32)
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    lab = np.stack([116.0 * f[..., 1] - 16.0,
                    500.0 * (f[..., 0] - f[..., 1]),
                    200.0 * (f[..., 1] - f[..., 2])], axis=-1)
    return lab.astype(np.float32)


def sq_dist(x, centers):
    """Squared distances (N, K) between points (N, 3) and centers (K, 3)."""
    return ((x * x).sum(1)[:, None] - 2.0 * x @ centers.T
            + (centers * centers).sum(1)[None, :])


def parse_palette(text):
    colors = []
    for item in text.split(","):
        h = item.strip().lstrip("#")
        if len(h) != 6:
            raise ValueError(f"bad palette color: {item!r} (use #RRGGBB)")
        colors.append([int(h[i:i + 2], 16) for i in (0, 2, 4)])
    return np.array(colors, dtype=np.uint8)


def flat_mask(lab, limit=6.0):
    """True where the 3x3 neighborhood has low contrast (not an edge)."""
    lo = np.stack([ndimage.minimum_filter(lab[..., i], size=3) for i in range(3)], -1)
    hi = np.stack([ndimage.maximum_filter(lab[..., i], size=3) for i in range(3)], -1)
    return np.linalg.norm(hi - lo, axis=-1) < limit


def auto_palette(rgb, lab, flat, colors, merge, min_share=0.005, seed=0):
    """Pick up to `colors` yarn colors with k-means in Lab.

    Only flat pixels are used, so edge blends never become palette entries.
    Clusters closer than `merge` (delta E) are merged and tiny clusters are
    dropped. Returns uint8 RGB palette sorted by coverage.
    """
    if flat.sum() < 0.01 * flat.size:
        flat = np.ones_like(flat)

    x_lab, x_rgb = lab[flat], rgb[flat].astype(np.float32)
    rng = np.random.default_rng(seed)
    if len(x_lab) > 200_000:
        idx = rng.choice(len(x_lab), 200_000, replace=False)
        x_lab, x_rgb = x_lab[idx], x_rgb[idx]

    # k-means++ init
    k = min(colors, len(x_lab))
    centers = [x_lab[rng.integers(len(x_lab))]]
    for _ in range(1, k):
        d = sq_dist(x_lab, np.array(centers)).min(1)
        centers.append(x_lab[rng.choice(len(x_lab), p=d / d.sum())])
    centers = np.array(centers, dtype=np.float32)

    for _ in range(40):
        assign = sq_dist(x_lab, centers).argmin(1)
        new = centers.copy()
        for j in range(k):
            members = x_lab[assign == j]
            if len(members):
                new[j] = members.mean(0)
        if np.abs(new - centers).max() < 0.05:
            centers = new
            break
        centers = new
    assign = sq_dist(x_lab, centers).argmin(1)

    clusters = []  # [count, lab_sum, rgb_sum]
    for j in range(k):
        sel = assign == j
        if sel.any():
            clusters.append([int(sel.sum()), x_lab[sel].sum(0), x_rgb[sel].sum(0)])

    # merge near-identical clusters, closest pair first
    while len(clusters) > 1:
        means = np.array([c[1] / c[0] for c in clusters])
        d = np.sqrt(np.maximum(sq_dist(means, means), 0))
        np.fill_diagonal(d, np.inf)
        a, b = np.unravel_index(d.argmin(), d.shape)
        if d[a, b] >= merge:
            break
        clusters[a] = [clusters[a][i] + clusters[b][i] for i in range(3)]
        del clusters[b]

    total = sum(c[0] for c in clusters)
    kept = [c for c in clusters if c[0] / total >= min_share] or clusters
    kept.sort(key=lambda c: -c[0])
    return np.array([np.round(c[2] / c[0]) for c in kept], dtype=np.uint8)


def auto_outline(rgb, lab, pal_lab, margin=5.0, min_share=0.0005, split=6.0, seed=0):
    """Estimate dark contour colors from pixels clearly darker than the darkest
    yarn. Such pixels only exist on thin outlines (and the cores of dark
    lines), which never make it into the k-means palette. The dark pixels are
    split in two (e.g. a neutral contour and a warm one) when the halves are
    at least `split` delta E apart. Returns (1 or 2, 3) uint8 or None."""
    sel = lab[..., 0] < pal_lab[:, 0].min() - margin
    if sel.sum() < min_share * sel.size:
        return None
    x_lab, x_rgb = lab[sel], rgb[sel].astype(np.float32)
    rng = np.random.default_rng(seed)
    centers = x_lab[rng.choice(len(x_lab), 2, replace=False)]
    for _ in range(20):
        assign = sq_dist(x_lab, centers).argmin(1)
        if (assign == 0).all() or (assign == 1).all():
            break
        centers = np.stack([x_lab[assign == j].mean(0) for j in range(2)])
    if (assign == 0).all() or (assign == 1).all() \
            or np.linalg.norm(centers[0] - centers[1]) < split:
        return np.round(x_rgb.mean(0))[None, :].astype(np.uint8)
    return np.round(np.stack([x_rgb[assign == j].mean(0) for j in range(2)])).astype(np.uint8)


def smooth_chroma(lab, radius=2, sigma_s=1.5, sigma_l=6.0):
    """Joint bilateral filter on a/b guided by L.

    JPEG stores color at half resolution, so single pixels get reddish or
    greenish tints (e.g. brown spots at the tip of a blue line). Lightness is
    reliable, so chroma is averaged only over neighbors of similar lightness:
    tints vanish while thin lines keep their own color.
    """
    h, w, _ = lab.shape
    r = radius
    light = lab[..., 0]
    lp = np.pad(light, r, mode="edge")
    abp = np.pad(lab[..., 1:], ((r, r), (r, r), (0, 0)), mode="edge")
    acc = np.zeros((h, w, 2), dtype=np.float32)
    wsum = np.zeros((h, w), dtype=np.float32)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ln = lp[r + dy:r + dy + h, r + dx:r + dx + w]
            wgt = np.exp(-(dx * dx + dy * dy) / (2 * sigma_s ** 2)
                         - (ln - light) ** 2 / (2 * sigma_l ** 2)).astype(np.float32)
            acc += wgt[..., None] * abp[r + dy:r + dy + h, r + dx:r + dx + w]
            wsum += wgt
    out = lab.copy()
    out[..., 1:] = acc / wsum[..., None]
    return out


def unmix(lab, pal_lab, margin=3.0):
    """Coverage fractions (h, w, K) of the palette colors for every pixel.

    A pixel is explained either as one pure color or as a mix of two colors
    (the Lab segment between them that passes closest to the pixel). Pure wins
    unless a mix fits better by more than `margin` delta E, so pixels inside a
    wide area of an in-between color stay that color.
    """
    h, w, _ = lab.shape
    k = len(pal_lab)
    px = lab.reshape(-1, 3)
    pairs = [(a, b) for a in range(k) for b in range(a + 1, k)]
    alpha = np.zeros((len(px), k), dtype=np.float32)
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
    edges/tips of those areas are kept.
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


def resize_alpha(alpha, size):
    """Resize coverage maps to the knot grid (W, H) -> (H, W, K)."""
    out = np.empty((size[1], size[0], alpha.shape[-1]), dtype=np.float32)
    for k in range(alpha.shape[-1]):
        im = Image.fromarray(np.ascontiguousarray(alpha[..., k]), "F")
        out[..., k] = np.asarray(im.resize(size, Image.Resampling.BILINEAR))
    return out


def ridge_strength(a, sigmas):
    """Scale-normalised bright-ridge response of a coverage map (max over sigmas)."""
    best = np.zeros(a.shape, dtype=np.float32)
    for sigma in sigmas:
        h = hessian_matrix(a, sigma=sigma, order="rc", use_gaussian_derivatives=True)
        lam = hessian_matrix_eigvals(h)[1]  # most negative eigenvalue
        np.maximum(best, (-lam * sigma * sigma).astype(np.float32), out=best)
    return best


def shifted(a, dy, dx):
    """`a` shifted by (dy, dx) with edge replication."""
    r = max(abs(dy), abs(dx))
    p = np.pad(a, r, mode="edge")
    h, w = a.shape
    return p[r + dy:r + dy + h, r + dx:r + dx + w]


def lineness(a, dists=(3, 5)):
    """How much a pixel stands above both sides in some direction.

    Positive on a thin line (both sides lower across the line), ~0 or negative
    on the edge of a wide area (one side is always the area itself). Used to
    reject ridge responses that come from edges instead of lines.
    """
    a = ndimage.gaussian_filter(a, 1.0)
    best = np.full(a.shape, -np.inf, dtype=np.float32)
    for d in dists:
        low = np.full(a.shape, np.inf, dtype=np.float32)
        for dy, dx in ((0, d), (d, 0), (d, d), (d, -d)):
            side = np.maximum(shifted(a, dy, dx), shifted(a, -dy, -dx))
            np.minimum(low, side, out=low)
        np.maximum(best, a - low, out=best)
    return best


NB = np.ones((3, 3), dtype=np.uint8)
NB[1, 1] = 0


def prune(skel, spur):
    """Remove skeleton branches shorter than `spur` px (a wedge-shaped strip
    skeletonizes into a centerline with short side branches at the wide end).

    Endpoints are peeled off `spur` times; the surviving ends are then regrown
    along the original skeleton so real lines keep their full length.
    """
    if spur <= 0:
        return skel
    pruned = skel.copy()
    for _ in range(spur):
        nb = ndimage.convolve(pruned.astype(np.uint8), NB, mode="constant")
        pruned &= ~(nb == 1)
    nb = ndimage.convolve(pruned.astype(np.uint8), NB, mode="constant")
    grow = pruned & (nb == 1)
    for _ in range(spur):
        grow = ndimage.binary_dilation(grow, structure=EIGHT) & skel
    return pruned | grow


def detect_lines(a, ln, sigmas=(1.5, 2.5), strong=(0.10, 0.25, 0.15),
                 weak=(0.05, 0.12, 0.06), min_len=12, max_width=6, spur=6):
    """Centerlines of thin lines in one coverage map: (skeleton, strength, width).

    A thin line is a ridge in the coverage map; the ridge is followed with
    hysteresis (weak pixels connected to strong ones) so a line that is
    blurred below 50% coverage still stays in one piece. Thresholds are
    (ridge strength, coverage, lineness). `width` holds, on every skeleton
    pixel, the width of its line: the coverage summed across the line (which
    blur does not change), median per connected line.
    """
    r = ridge_strength(a, sigmas)
    seed = (r > strong[0]) & (a > strong[1]) & (ln > strong[2])
    cand = (r > weak[0]) & (a > weak[1]) & (ln > weak[2])
    comp, n = ndimage.label(cand, structure=EIGHT)
    keep = np.zeros(n + 1, dtype=bool)
    keep[np.unique(comp[seed])] = True
    keep[0] = False
    skel = prune(skeletonize(keep[comp]), spur)
    comp, n = ndimage.label(skel, structure=EIGHT)
    sizes = np.bincount(comp.ravel())
    skel &= (sizes >= min_len)[comp]
    width = np.zeros(a.shape, dtype=np.uint8)
    if n:
        win = 9
        local = ndimage.uniform_filter(a, size=win) * win
        med = ndimage.median(local, comp, np.arange(1, n + 1))
        lut = np.concatenate([[0], np.clip(np.rint(med), 1, max_width)]).astype(np.uint8)
        width[skel] = lut[comp[skel]]
    return skel, r, width


def classify_lines(skel, lab, labels, pal_lab, n_region, between, inner=2, outer=4,
                   penalty=4.0, max_score=12.0, min_s=0.15, rho=(0.35, 1.5),
                   boundary=(0.8, -3.0, 4.0)):
    """Color index per skeleton pixel (-1 = none), decided per connected line.

    Pixel colors along a blurred 1px line are ambiguous (a blurred blue line
    looks grey or dark). So every connected line takes the color that best
    explains its mean source color as "background + s * (color - background)".
    The background is the mean palette color of `labels` (the region labels,
    with all thin lines already removed, so a neighbouring parallel line
    cannot leak in) on a ring around the line.

    Outline colors (index >= n_region) are contours between two regions, and
    they are hard to tell from a blurred blue or brown line by color alone.
    So they get a bonus when the ring holds two different region colors and a
    penalty when the line runs inside one color (`boundary` = dominance
    threshold, bonus, penalty).

    JPEG stores color at half resolution, so a thin line keeps its lightness
    but loses much of its chroma. Hence s comes from L alone, and the a/b
    shift only has to point the right way with an attenuation in `rho`;
    a candidate that would need *more* chroma than the line shows (a dark
    outline color explaining a blurred blue line) is penalised. Colors that
    lie between two others in RGB (`between`) get a penalty, so a blurred
    blue line is called blue rather than a faint grey one.
    """
    comp, n = ndimage.label(skel, structure=EIGHT)
    if n == 0:
        return np.full(skel.shape, -1, dtype=np.int16)
    ids = np.arange(1, n + 1)
    near = ndimage.binary_dilation(skel, structure=EIGHT, iterations=inner)
    ring = ndimage.binary_dilation(near, structure=EIGHT, iterations=outer - inner) & ~near
    ring_ids = ndimage.maximum_filter(comp, size=2 * outer + 1) * ring
    line_mean = np.stack([ndimage.mean(lab[..., i], comp, ids) for i in range(3)], -1)
    share = np.stack([ndimage.sum(labels == v, ring_ids, ids) for v in range(n_region)], -1)
    total = np.maximum(share.sum(1, keepdims=True), 1)
    bg_mean = (share / total) @ pal_lab[:n_region]
    on_boundary = share.max(1) / total[:, 0] < boundary[0]
    best_score = np.full(n, np.inf)
    best_c = np.full(n, -1, dtype=np.int16)
    o = line_mean[:, 1:] - bg_mean[:, 1:]  # observed a/b shift
    for c in range(len(pal_lab)):
        d_l = pal_lab[c][0] - bg_mean[:, 0]
        s = np.clip((line_mean[:, 0] - bg_mean[:, 0]) / np.where(np.abs(d_l) < 1, 1, d_l), 0, 1)
        s[np.abs(d_l) < 1] = 0
        l_res = np.abs(line_mean[:, 0] - (bg_mean[:, 0] + s * d_l))
        p = s[:, None] * (pal_lab[c][1:] - bg_mean[:, 1:])  # predicted a/b shift
        pp = (p * p).sum(1)
        r = (o * p).sum(1) / np.maximum(pp, 1e-3)
        # the attenuation ratio is meaningless for a tiny predicted shift
        # (neutral color on neutral background): shrink it towards 1
        w = np.clip(np.sqrt(pp) / 4.0, 0, 1)
        r = w * r + (1.0 - w)
        perp = np.linalg.norm(o - r[:, None] * p, axis=1)
        r_pen = 4.0 * np.abs(1.0 - r) \
            + 15.0 * (np.maximum(0, r - rho[1]) + np.maximum(0, rho[0] - r))
        score = l_res + perp + r_pen + (penalty if c in between else 0.0)
        if c >= n_region:
            score = score + np.where(on_boundary, boundary[1], boundary[2])
        ok = (score < best_score) & (s > min_s) & (score < max_score)
        best_score[ok], best_c[ok] = score[ok], c
    lut = np.concatenate([[-1], best_c]).astype(np.int16)
    return lut[comp]


def thicken(skel, width):
    """Grow a 1px skeleton to the per-pixel `width` (uint8 map, 0 = not a line)."""
    out = np.zeros(skel.shape, dtype=bool)
    for w in np.unique(width[skel]):
        part = skel & (width == w)
        if w <= 1:
            out |= part
        else:
            out |= ndimage.binary_dilation(part, structure=np.ones((w, w), dtype=bool))
    return out


def _save_indexed(labels, colors, path):
    """Debug helper: save a label map as a palette PNG."""
    im = Image.fromarray(labels, "P")
    flat = colors.ravel().tolist()
    im.putpalette(flat + [0] * (768 - len(flat)))
    im.save(path)


def fill_holes(labels, holes):
    """Every hole pixel takes the label of the nearest non-hole pixel."""
    if not holes.any():
        return
    iy, ix = ndimage.distance_transform_edt(holes, return_distances=False,
                                            return_indices=True)
    labels[:] = labels[iy, ix]


def smooth_bumps(labels, n):
    """One pass: a pixel with >= 3 of its 4 neighbors in one other color takes that color.

    Removes 1px bumps and fills 1px notches on edges. Line tips (one same-color
    neighbor behind, a same-color neighbor beside) are left alone.
    """
    p = np.pad(labels, 1, mode="edge")
    nb = np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    new = labels.copy()
    for c in range(n):
        new[((nb == c).sum(0) >= 3) & (labels != c)] = c
    changed = int((new != labels).sum())
    labels[:] = new
    return changed


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


def convert(src, dst, width_cm, height_cm, colors, points=None, reed=None,
            density=None, palette=None, merge=12.0, min_area=20, denoise=0,
            rotate=True, outline="auto", outline_mode="drop", line_width=0,
            lines=True, debug_dir=None):
    px_w, px_h = compute_pixels(width_cm, height_cm, points, reed, density)

    img = Image.open(src).convert("RGB")

    if rotate and img.width != img.height and width_cm != height_cm \
            and (img.width > img.height) != (width_cm > height_cm):
        img = img.transpose(Image.Transpose.ROTATE_90)
        print("image rotated 90 deg to match carpet orientation", flush=True)

    # warn if aspect ratio of image and carpet differ (image will be stretched)
    img_ratio = img.width / img.height
    carpet_ratio = width_cm / height_cm
    if abs(img_ratio - carpet_ratio) / carpet_ratio > 0.02:
        print(f"WARNING: image ratio {img_ratio:.3f} != carpet ratio {carpet_ratio:.3f}, "
              f"image will be stretched", file=sys.stderr)

    # 1. remove jpeg speckle at source resolution
    if denoise and denoise > 1:
        img = img.filter(ImageFilter.MedianFilter(denoise | 1))

    rgb = np.asarray(img)
    lab = rgb_to_lab(rgb)
    flat = flat_mask(lab)

    # 2. yarn palette (each color = one yarn); outline colors only occur as lines
    if palette is None:
        palette = auto_palette(rgb, lab, flat, colors, merge)
    n = len(palette)
    if isinstance(outline, str) and outline == "auto":
        outline = auto_outline(rgb, lab, rgb_to_lab(palette))
        if outline is not None:
            print("outline colors: " + ", ".join("#{:02X}{:02X}{:02X}".format(*c)
                                                 for c in outline.tolist()))
    all_colors = palette if outline is None else np.concatenate([palette, outline])
    n_all = len(all_colors)
    pal_lab = rgb_to_lab(all_colors)

    # 3. coverage fractions per region color at source resolution, then on the
    #    knot grid (outline colors are not used here: they would steal blurred
    #    blue lines, which look dark too)
    lab_s = smooth_chroma(lab)
    alpha = unmix(lab_s, pal_lab[:n])
    blends = unmix_thin_blends(alpha, lab_s, palette, pal_lab)
    print(f"edge blend pixels unmixed: {blends}", flush=True)
    alpha = resize_alpha(alpha, (px_w, px_h))
    del lab, flat

    # 4. regions: strongest region color; parts thinner than 3 knots become
    #    holes, filled from their surroundings (lines are redrawn below)
    #    (coverage is smoothed a little first so soft, noisy boundaries do not
    #    flicker between two colors). Line-like strips up to 5 knots wide are
    #    holes too: they are redrawn as lines with a measured width below.
    smooth = np.stack([ndimage.gaussian_filter(alpha[..., k], 1.0) for k in range(n)], -1)
    labels = smooth.argmax(-1).astype(np.uint8)
    del smooth
    if lines:
        liny = [lineness(alpha[..., k]) for k in range(n)]
        holes = np.zeros(labels.shape, dtype=bool)
        five = np.ones((5, 5), dtype=bool)
        for k in range(n):
            m = labels == k
            holes |= m & ~ndimage.binary_opening(m, structure=EIGHT)
            holes |= m & ~ndimage.binary_opening(m, structure=five) & (liny[k] > 0.15)
        fill_holes(labels, holes)
        print(f"region holes refilled: {int(holes.sum())} px", flush=True)
        if debug_dir:
            _save_indexed(labels, all_colors, os.path.join(debug_dir, "regions.png"))

    # 5. lines: find thin lines in every coverage map, decide the color of each
    #    connected line from its mean color, redraw centerlines with their width
    # in keep mode all outline colors become one extra yarn (index n)
    keep_outline = outline_mode == "keep" and outline is not None
    n_used = n + 1 if keep_outline else n
    if lines:
        maps = [alpha[..., k] for k in range(n)]
        if outline is not None:
            alpha_o = unmix(lab_s, pal_lab)[..., n:]
            maps += [m for m in np.moveaxis(resize_alpha(alpha_o, (px_w, px_h)), -1, 0)]
            liny += [lineness(m) for m in maps[n:]]
            del alpha_o
        del alpha
        # source Lab sampled on the knot grid, for the mean color of each line
        ys = (np.arange(px_h) * lab_s.shape[0] / px_h).astype(int)
        xs = (np.arange(px_w) * lab_s.shape[1] / px_w).astype(int)
        lab_t = lab_s[ys][:, xs]
        del lab_s
        between = set(blend_pairs(palette))
        regions = labels.copy()  # region labels around each line, lines removed
        best = np.zeros(labels.shape, dtype=np.float32)
        drawn = np.zeros(n_all, dtype=np.int64)
        # pass 1: find and classify lines in every map
        found = []
        contour = np.zeros(labels.shape, dtype=bool)
        for a, ln in zip(maps, liny):
            skel, strength, width = detect_lines(a, ln)
            if line_width:
                width[skel] = line_width
            color = classify_lines(skel, lab_t, regions, pal_lab, n, between)
            if (color >= n).any():
                contour |= ndimage.binary_dilation(color >= n, structure=EIGHT, iterations=2)
            found.append((skel, strength, width, color))
        del maps, liny
        # pass 2: a contour is also a weak ridge in some region color's map (a
        # dark contour looks a bit brown); such duplicates of a line already
        # classified as outline must not be drawn as brown. Then draw.
        for skel, strength, width, color in found:
            comp, nc = ndimage.label(skel & (color >= 0) & (color < n), structure=EIGHT)
            if nc:
                dup = ndimage.mean(contour, comp, np.arange(1, nc + 1)) > 0.6
                color[np.concatenate([[False], dup])[comp]] = -1
            s = ndimage.maximum_filter(strength, size=7)
            for c in np.unique(color[skel]):
                if c < 0 or (c >= n and not keep_outline):
                    continue
                m = thicken(color == c, width)
                hit = m & (s > best)
                best[hit] = s[hit]
                labels[hit] = min(int(c), n)
                drawn[c] += int((color == c).sum())
        print("line centerline pixels drawn per color: "
              + ", ".join(f"{c}: {d}" for c, d in enumerate(drawn.tolist())), flush=True)
        if debug_dir:
            _save_indexed(labels, all_colors, os.path.join(debug_dir, "lines.png"))
    else:
        del alpha, lab_s

    # 6. small areas take the dominant surrounding color, 1px bumps/notches smoothed
    if min_area and min_area > 1:
        fixed = remove_islands(labels, n_used, min_area)
        bumps = smooth_bumps(labels, n_used)
        fixed += remove_islands(labels, n_used, min_area)
        print(f"islands cleaned: {fixed} px repainted (min area {min_area}), "
              f"bumps smoothed: {bumps} px")

    # 7. save 8-bit palette TIFF, no compression
    out_palette = palette
    if keep_outline:
        out_palette = np.concatenate([palette, np.round(outline.mean(0))[None, :].astype(np.uint8)])
    pal = Image.fromarray(labels, "P")
    flat_palette = out_palette.ravel().tolist()
    pal.putpalette(flat_palette + [0] * (768 - len(flat_palette)))
    pal.save(dst, format="TIFF", compression=None)

    # palette text: index -> RGB
    txt = os.path.splitext(dst)[0] + "_palette.txt"
    counts = np.bincount(labels.ravel(), minlength=n_used)
    with open(txt, "w") as f:
        for i, (r, g, b) in enumerate(out_palette.tolist()):
            f.write(f"{i}\t{r}\t{g}\t{b}\t#{r:02X}{g:02X}{b:02X}\n")

    print(f"{dst}: {px_w} x {px_h} px, {n_used} colors")
    for i, (r, g, b) in enumerate(out_palette.tolist()):
        print(f"  {i}  #{r:02X}{g:02X}{b:02X}  {100.0 * counts[i] / labels.size:5.1f}%")
    print(f"palette: {txt}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("--out", default=None, help="output .tiff (default: <src>.tiff)")
    p.add_argument("--width", type=float, required=True, help="carpet width cm")
    p.add_argument("--height", type=float, required=True, help="carpet height cm")
    p.add_argument("--points", type=float, help="points per m^2")
    p.add_argument("--reed", type=float, help="horizontal points per meter")
    p.add_argument("--density", type=float, help="vertical points per meter")
    p.add_argument("--colors", type=int, default=8,
                   help="max number of yarns (5/6/8/12); near-identical colors are merged")
    p.add_argument("--palette", default=None,
                   help='fixed yarn colors, e.g. "#F9F6E8,#5D757C,#6A5C4E" (overrides --colors)')
    p.add_argument("--outline", default="auto",
                   help='colors that only occur as thin contour lines, e.g. "#504F48"; '
                        '"auto" (default) measures the dark contour color, "none" disables')
    p.add_argument("--outline-mode", choices=["drop", "keep"], default="drop",
                   help="drop: erase outline lines (neighbours close over them); "
                        "keep: draw them as extra yarns (default drop)")
    p.add_argument("--line-width", type=int, default=0,
                   help="fixed width in knots for redrawn thin lines "
                        "(default 0 = measure each line's own width)")
    p.add_argument("--no-lines", action="store_true",
                   help="disable line detection (pure region labeling)")
    p.add_argument("--merge", type=float, default=12.0,
                   help="merge auto colors closer than this delta E (default 12)")
    p.add_argument("--min-area", type=int, default=20,
                   help="areas smaller than this many px take the surrounding color (0=off)")
    p.add_argument("--denoise", type=int, default=0,
                   help="median filter size on source image (0=off; breaks 1px lines)")
    p.add_argument("--no-rotate", action="store_true",
                   help="do not rotate image to match carpet orientation")
    p.add_argument("--debug-dir", default=None,
                   help="write regions.png / lines.png (intermediate label maps) here")
    a = p.parse_args()

    palette = parse_palette(a.palette) if a.palette else None
    if a.outline in ("auto", "none", ""):
        outline = "auto" if a.outline == "auto" else None
    else:
        outline = parse_palette(a.outline)
    out = a.out or os.path.splitext(a.src)[0] + ".tiff"
    convert(a.src, out, a.width, a.height, a.colors, a.points, a.reed, a.density,
            palette, a.merge, a.min_area, a.denoise, not a.no_rotate,
            outline, a.outline_mode, a.line_width, not a.no_lines, a.debug_dir)


if __name__ == "__main__":
    main()
