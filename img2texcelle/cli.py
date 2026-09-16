"""Command line: python -m img2texcelle design.jpg --width 200 --height 300 --reed 397 --density 500"""

import argparse

from .color import parse_palette
from .options import Options
from .output import FORMATS
from .pipeline import convert
from .workspace import discard_run, finish_run, prepare_run


def build_parser():
    p = argparse.ArgumentParser(
        prog="img2texcelle",
        description="Convert a flat carpet design image into a Texcelle indexed TIFF/BMP "
                    "(one palette entry per yarn, one pixel per knot). The image is moved "
                    "into data/<name>/ and the outputs are written next to it.")
    p.add_argument("src", help="design image (jpg/png), flat colors, carpet aspect ratio")
    p.add_argument("--format", choices=sorted(FORMATS), default="tiff",
                   help="output format: tiff or bmp, both 8-bit indexed and uncompressed "
                        "(default tiff)")
    p.add_argument("--width", type=float, required=True, help="carpet width cm")
    p.add_argument("--height", type=float, required=True, help="carpet height cm")
    p.add_argument("--reed", type=float,
                   help="loom quality: horizontal points per meter (e.g. 397)")
    p.add_argument("--density", type=float,
                   help="loom quality: vertical rows per meter (e.g. 500 = 50 per 10 cm)")
    p.add_argument("--points", type=float,
                   help="points per m^2 for a square quality (instead of --reed/--density)")
    p.add_argument("--grid", default=None,
                   help="exact knot grid WxH (e.g. 793x1501) to match an existing Texcelle "
                        "file; --reed/--density then only fill the file header")
    p.add_argument("--fit", choices=["crop", "stretch"], default=None,
                   help="when the image and carpet aspect ratios differ: crop the image "
                        "center to the carpet ratio, or stretch it (default: error)")
    p.add_argument("--colors", type=int, default=8,
                   help="max number of yarns for the auto palette; near-identical colors "
                        "are merged (default 8)")
    p.add_argument("--palette", default=None,
                   help='fixed yarn colors, e.g. "#F9F6E8,#5D757C,#6A5C4E" (overrides '
                        '--colors; recommended, the loom\'s yarn colors are known)')
    p.add_argument("--merge", type=float, default=6.0,
                   help="merge auto colors closer than this delta E (default 12)")
    p.add_argument("--min-area", type=int, default=None,
                   help="areas smaller than this many knots take the surrounding color "
                        "(0=off; default 20 mm^2: 4 knots at 397x500)")
    p.add_argument("--specks", type=int, default=0,
                   help="for shaded renders: repaint same-hue islands (shadow/highlight "
                        "slivers) smaller than this many knots that are enclosed by one "
                        "color (0 = off; 12 is a good value at 397x500; it also erases "
                        "about 1%% of real same-hue details, so off by default)")
    p.add_argument("--denoise", type=int, default=0,
                   help="median filter size on source image (0=off; breaks 1px lines)")
    p.add_argument("--no-rotate", action="store_true",
                   help="do not rotate image to match carpet orientation")
    p.add_argument("--symmetry", choices=["auto", "none", "lr", "tb", "both"], default="auto",
                   help="mirror symmetry of the design: auto (default) detects it from the "
                        "image; lr / tb / both force it; none disables. Symmetric halves "
                        "are decided together and copied, so opposite motifs are identical")
    p.add_argument("--debug-dir", default=None,
                   help="write regions.png (the label map before cleanup) here")
    return p


def parse_grid(p, text):
    try:
        grid = tuple(int(v) for v in text.lower().split("x"))
        assert len(grid) == 2 and min(grid) > 0
    except (ValueError, AssertionError):
        p.error("--grid must be WxH, e.g. 793x1501")
    return grid


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    grid = parse_grid(p, a.grid) if a.grid else None
    if not grid and not a.points and not (a.reed and a.density):
        p.error("give --reed and --density, --points, or --grid")
    opts = Options(
        width_cm=a.width, height_cm=a.height, reed=a.reed, density=a.density,
        points=a.points, grid=grid, colors=a.colors,
        palette=parse_palette(a.palette) if a.palette else None, merge=a.merge,
        min_area=a.min_area, specks=a.specks, denoise=a.denoise, rotate=not a.no_rotate,
        fit=a.fit, symmetry=a.symmetry, fmt=a.format, debug_dir=a.debug_dir)
    paths = prepare_run(a.src, a.format)
    try:
        convert(str(paths.source), str(paths.image), opts)
    except BaseException:
        discard_run(paths)
        raise
    if finish_run(paths):
        print(f"source moved to {paths.source_target}")
    print(f"run folder: {paths.run_dir}")
