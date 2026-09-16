"""End-to-end smoke test on a synthetic flat design: the output must contain
only palette colors (indices 1..K), leave index 0 unused and carry
reed/density in the resolution fields."""

import numpy as np
import pytest
from PIL import Image

from img2texcelle import Options, convert
from img2texcelle.color import parse_palette

PALETTE = "#510A15,#FEF7D4,#D5A556"


def make_design(path, w=400, h=600):
    """Red field, cream border band, tan blobs and a thin line, mirrored both ways."""
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    pal = parse_palette(PALETTE)
    rgb[:] = pal[0]
    rgb[30:-30, 30:-30] = pal[1]
    rgb[60:-60, 60:-60] = pal[0]
    for y0 in (200, h - 260):
        rgb[y0:y0 + 60, 90:150] = pal[2]
        rgb[y0:y0 + 60, w - 150:w - 90] = pal[2]
    rgb[150:152, 100:w - 100] = pal[1]  # a thin line
    rgb[h - 152:h - 150, 100:w - 100] = pal[1]
    Image.fromarray(rgb).save(path, quality=92)


@pytest.mark.parametrize("fmt", ["tiff", "bmp"])
def test_output_is_indexed_with_palette_only(tmp_path, fmt):
    src = tmp_path / "design.jpg"
    make_design(str(src))
    dst = tmp_path / f"design.{fmt}"
    opts = Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE), fmt=fmt)
    labels, palette = convert(str(src), str(dst), opts)

    im = Image.open(dst)
    assert im.mode == "P"
    assert im.size == (79, 150)
    arr = np.asarray(im)
    used = np.unique(arr)
    assert 0 not in used and used.max() <= 3
    assert tuple(round(v) for v in im.info["dpi"]) == (397, 500)  # BMP stores pels per meter
    assert np.array_equal(arr, labels + 1)
    # exact mirror symmetry both ways
    assert np.array_equal(arr, arr[:, ::-1])
    assert np.array_equal(arr, arr[::-1])
    # the field and the band came through
    assert arr[75, 40] == 1 and arr[75, 8] == 2 and arr[57, 24] == 3

    txt = (tmp_path / f"design_palette.txt").read_text().splitlines()
    assert txt[0] == "1\t81\t10\t21\t#510A15"
    assert len(txt) == 3


def test_coarse_source_is_an_error(tmp_path):
    src = tmp_path / "small.jpg"
    make_design(str(src), 40, 60)
    with pytest.raises(SystemExit, match="coarser than the knot grid"):
        convert(str(src), str(tmp_path / "small.tiff"),
                Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))


def test_aspect_mismatch_is_an_error(tmp_path):
    src = tmp_path / "wide.jpg"
    make_design(str(src), 600, 600)
    with pytest.raises(SystemExit, match="--fit crop"):
        convert(str(src), str(tmp_path / "wide.tiff"),
                Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))
