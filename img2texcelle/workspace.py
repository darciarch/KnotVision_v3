"""Where a run lives: data/<name>/ holds the source image and every output.

`prepare_run` creates data/<name>/ (name = the source file name without
extension) and picks the output names: <name>.tiff / <name>.bmp plus
<name>_palette.txt, or the next free <name>_2, <name>_3, ... when those
exist, so nothing is ever overwritten. `finish_run` then moves the source
image into the folder (only after a successful conversion, so a failed run
leaves the source where it was); a source already inside is left alone.
"""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .output import FORMATS, palette_txt_path


def project_root():
    """The directory holding pyproject.toml (parent of this package)."""
    return Path(__file__).resolve().parents[1]


def data_dir():
    return project_root() / "data"


@dataclass
class RunPaths:
    run_dir: Path      # data/<name>/
    source: Path       # the source image where it is now
    image: Path        # output tiff/bmp
    palette_txt: Path  # output palette text

    @property
    def source_target(self):
        """Where the source image lives after `finish_run`."""
        return self.run_dir / self.source.name


def next_free_name(run_dir, stem, fmt):
    """First (image, palette_txt) pair under run_dir that does not exist yet."""
    ext = FORMATS[fmt][0]
    i = 1
    while True:
        base = stem if i == 1 else f"{stem}_{i}"
        image = run_dir / (base + ext)
        txt = Path(palette_txt_path(str(image)))
        if not image.exists() and not txt.exists():
            return image, txt
        i += 1


def prepare_run(src, fmt, root=None):
    """Create data/<name>/ and pick output names for source `src`."""
    src = Path(src).resolve()
    if not src.is_file():
        raise SystemExit(f"ERROR: source image not found: {src}")
    run_dir = (Path(root) if root else data_dir()) / src.stem
    target = run_dir / src.name
    if src.parent != run_dir and target.exists():
        raise SystemExit(f"ERROR: {target} already exists; remove it or rename the source")
    run_dir.mkdir(parents=True, exist_ok=True)
    image, txt = next_free_name(run_dir, src.stem, fmt)
    return RunPaths(run_dir, src, image, txt)


def finish_run(paths):
    """Move the source image into the run folder. Returns True if it was moved."""
    if paths.source.parent == paths.run_dir:
        return False
    shutil.move(str(paths.source), str(paths.source_target))
    return True


def discard_run(paths):
    """After a failed conversion: remove the run folder if it is empty."""
    try:
        os.rmdir(paths.run_dir)
    except OSError:
        pass
