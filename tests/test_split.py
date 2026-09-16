"""img2texcelle.split: exactly equal halves/quarters into data/cropped_images/."""

import pytest
from PIL import Image

from img2texcelle.split import main, split_boxes, split_file, split_image


def mirrored_image(w, h):
    """A both-ways mirror-symmetric RGB image with distinct pixels in one quadrant."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            qx, qy = min(x, w - 1 - x), min(y, h - 1 - y)
            px[x, y] = (qx * 17 % 256, qy * 29 % 256, (qx + qy) % 256)
    return img


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
