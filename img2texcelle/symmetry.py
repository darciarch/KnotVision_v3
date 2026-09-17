"""Mirror symmetry of the design: finding the axis, centring it, enforcing it.

One measurement (`measure_axis`) serves both the pipeline (`--symmetry`) and
`img2texcelle.split --symmetric`. It has to work on designs whose medallion is
off centre: in data/fomggggggbro the top/bottom axis is at row 2399.5 of
5056, 128 px above the centre, and only the medallion mirrors exactly there
(the crowns and corner motifs were drawn 100+ px away from their mirror
positions, the fine ornament never matches). So the axis is judged from the
rows that meet at the cut, not from the whole image, and a second number
tells whether the halves match everywhere (then their evidence may be
averaged) or only near the axis (then one half is copied).
"""

import math

import numpy as np
from PIL import Image

AXIS_CONTRAST = 0.7   # measure_axis contrast below which an axis is trusted
EXACT_MATCH = 0.35    # measure_axis match below which the halves match everywhere
AXIS_NAMES = {1: "left/right", 0: "top/bottom"}


def _grey(img, factor):
    w, h = img.size
    small = img.convert("L").resize((max(w // factor, 8), max(h // factor, 8)), Image.BOX)
    return np.asarray(small).astype(np.float32)


def mirror_error(g, axis, d, band=None):
    """Mean |g - mirror of g| for the mirror axis at (size - 1 + d) / 2 along
    `axis` (pixel i mirrors onto pixel size - 1 + d - i; d = 0 is the centre,
    positive = axis right/down). Only the overlap of the image with its
    mirror counts (nothing wraps around), 1/16 of the other side is cut off
    at both edges, and with `band` only the rows (columns) within
    band * size of the axis are compared: the rows that meet at the cut."""
    size, other = g.shape[axis], g.shape[1 - axis]
    lo, hi = max(0, d), size + min(0, d)
    if band is not None:
        c, r = (size - 1 + d) / 2, band * size
        lo, hi = max(lo, math.floor(c - r)), min(hi, math.ceil(c + r) + 1)
    if hi <= lo:
        return math.inf
    edge = max(other // 16, 1)
    sl = [slice(edge, other - edge)] * 2
    sl[axis] = slice(lo, hi)
    a = g[tuple(sl)]
    sl[axis] = slice(size - hi + d, size - lo + d)  # the mirrored rows, in reverse
    b = np.flip(g[tuple(sl)], axis)
    return float(np.abs(a - b).mean())


def measure_axis(img, axis, margin=0.25, band=0.15, far=32):
    """Find the mirror axis of `img` along `axis` (1 = left/right, 0 = top/bottom).

    Returns (shift, contrast, match). `shift` is in full-res px, positive =
    axis right/down of the centre, axis at (size - 1 + shift) / 2 px
    (`crop_to_axis` removes `shift` px on one side to centre it). The search
    covers +-`margin` of the size on a greyscale reduced by up to 8x (at least
    128 px on the short side), comparing only the rows within +-`band` of the
    size around each candidate axis, then refines at full resolution.

    `contrast` = mirror error at the best axis / best error more than `far`
    px away from it: 0 = perfect mirror, ~1 = no axis (flat curve). Measured
    2026-09-17: the real design 0.00, a scanned design 0.16, a Gemini render
    0.12 left/right and 0.57 top/bottom (medallion mirrors, crowns don't);
    Gemini quarter renders (no symmetry) 0.79-0.99. Threshold AXIS_CONTRAST.

    `match` = whole-image mirror error at that axis / error of a 32 px shift
    (1/4 size): below EXACT_MATCH the halves match everywhere (the real
    design 0.00-0.02, Gemini renders 0.07-0.27 left/right), otherwise only
    near the axis (the Gemini render above: 1.00 top/bottom).
    """
    w, h = img.size
    c = max(1, min(8, min(w, h) // 128))
    g = _grey(img, c)
    size = g.shape[axis]
    lim = max(int(size * margin), 1)
    errs = {d: mirror_error(g, axis, d, band) for d in range(-lim, lim + 1)}
    best = min(errs, key=errs.get)
    others = [e for d, e in errs.items() if abs(d - best) * c > far]
    contrast = errs[best] / min(others) if others and min(others) > 0 else 1.0

    gf = np.asarray(img.convert("L")).astype(np.float32)
    shift = min(range(best * c - c, best * c + c + 1),
                key=lambda d: mirror_error(gf, axis, d, band))

    g4 = _grey(img, 4)
    edge = max(min(g4.shape) // 16, 1)
    ref = min(np.abs(g4 - np.roll(g4, 8, axis=a))[edge:-edge, edge:-edge].mean() for a in (0, 1))
    err = mirror_error(g4, axis, int(round(shift / 4)))
    match = err / ref if ref > 0 else 0.0
    return shift, contrast, match


def describe_axis(axis, size, shift):
    """'at row 2399.5 (128 px above the centre)' / 'at column 1695.5 (at the centre)'."""
    pos = (size - 1 + shift) / 2
    unit = "column" if axis == 1 else "row"
    if shift == 0:
        where = "at the centre"
    else:
        side = ("right" if shift > 0 else "left") if axis == 1 else ("below" if shift > 0 else "above")
        where = f"{abs(shift) / 2:g} px {side} the centre"
    return f"at {unit} {pos:g} ({where})"


def crop_to_axis(img, shift_x=0, shift_y=0):
    """Crop the image symmetrically around a mirror axis off centre by
    (shift_x, shift_y) px (the shifts from `measure_axis`, positive = axis
    right/down of the centre), so that the axis becomes the image centre and
    the knot grid mirrors onto itself."""
    w, h = img.size
    x0, x1 = max(0, shift_x), w + min(0, shift_x)
    y0, y1 = max(0, shift_y), h + min(0, shift_y)
    return img.crop((x0, y0, x1, y1))


def find_and_centre(img, mode="auto"):
    """Decide the symmetric axes (`mode`: auto / none / lr / tb / both) and
    crop the image so an off-centre axis becomes the centre.

    `auto` takes an axis whose contrast is below AXIS_CONTRAST; `lr` / `tb` /
    `both` take the axis regardless, at the measured position when it is
    clear, otherwise at the centre with a warning (a guess could crop the
    image by a random amount). Returns (img, copy_lr, copy_tb, avg_lr, avg_tb):
    `copy_*` = the axis is taken (the left/top half is copied onto the other,
    `mirror_copy`), `avg_*` = the halves also match everywhere (match below
    EXACT_MATCH), so their coverage may be averaged (`mirror_average`).
    """
    axes = {"auto": [1, 0], "both": [1, 0], "lr": [1], "tb": [0], "none": []}[mode]
    taken = {}  # axis -> (shift, match)
    for ax in axes:
        size = img.size[0] if ax == 1 else img.size[1]
        shift, contrast, match = measure_axis(img, ax)
        where = describe_axis(ax, size, shift)
        if contrast > AXIS_CONTRAST:
            if mode == "auto":
                print(f"symmetry: {AXIS_NAMES[ax]} not symmetric (best axis {where}, "
                      f"contrast {contrast:.2f} > {AXIS_CONTRAST})", flush=True)
                continue
            print(f"warning: no clear {AXIS_NAMES[ax]} mirror axis (contrast {contrast:.2f} "
                  f"> {AXIS_CONTRAST}; best candidate {where}); forced, using the centre",
                  flush=True)
            shift, match, where = 0, 1.0, describe_axis(ax, size, 0)  # never average
        taken[ax] = (shift, match)
        print(f"symmetry: {AXIS_NAMES[ax]} axis {where}, contrast {contrast:.2f}, halves "
              f"match {match:.2f} -> " + ("average + copy" if match < EXACT_MATCH else "copy only"),
              flush=True)
    if not taken:
        print("symmetry: none", flush=True)
    elif any(s for s, _ in taken.values()):
        img = crop_to_axis(img, taken.get(1, (0,))[0], taken.get(0, (0,))[0])
        print(f"image cropped to {img.width}x{img.height} to centre the mirror axis", flush=True)
    avg = {ax: m < EXACT_MATCH for ax, (_, m) in taken.items()}
    return img, 1 in taken, 0 in taken, avg.get(1, False), avg.get(0, False)


def mirror_average(a, lr, tb):
    """Average an (h, w, K) coverage map with its mirror image(s), so both
    halves of a symmetric design are decided from the same evidence."""
    if lr:
        a = 0.5 * (a + a[:, ::-1])
    if tb:
        a = 0.5 * (a + a[::-1])
    return a


def mirror_copy(labels, lr, tb):
    """Make the label map exactly symmetric: the left (top) half is copied
    onto the right (bottom) half; a middle column/row stays as it is."""
    h, w = labels.shape
    if lr:
        labels[:, w - w // 2:] = labels[:, :w // 2][:, ::-1]
    if tb:
        labels[h - h // 2:] = labels[:h // 2][::-1]
