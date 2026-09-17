"""Split a design image into 2 or 4 parts on its mirror axes.

    python -m img2texcelle.split design.jpg --parts 2 --axis lr     # left / right
    python -m img2texcelle.split design.jpg --parts 2 --axis tb     # top / bottom
    python -m img2texcelle.split design.jpg --parts 4 --keep tl     # only the top-left quarter
    python -m img2texcelle.split design.jpg --parts 2 --axis lr --symmetric   # cut on the real mirror axis

Mirror-symmetric designs only need one half or quarter, so this writes the
parts as lossless PNG into data/cropped_images/<stem>/<stem>_<part>.png, one
folder per source image. A later run on the same image adds to that folder
and never overwrites: <stem>_<part>_2.png, _3, ... The source image stays
where it is.

The cut is at the geometric centre; when a side has an odd number of pixels
the middle column/row goes into both parts, so the parts have the same size.
A design whose mirror axis is off centre (a medallion drawn above the middle)
needs --symmetric: the real axis of every cut axis is found with
`symmetry.measure_axis` and the cut is made there, so each part runs from
the axis to its own edge (a part is complete, nothing is cropped, but the
two parts then differ in size). A pixel row/column on the axis goes into
both parts. --shift DX,DY sets the axis by hand.
"""

import argparse
from pathlib import Path

from PIL import Image

from .symmetry import AXIS_CONTRAST, AXIS_NAMES, describe_axis, measure_axis
from .workspace import data_dir

PART_NAMES = {
    (2, "lr"): ["left", "right"],
    (2, "tb"): ["top", "bottom"],
    (4, None): ["tl", "tr", "bl", "br"],
}
OUT_DIR_NAME = "cropped_images"


def part_names(parts, axis):
    """Valid part names for `parts` / `axis`, or ValueError."""
    if parts == 2 and axis not in ("lr", "tb"):
        raise ValueError("2 parts need --axis lr (left/right) or tb (top/bottom)")
    if parts == 4 and axis is not None:
        raise ValueError("4 parts take no --axis")
    if parts not in (2, 4):
        raise ValueError("--parts must be 2 or 4")
    return list(PART_NAMES[(parts, axis)])


def cut_ranges(size, shift=0):
    """Index ranges (first, second) of the two parts along one side of `size`
    px, cut at the mirror axis (size - 1 + shift) / 2 (`measure_axis`
    convention; shift 0 = the geometric centre). When the axis lies on a
    pixel (size - 1 + shift even) that pixel belongs to both parts."""
    twice = size - 1 + shift  # 2 x axis position
    if twice % 2 == 0:
        mid = twice // 2
        return (0, mid + 1), (mid, size)
    cut = (twice + 1) // 2
    return (0, cut), (cut, size)


def shared_pixel(size, shift=0):
    """True when the axis lies on a pixel that goes into both parts."""
    return (size - 1 + shift) % 2 == 0


def split_boxes(width, height, parts, axis=None, shifts=None):
    """PIL crop boxes (left, top, right, bottom) per part name. `shifts` =
    {1: dx, 0: dy} moves the cut off the centre (see `cut_ranges`)."""
    names = part_names(parts, axis)
    shifts = shifts or {}
    (xl, xr) = cut_ranges(width, shifts.get(1, 0))
    (yt, yb) = cut_ranges(height, shifts.get(0, 0))
    x_ranges, y_ranges = {"l": xl, "r": xr}, {"t": yt, "b": yb}
    if parts == 2 and axis == "lr":
        return {"left": (xl[0], 0, xl[1], height), "right": (xr[0], 0, xr[1], height)}
    if parts == 2:
        return {"top": (0, yt[0], width, yt[1]), "bottom": (0, yb[0], width, yb[1])}
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


def split_image(img, parts, axis=None, keep=None, shifts=None):
    """Return {part name: cropped Image} for the requested parts."""
    boxes = split_boxes(img.width, img.height, parts, axis, shifts)
    wanted = check_keep(keep, list(boxes))
    return {name: img.crop(boxes[name]) for name in wanted}


def cut_axes(parts, axis):
    """numpy axes the cut mirrors: 1 = left/right, 0 = top/bottom."""
    if parts == 4:
        return [1, 0]
    return [1] if axis == "lr" else [0]


def find_cuts(img, parts, axis=None, symmetric=False, shift=None):
    """Where to cut: {numpy axis: shift} for the cut axes (`measure_axis`
    convention, positive = axis right/down of the centre).

    `shift` = (dx, dy) px sets the axes by hand; otherwise, with `symmetric`,
    each cut axis is measured with `measure_axis`; an axis whose contrast is
    above AXIS_CONTRAST is not trusted and stays at the centre (a warning
    names the best candidate and the --shift that forces it). Without either
    flag the cut is at the centre ({}).
    """
    if not symmetric and shift is None:
        return {}
    found = {}
    for ax in cut_axes(parts, axis):
        size = img.size[0] if ax == 1 else img.size[1]
        if shift is not None:
            d = int(shift[0] if ax == 1 else shift[1])
            print(f"symmetry: {AXIS_NAMES[ax]} axis {describe_axis(ax, size, d)} (--shift)",
                  flush=True)
        else:
            d, contrast, _ = measure_axis(img, ax)
            where = describe_axis(ax, size, d)
            if contrast > AXIS_CONTRAST:
                force = f"--shift {d},0" if ax == 1 else f"--shift 0,{d}"
                print(f"warning: no clear {AXIS_NAMES[ax]} mirror axis (contrast {contrast:.2f} "
                      f"> {AXIS_CONTRAST}); best candidate {where}; cutting at the centre, "
                      f"use {force} to force that axis", flush=True)
                d = 0
            else:
                print(f"symmetry: {AXIS_NAMES[ax]} axis {where}, contrast {contrast:.2f}",
                      flush=True)
        found[ax] = d
    return found


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
    `symmetric` / `shift`: see `find_cuts`."""
    src = Path(src).resolve()
    if not src.is_file():
        raise SystemExit(f"ERROR: source image not found: {src}")
    img = Image.open(src)
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "PA") else "RGB")
    shifts = find_cuts(img, parts, axis, symmetric, shift)
    shared = [("column" if ax == 1 else "row") for ax in cut_axes(parts, axis)
              if shared_pixel(img.size[0] if ax == 1 else img.size[1], shifts.get(ax, 0))]
    if shared:
        print(f"warning: the axis lies on a pixel {' and '.join(shared)} "
              f"({img.width}x{img.height}); it is included in both parts", flush=True)
    pieces = split_image(img, parts, axis, keep, shifts)
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
        description="Split a design image into 2 halves or 4 quarters, written as PNG "
                    "into data/cropped_images/<name>/<name>_<part>.png (one folder per "
                    "image, later runs add to it, nothing is overwritten). The source "
                    "is not moved. The cut is at the centre unless --symmetric / --shift "
                    "put it on the real mirror axis; a pixel row/column on the axis goes "
                    "into both parts.")
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
                   help="find the real mirror axis of the design (also well off centre, "
                        "e.g. a medallion drawn above the middle) and cut there: each "
                        "part runs from the axis to its own edge, so the parts differ "
                        "in size when the axis is off centre, and nothing is cropped")
    p.add_argument("--shift", default=None, metavar="DX,DY",
                   help="set the mirror axis by hand instead of --symmetric: the axis is "
                        "DX/2 px right and DY/2 px down of the centre (negative = left/up), "
                        "e.g. --shift 0,-256 for an axis 128 px above the centre")
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
