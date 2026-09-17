"""vote.resize_alpha: bit-identical to PIL's BOX resize of the whole source,
and a crop of the source gives the same knots as the whole (PIL's own box
argument is single precision and flips exact ties)."""

import math

import numpy as np
from PIL import Image

from img2texcelle.vote import resize_alpha


def pil_box(a, size):
    return np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(a[..., c]), "F")
                                .resize(size, Image.Resampling.BOX)) for c in range(a.shape[-1])], -1)


def test_resize_alpha_matches_pil_and_is_crop_independent():
    rng = np.random.default_rng(1)
    # 5082 rows onto 1500 knots: a knot boundary falls on a half pixel every
    # 250 rows (the real design's render), the exact-tie case
    for (w, h, pw, ph) in ((200, 5082, 47, 1500), (3388, 120, 794, 30), (400, 600, 79, 150)):
        a = rng.random((h, w, 2)).astype(np.float32)
        a[..., 1] = a[..., 0] > 0.5  # a binary coverage map ties exactly
        whole = resize_alpha(a, (pw, ph))
        assert np.array_equal(whole, pil_box(a, (pw, ph)))
        sx, sy = w / pw, h / ph
        for (kx0, kx1, ky0, ky1) in ((0, pw - pw // 2 + 20, 0, ph - ph // 2 + 20),
                                     (pw // 2 - 20, pw, ph // 2 - 20, ph), (pw // 10, pw // 5, ph // 6, ph // 2)):
            kx0, kx1, ky0, ky1 = max(kx0, 0), min(kx1, pw), max(ky0, 0), min(ky1, ph)
            X0, Y0 = math.floor(kx0 * sx), math.floor(ky0 * sy)
            X1, Y1 = min(math.ceil(kx1 * sx), w), min(math.ceil(ky1 * sy), h)
            part = resize_alpha(np.ascontiguousarray(a[Y0:Y1, X0:X1]), (kx1 - kx0, ky1 - ky0),
                                (sx, sy), (kx0, ky0), (X0, Y0), (w, h))
            assert np.array_equal(part, whole[ky0:ky1, kx0:kx1]), (w, h, kx0, kx1, ky0, ky1)


def test_pil_box_argument_is_not_exact():
    """Why resize_alpha exists: the same rows through PIL's fractional box differ."""
    rng = np.random.default_rng(1)
    a = rng.random((5082, 40)).astype(np.float32)
    im = Image.fromarray(a, "F")
    whole = np.asarray(im.resize((10, 1500), Image.Resampling.BOX))
    part = np.asarray(im.resize((10, 770), Image.Resampling.BOX, box=(0, 0, 40, 770 * 5082 / 1500)))
    assert not np.array_equal(part, whole[:770])
    assert set(np.unique(np.nonzero(part != whole[:770])[0]).tolist()) <= {124, 125}
