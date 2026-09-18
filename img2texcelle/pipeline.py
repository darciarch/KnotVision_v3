"""The conversion pipeline: design image -> one yarn per knot.

The source is a flat-colored image with square pixels, the carpet's aspect
ratio (within 10%) and more pixels than knots in both directions, so every
knot takes the yarn covering most of its area:

  1. rotate to the carpet orientation, find the mirror axes (also off
     centre) and mirror one half onto the other so they are the centre
     (--piece: the image is a half or quarter, mirrored into the full
     image first, its axes at the centre, nothing measured), fit the
     carpet size (--stretch: the given size, up to 10% distortion;
     otherwise the height follows the image), check that the source is
     finer than the knot grid, and choose the part to convert: the kept
     half of every copy-only axis plus a pad of reflected pixels beyond the
     axis, the whole extent of an averaged axis
  2. yarn palette: --palette, or k-means in Lab on flat pixels of the part
  3. unmix every source pixel of the part into coverage fractions of at
     most two yarns (a blurred edge is "60% brown / 40% cream", not a wrong
     in-between color); only colors found nearby may mix; thin strips of an
     in-between color are unmixed into their neighbours
  4. area-average the fractions onto the knots (halves that match everywhere
     are averaged with their mirror), argmax; straight half-covered runs are
     decided as a whole
  5. cleanup: islands below --min-area; the pad is dropped
  6. --part: save the kept part (<name>_part.png + .json) for editing and
     `img2texcelle.assemble`; otherwise mirror the part onto the full grid
     and save the indexed TIFF/BMP (index 0 unused, reed/density in the
     header) and the palette text file
"""

import math
import os

import numpy as np
from PIL import Image

from .cleanup import remove_islands
from .color import auto_palette, flat_mask, hex_color, rgb_to_lab, smooth_chroma
from .grid import (compute_pixels, default_min_area, fit_carpet, knot_size_mm,
                   rotate_piece, rotate_to_carpet, source_scale)
from .options import Options
from .output import palette_txt_path, save_debug_png, save_indexed, save_part, write_palette_txt
from .symmetry import (AXIS_NAMES, FLAGS, PAD_KNOTS, centre_axes, describe_axis, find_axes,
                       mirror_copy, mirror_halves, mirror_piece, part_region)
from .unmix import unmix, unmix_thin_blends
from .vote import vote_knots


def source_crop(region, sx, sy, img_w, img_h):
    """The source pixels (X0, Y0, X1, Y1) holding the knots of the rectangle
    `region` = (x0, y0, x1, y1): the knot boundaries fall on fractional
    pixels, so the crop is rounded outwards. `vote.resize_alpha` is then
    told the crop's origin and the whole grid's scale, and gives every knot
    exactly the value it has in the whole image."""
    X0, Y0 = math.floor(region[0] * sx), math.floor(region[1] * sy)
    X1, Y1 = min(math.ceil(region[2] * sx), img_w), min(math.ceil(region[3] * sy), img_h)
    return X0, Y0, X1, Y1


def assemble_full(part_labels, part, grid, sides):
    """Place the kept part on the full knot grid and mirror it across every
    taken axis (`sides` = {axis: 'left' / 'right' / 'top' / 'bottom'})."""
    px_w, px_h = grid
    full = np.zeros((px_h, px_w), dtype=np.uint8)
    x0, y0, x1, y1 = part
    full[y0:y1, x0:x1] = part_labels
    mirror_copy(full, sides.get(1), sides.get(0))
    return full


def convert(src, dst, opts: Options):
    """Convert image `src` to the Texcelle file `dst` (plus <dst>_palette.txt),
    or with opts.part to the part PNG `dst` (plus its JSON). Returns
    (labels, palette): the knot map (H, W) with 0-based yarn indices (the
    part only with opts.part) and the uint8 (K, 3) yarn colors."""
    # 1. geometry: orientation, mirror symmetry, carpet size, source scale, part
    piece = opts.piece
    if piece and opts.symmetry != "auto":
        raise ValueError(f"piece {piece!r} fixes the mirror axes; symmetry must stay 'auto'")
    img = Image.open(src).convert("RGB")
    if piece:
        piece_size = img.size
        img = mirror_piece(img, piece)  # the rotation is decided on the full image
    size0 = img.size
    img = rotate_to_carpet(img, opts.width_cm, opts.height_cm)
    rotated = img.size != size0
    measured = img.size  # the axes are described in this image
    stretch_to = (opts.width_cm, opts.height_cm) if opts.stretch else None
    label = None
    if piece:
        given, piece = piece, rotate_piece(piece) if rotated else piece
        axes, sides = centre_axes(img.size, piece)
        label = f"piece {piece} {piece_size[0]}x{piece_size[1]} mirrored to {size0[0]}x{size0[1]}"
        which = "both axes" if len(axes) == 2 else f"{AXIS_NAMES[next(iter(axes))]} axis"
        print(f"piece {piece}: image {piece_size[0]}x{piece_size[1]} mirrored to {size0[0]}x"
              f"{size0[1]}, {which} at the centre, copy only"
              + (f" (rotated 90 deg to {img.width}x{img.height}, piece {given} -> {piece})"
                 if rotated else ""), flush=True)
        if rotated:
            label += f", rotated to {img.width}x{img.height}"
        img, sides = mirror_halves(img, axes, stretch_to, sides)
    else:
        axes = find_axes(img, opts.symmetry, opts.average)
        img, sides = mirror_halves(img, axes, stretch_to)
    width_cm, height_cm, off = fit_carpet(img, opts.width_cm, opts.height_cm, opts.stretch, label=label)
    px_w, px_h, ppm_x, ppm_y = compute_pixels(width_cm, height_cm, opts.reed, opts.density)
    if abs(height_cm - opts.height_cm) >= 0.05:
        taller = "taller" if height_cm > opts.height_cm else "shorter"
        print(f"\n*** CARPET {width_cm:g} x {height_cm:.1f} cm, KNOT GRID {px_w} x {px_h} ***\n"
              f"    (requested {opts.width_cm:g} x {opts.height_cm:g} cm: the height follows the "
              f"image {label or f'{img.width}x{img.height}'}, "
              f"{100 * abs(height_cm - opts.height_cm) / opts.height_cm:.1f}% "
              f"{taller}, nothing stretched; --stretch fits {opts.height_cm:g} cm)\n", flush=True)
    knot_w_mm, knot_h_mm = knot_size_mm(width_cm, height_cm, px_w, px_h)
    min_area = opts.min_area
    if min_area is None:
        min_area = default_min_area(knot_w_mm, knot_h_mm)
    sx, sy, scale = source_scale(img, px_w, px_h)
    print(f"knot grid {px_w} x {px_h} ({width_cm:g} x {height_cm:.1f} cm, {ppm_x:.0f} x {ppm_y:.0f} "
          f"points/m, knot {knot_w_mm:.2f} x {knot_h_mm:.2f} mm, {ppm_x * ppm_y:.0f} points/m^2), "
          f"{sx:.2f} x {sy:.2f} source px per knot, min area {min_area} knots", flush=True)

    pad = PAD_KNOTS if opts.pad is None else opts.pad
    region, part = part_region(px_w, px_h, axes, sides, pad)
    rw, rh = region[2] - region[0], region[3] - region[1]
    pw, ph = part[2] - part[0], part[3] - part[1]
    if axes:
        print(f"part: knots [{part[0]}, {part[2]}) x [{part[1]}, {part[3]}) of {px_w} x {px_h} "
              f"({pw} x {ph}); converting {rw} x {rh} knots = {100 * rw * rh / (px_w * px_h):.0f}% "
              f"of the grid (the part, {pad} knots pad beyond a copy-only axis, both halves of an "
              f"averaged axis)", flush=True)
    crop = source_crop(region, sx, sy, img.width, img.height)
    geometry = ((sx, sy), (region[0], region[1]), (crop[0], crop[1]), img.size)
    rgb = np.asarray(img)[crop[1]:crop[3], crop[0]:crop[2]]
    del img
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

    # 4. one yarn per knot (the region holds both halves of an averaged axis;
    #    straight runs are decided by the part's knots, not the pad's)
    inside = (slice(part[1] - region[1], part[3] - region[1]),
              slice(part[0] - region[0], part[2] - region[0]))
    count = None
    if (rw, rh) != (pw, ph):
        count = np.zeros((rh, rw), dtype=bool)
        count[inside] = True
    labels = vote_knots(alpha, (rw, rh), axes.get(1, (0, False))[1], axes.get(0, (0, False))[1],
                        geometry, count)
    del alpha
    if opts.debug_dir:
        os.makedirs(opts.debug_dir, exist_ok=True)
        save_debug_png(labels[inside], palette, os.path.join(opts.debug_dir, "regions.png"))

    # 5. cleanup: small areas take the dominant surrounding color; the pad
    #    (knots the mirror will overwrite) is dropped
    if min_area > 1:
        fixed = remove_islands(labels, n, min_area)
        print(f"islands cleaned: {fixed} knots repainted (min area {min_area})")
    labels = np.ascontiguousarray(labels[inside])

    # 6. files: the part for editing, or the mirrored knot map
    txt = palette_txt_path(dst)
    write_palette_txt(palette, txt)
    if opts.part:
        info = {
            "source": os.path.basename(src),
            "rotated": rotated,
            "carpet_cm": [width_cm, round(height_cm, 2)],
            "stretch": opts.stretch,
            "distortion": round(off, 4),
            "reed": opts.reed, "density": opts.density, "ppm": [ppm_x, ppm_y],
            "grid": [px_w, px_h],
            "part": {"x": part[0], "y": part[1], "width": pw, "height": ph},
            "pad": pad,
            "min_area": min_area,
            "axes": {FLAGS[ax]: {"kept": sides[ax], "averaged": avg, "shift": shift,
                                 "position": describe_axis(ax, measured[0] if ax == 1 else measured[1], shift)}
                     for ax, (shift, avg) in axes.items()},
            "palette": [hex_color(c) for c in palette.tolist()],
        }
        if piece:
            info["piece"] = piece  # for the record (after the rotation); assemble does not use it
        save_part(labels, palette, dst, info)
        print(f"{dst}: part {pw} x {ph} px at ({part[0]}, {part[1]}) of {px_w} x {px_h}, {n} colors "
              f"(indices 1-{n}, 0 unused); finish with: python -m img2texcelle.assemble {dst}")
        print(f"palette: {txt}")
        return labels, palette

    if axes:
        labels = assemble_full(labels, part, (px_w, px_h), sides)
    save_indexed(labels, palette, dst, opts.fmt, (ppm_x, ppm_y))

    counts = np.bincount(labels.ravel(), minlength=n)
    print(f"{dst}: {px_w} x {px_h} px, {n} colors (indices 1-{n}, 0 unused)")
    for i, c in enumerate(palette.tolist()):
        print(f"  {i + 1}  {hex_color(c)}  {100.0 * counts[i] / labels.size:5.1f}%")
    print(f"palette: {txt}")
    return labels, palette
