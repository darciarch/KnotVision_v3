"""symmetry.measure_axis / find_axes / mirror_halves: axes off centre, axis-only symmetry."""

import numpy as np
from PIL import Image

from img2texcelle.symmetry import (AXIS_CONTRAST, EXACT_MATCH, describe_axis, find_axes,
                                   half_sizes, measure_axis, mirror_copy, mirror_error,
                                   mirror_half, mirror_halves, mirrored_size)

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
    assert shift == -60 and contrast < AXIS_CONTRAST
    assert match > EXACT_MATCH  # the halves match only near the axis
    assert measure_axis(img, 1)[1] > AXIS_CONTRAST  # left/right: nothing


def test_noise_has_no_axis():
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 256, (240, 160, 3), dtype=np.uint8))
    assert measure_axis(img, 1)[1] > AXIS_CONTRAST
    assert measure_axis(img, 0)[1] > AXIS_CONTRAST


def test_find_axes_modes(capsys):
    img = band_only_image()  # 200x300, top/bottom axis at row 119.5 (60 px above the centre)
    assert find_axes(img, "auto") == {0: (-60, False)}
    assert "copy only" in capsys.readouterr().out
    # forced: the measured axis is used, not the centre; an unclear forced
    # axis stays at the centre and is never averaged
    assert find_axes(img, "both") == {1: (0, False), 0: (-60, False)}
    assert "warning: no clear left/right" in capsys.readouterr().out
    assert find_axes(img, "none") == {}
    # an exact mirror is averaged as well
    assert find_axes(off_centre_image(160, 240, 3, 2), "auto") == {1: (-3, True), 0: (-2, True)}


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
    # an axis at the centre leaves the image alone; no axis, nothing
    out, sides = mirror_halves(img, {1: (0, True), 0: (-60, False)})
    assert sides == {1: "left", 0: "bottom"} and out.size == (200, 360)
    assert mirror_halves(img, {})[1] == {} and mirror_halves(img, {1: (0, True)})[0] is img


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
