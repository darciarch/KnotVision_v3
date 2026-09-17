"""Conversion settings, one object instead of a long argument list."""

from dataclasses import dataclass

import numpy as np


@dataclass
class Options:
    width_cm: float
    height_cm: float
    # knot grid: reed / density = points per m across / rows per m along
    reed: float | None = None
    density: float | None = None
    # yarn colors: fixed palette (uint8 (K, 3)) or up to `colors` auto colors
    colors: int = 8
    palette: np.ndarray | None = None
    merge: float = 12.0          # delta E below which auto colors are merged
    # cleanup
    min_area: int | None = None  # knots; None = 20 mm^2 worth of knots
    # symmetry
    symmetry: str = "auto"       # auto / none / lr / tb / both
    # output
    fmt: str = "tiff"            # tiff / bmp
    debug_dir: str | None = None
