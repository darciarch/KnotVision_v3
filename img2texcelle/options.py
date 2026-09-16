"""Conversion settings, one object instead of a 20-argument function."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Options:
    width_cm: float
    height_cm: float
    # knot grid: reed/density (points per m across / rows per m along), or
    # points per m^2 (square), or an exact WxH grid
    reed: float | None = None
    density: float | None = None
    points: float | None = None
    grid: tuple[int, int] | None = None
    # yarn colors: fixed palette (uint8 (K, 3)) or up to `colors` auto colors
    colors: int = 8
    palette: np.ndarray | None = None
    merge: float = 12.0          # delta E below which auto colors are merged
    # cleanup
    min_area: int | None = None  # knots; None = 20 mm^2 worth of knots
    specks: int = 0              # knots; 0 = off (shading slivers of a shaded render)
    # geometry
    denoise: int = 0             # median filter size at source resolution, 0 = off
    rotate: bool = True          # rotate 90 deg when image and carpet orientation differ
    fit: str | None = None       # None (error on aspect mismatch) / "crop" / "stretch"
    symmetry: str = "auto"       # auto / none / lr / tb / both
    # output
    fmt: str = "tiff"            # tiff / bmp
    debug_dir: str | None = None
