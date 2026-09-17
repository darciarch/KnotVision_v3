"""img2texcelle.split: exactly equal halves/quarters into data/cropped_images/."""

import numpy as np
import pytest
from PIL import Image

from img2texcelle.split import cut_ranges, find_cuts, main, split_boxes, split_file, split_image


def mirrored_image(w, h):
    """A both-ways mirror-symmetric RGB image with distinct pixels in one quadrant."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            qx, qy = min(x, w - 1 - x), min(y, h - 1 - y)
            px[x, y] = (qx * 17 % 256, qy * 29 % 256, (qx + qy) % 256)
    return img


def noisy_mirrored_image(w, h, block=16, seed=0):
    """A both-ways mirror-symmetric RGB image of random `block`-px squares (a
    design with distinct detail everywhere, so the mirror axis is unambiguous)."""
    rng = np.random.default_rng(seed)
    hw, hh = w - w // 2, h - h // 2
    q = rng.integers(0, 256, (-(-hh // block), -(-hw // block), 3), dtype=np.uint8)
    q = q.repeat(block, 0).repeat(block, 1)[:hh, :hw]
    a = np.concatenate([q, q[:, ::-1][:, (w % 2):]], axis=1)
    a = np.concatenate([a, a[::-1][(h % 2):]], axis=0)
    return Image.fromarray(a)


def off_centre_image(w, h, dx, dy):
    """`noisy_mirrored_image(w, h)` with a plain strip of dx px on the right and
    dy px at the bottom, so the mirror axis is dx/2 (dy/2) px left/up of the
    geometric centre (shift -dx, -dy in the `measure_axis` convention)."""
    img = Image.new("RGB", (w + dx, h + dy), (200, 90, 30))
    img.paste(noisy_mirrored_image(w, h), (0, 0))
    return img


def mirrors(a, b, method):
    return a.size == b.size and a.tobytes() == b.transpose(method).tobytes()


LR, TB = Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.FLIP_TOP_BOTTOM


def test_boxes_even():
    assert split_boxes(8, 12, 2, "lr") == {"left": (0, 0, 4, 12), "right": (4, 0, 8, 12)}
    assert split_boxes(8, 12, 2, "tb") == {"top": (0, 0, 8, 6), "bottom": (0, 6, 8, 12)}
    assert split_boxes(8, 12, 4) == {
        "tl": (0, 0, 4, 6), "tr": (4, 0, 8, 6), "bl": (0, 6, 4, 12), "br": (4, 6, 8, 12)}


def test_boxes_odd_share_the_middle_pixel():
    boxes = split_boxes(9, 13, 4)
    assert boxes["tl"] == (0, 0, 5, 7) and boxes["br"] == (4, 6, 9, 13)
    sizes = {(r - l, b - t) for l, t, r, b in boxes.values()}
    assert sizes == {(5, 7)}
    lr = split_boxes(9, 13, 2, "lr")
    assert lr["left"] == (0, 0, 5, 13) and lr["right"] == (4, 0, 9, 13)


def test_axis_rules():
    with pytest.raises(ValueError, match="--axis"):
        split_boxes(8, 12, 2)
    with pytest.raises(ValueError, match="no --axis"):
        split_boxes(8, 12, 4, "lr")


@pytest.mark.parametrize("size", [(8, 12), (9, 13)])
def test_halves_and_quarters_mirror_each_other(size):
    img = mirrored_image(*size)
    lr = split_image(img, 2, "lr")
    assert lr["left"].size == lr["right"].size
    assert lr["left"].tobytes() == lr["right"].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
    tb = split_image(img, 2, "tb")
    assert tb["top"].tobytes() == tb["bottom"].transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
    q = split_image(img, 4)
    assert q["tl"].tobytes() == q["tr"].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
    assert q["tl"].tobytes() == q["bl"].transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()


def test_keep_filters_and_validates():
    img = mirrored_image(8, 12)
    assert list(split_image(img, 4, keep=["tl"])) == ["tl"]
    assert list(split_image(img, 4, keep=["br", "tl"])) == ["tl", "br"]
    with pytest.raises(ValueError, match="valid: left, right"):
        split_image(img, 2, "lr", keep=["tl"])


def test_files_go_to_cropped_images_and_never_overwrite(tmp_path):
    data = tmp_path / "data"
    src = tmp_path / "design.jpeg"
    mirrored_image(8, 12).save(src, quality=100)
    first = split_file(src, 4, keep=["tl"], root=data)
    out = data / "cropped_images" / "design"
    assert first == [out / "design_tl.png"]
    assert Image.open(first[0]).size == (4, 6)
    assert src.exists()  # the source stays in place
    first[0].write_bytes(b"x")
    second = split_file(src, 4, keep=["tl"], root=data)
    assert second == [out / "design_tl_2.png"]  # same folder, new name
    assert first[0].read_bytes() == b"x"
    both = split_file(src, 2, "tb", root=data)
    assert [p.name for p in both] == ["design_top.png", "design_bottom.png"]
    assert {p.parent for p in both} == {out}
    other = tmp_path / "other.png"
    mirrored_image(8, 12).save(other)
    assert split_file(other, 4, keep=["br"], root=data)[0].parent == data / "cropped_images" / "other"


def test_main_argument_errors(tmp_path, monkeypatch):
    src = tmp_path / "design.png"
    mirrored_image(8, 12).save(src)
    monkeypatch.setattr("img2texcelle.split.data_dir", lambda: tmp_path / "data")
    with pytest.raises(SystemExit):
        main([str(src), "--parts", "2"])                   # no --axis
    with pytest.raises(SystemExit):
        main([str(src), "--parts", "4", "--keep", "left"])  # wrong part name
    main([str(src), "--parts", "4", "--keep", "tl,br"])
    names = sorted(p.name for p in (tmp_path / "data" / "cropped_images" / "design").iterdir())
    assert names == ["design_br.png", "design_tl.png"]


def test_cut_ranges():
    assert cut_ranges(8) == ((0, 4), (4, 8))
    assert cut_ranges(9) == ((0, 5), (4, 9))          # middle pixel in both parts
    assert cut_ranges(163, -3) == ((0, 80), (80, 163))  # axis at 79.5
    assert cut_ranges(5056, -256) == ((0, 2400), (2400, 5056))
    assert cut_ranges(10, 3) == ((0, 7), (6, 10))     # axis at pixel 6
    assert split_boxes(163, 242, 4, shifts={1: -3, 0: -2}) == {
        "tl": (0, 0, 80, 120), "tr": (80, 0, 163, 120), "bl": (0, 120, 80, 242), "br": (80, 120, 163, 242)}


def test_off_centre_axis_is_not_symmetric_by_default():
    img = off_centre_image(160, 240, 3, 2)
    lr = split_image(img, 2, "lr")
    assert not mirrors(lr["left"], lr["right"], LR)
    assert find_cuts(img, 2, "lr") == {}  # no flag: cut at the centre


@pytest.mark.parametrize("kw", [{"symmetric": True}, {"shift": (-3, -2)}])
def test_find_cuts_gives_exact_mirrors(kw):
    img = off_centre_image(160, 240, 3, 2)  # 163 x 242, axes at 79.5 / 119.5
    found = find_cuts(img, 4, **kw)
    assert found == {1: -3, 0: -2}
    q = split_image(img, 4, shifts=found)
    assert q["tl"].size == (80, 120) and q["br"].size == (83, 122)
    # the parts are complete (the plain strips stay in the right/bottom parts)
    # and mirror each other up to the strips
    assert q["tr"].crop((0, 0, 80, 120)).transpose(LR).tobytes() == q["tl"].tobytes()
    assert q["bl"].crop((0, 0, 80, 120)).transpose(TB).tobytes() == q["tl"].tobytes()
    assert q["br"].getpixel((82, 121)) == (200, 90, 30)
    # --axis lr only cuts left/right
    found = find_cuts(img, 2, "lr", **kw)
    assert found == {1: -3}
    lr = split_image(img, 2, "lr", shifts=found)
    assert lr["left"].size == (80, 242) and lr["right"].size == (83, 242)
    assert lr["right"].crop((0, 0, 80, 242)).transpose(LR).tobytes() == lr["left"].tobytes()
    found = find_cuts(img, 2, "tb", **kw)
    assert found == {0: -2}
    tb = split_image(img, 2, "tb", shifts=found)
    assert tb["top"].size == (163, 120) and tb["bottom"].size == (163, 122)
    assert tb["bottom"].crop((0, 0, 163, 120)).transpose(TB).tobytes() == tb["top"].tobytes()


def test_axis_far_off_centre_is_found():
    img = off_centre_image(160, 240, 40, 60)  # 20% off centre on both axes
    assert find_cuts(img, 4, symmetric=True) == {1: -40, 0: -60}


def test_no_symmetry_cuts_at_the_centre(capsys):
    rng = np.random.default_rng(1)
    img = Image.fromarray(rng.integers(0, 256, (240, 160, 3), dtype=np.uint8))
    assert find_cuts(img, 4, symmetric=True) == {1: 0, 0: 0}
    out = capsys.readouterr().out
    assert out.count("warning: no clear") == 2 and "--shift" in out
    assert find_cuts(img, 4, shift=(6, -4)) == {1: 6, 0: -4}  # --shift always wins


def test_symmetric_flags_from_main(tmp_path, monkeypatch):
    src = tmp_path / "design.png"
    off_centre_image(160, 240, 3, 2).save(src)
    monkeypatch.setattr("img2texcelle.split.data_dir", lambda: tmp_path / "data")
    out = tmp_path / "data" / "cropped_images" / "design"
    main([str(src), "--parts", "2", "--axis", "lr", "--symmetric"])
    left, right = Image.open(out / "design_left.png"), Image.open(out / "design_right.png")
    assert left.size == (80, 242) and right.size == (83, 242)
    assert right.crop((0, 0, 80, 242)).transpose(LR).tobytes() == left.tobytes()
    main([str(src), "--parts", "4", "--shift", "-3,-2"])
    tl, tr = Image.open(out / "design_tl.png"), Image.open(out / "design_tr.png")
    assert tl.size == (80, 120) and tr.size == (83, 120)
    assert tr.crop((0, 0, 80, 120)).transpose(LR).tobytes() == tl.tobytes()
    with pytest.raises(SystemExit):
        main([str(src), "--parts", "4", "--shift", "3"])
