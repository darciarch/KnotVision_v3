"""img2texcelle: convert a flat carpet design image into a Texcelle indexed TIFF/BMP.

One palette entry per yarn, one pixel per knot. See `pipeline.convert` for
the processing steps and `cli.main` for the command line.
"""

from .options import Options
from .pipeline import convert

__version__ = "2.0.0"
__all__ = ["Options", "convert", "__version__"]
