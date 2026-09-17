"""Finish a --part run: mirror the (edited) part into the Texcelle file.

    python -m img2texcelle.assemble data/<name>/<name>_part.png [--format bmp]

Reads <name>_part.png and <name>_part.json (written by `python -m
img2texcelle ... --part`), places the part on the full knot grid, mirrors it
across the axes recorded in the JSON and writes <name>[_N].tiff / .bmp plus
<name>[_N]_palette.txt into the same folder, never overwriting. The source
image is not needed. Pixels are matched to the palette by RGB (an editor
may save RGB or reorder the palette); a color that is not a yarn is an error
that lists where it occurs, and so is a PNG whose size differs from the JSON.
"""

import argparse
from pathlib import Path

import numpy as np

from .output import FORMATS, load_part, palette_txt_path, save_indexed, write_palette_txt
from .pipeline import assemble_full
from .workspace import next_free_name


def assemble(part_png, fmt):
    """Mirror the part into the next free <name>[_N].<fmt>; returns (labels, path)."""
    labels, info = load_part(part_png)
    palette = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in info["palette"]],
                       dtype=np.uint8)
    p = info["part"]
    part = (p["x"], p["y"], p["x"] + p["width"], p["y"] + p["height"])
    sides = {1: info["axes"]["lr"]["kept"]} if "lr" in info["axes"] else {}
    if "tb" in info["axes"]:
        sides[0] = info["axes"]["tb"]["kept"]
    full = assemble_full(labels, part, tuple(info["grid"]), sides)
    png = Path(part_png).resolve()
    image, txt = next_free_name(png.parent, Path(info["source"]).stem, fmt)
    save_indexed(full, palette, str(image), fmt, tuple(info["ppm"]))
    write_palette_txt(palette, str(txt))
    return full, image


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python -m img2texcelle.assemble",
        description="Mirror a --part output (<name>_part.png + .json) into the Texcelle file.")
    ap.add_argument("part", help="<name>_part.png written by python -m img2texcelle --part "
                                 "(its _part.json must be next to it)")
    ap.add_argument("--format", choices=sorted(FORMATS), default="tiff",
                    help="output format: tiff or bmp (default tiff)")
    a = ap.parse_args(argv)
    full, image = assemble(a.part, a.format)
    h, w = full.shape
    n = int(full.max()) + 1
    print(f"{image}: {w} x {h} px, {n} colors (indices 1-{n}, 0 unused)")
    print(f"palette: {palette_txt_path(str(image))}")


if __name__ == "__main__":
    main()
