"""The conversion pipeline: design image -> one yarn per knot.

The source is a flat-colored image with square pixels, the carpet's aspect
ratio (within 10%) and more pixels than knots in both directions, so every
knot takes the yarn covering most of its area:

  1. rotate to the carpet orientation, find the mirror axes (also off
     centre) and crop so they are the centre, check the aspect ratio (up to
     10% off: resized onto the knot grid, the distortion is printed) and
     that the source is finer than the knot grid
  2. yarn palette: --palette, or k-means in Lab on flat pixels
  3. unmix every source pixel into coverage fractions of at most two yarns
     (a blurred edge is "60% brown / 40% cream", not a wrong in-between color);
     only colors found nearby may mix; thin strips of an in-between color are
     unmixed into their neighbours
  4. area-average the fractions onto the knots (halves that match everywhere
     are averaged with their mirror), argmax; straight half-covered runs are
     decided as a whole
  5. cleanup: islands below --min-area, exact mirror copy of the left/top
     half onto the other
  6. save indexed TIFF/BMP (index 0 unused, reed/density in the header) and
     the palette text file
"""

import math
import os

import numpy as np
from PIL import Image

from .cleanup import remove_islands
from .color import auto_palette, flat_mask, hex_color, rgb_to_lab, smooth_chroma
from .grid import (check_aspect, compute_pixels, default_min_area, knot_size_mm,
                   rotate_to_carpet, source_scale)
from .options import Options
from .output import palette_txt_path, save_debug_png, save_indexed, write_palette_txt
from .symmetry import find_and_centre, mirror_copy
from .unmix import unmix, unmix_thin_blends
from .vote import vote_knots


def convert(src, dst, opts: Options):
    """Convert image `src` to the Texcelle file `dst` (plus <dst>_palette.txt).
    Returns (labels, palette): the knot map (H, W) with 0-based yarn indices
    and the uint8 (K, 3) yarn colors."""
    px_w, px_h, ppm_x, ppm_y = compute_pixels(opts.width_cm, opts.height_cm,
                                              opts.reed, opts.density)
    knot_w_mm, knot_h_mm = knot_size_mm(opts.width_cm, opts.height_cm, px_w, px_h)
    min_area = opts.min_area
    if min_area is None:
        min_area = default_min_area(knot_w_mm, knot_h_mm)

    # 1. geometry: orientation, mirror symmetry, aspect ratio, source scale
    img = Image.open(src).convert("RGB")
    img = rotate_to_carpet(img, opts.width_cm, opts.height_cm)
    img, copy_lr, copy_tb, avg_lr, avg_tb = find_and_centre(img, opts.symmetry)
    img = check_aspect(img, opts.width_cm, opts.height_cm)
    sx, sy, scale = source_scale(img, px_w, px_h)
    print(f"knot grid {px_w} x {px_h} ({ppm_x:.0f} x {ppm_y:.0f} points/m, knot "
          f"{knot_w_mm:.2f} x {knot_h_mm:.2f} mm, {ppm_x * ppm_y:.0f} points/m^2), "
          f"{sx:.2f} x {sy:.2f} source px per knot, min area {min_area} knots", flush=True)

    rgb = np.asarray(img)
    lab = rgb_to_lab(rgb)

    # 2. yarn palette (each color = one yarn)
    palette = opts.palette
    if palette is None:
        palette = auto_palette(rgb, lab, flat_mask(lab), opts.colors, opts.merge)
    n = len(palette)
    pal_lab = rgb_to_lab(palette)

    # 3. coverage fractions per yarn at source resolution; only neighbours (a
    #    blurred edge, JPEG chroma bleed) can mix into a pixel
    lab_s = smooth_chroma(lab)
    del lab
    alpha = unmix(lab_s, pal_lab, reach=math.ceil(scale))
    blends = unmix_thin_blends(alpha, lab_s, palette, pal_lab)
    print(f"edge blend pixels unmixed: {blends}", flush=True)
    del lab_s

    # 4. one yarn per knot
    labels = vote_knots(alpha, (px_w, px_h), avg_lr, avg_tb)
    del alpha
    if opts.debug_dir:
        os.makedirs(opts.debug_dir, exist_ok=True)
        save_debug_png(labels, palette, os.path.join(opts.debug_dir, "regions.png"))

    # 5. cleanup: small areas take the dominant surrounding color; exact
    #    symmetry (tie-breaks could differ per half)
    if min_area > 1:
        fixed = remove_islands(labels, n, min_area)
        print(f"islands cleaned: {fixed} knots repainted (min area {min_area})")
    if copy_lr or copy_tb:
        mirror_copy(labels, copy_lr, copy_tb)

    # 6. files
    save_indexed(labels, palette, dst, opts.fmt, (ppm_x, ppm_y))
    txt = palette_txt_path(dst)
    write_palette_txt(palette, txt)

    counts = np.bincount(labels.ravel(), minlength=n)
    print(f"{dst}: {px_w} x {px_h} px, {n} colors (indices 1-{n}, 0 unused)")
    for i, c in enumerate(palette.tolist()):
        print(f"  {i + 1}  {hex_color(c)}  {100.0 * counts[i] / labels.size:5.1f}%")
    print(f"palette: {txt}")
    return labels, palette
