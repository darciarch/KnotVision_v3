"""symmetry.measure_axis / find_and_centre: axes off centre, axis-only symmetry."""

import numpy as np
from PIL import Image

from img2texcelle.symmetry import (AXIS_CONTRAST, EXACT_MATCH, crop_to_axis, describe_axis,
                                   find_and_centre, measure_axis, mirror_error)

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


def test_find_and_centre_modes(capsys):
    img = band_only_image()
    out, copy_lr, copy_tb, avg_lr, avg_tb = find_and_centre(img, "auto")
    assert (copy_lr, copy_tb, avg_lr, avg_tb) == (False, True, False, False)
    assert out.size == (200, 240)  # 60 px cropped from the bottom
    assert "copy only" in capsys.readouterr().out
    # forced: the measured axis is used, not the centre; an unclear forced
    # axis stays at the centre
    out, copy_lr, copy_tb, avg_lr, avg_tb = find_and_centre(img, "both")
    assert (copy_lr, copy_tb, avg_lr, avg_tb) == (True, True, False, False)
    assert out.size == (200, 240) and "warning: no clear left/right" in capsys.readouterr().out
    assert find_and_centre(img, "none")[1:] == (False, False, False, False)
    # an exact mirror is averaged as well
    exact = off_centre_image(160, 240, 3, 2)
    out, *flags = find_and_centre(exact, "auto")
    assert flags == [True, True, True, True] and out.size == (160, 240)
    assert out.tobytes() == crop_to_axis(exact, -3, -2).tobytes()


def test_describe_axis():
    assert describe_axis(0, 5056, -256) == "at row 2399.5 (128 px above the centre)"
    assert describe_axis(1, 3392, 0) == "at column 1695.5 (at the centre)"
    assert describe_axis(1, 10, 3) == "at column 6 (1.5 px right the centre)"
