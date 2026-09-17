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

An axis off centre splits the image into two halves of different size. One
of them is kept and mirrored onto the other (`mirror_halves`), so the axis
becomes the image centre and nothing is cropped: without --stretch the
larger half (the carpet height then follows the image), with --stretch the
half whose mirrored image fits the carpet ratio with the least distortion.

Only the kept part is converted (`part_region`): the kept half of every
copy-only axis plus a pad of PAD_KNOTS beyond the axis (reflected pixels,
so the pad is what the mirror will put there), the whole extent of an
averaged axis (both halves are evidence). The part without the pad is the
output part; the full knot map is the part mirrored (`mirror_copy`).
"""

import itertools
import math

import numpy as np
from PIL import Image

from .grid import distortion

AXIS_CONTRAST_AUTO = 0.4    # --symmetry auto takes an axis below this contrast
AXIS_CONTRAST = 0.7         # below this an axis is worth a hint (auto) / a --symmetric cut (split)
AXIS_CONTRAST_FORCED = 0.9  # --symmetry lr/tb/both use the measured position below this
EXACT_MATCH = 0.35          # measure_axis match below which the halves match everywhere
PAD_KNOTS = 20              # knots processed beyond a copy-only axis (see `part_region`)
AXIS_NAMES = {1: "left/right", 0: "top/bottom"}
FLAGS = {1: "lr", 0: "tb"}


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
    (`half_sizes` / `mirror_half` split and centre the image there). The search
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


def half_sizes(size, shift):
    """Pixels in the two halves (left/top, right/bottom) cut at the mirror
    axis (size - 1 + shift) / 2 (`shift` from `measure_axis`); a pixel row
    on the axis counts in both halves. fom: 5056 rows, shift -256 -> 2400
    above and 2656 below the axis."""
    twice = size - 1 + shift  # the axis is at twice / 2
    return twice // 2 + 1, size - (twice + 1) // 2


def mirrored_size(size, shift, side):
    """Size of the image along an axis after `mirror_half` keeps `side`
    ('left' / 'top' = the first half, anything else the second)."""
    first, second = half_sizes(size, shift)
    on_axis = (size - 1 + shift) % 2 == 0
    return 2 * (first if side in ("left", "top") else second) - on_axis


def mirror_half(img, axis, shift, side):
    """Keep the `side` half ('left' / 'right' for axis 1, 'top' / 'bottom'
    for axis 0) of the mirror axis (size - 1 + shift) / 2 and replace the
    other half with its mirror image, so the axis becomes the image centre.
    The image grows or shrinks along `axis` to `mirrored_size`; a pixel row
    on the axis stays single."""
    a = np.asarray(img)
    size = a.shape[axis]
    twice = size - 1 + shift
    on_axis = int(twice % 2 == 0)

    def rows(lo, hi):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(lo, hi)
        return a[tuple(sl)]

    if side in ("left", "top"):
        keep = rows(0, twice // 2 + 1)
        out = np.concatenate([keep, np.flip(rows(0, twice // 2 + 1 - on_axis), axis)], axis)
    else:
        start = (twice + 1) // 2
        keep = rows(start, size)
        out = np.concatenate([np.flip(rows(start + on_axis, size), axis), keep], axis)
    return Image.fromarray(np.ascontiguousarray(out))


def find_axes(img, mode="auto", average=True):
    """Decide the symmetric axes (`mode`: auto / none / lr / tb / both).

    `auto` takes an axis whose contrast is below AXIS_CONTRAST_AUTO; one
    between that and AXIS_CONTRAST (fom top/bottom: 0.57) is not used but
    named, with the --symmetry flag that forces it. `lr` / `tb` / `both`
    take the axis regardless, at the measured position when its contrast is
    below AXIS_CONTRAST_FORCED, otherwise at the centre with a warning (a
    guess could mirror the image at a random place). Returns
    {axis: (shift, average)} for the taken axes (1 = left/right, 0 =
    top/bottom): `shift` is the axis position from `measure_axis` (0 =
    centre), `average` says the halves match everywhere (match below
    EXACT_MATCH) and `average` was not switched off (--no-average), so their
    coverage may be averaged (`mirror_average`); either way the kept half is
    copied onto the other after cleanup (`mirror_copy`).
    """
    axes = {"auto": [1, 0], "both": [1, 0], "lr": [1], "tb": [0], "none": []}[mode]
    taken = {}
    for ax in axes:
        size = img.size[0] if ax == 1 else img.size[1]
        shift, contrast, match = measure_axis(img, ax)
        where = describe_axis(ax, size, shift)
        if mode == "auto" and contrast >= AXIS_CONTRAST_AUTO:
            if contrast < AXIS_CONTRAST:
                print(f"warning: {AXIS_NAMES[ax]} mirror axis unclear, not used (best candidate "
                      f"{where}, contrast {contrast:.2f} >= {AXIS_CONTRAST_AUTO}); force it with "
                      f"--symmetry {FLAGS[ax]}" + (" (or both)" if len(axes) > 1 else ""), flush=True)
            else:
                print(f"symmetry: {AXIS_NAMES[ax]} not symmetric (best axis {where}, "
                      f"contrast {contrast:.2f} >= {AXIS_CONTRAST})", flush=True)
            continue
        if mode != "auto" and contrast >= AXIS_CONTRAST_FORCED:
            print(f"warning: no clear {AXIS_NAMES[ax]} mirror axis (contrast {contrast:.2f} "
                  f">= {AXIS_CONTRAST_FORCED}; best candidate {where}); forced, using the centre",
                  flush=True)
            shift, match, where = 0, 1.0, describe_axis(ax, size, 0)  # never average
        avg = bool(average and match < EXACT_MATCH)
        taken[ax] = (int(shift), avg)
        how = "average + copy" if avg else ("copy only (--no-average)" if match < EXACT_MATCH
                                            else "copy only")
        print(f"symmetry: {AXIS_NAMES[ax]} axis {where}, contrast {contrast:.2f}, halves "
              f"match {match:.2f} -> {how}", flush=True)
    if not taken:
        print("symmetry: none", flush=True)
    return taken


def mirror_halves(img, axes, stretch_to=None):
    """Make every taken axis the image centre by keeping one half and
    replacing the other with its mirror (`mirror_half`); an averaged axis
    already at the centre leaves the image alone (both halves keep their
    evidence), a copy-only axis at the centre still replaces the other half
    (only the kept half and a reflected pad are converted, `part_region`).

    `axes` is `find_axes`' result. Without `stretch_to` the larger half is
    kept: nothing is cropped, the image only grows (fom: 3392x5056 with the
    axis 128 px above the centre becomes 3392x5312 from its bottom half) and
    the carpet height follows the new image ratio (`grid.fit_carpet`). With
    `stretch_to` = (width_cm, height_cm) the halves whose mirrored image is
    closest to the carpet ratio are kept (fom: the bottom half, 4.4%
    distortion, against 6.0% for the top half); the image is then stretched
    onto the knot grid. Returns (img, sides) with sides = {axis: 'left' /
    'right' / 'top' / 'bottom'} for every taken axis, the half `mirror_copy`
    copies from."""
    w, h = img.size
    choices = {}  # axis -> {side: mirrored size}
    for ax, (shift, _) in axes.items():
        size, names = (w, ("left", "right")) if ax == 1 else (h, ("top", "bottom"))
        choices[ax] = {name: mirrored_size(size, shift, name) for name in names}

    def image_size(sides):
        return (choices[1][sides[1]] if 1 in sides else w,
                choices[0][sides[0]] if 0 in sides else h)

    if stretch_to is None:
        sides = {ax: max(c, key=c.get) for ax, c in choices.items()}  # ties -> left/top
    else:
        combos = [dict(zip(choices, names)) for names in itertools.product(*choices.values())]
        sides = min(combos, key=lambda c: distortion(*image_size(c), *stretch_to)) if combos else {}
    for ax, side in sides.items():
        shift, average = axes[ax]
        if shift == 0:
            if not average:
                img = mirror_half(img, ax, 0, side)
            continue
        other = next(n for n in choices[ax] if n != side)
        size, unit = (w, "columns") if ax == 1 else (h, "rows")
        kept, dropped = half_sizes(size, shift)
        if side in ("right", "bottom"):
            kept, dropped = dropped, kept
        img = mirror_half(img, ax, shift, side)
        alt = {**sides, ax: other}
        why = "the larger half" if stretch_to is None else (
            f"{100 * distortion(*image_size(sides), *stretch_to):.1f}% distortion against "
            f"{100 * distortion(*image_size(alt), *stretch_to):.1f}% with the {other} half")
        print(f"symmetry: {side} half ({kept} {unit}) kept and mirrored onto the {other} "
              f"({dropped} {unit}): image {img.width}x{img.height} ({why})", flush=True)
    return img, sides


def part_region(px_w, px_h, axes, sides, pad=PAD_KNOTS):
    """Which knots are converted and which are the output part.

    Returns (region, part) as (x0, y0, x1, y1) knot rectangles of the
    px_w x px_h grid. Along a copy-only axis (`axes` from `find_axes`,
    `sides` from `mirror_halves`) the part is the kept half (an odd grid's
    middle knot, centred on the axis, belongs to it) and the region adds
    `pad` knots beyond the axis: the reach of `straighten_runs` (runs of 15,
    window 9), `directional_mean` and `remove_islands`, so a knot of the
    part is decided as in the whole image unless a structure crosses the
    pad. Along an averaged axis the region is the whole extent (the other
    half is evidence) and the part is still the kept half. No axis: both
    are the whole grid.
    """
    region, part = [0, 0, px_w, px_h], [0, 0, px_w, px_h]
    for ax, (_, average) in axes.items():
        size = px_w if ax == 1 else px_h
        first = sides[ax] in ("left", "top")
        lo, hi = (0, size - size // 2) if first else (size // 2, size)
        i = 0 if ax == 1 else 1
        part[i], part[i + 2] = lo, hi
        if not average:
            region[i], region[i + 2] = (0, min(hi + pad, size)) if first else (max(lo - pad, 0), size)
    return tuple(region), tuple(part)


def mirror_average(a, lr, tb):
    """Average an (h, w, K) coverage map with its mirror image(s), so both
    halves of a symmetric design are decided from the same evidence."""
    if lr:
        a = 0.5 * (a + a[:, ::-1])
    if tb:
        a = 0.5 * (a + a[::-1])
    return a


def mirror_copy(labels, lr=None, tb=None):
    """Make the label map exactly symmetric: the `lr` half ('left' / 'right')
    is copied onto the other, then the `tb` half ('top' / 'bottom'); None
    leaves that axis alone. A middle column/row stays as it is."""
    h, w = labels.shape
    if lr == "left":
        labels[:, w - w // 2:] = labels[:, :w // 2][:, ::-1]
    elif lr == "right":
        labels[:, :w // 2] = labels[:, w - w // 2:][:, ::-1]
    if tb == "top":
        labels[h - h // 2:] = labels[:h // 2][::-1]
    elif tb == "bottom":
        labels[:h // 2] = labels[h - h // 2:][::-1]
