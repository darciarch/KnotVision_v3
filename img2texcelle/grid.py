"""Knot grid geometry and fitting the source image to the carpet."""

import math
import sys

from PIL import Image


def compute_pixels(width_cm, height_cm, points=None, reed=None, density=None, grid=None):
    """Return (px_w, px_h, ppm_x, ppm_y): the knot grid and the points per
    meter written into the file header (Texcelle stores reed/density there)."""
    if reed and density:
        ppm_x, ppm_y = reed, density
    elif points:
        # square assumption: same points per meter in both directions
        ppm_x = ppm_y = math.sqrt(points)
    elif grid:
        ppm_x, ppm_y = grid[0] * 100.0 / width_cm, grid[1] * 100.0 / height_cm
    else:
        raise ValueError("give --points, --reed and --density, or --grid")
    if grid:
        px_w, px_h = grid
    else:
        px_w = round(width_cm / 100.0 * ppm_x)
        px_h = round(height_cm / 100.0 * ppm_y)
    return px_w, px_h, ppm_x, ppm_y


def knot_size_mm(width_cm, height_cm, px_w, px_h):
    """Size of one knot in mm (knots are not square on a real loom)."""
    return width_cm * 10.0 / px_w, height_cm * 10.0 / px_h


def default_min_area(knot_w_mm, knot_h_mm, mm2=20.0):
    """Islands below this many knots are repainted: `mm2` worth of knots
    (20 knots at 1 M points/m^2, 4 knots at 397 x 500), at least 2."""
    return max(2, round(mm2 / (knot_w_mm * knot_h_mm)))


def rotate_to_carpet(img, width_cm, height_cm):
    """Rotate the image 90 deg when its orientation differs from the carpet's."""
    if img.width != img.height and width_cm != height_cm \
            and (img.width > img.height) != (width_cm > height_cm):
        img = img.transpose(Image.Transpose.ROTATE_90)
        print("image rotated 90 deg to match carpet orientation", flush=True)
    return img


def fit_to_carpet(img, width_cm, height_cm, px_w, px_h, fit=None, tol=0.02):
    """Check the image aspect ratio against the carpet.

    The image must have the carpet's ratio either with square pixels (a
    rendering: 2:3 for 200 x 300 cm) or with one pixel per knot in both
    directions (a Texcelle-like grid: 793:1501, knots are not square).
    Otherwise `fit` must be "crop" (centre crop) or "stretch" (circles become
    ellipses); with `fit` None it is an error.
    """
    img_ratio = img.width / img.height
    carpet_ratio = width_cm / height_cm
    grid_ratio = px_w / px_h
    off = min(abs(img_ratio - carpet_ratio) / carpet_ratio,
              abs(img_ratio - grid_ratio) / grid_ratio)
    if off <= tol:
        return img
    if img_ratio > carpet_ratio:
        crop_w, crop_h = round(img.height * carpet_ratio), img.height
    else:
        crop_w, crop_h = img.width, round(img.width / carpet_ratio)
    if fit is None:
        raise SystemExit(
            f"ERROR: image ratio {img_ratio:.3f} ({img.width}x{img.height}) matches "
            f"neither the carpet ratio {carpet_ratio:.3f} ({width_cm:g}x{height_cm:g} cm) "
            f"nor the knot grid ratio {grid_ratio:.3f} ({px_w}x{px_h}). Use --fit crop "
            f"(center crop to {crop_w}x{crop_h}), --fit stretch, or make the source "
            f"{2 * px_w}x{2 * px_h} (2 px per knot).")
    if fit == "crop":
        x0, y0 = (img.width - crop_w) // 2, (img.height - crop_h) // 2
        img = img.crop((x0, y0, x0 + crop_w, y0 + crop_h))
        print(f"image center-cropped to {crop_w}x{crop_h} to match carpet ratio", flush=True)
    else:
        print(f"WARNING: image ratio {img_ratio:.3f} != carpet ratio {carpet_ratio:.3f}, "
              f"image will be stretched", file=sys.stderr)
    return img


def source_scale(img, px_w, px_h):
    """Source px per knot: (sx, sy, geometric mean). The source must be finer
    than the knot grid (> 1 px per knot): every knot then takes the color
    covering most of it. A coarser source cannot be converted (its 1 px lines
    would break into beads on the knot grid)."""
    sx, sy = img.width / px_w, img.height / px_h
    scale = math.sqrt(sx * sy)
    if scale <= 1.0:
        raise SystemExit(
            f"ERROR: source is coarser than the knot grid ({sx:.2f} x {sy:.2f} source px per "
            f"knot, grid {px_w}x{px_h}). The source needs more than 1 px per knot, ideally "
            f"2 px per knot ({2 * px_w}x{2 * px_h}); render the design larger.")
    return sx, sy, scale
