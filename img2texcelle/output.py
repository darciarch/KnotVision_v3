"""Writing the Texcelle files: indexed TIFF/BMP and the palette text."""

import os

from PIL import Image

# output format -> file extensions (the first one is used for the default name)
FORMATS = {"tiff": (".tiff", ".tif"), "bmp": (".bmp",)}


def format_from_extension(path):
    """'tiff' / 'bmp' from a file name, or None if unknown."""
    ext = os.path.splitext(path)[1].lower()
    return next((f for f, exts in FORMATS.items() if ext in exts), None)


def palette_txt_path(image_path):
    return os.path.splitext(image_path)[0] + "_palette.txt"


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


def save_debug_png(labels, palette, path):
    """Debug helper: save a label map as a palette PNG."""
    im = Image.fromarray(labels, "P")
    flat = palette.ravel().tolist()
    im.putpalette(flat + [0] * (768 - len(flat)))
    im.save(path)
