"""Writing the Texcelle files: indexed TIFF/BMP and the palette text; the
intermediate part (<name>_part.png + <name>_part.json, see `save_part`)."""

import json
import os

import numpy as np
from PIL import Image

# output format -> file extensions (the first one is used for the default name)
FORMATS = {"tiff": (".tiff", ".tif"), "bmp": (".bmp",)}
PART_SUFFIX = "_part.png"   # --part: the kept part on the knot grid, plus _part.json
PART_FORMAT = "img2texcelle-part"
PART_VERSION = 1


def format_from_extension(path):
    """'tiff' / 'bmp' from a file name, or None if unknown."""
    ext = os.path.splitext(path)[1].lower()
    return next((f for f, exts in FORMATS.items() if ext in exts), None)


def output_stem(image_path):
    """<dir>/<name>[_N] of an output file (tiff / bmp / _part.png)."""
    if image_path.endswith(PART_SUFFIX):
        return image_path[:-len(PART_SUFFIX)]
    return os.path.splitext(image_path)[0]


def palette_txt_path(image_path):
    return output_stem(image_path) + "_palette.txt"


def part_json_path(part_png_path):
    return part_png_path[:-4] + ".json"


def save_indexed(labels, palette, path, fmt, ppm):
    """8-bit palette TIFF or BMP, uncompressed, like Texcelle's own files:
    index 0 is black and unused (yarns start at 1) and the resolution fields
    hold points per meter (397 x 500 -> "397 x 500 dpi")."""
    im = Image.fromarray(labels + 1, "P")
    flat = [0, 0, 0] + palette.ravel().tolist()
    im.putpalette(flat + [0] * (768 - len(flat)))
    dpi = (float(ppm[0]), float(ppm[1]))
    if fmt == "bmp":
        im.save(path, format="BMP", dpi=dpi)
    else:
        im.save(path, format="TIFF", compression=None, dpi=dpi)


def write_palette_txt(palette, path):
    """One line per yarn: index<TAB>R<TAB>G<TAB>B<TAB>#RRGGBB (index 0 is not listed)."""
    with open(path, "w") as f:
        for i, (r, g, b) in enumerate(palette.tolist(), start=1):
            f.write(f"{i}\t{r}\t{g}\t{b}\t#{r:02X}{g:02X}{b:02X}\n")


def save_part(labels, palette, path, info):
    """--part: the kept part as an 8-bit palette PNG (index 0 reserved, yarns
    from 1, like the Texcelle file) plus the JSON `info` next to it
    (`part_json_path`) that `img2texcelle.assemble` mirrors it with."""
    im = Image.fromarray(labels + 1, "P")
    flat = [0, 0, 0] + palette.ravel().tolist()
    im.putpalette(flat + [0] * (768 - len(flat)))
    im.save(path, format="PNG")
    with open(part_json_path(path), "w") as f:
        json.dump({"format": PART_FORMAT, "version": PART_VERSION, **info}, f, indent=1)
        f.write("\n")


def load_part(path):
    """Read a part PNG (as written by `save_part` or re-saved by an image
    editor) and its JSON. Returns (labels (h, w) 0-based, info).

    Pixels are matched to the palette by RGB, not by index (an editor saves
    RGB or reorders the palette). A color that is not a yarn, including the
    reserved index 0 black unless a yarn is black, is an error naming where
    it occurs."""
    with open(part_json_path(path)) as f:
        info = json.load(f)
    if info.get("format") != PART_FORMAT:
        raise SystemExit(f"ERROR: {part_json_path(path)} is not an {PART_FORMAT} file")
    palette = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in info["palette"]],
                       dtype=np.uint8)
    im = Image.open(path)
    if im.mode == "P":  # keep the palette exact (RGB conversion of a P image is exact)
        rgb = np.asarray(im.convert("RGB"))
    elif im.mode == "RGB":
        rgb = np.asarray(im)
    elif im.mode in ("RGBA", "LA", "L", "PA"):
        rgb = np.asarray(im.convert("RGB"))
    else:
        raise SystemExit(f"ERROR: {path}: unsupported image mode {im.mode}")
    w, h = info["part"]["width"], info["part"]["height"]
    if rgb.shape[1] != w or rgb.shape[0] != h:
        raise SystemExit(f"ERROR: {path} is {rgb.shape[1]}x{rgb.shape[0]} px, the part in "
                         f"{part_json_path(path)} is {w}x{h}")
    key = (rgb[..., 0].astype(np.int32) << 16) | (rgb[..., 1].astype(np.int32) << 8) | rgb[..., 2]
    pal_key = (palette[:, 0].astype(np.int32) << 16) | (palette[:, 1].astype(np.int32) << 8) | palette[:, 2]
    lut = {int(k): i for i, k in enumerate(pal_key.tolist())}  # a later duplicate loses
    labels = np.full(key.shape, -1, dtype=np.int16)
    for k, i in lut.items():
        labels[key == k] = i
    bad = labels < 0
    if bad.any():
        ys, xs = np.nonzero(bad)
        colors = {}
        for y, x in zip(ys.tolist(), xs.tolist()):
            colors.setdefault(tuple(rgb[y, x].tolist()), []).append((x, y))
        lines = []
        for c, at in sorted(colors.items(), key=lambda kv: -len(kv[1]))[:10]:
            where = ", ".join(f"({x},{y})" for x, y in at[:5]) + (", ..." if len(at) > 5 else "")
            lines.append(f"  #{c[0]:02X}{c[1]:02X}{c[2]:02X}: {len(at)} px at {where}")
        if len(colors) > 10:
            lines.append(f"  ... {len(colors) - 10} more colors")
        raise SystemExit(f"ERROR: {path}: {int(bad.sum())} px in {len(colors)} colors that are "
                         f"not in the palette (index 0 black is reserved):\n" + "\n".join(lines))
    return labels.astype(np.uint8), info


def save_debug_png(labels, palette, path):
    """Debug helper: save a label map as a palette PNG."""
    im = Image.fromarray(labels, "P")
    flat = palette.ravel().tolist()
    im.putpalette(flat + [0] * (768 - len(flat)))
    im.save(path)
