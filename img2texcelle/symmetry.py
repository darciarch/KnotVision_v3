"""Mirror symmetry of the design: detection, centring the axis, enforcing it."""

import numpy as np


def detect_symmetry(img, ratio=0.35, margin=0.02):
    """Find mirror symmetry of a design image: {axis: shift} for the symmetric axes.

    axis 1 = left/right, 0 = top/bottom; `shift` is the roll (full-res px)
    that aligns the flipped image with the image: pixel i mirrors onto pixel
    size - 1 + shift - i, i.e. the mirror axis is shift / 2 px right/down of
    the centre (`crop_to_axis` removes `shift` px on one side to centre it).
    An axis counts as symmetric when the mean |image - mirrored image| (at
    1/4 size, best shift within `margin` of the size, image edges excluded)
    is below `ratio` times the same error for the image shifted by 8 px
    (measured: Gemini renders 0.07-0.27 left/right and 0.76-0.94 top/bottom,
    Texcelle designs 0.00-0.02 both).
    """
    small = img.convert("L").resize((max(img.width // 4, 8), max(img.height // 4, 8)))
    g = np.asarray(small).astype(np.float32)
    h, w = g.shape
    edge = max(min(h, w) // 16, 1)
    ref = min(np.abs(g - np.roll(g, 8, axis=a))[edge:-edge, edge:-edge].mean() for a in (0, 1))
    if ref <= 0:
        return {}
    out = {}
    for axis in (1, 0):
        size = g.shape[axis]
        lim = max(int(size * margin), 1)
        sl = [slice(edge, -edge)] * 2
        sl[axis] = slice(lim + edge, size - lim - edge)
        sl = tuple(sl)
        errs = [(np.abs(g - np.roll(np.flip(g, axis), d, axis))[sl].mean(), d)
                for d in range(-lim, lim + 1)]
        err, d = min(errs)
        if err < ratio * ref:
            out[axis] = 4 * d  # small px -> full px; refined by refine_axis_shift
    return out


def refine_axis_shift(img, axis, shift, search=4):
    """Full-resolution refinement of the mirror axis shift found at 1/4 size."""
    g = np.asarray(img.convert("L")).astype(np.float32)
    size = g.shape[axis]
    edge = max(size // 16, 1)
    sl = [slice(None)] * 2
    best = None
    for d in range(shift - search, shift + search + 1):
        sl[axis] = slice(abs(d) + edge, size - abs(d) - edge)
        e = np.abs(g - np.roll(np.flip(g, axis), d, axis))[tuple(sl)].mean()
        if best is None or e < best[0]:
            best = (e, d)
    return best[1]


def crop_to_axis(img, shift_x=0, shift_y=0):
    """Crop the image symmetrically around a mirror axis off centre by
    (shift_x, shift_y) px (the rolls from `detect_symmetry`, positive = axis
    right/down of the centre), so that the axis becomes the image centre and
    the knot grid mirrors onto itself."""
    w, h = img.size
    x0, x1 = max(0, shift_x), w + min(0, shift_x)
    y0, y1 = max(0, shift_y), h + min(0, shift_y)
    return img.crop((x0, y0, x1, y1))


def find_and_centre(img, mode="auto"):
    """Decide the symmetric axes (`mode`: auto / none / lr / tb / both) and
    crop the image so a detected off-centre axis becomes the centre.
    Returns (img, sym_lr, sym_tb)."""
    sym = {}
    if mode == "auto":
        sym = {ax: refine_axis_shift(img, ax, d) for ax, d in detect_symmetry(img).items()}
    if mode in ("lr", "both"):
        sym[1] = 0
    if mode in ("tb", "both"):
        sym[0] = 0
    if sym:
        names = {1: "left/right", 0: "top/bottom"}
        print("symmetry: " + ", ".join(
            f"{names[ax]}" + (f" (axis off centre by {d / 2:g} px)" if d else "")
            for ax, d in sym.items()), flush=True)
        if any(sym.values()):
            img = crop_to_axis(img, sym.get(1, 0), sym.get(0, 0))
            print(f"image cropped to {img.width}x{img.height} to centre the mirror axis",
                  flush=True)
    else:
        print("symmetry: none", flush=True)
    return img, 1 in sym, 0 in sym


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
