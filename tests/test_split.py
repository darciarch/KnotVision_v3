"""img2texcelle.split: exactly equal halves/quarters into data/cropped_images/."""

import numpy as np
import pytest
from PIL import Image

from img2texcelle.split import centre_on_axis, main, split_boxes, split_file, split_image


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
    geometric centre (shift -dx, -dy in the `detect_symmetry` convention)."""
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


def test_off_centre_axis_is_not_symmetric_by_default():
    img = off_centre_image(160, 240, 3, 2)
    lr = split_image(img, 2, "lr")
    assert not mirrors(lr["left"], lr["right"], LR)
    assert centre_on_axis(img, 2, "lr")[0] is img  # no flag: untouched


@pytest.mark.parametrize("kw", [{"symmetric": True}, {"shift": (-3, -2)}])
def test_centre_on_axis_makes_exact_mirrors(kw):
    img = off_centre_image(160, 240, 3, 2)
    cut, found = centre_on_axis(img, 4, **kw)
    assert cut.size == (160, 240) and found == {1: -3, 0: -2}
    q = split_image(cut, 4)
    assert mirrors(q["tl"], q["tr"], LR) and mirrors(q["tl"], q["bl"], TB)
    # --axis lr only centres left/right; the extra bottom rows stay
    cut, found = centre_on_axis(img, 2, "lr", **kw)
    assert cut.size == (160, 242) and found == {1: -3}
    lr = split_image(cut, 2, "lr")
    assert mirrors(lr["left"], lr["right"], LR)
    cut, found = centre_on_axis(img, 2, "tb", **kw)
    assert cut.size == (163, 240) and found == {0: -2}
    tb = split_image(cut, 2, "tb")
    assert mirrors(tb["top"], tb["bottom"], TB)


def test_symmetric_flags_from_main(tmp_path, monkeypatch):
    src = tmp_path / "design.png"
    off_centre_image(160, 240, 3, 2).save(src)
    monkeypatch.setattr("img2texcelle.split.data_dir", lambda: tmp_path / "data")
    out = tmp_path / "data" / "cropped_images" / "design"
    main([str(src), "--parts", "2", "--axis", "lr", "--symmetric"])
    assert mirrors(Image.open(out / "design_left.png"), Image.open(out / "design_right.png"), LR)
    main([str(src), "--parts", "4", "--shift", "-3,-2"])
    assert Image.open(out / "design_tl.png").size == (80, 120)
    assert mirrors(Image.open(out / "design_tl.png"), Image.open(out / "design_br.png"), LR) is False
    assert mirrors(Image.open(out / "design_tl.png"), Image.open(out / "design_tr.png"), LR)
    with pytest.raises(SystemExit):
        main([str(src), "--parts", "4", "--shift", "3"])
