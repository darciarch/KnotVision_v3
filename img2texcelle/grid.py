"""Knot grid geometry and checking the source image against the carpet."""

from PIL import Image

MAX_ASPECT_OFF = 0.10  # --stretch: max distortion; without: max height deviation


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
    """Rotate the image 90 deg when its orientation differs from the carpet's
    (ROTATE_90 turns counter-clockwise: the top edge becomes the left edge)."""
    if img.width != img.height and width_cm != height_cm \
            and (img.width > img.height) != (width_cm > height_cm):
        img = img.transpose(Image.Transpose.ROTATE_90)
        print("image rotated 90 deg to match carpet orientation", flush=True)
    return img


# where a --piece of the image lies after `rotate_to_carpet` (counter-clockwise:
# top -> left -> bottom -> right, top-left -> bottom-left -> bottom-right -> top-right)
ROTATED_PIECE = {"t": "l", "l": "b", "b": "r", "r": "t",
                 "tl": "bl", "bl": "br", "br": "tr", "tr": "tl"}


def rotate_piece(piece):
    """The name of `piece` (t/b/l/r/tl/tr/bl/br, in the unrotated image)
    after `rotate_to_carpet` turned the image 90 deg."""
    return ROTATED_PIECE[piece]


def distortion(img_w, img_h, width_cm, height_cm):
    """Anisotropic stretch when an image of img_w x img_h square pixels is
    mapped onto width_cm x height_cm: the larger of the two scale factors
    over the smaller, minus 1 (0 = the image has the carpet's ratio)."""
    fx, fy = width_cm / img_w, height_cm / img_h
    return max(fx, fy) / min(fx, fy) - 1.0


def fit_carpet(img, width_cm, height_cm, stretch, max_off=MAX_ASPECT_OFF, label=None):
    """The carpet size (width_cm, height_cm) the image is mapped onto.

    With `stretch` it is the requested size: the image is area-averaged onto
    that knot grid (the vote), which distorts it by the difference of the
    two ratios; up to `max_off` is accepted and printed, more is an error.
    Without `stretch` nothing is stretched: the width is kept and the height
    follows the image ratio, so the knot grid grows or shrinks with the
    image (fom's mirrored 3392x5312 gives 200 x 313.2 cm instead of 200 x
    300); a height more than `max_off` off the requested one is an error
    that points to --stretch. `label` names the image in the messages
    instead of its size (--piece: 'piece t 400x300 mirrored to 400x600').
    Returns (width_cm, height_cm, distortion).
    """
    label = label or f"{img.width}x{img.height}"
    img_ratio = img.width / img.height
    carpet_ratio = width_cm / height_cm
    if stretch:
        off = distortion(img.width, img.height, width_cm, height_cm)
        if off > max_off:
            raise SystemExit(
                f"ERROR: fitting the image {label} (ratio {img_ratio:.3f}) into "
                f"{width_cm:g} x {height_cm:g} cm (ratio {carpet_ratio:.3f}) would distort it by "
                f"{100 * off:.1f}%, more than {100 * max_off:.0f}%; give the carpet's real "
                f"size (at {width_cm:g} cm width the image is {width_cm / img_ratio:.1f} cm high) "
                f"or a source with the carpet's ratio")
        print(f"aspect: image {label} (ratio {img_ratio:.3f}) stretched onto "
              f"{width_cm:g} x {height_cm:g} cm (ratio {carpet_ratio:.3f}): {100 * off:.1f}% "
              f"distortion (--stretch)", flush=True)
        return width_cm, height_cm, off
    fitted = width_cm / img_ratio
    off = abs(fitted - height_cm) / height_cm
    if off > max_off:
        raise SystemExit(
            f"ERROR: at {width_cm:g} cm width the image {label} gives a "
            f"{width_cm:g} x {fitted:.1f} cm carpet, {100 * off:.1f}% off the requested "
            f"{height_cm:g} cm height (more than {100 * max_off:.0f}%); use --stretch to fit "
            f"the design into {width_cm:g} x {height_cm:g} cm, or give the image's height "
            f"(--height {fitted:.0f})")
    return width_cm, fitted, 0.0


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
