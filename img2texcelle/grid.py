"""Knot grid geometry and checking the source image against the carpet."""

from PIL import Image

MAX_ASPECT_OFF = 0.10  # image ratio may differ from the carpet ratio by this much


def compute_pixels(width_cm, height_cm, reed, density):
    """Return (px_w, px_h, ppm_x, ppm_y): the knot grid and the points per
    meter written into the file header (Texcelle stores reed/density there)."""
    if not (reed and density):
        raise ValueError("give reed and density")
    ppm_x, ppm_y = reed, density
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


def check_aspect(img, width_cm, height_cm, max_off=MAX_ASPECT_OFF):
    """Check the image aspect ratio against the carpet's ratio in cm.

    The image has square pixels, so its ratio should be the carpet's. A
    difference up to `max_off` is accepted: the image is later resized onto
    the knot grid (the area average in the vote), which distorts it by that
    much, and the distortion is printed. A larger difference is an error.
    Returns the image unchanged.
    """
    img_ratio = img.width / img.height
    carpet_ratio = width_cm / height_cm
    off = abs(img_ratio - carpet_ratio) / carpet_ratio
    if off > max_off:
        raise SystemExit(
            f"ERROR: image ratio {img_ratio:.3f} ({img.width}x{img.height}) is "
            f"{100 * off:.1f}% off the carpet ratio {carpet_ratio:.3f} "
            f"({width_cm:g} x {height_cm:g} cm); the image must have the carpet's aspect "
            f"ratio within {100 * max_off:.0f}%")
    print(f"aspect: image ratio {img_ratio:.3f} ({img.width}x{img.height}) vs carpet "
          f"{carpet_ratio:.3f}, resized to the knot grid with {100 * off:.1f}% distortion",
          flush=True)
    return img


def source_scale(img, px_w, px_h):
    """Source px per knot: (sx, sy, geometric mean). The source must have
    more pixels than knots in both directions: every knot then takes the
    color covering most of it. A coarser source cannot be converted (its 1 px
    lines would break into beads on the knot grid)."""
    sx, sy = img.width / px_w, img.height / px_h
    if sx <= 1.0 or sy <= 1.0:
        raise SystemExit(
            f"ERROR: source {img.width}x{img.height} is coarser than the knot grid "
            f"{px_w}x{px_h} ({sx:.2f} x {sy:.2f} source px per knot); the image needs more "
            f"pixels than knots in both directions")
    return sx, sy, (sx * sy) ** 0.5
