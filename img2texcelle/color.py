"""Color space, palette parsing and the automatic yarn palette."""

import numpy as np
from scipy import ndimage


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
    """'#RRGGBB,#RRGGBB,...' -> uint8 (K, 3)."""
    colors = []
    for item in text.split(","):
        h = item.strip().lstrip("#")
        if len(h) != 6:
            raise ValueError(f"bad palette color: {item!r} (use #RRGGBB)")
        colors.append([int(h[i:i + 2], 16) for i in (0, 2, 4)])
    return np.array(colors, dtype=np.uint8)


def hex_color(rgb):
    r, g, b = (int(v) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


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

    Note: yarns that only occur in 1-knot lines never enter the flat sample,
    so at loom quality a fixed --palette is far more accurate.
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
        d = np.maximum(sq_dist(x_lab, np.array(centers)).min(1), 0)  # rounding can give -1e-6
        if d.sum() <= 0:
            break
        centers.append(x_lab[rng.choice(len(x_lab), p=d / d.sum())])
    centers = np.array(centers, dtype=np.float32)
    k = len(centers)

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
