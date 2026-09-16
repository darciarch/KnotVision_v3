"""Split a design image into 2 or 4 exactly equal parts.

    python -m img2texcelle.split design.jpg --parts 2 --axis lr     # left / right
    python -m img2texcelle.split design.jpg --parts 2 --axis tb     # top / bottom
    python -m img2texcelle.split design.jpg --parts 4 --keep tl     # only the top-left quarter
    python -m img2texcelle.split design.jpg --parts 2 --axis lr --symmetric   # cut on the real mirror axis

Mirror-symmetric designs only need one half or quarter, so this writes the
parts as lossless PNG into data/cropped_images/<stem>/<stem>_<part>.png, one
folder per source image. A later run on the same image adds to that folder
and never overwrites: <stem>_<part>_2.png, _3, ... The source image stays
where it is. When a side has an odd number of pixels the middle
column/row goes into both parts, so the parts always have the same size.

The cut is at the geometric centre. A render whose mirror axis is a few px
off centre gives parts that are not exact mirrors of each other; --symmetric
finds the real axis (symmetry.find_axis_shift) and crops the image so the
axis is the centre before cutting, --shift DX,DY sets that crop by hand.
"""

import argparse
import math
from pathlib import Path

from PIL import Image

from .symmetry import crop_to_axis, find_axis_shift
from .workspace import data_dir

PART_NAMES = {
    (2, "lr"): ["left", "right"],
    (2, "tb"): ["top", "bottom"],
    (4, None): ["tl", "tr", "bl", "br"],
}
OUT_DIR_NAME = "cropped_images"
AXIS_NAMES = {1: "left/right", 0: "top/bottom"}
ASYMMETRIC = 0.35  # find_axis_shift quality above which an axis is not trusted


def part_names(parts, axis):
    """Valid part names for `parts` / `axis`, or ValueError."""
    if parts == 2 and axis not in ("lr", "tb"):
        raise ValueError("2 parts need --axis lr (left/right) or tb (top/bottom)")
    if parts == 4 and axis is not None:
        raise ValueError("4 parts take no --axis")
    if parts not in (2, 4):
        raise ValueError("--parts must be 2 or 4")
    return list(PART_NAMES[(parts, axis)])


def half(n):
    """Size of one half of `n` pixels: n/2, or (n+1)/2 when n is odd (the
    middle pixel then belongs to both halves)."""
    return math.ceil(n / 2)


def split_boxes(width, height, parts, axis=None):
    """PIL crop boxes (left, top, right, bottom) per part name."""
    names = part_names(parts, axis)
    hw, hh = half(width), half(height)
    x_ranges = {"l": (0, hw), "r": (width - hw, width)}
    y_ranges = {"t": (0, hh), "b": (height - hh, height)}
    if parts == 2 and axis == "lr":
        return {"left": (0, 0, hw, height), "right": (width - hw, 0, width, height)}
    if parts == 2:
        return {"top": (0, 0, width, hh), "bottom": (0, height - hh, width, height)}
    boxes = {}
    for name in names:  # "tl", "tr", "bl", "br"
        y0, y1 = y_ranges[name[0]]
        x0, x1 = x_ranges[name[1]]
        boxes[name] = (x0, y0, x1, y1)
    return boxes


def check_keep(keep, names):
    """Validate `keep` (a list of part names) against `names`; None = all."""
    if keep is None:
        return list(names)
    bad = [k for k in keep if k not in names]
    if bad:
        raise ValueError(f"unknown part(s) {', '.join(bad)}; valid: {', '.join(names)}")
    return [n for n in names if n in keep]  # canonical order, no duplicates


def split_image(img, parts, axis=None, keep=None):
    """Return {part name: cropped Image} for the requested parts."""
    boxes = split_boxes(img.width, img.height, parts, axis)
    wanted = check_keep(keep, list(boxes))
    return {name: img.crop(boxes[name]) for name in wanted}


def cut_axes(parts, axis):
    """numpy axes the cut mirrors: 1 = left/right, 0 = top/bottom."""
    if parts == 4:
        return [1, 0]
    return [1] if axis == "lr" else [0]


def centre_on_axis(img, parts, axis=None, symmetric=False, shift=None):
    """Crop `img` so its real mirror axis (per cut axis) is the centre.

    `shift` = (dx, dy) px sets the axis by hand (positive = axis right/down
    of the centre, the `detect_symmetry` convention); otherwise, with
    `symmetric`, it is found with `find_axis_shift`; an axis whose mirror
    error is above ASYMMETRIC is not trusted and stays at the centre (a
    warning is printed). Axes the cut does not mirror are left alone.
    Returns (img, {axis: shift}).
    """
    if not symmetric and shift is None:
        return img, {}
    found = {}
    for ax in cut_axes(parts, axis):
        if shift is not None:
            d = int(shift[0] if ax == 1 else shift[1])
        else:
            d, quality = find_axis_shift(img, ax)
            if quality > ASYMMETRIC:
                print(f"warning: the image does not look mirror-symmetric {AXIS_NAMES[ax]} "
                      f"(error ratio {quality:.2f}); cutting at the centre", flush=True)
                d = 0
        found[ax] = d
        print(f"symmetry: {AXIS_NAMES[ax]} axis "
              + (f"off centre by {d / 2:g} px" if d else "at the centre"), flush=True)
    if any(found.values()):
        img = crop_to_axis(img, found.get(1, 0), found.get(0, 0))
        print(f"image cropped to {img.width}x{img.height} to centre the mirror axis",
              flush=True)
    return img, found


def output_dir(stem, root=None):
    """data/cropped_images/<stem>/ (created on first use, reused afterwards)."""
    return (Path(root) if root else data_dir()) / OUT_DIR_NAME / stem


def free_path(out_dir, stem, name):
    """<stem>_<name>.png, or the first free <stem>_<name>_2.png, _3, ..."""
    i = 1
    while True:
        suffix = "" if i == 1 else f"_{i}"
        path = out_dir / f"{stem}_{name}{suffix}.png"
        if not path.exists():
            return path
        i += 1


def split_file(src, parts, axis=None, keep=None, root=None, symmetric=False, shift=None):
    """Split image file `src` and write the parts as PNG. Returns the paths.
    `symmetric` / `shift`: see `centre_on_axis`."""
    src = Path(src).resolve()
    if not src.is_file():
        raise SystemExit(f"ERROR: source image not found: {src}")
    img = Image.open(src)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "PA") else "RGB")
    img, _ = centre_on_axis(img, parts, axis, symmetric, shift)
    odd = [ax for ax, n in (("width", img.width), ("height", img.height)) if n % 2]
    if odd:
        print(f"warning: odd {' and '.join(odd)} ({img.width}x{img.height}); the middle "
              "pixel row/column is included in both parts", flush=True)
    pieces = split_image(img, parts, axis, keep)
    out_dir = output_dir(src.stem, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, piece in pieces.items():
        path = free_path(out_dir, src.stem, name)
        piece.save(path, format="PNG")
        written.append(path)
    return written


def build_parser():
    p = argparse.ArgumentParser(
        prog="img2texcelle.split",
        description="Split a design image into 2 or 4 exactly equal parts, written as "
                    "PNG into data/cropped_images/<name>/<name>_<part>.png (one folder per "
                    "image, later runs add to it, nothing is overwritten). The source "
                    "is not moved. An odd side puts its middle pixel into both parts.")
    p.add_argument("src", help="design image (jpg/png)")
    p.add_argument("--parts", type=int, choices=[2, 4], required=True,
                   help="2 halves or 4 quarters")
    p.add_argument("--axis", choices=["lr", "tb"], default=None,
                   help="for --parts 2: lr = left/right halves (vertical cut), "
                        "tb = top/bottom halves (horizontal cut)")
    p.add_argument("--keep", default=None,
                   help="comma-separated parts to save (default all): left,right / "
                        "top,bottom for 2 parts; tl,tr,bl,br for 4 parts (e.g. --keep tl)")
    p.add_argument("--symmetric", action="store_true",
                   help="find the real mirror axis of the design and crop the image so it "
                        "is the centre before cutting, so the parts are exact mirrors "
                        "of each other (a few px are dropped on one side)")
    p.add_argument("--shift", default=None, metavar="DX,DY",
                   help="set the mirror-axis offset by hand instead of --symmetric: the "
                        "axis is DX/2 px right and DY/2 px down of the centre (negative = "
                        "left/up), e.g. --shift 6,0 for an axis 3 px right of centre")
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    keep = [k.strip() for k in a.keep.split(",") if k.strip()] if a.keep else None
    shift = None
    try:
        names = part_names(a.parts, a.axis)
        check_keep(keep, names)
        if a.shift is not None:
            shift = tuple(int(v) for v in a.shift.split(","))
            if len(shift) != 2:
                raise ValueError("--shift takes two integers: DX,DY")
    except ValueError as e:
        p.error(str(e))
    written = split_file(a.src, a.parts, a.axis, keep, symmetric=a.symmetric, shift=shift)
    for path in written:
        img = Image.open(path)
        print(f"{path}  ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
