"""End-to-end smoke test on a synthetic flat design: the output must contain
only palette colors (indices 1..K), leave index 0 unused and carry
reed/density in the resolution fields; the carpet-size (--stretch) and
source-scale rules."""

import json

import numpy as np
import pytest
from PIL import Image

from img2texcelle import Options, convert
from img2texcelle.assemble import assemble
from img2texcelle.cli import main
from img2texcelle.color import parse_palette
from img2texcelle.symmetry import mirror_piece

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
    make_design(str(src), 600, 600)  # 50% off the 2:3 carpet
    with pytest.raises(SystemExit, match="use --stretch"):
        convert(str(src), str(tmp_path / "wide.tiff"),
                Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))
    with pytest.raises(SystemExit, match="would distort it by 50.0%"):
        convert(str(src), str(tmp_path / "wide.tiff"),
                Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE),
                        stretch=True))


def test_small_aspect_mismatch_stretch_or_follow_the_image(tmp_path, capsys):
    src = tmp_path / "wide.jpg"
    make_design(str(src), 420, 600)  # ratio 0.70 vs 0.667: 5% off
    # --stretch: the requested size, the image is stretched onto the knot grid
    labels, _ = convert(str(src), str(tmp_path / "wide.tiff"),
                        Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE),
                                stretch=True))
    assert labels.shape == (150, 79)
    assert "5.0% distortion" in capsys.readouterr().out
    # default: the width is kept, the height follows the image: 20 x 28.6 cm
    labels, _ = convert(str(src), str(tmp_path / "wide2.tiff"),
                        Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))
    assert labels.shape == (143, 79)
    out = capsys.readouterr().out
    assert "*** CARPET 20 x 28.6 cm, KNOT GRID 79 x 143 ***" in out
    assert "4.8% shorter" in out and "--stretch fits 30 cm" in out


def test_off_centre_axis_keeps_the_larger_half(tmp_path, capsys):
    """The design cut 40 px below its top/bottom axis: the bottom half (340
    rows) is kept and mirrored, the carpet grows to 20 x 34 cm; with
    --stretch the top half (260 rows, 13% off) loses to the bottom half
    (340 rows, 11%) but both exceed 10%."""
    src = tmp_path / "cut.jpg"
    make_design(str(src))
    rgb = np.asarray(Image.open(src))[40:]  # 400x560, axis at row 259.5
    Image.fromarray(rgb).save(src, quality=92)
    labels, _ = convert(str(src), str(tmp_path / "cut.tiff"),
                        Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))
    out = capsys.readouterr().out
    assert "top/bottom axis at row 259.5 (20 px above the centre)" in out
    assert "bottom half (300 rows) kept and mirrored onto the top (260 rows): image 400x600" in out
    assert "*** CARPET 20 x 30.0 cm, KNOT GRID 79 x 150 ***" not in out  # exact: no banner
    assert labels.shape == (150, 79)
    assert np.array_equal(labels, labels[::-1]) and np.array_equal(labels, labels[:, ::-1])
    assert labels[75, 40] == 0 and labels[75, 8] == 1 and labels[57, 24] == 2


def test_no_average_and_pad_give_the_same_design(tmp_path, capsys):
    """Only the kept part plus a pad is converted. Against a run that converts
    the whole grid (pad = the grid) the knots may differ only within the pad
    of an axis; on the synthetic design they do not differ at all."""
    src = tmp_path / "design.jpg"
    make_design(str(src))
    base = dict(reed=397, density=500, palette=parse_palette(PALETTE), average=False)
    whole, _ = convert(str(src), str(tmp_path / "whole.tiff"), Options(20, 30, pad=1000, **base))
    out = capsys.readouterr().out
    assert "copy only (--no-average)" in out
    assert "part: knots [0, 40) x [0, 75) of 79 x 150 (40 x 75); converting 79 x 150 knots" in out
    padded, _ = convert(str(src), str(tmp_path / "padded.tiff"), Options(20, 30, **base))
    assert "converting 60 x 95 knots = 48% of the grid" in capsys.readouterr().out
    assert whole.shape == padded.shape == (150, 79)
    assert np.array_equal(padded, padded[:, ::-1]) and np.array_equal(padded, padded[::-1])
    diff = np.argwhere(whole != padded)
    assert len(diff) == 0, diff
    # the default (averaged) run of the symmetric design agrees as well
    averaged, _ = convert(str(src), str(tmp_path / "avg.tiff"),
                          Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE)))
    assert "converting 79 x 150 knots" in capsys.readouterr().out
    assert np.array_equal(averaged, padded)


def test_part_and_assemble(tmp_path, capsys):
    src = tmp_path / "design.jpg"
    make_design(str(src))
    opts = Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE), fmt="bmp")
    full, _ = convert(str(src), str(tmp_path / "design.bmp"), opts)
    png = tmp_path / "design_part.png"
    part, _ = convert(str(src), str(png), Options(**{**opts.__dict__, "part": True}))
    out = capsys.readouterr().out
    assert part.shape == (75, 40)  # the left/top quarter, with the middle column of the odd grid
    assert f"{png}: part 40 x 75 px at (0, 0) of 79 x 150" in out
    assert np.array_equal(part, full[:75, :40])
    im = Image.open(png)
    assert im.mode == "P" and np.array_equal(np.asarray(im), part + 1)
    info = json.loads((tmp_path / "design_part.json").read_text())
    assert info["format"] == "img2texcelle-part" and info["grid"] == [79, 150]
    assert info["part"] == {"x": 0, "y": 0, "width": 40, "height": 75}
    assert info["axes"] == {"lr": {"kept": "left", "averaged": True, "shift": 0,
                                   "position": "at column 199.5 (at the centre)"},
                            "tb": {"kept": "top", "averaged": True, "shift": 0,
                                   "position": "at row 299.5 (at the centre)"}}
    assert info["palette"] == ["#510A15", "#FEF7D4", "#D5A556"] and info["ppm"] == [397, 500]
    assert info["source"] == "design.jpg" and info["carpet_cm"] == [20, 30] and not info["rotated"]
    assert (tmp_path / "design_palette.txt").read_text().splitlines()[0] == "1\t81\t10\t21\t#510A15"
    assert not (tmp_path / "design_part.bmp").exists()

    # assemble: the same file as the direct run, named after the source, never overwriting
    labels, image = assemble(str(png), "bmp")
    assert image == tmp_path / "design_2.bmp"  # design.bmp exists
    assert np.array_equal(labels, full)
    assert np.array_equal(np.asarray(Image.open(image)), np.asarray(Image.open(tmp_path / "design.bmp")))
    assert (tmp_path / "design_2_palette.txt").read_text() == (tmp_path / "design_palette.txt").read_text()
    assert tuple(round(v) for v in Image.open(image).info["dpi"]) == (397, 500)

    # an editor saves RGB and edits a knot: matched by color, the edit is mirrored 4 times
    rgb = Image.open(png).convert("RGB")
    a = np.asarray(rgb).copy()
    a[10, 10] = parse_palette(PALETTE)[2]
    Image.fromarray(a).save(png)
    labels, image = assemble(str(png), "tiff")
    assert image == tmp_path / "design_3.tiff"  # design_2_palette.txt exists
    assert labels[10, 10] == labels[10, 68] == labels[139, 10] == labels[139, 68] == 2
    labels[10, 10] = labels[10, 68] = labels[139, 10] = labels[139, 68] = full[10, 10]
    assert np.array_equal(labels, full)

    # a foreign color (and the reserved black) is an error naming the pixels
    a[5, 7] = (1, 2, 3)
    a[6, 7] = (0, 0, 0)
    Image.fromarray(a).save(png)
    with pytest.raises(SystemExit) as e:
        assemble(str(png), "bmp")
    assert "2 px in 2 colors that are not in the palette" in str(e.value)
    assert "#010203: 1 px at (7,5)" in str(e.value) and "#000000: 1 px at (7,6)" in str(e.value)
    # a wrong size is an error
    Image.fromarray(a[:-1]).save(png)
    with pytest.raises(SystemExit, match="is 40x74 px, the part in .* is 40x75"):
        assemble(str(png), "bmp")


def test_part_without_symmetry_is_the_whole_grid(tmp_path):
    src = tmp_path / "design.jpg"
    make_design(str(src))
    png = tmp_path / "design_part.png"
    part, _ = convert(str(src), str(png), Options(20, 30, reed=397, density=500,
                                                  palette=parse_palette(PALETTE), symmetry="none",
                                                  part=True))
    assert part.shape == (150, 79)
    info = json.loads((tmp_path / "design_part.json").read_text())
    assert info["axes"] == {} and info["part"] == {"x": 0, "y": 0, "width": 79, "height": 150}
    labels, image = assemble(str(png), "bmp")
    assert image == tmp_path / "design_2.bmp"  # design_palette.txt exists
    assert np.array_equal(labels, part)


def make_pieces(tmp_path):
    """The synthetic design decoded, its pieces as lossless PNG: {piece: path}
    for t, b, tl, br plus the `mirror_piece` fulls of t and tl."""
    src = tmp_path / "design.jpg"
    make_design(str(src))
    a = np.asarray(Image.open(src).convert("RGB"))
    boxes = {"t": a[:300], "b": a[300:], "tl": a[:300, :200], "br": a[300:, 200:]}
    paths = {}
    for name, crop in boxes.items():
        paths[name] = tmp_path / f"{name}.png"
        Image.fromarray(np.ascontiguousarray(crop)).save(paths[name])
    for name in ("t", "tl"):
        paths[name + "_full"] = tmp_path / f"{name}_full.png"
        mirror_piece(Image.open(paths[name]), name).save(paths[name + "_full"])
    return paths


def base_opts(**kw):
    return Options(20, 30, reed=397, density=500, palette=parse_palette(PALETTE), **kw)


def test_piece_half_and_quarter_match_the_mirrored_full_run(tmp_path, capsys):
    """--piece t / tl must give the same knots as the mirrored full image run
    with --symmetry tb / both --no-average (find_axes keeps top/left on the
    centre tie, the same side as the piece)."""
    paths = make_pieces(tmp_path)
    half, _ = convert(str(paths["t"]), str(tmp_path / "t.tiff"), base_opts(piece="t"))
    out = capsys.readouterr().out
    assert "piece t: image 400x300 mirrored to 400x600, top/bottom axis at the centre, copy only" in out
    assert "symmetry:" not in out and "rotated" not in out
    assert "part: knots [0, 79) x [0, 75) of 79 x 150 (79 x 75); converting 79 x 95 knots = 63%" in out
    ref, _ = convert(str(paths["t_full"]), str(tmp_path / "t_ref.tiff"),
                     base_opts(symmetry="tb", average=False))
    assert "top/bottom axis at row 299.5 (at the centre)" in capsys.readouterr().out
    assert half.shape == (150, 79) and np.array_equal(half, ref)
    assert np.array_equal(half, half[::-1])

    quarter, _ = convert(str(paths["tl"]), str(tmp_path / "tl.tiff"), base_opts(piece="tl"))
    out = capsys.readouterr().out
    assert "piece tl: image 200x300 mirrored to 400x600, both axes at the centre, copy only" in out
    assert "part: knots [0, 40) x [0, 75) of 79 x 150 (40 x 75); converting 60 x 95 knots = 48%" in out
    ref, _ = convert(str(paths["tl_full"]), str(tmp_path / "tl_ref.tiff"),
                     base_opts(symmetry="both", average=False))
    assert quarter.shape == (150, 79) and np.array_equal(quarter, ref)
    assert np.array_equal(quarter, quarter[::-1]) and np.array_equal(quarter, quarter[:, ::-1])
    assert quarter[75, 40] == 0 and quarter[75, 8] == 1 and quarter[57, 24] == 2


def test_piece_from_the_other_side_is_symmetric_and_kept(tmp_path, capsys):
    paths = make_pieces(tmp_path)
    labels, _ = convert(str(paths["b"]), str(tmp_path / "b.tiff"), base_opts(piece="b"))
    assert "part: knots [0, 79) x [75, 150) of 79 x 150" in capsys.readouterr().out
    assert np.array_equal(labels, labels[::-1])
    assert labels[75, 40] == 0 and labels[75, 8] == 1 and labels[57, 24] == 2
    png = tmp_path / "br_part.png"
    part, _ = convert(str(paths["br"]), str(png), base_opts(piece="br", part=True))
    assert part.shape == (75, 40) and "part 40 x 75 px at (39, 75) of 79 x 150" in capsys.readouterr().out
    info = json.loads((tmp_path / "br_part.json").read_text())
    assert info["piece"] == "br" and info["part"] == {"x": 39, "y": 75, "width": 40, "height": 75}
    assert info["axes"]["lr"]["kept"] == "right" and info["axes"]["tb"]["kept"] == "bottom"
    assert not info["axes"]["lr"]["averaged"] and info["axes"]["tb"]["shift"] == 0
    labels, _ = assemble(str(png), "bmp")
    assert np.array_equal(labels, labels[::-1]) and np.array_equal(labels, labels[:, ::-1])
    assert np.array_equal(labels[75:, 39:], part)


def test_piece_is_rotated_with_the_image(tmp_path, capsys):
    """The top half of the 2:3 design for a 30 x 20 (landscape) carpet: the
    full image is rotated counter-clockwise, so the piece becomes the left half."""
    paths = make_pieces(tmp_path)
    labels, _ = convert(str(paths["t"]), str(tmp_path / "rot.tiff"),
                        Options(30, 20, reed=397, density=500, palette=parse_palette(PALETTE), piece="t"))
    out = capsys.readouterr().out
    assert "image rotated 90 deg" in out
    assert ("piece l: image 400x300 mirrored to 400x600, left/right axis at the centre, copy only "
            "(rotated 90 deg to 600x400, piece t -> l)") in out
    assert "part: knots [0, 60) x [0, 100) of 119 x 100 (60 x 100); converting 80 x 100 knots" in out
    assert labels.shape == (100, 119) and np.array_equal(labels, labels[:, ::-1])
    assert labels[50, 60] == 0 and labels[8, 50] == 1


def test_piece_pad_rule(tmp_path, capsys):
    """Only the part plus the pad is converted: against an unlimited pad the
    knots may differ only within 20 knots of an axis; the count is reported.
    Also on the quarter upscaled 2x (a piece at the full image's pixel count:
    the scale doubles on the mirrored axes)."""
    paths = make_pieces(tmp_path)
    big = tmp_path / "tl_big.png"
    Image.open(paths["tl"]).resize((400, 600), Image.NEAREST).save(big)
    for name, path in (("crop", paths["tl"]), ("2x", big)):
        padded, _ = convert(str(path), str(tmp_path / f"{name}.tiff"), base_opts(piece="tl"))
        whole, _ = convert(str(path), str(tmp_path / f"{name}_whole.tiff"),
                           base_opts(piece="tl", pad=5000))
        assert "converting 79 x 150 knots = 100%" in capsys.readouterr().out
        assert np.array_equal(padded, padded[::-1]) and np.array_equal(padded, padded[:, ::-1])
        diff = np.argwhere(whole != padded)
        near = (np.abs(diff[:, 0] - 74.5) <= 20) | (np.abs(diff[:, 1] - 39) <= 20)
        assert near.all(), diff[~near]
        assert len(diff) == 0, f"{name}: {len(diff)} knots differ within the pad"


def test_piece_with_symmetry_is_a_cli_error(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main([str(tmp_path / "nothing.png"), "--width", "20", "--height", "30", "--reed", "397",
              "--density", "500", "--piece", "t", "--symmetry", "both"])
    assert "--piece t already fixes the mirror axes; drop --symmetry both" in capsys.readouterr().err
    assert not (tmp_path / "nothing").exists()
    with pytest.raises(ValueError, match="symmetry must stay 'auto'"):
        convert("nothing.png", "x.tiff", base_opts(piece="t", symmetry="tb"))
