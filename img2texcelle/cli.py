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
    p.add_argument("src", help="design image (jpg/png): square pixels, flat colors, aspect "
                               "ratio near the carpet's (see --stretch), more pixels than "
                               "knots in both directions")
    p.add_argument("--format", choices=sorted(FORMATS), default="tiff",
                   help="output format: tiff or bmp, both 8-bit indexed and uncompressed "
                        "(default tiff)")
    p.add_argument("--width", type=float, required=True, help="carpet width cm")
    p.add_argument("--height", type=float, required=True, help="carpet height cm")
    p.add_argument("--stretch", action="store_true",
                   help="fit the design into the given cm size by stretching it (up to 10%%). "
                        "Without it nothing is stretched: --width is kept and the height "
                        "follows the image ratio (the knot grid grows with it; more than "
                        "10%% off --height is an error)")
    p.add_argument("--reed", type=float, required=True,
                   help="loom quality: horizontal points per meter (e.g. 397)")
    p.add_argument("--density", type=float, required=True,
                   help="loom quality: vertical rows per meter (e.g. 500 = 50 per 10 cm)")
    p.add_argument("--colors", type=int, default=8,
                   help="max number of yarns for the auto palette; near-identical colors "
                        "are merged (default 8)")
    p.add_argument("--palette", default=None,
                   help='fixed yarn colors, e.g. "#F9F6E8,#5D757C,#6A5C4E" (overrides '
                        '--colors; recommended, the loom\'s yarn colors are known)')
    p.add_argument("--merge", type=float, default=6.0,
                   help="merge auto colors closer than this delta E (default 6)")
    p.add_argument("--min-area", type=int, default=None,
                   help="areas smaller than this many knots take the surrounding color "
                        "(0=off; default 20 mm^2: 4 knots at 397x500)")
    p.add_argument("--symmetry", choices=["auto", "none", "lr", "tb", "both"], default="auto",
                   help="mirror symmetry of the design: auto (default) detects it from the "
                        "image; lr / tb / both force it; none disables. Symmetric halves "
                        "are decided together and copied, so opposite motifs are identical")
    p.add_argument("--debug-dir", default=None,
                   help="write regions.png (the label map before cleanup) here")
    return p


def main(argv=None):
    p = build_parser()
    a = p.parse_args(argv)
    opts = Options(
        width_cm=a.width, height_cm=a.height, reed=a.reed, density=a.density,
        colors=a.colors, palette=parse_palette(a.palette) if a.palette else None,
        merge=a.merge, min_area=a.min_area, symmetry=a.symmetry, stretch=a.stretch,
        fmt=a.format,
        debug_dir=a.debug_dir)
    paths = prepare_run(a.src, a.format)
    try:
        convert(str(paths.source), str(paths.image), opts)
    except BaseException:
        discard_run(paths)
        raise
    if finish_run(paths):
        print(f"source moved to {paths.source_target}")
    print(f"run folder: {paths.run_dir}")
