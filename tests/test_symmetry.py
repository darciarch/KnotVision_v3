"""symmetry.measure_axis / find_axes / mirror_halves: axes off centre, axis-only
symmetry; --piece: mirror_piece, centre_axes, the piece name under rotation."""

import numpy as np
import pytest
from PIL import Image

from img2texcelle.grid import rotate_piece, rotate_to_carpet
from img2texcelle.symmetry import (AXIS_CONTRAST, AXIS_CONTRAST_AUTO, EXACT_MATCH, PIECES,
                                   centre_axes, describe_axis, find_axes, half_sizes,
                                   measure_axis, mirror_copy, mirror_error, mirror_half,
                                   mirror_halves, mirror_piece, mirrored_size, part_region,
                                   piece_sides)

from test_split import noisy_mirrored_image, off_centre_image


def band_only_image(w=200, h=300, shift_y=-60, band=0.15, seed=3):
    """Random 16 px blocks, mirrored top/bottom only within +-band*h of the
    axis (h - 1 + shift_y) / 2: a medallion that mirrors while the motifs
    above and below it do not (the Gemini render case)."""
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 256, (-(-h // 16), -(-w // 16), 3), dtype=np.uint8)
    a = a.repeat(16, 0).repeat(16, 1)[:h, :w].copy()
    twice = h - 1 + shift_y
    lo = int((twice / 2) - band * h)
    for i in range(max(lo, 0), twice // 2 + 1):
        a[twice - i] = a[i]
    return Image.fromarray(a)


def test_mirror_error_is_zero_on_a_mirror_and_ignores_wrapping():
    img = off_centre_image(160, 240, 3, 2)
    g = np.asarray(img.convert("L")).astype(np.float32)
    assert mirror_error(g, 1, -3) == 0 and mirror_error(g, 0, -2) == 0
    assert mirror_error(g, 1, -3, band=0.15) == 0
    assert mirror_error(g, 1, 0) > 1  # the centre is not the axis
    assert mirror_error(g, 1, 500) == float("inf")  # no overlap


def test_exact_mirror_at_the_centre():
    img = noisy_mirrored_image(160, 240)
    for axis in (1, 0):
        shift, contrast, match = measure_axis(img, axis)
        assert shift == 0 and contrast == 0 and match == 0


def test_axis_off_centre_by_a_quarter():
    img = off_centre_image(160, 240, 40, 60)  # axes 20 / 30 px off centre
    assert measure_axis(img, 1)[:2] == (-40, 0)
    assert measure_axis(img, 0)[:2] == (-60, 0)
    assert measure_axis(img, 1)[2] < EXACT_MATCH


def test_band_only_symmetry_is_an_axis_but_not_an_exact_match():
    img = band_only_image()
    shift, contrast, match = measure_axis(img, 0)
    assert shift == -60 and contrast < AXIS_CONTRAST_AUTO
    assert match > EXACT_MATCH  # the halves match only near the axis
    assert measure_axis(img, 1)[1] > AXIS_CONTRAST  # left/right: nothing


def test_narrow_band_is_an_unclear_axis():
    """A mirror band of only 8% of the height (fom's top/bottom: 0.57)."""
    shift, contrast, _ = measure_axis(band_only_image(band=0.08, seed=5), 0)
    assert shift == -60 and AXIS_CONTRAST_AUTO <= contrast < AXIS_CONTRAST


def test_noise_has_no_axis():
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 256, (240, 160, 3), dtype=np.uint8))
    assert measure_axis(img, 1)[1] > AXIS_CONTRAST
    assert measure_axis(img, 0)[1] > AXIS_CONTRAST


def test_find_axes_modes(capsys):
    img = band_only_image()  # 200x300, top/bottom axis at row 119.5 (60 px above the centre)
    assert find_axes(img, "auto") == {0: (-60, False)}
    assert "copy only" in capsys.readouterr().out
    # forced: the measured axis is used below AXIS_CONTRAST_FORCED (left/right
    # here: 0.87, 12 px left); an unclear forced axis stays at the centre and
    # is never averaged
    assert find_axes(img, "both") == {1: (-24, False), 0: (-60, False)}
    assert "warning" not in capsys.readouterr().out
    rng = np.random.default_rng(0)
    noise = Image.fromarray(rng.integers(0, 256, (240, 160, 3), dtype=np.uint8))
    assert find_axes(noise, "lr") == {1: (0, False)}
    assert "warning: no clear left/right mirror axis" in capsys.readouterr().out
    assert find_axes(img, "none") == {}
    # an exact mirror is averaged as well, unless --no-average
    exact = off_centre_image(160, 240, 3, 2)
    assert find_axes(exact, "auto") == {1: (-3, True), 0: (-2, True)}
    assert find_axes(exact, "auto", average=False) == {1: (-3, False), 0: (-2, False)}
    assert "copy only (--no-average)" in capsys.readouterr().out


def test_unclear_axis_is_named_in_auto_and_taken_when_forced(capsys):
    img = band_only_image(band=0.08, seed=5)  # top/bottom contrast 0.56
    assert find_axes(img, "auto") == {}
    out = capsys.readouterr().out
    assert ("warning: top/bottom mirror axis unclear, not used (best candidate at row 119.5 "
            "(30 px above the centre), contrast 0.56 >= 0.4); force it with --symmetry tb (or both)") in out
    assert "symmetry: left/right not symmetric" in out
    assert find_axes(img, "tb") == {0: (-60, False)}
    assert "warning" not in capsys.readouterr().out


def test_part_region():
    # no axis: everything
    assert part_region(79, 150, {}, {}) == ((0, 0, 79, 150), (0, 0, 79, 150))
    # copy-only axes: the kept half (odd: with the middle knot) plus the pad
    axes = {1: (0, False), 0: (-2, False)}
    assert part_region(79, 150, axes, {1: "left", 0: "top"}, 20) == ((0, 0, 60, 95), (0, 0, 40, 75))
    assert part_region(79, 150, axes, {1: "right", 0: "bottom"}, 20) == ((19, 55, 79, 150), (39, 75, 79, 150))
    # an averaged axis: the whole extent is converted, the part is still the kept half
    assert part_region(794, 1566, {1: (0, True), 0: (-256, False)}, {1: "left", 0: "bottom"}) \
        == ((0, 763, 794, 1566), (0, 783, 397, 1566))
    # the pad never leaves the grid
    assert part_region(10, 10, {1: (0, False)}, {1: "left"}, 20) == ((0, 0, 10, 10), (0, 0, 5, 10))


def test_half_sizes_and_mirror_half():
    assert half_sizes(5056, -256) == (2400, 2656)  # fom: axis at row 2399.5
    assert mirrored_size(5056, -256, "top") == 4800
    assert mirrored_size(5056, -256, "bottom") == 5312
    assert half_sizes(10, 3) == (7, 4)  # axis on column 6: in both halves
    assert (mirrored_size(10, 3, "left"), mirrored_size(10, 3, "right")) == (13, 7)
    cols = np.arange(10, dtype=np.uint8)[None, :, None].repeat(2, 0).repeat(3, 2)
    img = Image.fromarray(cols)
    assert np.asarray(mirror_half(img, 1, 3, "right"))[0, :, 0].tolist() == [9, 8, 7, 6, 7, 8, 9]
    assert np.asarray(mirror_half(img, 1, 3, "left"))[0, :, 0].tolist() == list(range(7)) + [5, 4, 3, 2, 1, 0]
    assert np.asarray(mirror_half(img, 1, 2, "right"))[0, :, 0].tolist() == [9, 8, 7, 6, 6, 7, 8, 9]
    rows = Image.fromarray(np.ascontiguousarray(cols.transpose(1, 0, 2)))
    assert np.asarray(mirror_half(rows, 0, 2, "top"))[:, 0, 0].tolist() == [0, 1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 0]


def test_mirror_halves_keeps_the_larger_half_or_the_better_fit(capsys):
    img = band_only_image()  # 200x300, axis 60 px above the centre: 120 rows above, 180 below
    axes = {0: (-60, False)}
    out, sides = mirror_halves(img, axes)
    assert sides == {0: "bottom"} and out.size == (200, 360)
    assert np.array_equal(np.asarray(out), np.asarray(out)[::-1])
    assert np.array_equal(np.asarray(out)[180:], np.asarray(img)[120:])
    assert "bottom half (180 rows) kept and mirrored onto the top (120 rows)" in capsys.readouterr().out
    # --stretch: the half whose mirrored image is closest to the carpet ratio
    out, sides = mirror_halves(img, axes, (20, 24))  # 200x240 fits exactly
    assert sides == {0: "top"} and out.size == (200, 240)
    assert np.array_equal(np.asarray(out)[:120], np.asarray(img)[:120])
    assert "0.0% distortion against 50.0% with the bottom half" in capsys.readouterr().out
    out, sides = mirror_halves(img, axes, (20, 36))
    assert sides == {0: "bottom"} and out.size == (200, 360)
    # an averaged axis at the centre leaves the image alone; no axis, nothing
    out, sides = mirror_halves(img, {1: (0, True), 0: (-60, False)})
    assert sides == {1: "left", 0: "bottom"} and out.size == (200, 360)
    assert mirror_halves(img, {})[1] == {} and mirror_halves(img, {1: (0, True)})[0] is img
    # a copy-only axis at the centre: the left half is kept and mirrored (the
    # pad beyond the axis must be reflected pixels, not the other half)
    out, sides = mirror_halves(img, {1: (0, False)})
    assert sides == {1: "left"} and out.size == (200, 300)
    assert np.array_equal(np.asarray(out)[:, :100], np.asarray(img)[:, :100])
    assert np.array_equal(np.asarray(out), np.asarray(out)[:, ::-1])


def test_mirror_copy_sides():
    a = np.arange(12).reshape(3, 4)
    mirror_copy(a.copy(), None, None)
    b = a.copy(); mirror_copy(b, "left", None)
    assert b.tolist() == [[0, 1, 1, 0], [4, 5, 5, 4], [8, 9, 9, 8]]
    b = a.copy(); mirror_copy(b, "right", "bottom")
    assert b.tolist() == [[11, 10, 10, 11], [7, 6, 6, 7], [11, 10, 10, 11]]
    b = a.copy(); mirror_copy(b, None, "top")
    assert b.tolist() == [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 2, 3]]


def test_describe_axis():
    assert describe_axis(0, 5056, -256) == "at row 2399.5 (128 px above the centre)"
    assert describe_axis(1, 3392, 0) == "at column 1695.5 (at the centre)"
    assert describe_axis(1, 10, 3) == "at column 6 (1.5 px right the centre)"


def piece_box(piece, w, h):
    """The (x0, y0, x1, y1) box a piece occupies in a w x h full image."""
    x0, x1 = (0, w) if piece[-1] not in "lr" else ((0, w // 2) if piece[-1] == "l" else (w // 2, w))
    y0, y1 = (0, h) if piece[0] not in "tb" else ((0, h // 2) if piece[0] == "t" else (h // 2, h))
    return x0, y0, x1, y1


@pytest.mark.parametrize("piece", PIECES)
def test_mirror_piece_keeps_the_piece_and_mirrors_the_rest(piece):
    rng = np.random.default_rng(1)
    a = rng.integers(0, 256, (8, 6, 3), dtype=np.uint8)  # 6 x 8, nothing symmetric
    full = np.asarray(mirror_piece(Image.fromarray(a), piece))
    sides = piece_sides(piece)
    assert full.shape == (16 if 0 in sides else 8, 12 if 1 in sides else 6, 3)
    x0, y0, x1, y1 = piece_box(piece, full.shape[1], full.shape[0])
    assert np.array_equal(full[y0:y1, x0:x1], a)  # the piece is where it was
    assert np.array_equal(full, full[:, ::-1]) == (1 in sides)  # left/right mirror iff mirrored
    assert np.array_equal(full, full[::-1]) == (0 in sides)
    if 1 in sides:  # the edge column is doubled: the axis is on a pixel boundary
        assert np.array_equal(full[:, 5], full[:, 6])


def test_piece_sides_and_centre_axes():
    assert piece_sides("t") == {0: "top"} and piece_sides("r") == {1: "right"}
    assert piece_sides("br") == {1: "right", 0: "bottom"} and list(piece_sides("tl")) == [1, 0]
    with pytest.raises(ValueError, match="unknown piece 'x'"):
        piece_sides("x")
    for piece in PIECES:
        axes, sides = centre_axes((400, 600), piece)
        assert sides == piece_sides(piece) and set(axes) == set(sides)
        assert all(v == (0, False) for v in axes.values())  # centre, copy only
    assert centre_axes((400, 600), "bl", average=True) == ({1: (0, True), 0: (0, True)},
                                                           {1: "left", 0: "bottom"})
    # mirror_halves takes the piece's side instead of choosing one
    img = mirror_piece(noisy_mirrored_image(60, 40), "br")
    axes, sides = centre_axes(img.size, "br")
    out, sides = mirror_halves(img, axes, sides=sides)
    assert sides == {1: "right", 0: "bottom"} and out.size == img.size
    assert np.array_equal(np.asarray(out), np.asarray(img))


@pytest.mark.parametrize("piece", PIECES)
def test_rotate_piece_follows_rotate_to_carpet(piece):
    """A 4x6 image is rotated for a 30x20 carpet (ROTATE_90: counter-
    clockwise); the marked piece lands where `rotate_piece` says."""
    a = np.zeros((6, 4), dtype=np.uint8)
    x0, y0, x1, y1 = piece_box(piece, 4, 6)
    a[y0:y1, x0:x1] = 1
    r = np.asarray(rotate_to_carpet(Image.fromarray(a), 30, 20))
    assert r.shape == (4, 6)
    x0, y0, x1, y1 = piece_box(rotate_piece(piece), 6, 4)
    expect = np.zeros((4, 6), dtype=np.uint8)
    expect[y0:y1, x0:x1] = 1
    assert np.array_equal(r, expect)
    p = piece
    for _ in range(4):
        p = rotate_piece(p)
    assert p == piece
