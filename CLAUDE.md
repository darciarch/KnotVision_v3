# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`img2texcelle` (a Python package, run as `python -m img2texcelle`) converts a finished carpet design image (jpg/png) into an indexed TIFF or BMP for Texcelle (carpet/weaving CAD). Every palette entry is one yarn, and every pixel is one knot/point. So the output must contain only palette colors, with no speckles, no one-pixel noise, and no in-between blend colors at edges. The user judges results by zooming into the output, and they communicate in Turkish.

Every run lives in `data/<name>/` (name = source file name without extension): the source image is **moved** there, and `<name>.tiff` / `<name>.bmp` plus `<name>_palette.txt` are written next to it. A second run on the same image writes `<name>_2.*`, then `_3`, ...; nothing is ever overwritten. `data/` is gitignored.

## The real loom (ground truth)

`data/real_design/003_200X300_397X50_X.zip` (and the unpacked `.bmp`) holds a real, weave-ready Texcelle design for a 200×300 cm carpet. Everything the tool produces should look like it:

- **Grid**: 793×1501 knots = reed 397 points/m across × 500 rows/m along ("397X50" = 50 rows per 10 cm), ≈198 500 points/m². A knot is 2.52×2.00 mm, **not square**. `--reed 397 --density 500` gives 794×1500; `--grid 793x1501` forces the exact size of an existing file.
- **Header**: BMP pels-per-meter = 15630/19685, i.e. Texcelle writes reed/density into the resolution fields as if they were dpi (PIL reads `dpi == (397, 500)`). The tool writes the same (`dpi=(ppm_x, ppm_y)`) for BMP and TIFF.
- **Palette**: index 0 is black and unused; yarns are indices 1..15. The tool reserves index 0 the same way; `<name>_palette.txt` starts at 1.
- **Style**: flat symbolic colors, no shading; pixel art where 21% of all knots lie in 1-knot-wide strokes and 44% of the 10 314 connected components are under 20 knots. So any "thinner than 3 knots is noise" rule destroys the design; the default `--min-area` is 20 mm² worth of knots (4 at 397×500).
- **Source discipline**: all sources are now Gemini renders like `data/sonGemini_Generated_Image_t4zyvst4zyvst4zy.jpeg` (1696×2528, 2:3, ~2.1 source px per knot at 397×500). A source must be flat-colored (no shadows, gradients, bevels), have the carpet's aspect ratio (2:3, or knot-proportioned 793:1501) and be finer than the knot grid; best is 2 px per knot (1586×3002). A source coarser than the knot grid is an error (the old "regions + lines" path for small soft JPEGs was removed on 2026-09-16). Shaded renders turn bevels into same-hue slivers; `--specks 12` is the opt-in remedy, the honest answer is a flat source.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"   # pillow, numpy, scipy (+ pytest); Arch: system pip is blocked

# real loom quality: reed (points per m across) / density (rows per m along); the loom's yarn colors are known, so pass them
.venv/bin/python -m img2texcelle design.jpg --width 200 --height 300 --reed 397 --density 500 --palette "#510A15,#FEF7D4,#D5A556,#774133"
# shaded Gemini render: also erase same-hue shadow/highlight slivers (opt-in), BMP output
.venv/bin/python -m img2texcelle render.jpg --width 200 --height 300 --reed 397 --density 500 --palette "#530C17,#FDECC7,#C49B66,#341D0E,#614027" --specks 12 --format bmp
# exact knot grid of an existing Texcelle file (reed/density only fill the header)
.venv/bin/python -m img2texcelle design.jpg --width 200 --height 300 --grid 793x1501 --reed 397 --density 500 --palette ...
# auto palette (upper bound on yarns; at loom quality it misses yarns used only for 1-knot lines)
.venv/bin/python -m img2texcelle design.jpg --width 200 --height 300 --reed 397 --density 500 --colors 8
# image/carpet aspect mismatch is an error unless --fit crop (center crop) or --fit stretch is given

.venv/bin/python -m pytest          # smoke test on a synthetic design + data/<name>/ folder rules

# split a design into halves/quarters on its mirror axes (mirror-symmetric designs only need one part)
.venv/bin/python -m img2texcelle.split data/design.jpg --parts 2 --axis lr    # left/right halves (tb = top/bottom)
.venv/bin/python -m img2texcelle.split data/design.jpg --parts 4 --keep tl    # only the top-left quarter (tl,tr,bl,br)
.venv/bin/python -m img2texcelle.split data/design.jpg --parts 2 --axis tb --symmetric   # cut on the real mirror axis (medallion off centre: parts differ in size)
```

`img2texcelle.split` writes lossless PNGs to `data/cropped_images/<name>/<name>_<part>.png`, one folder per source image; a later run on the same image adds to that folder with `_2`, `_3`, ... (nothing is ever overwritten) and the source is left where it is. `--keep` is a comma-separated list of part names (default all). The cut is at the geometric centre; an odd side puts its middle pixel row/column into both parts (a warning is printed), so the parts have the same size. `--symmetric` measures the real mirror axis of each cut axis with `symmetry.measure_axis` (the same measurement the pipeline uses, see step 1) and cuts there: each part runs from the axis to its own edge, so nothing is cropped and the parts differ in size when the axis is off centre (fom: top 3392×2400, bottom 3392×2656; a pixel row/column on the axis goes into both parts). An axis with contrast > 0.7 is not trusted: the warning names the best candidate and the `--shift DX,DY` that forces it, and the cut stays at the centre. `--shift DX,DY` sets the axes by hand (`measure_axis` sign convention: the axis is DX/2 px right and DY/2 px down of the centre; fom top/bottom = `--shift 0,-256`).

Tuning flags: `--merge` (delta E for merging auto colors), `--min-area` (knots; default 20 mm² of knots: 4 at 397×500), `--specks` (knots; default 0 = off: repaint same-hue islands below this size that one color encloses; 12 at 397×500; erases ~1% of real same-hue details on the real design, hence opt-in), `--symmetry` (`auto` / `none` / `lr` / `tb` / `both`, default `auto`: the left/top half of a mirror-symmetric design is copied onto the other, so opposite motifs are identical; halves that match everywhere are also decided from both together; forced modes use the measured axis position), `--fit` (`crop` / `stretch`), `--grid` (WxH), `--points` (points per m², square), `--denoise` (median size, default off, breaks 1 px lines), `--no-rotate`, `--format` (`tiff` / `bmp`, default `tiff`), `--debug-dir` (writes `regions.png`, the label map before cleanup).

A run on a 1696×2528 render at 397×500 takes ~60 s.

## Layout

```
img2texcelle/
  cli.py        argparse -> Options, data/<name>/ via workspace, convert()
  options.py    Options dataclass (all settings)
  workspace.py  data/<name>/: move the source, pick <name>[_N].tiff/bmp + _palette.txt
  pipeline.py   convert(src, dst, opts): the steps below, ~100 lines of orchestration
  grid.py       compute_pixels (knot grid + header ppm), knot size, rotate/aspect fit, source scale check
  symmetry.py   mirror_error, measure_axis, describe_axis, crop_to_axis, find_and_centre, mirror_average, mirror_copy
  color.py      rgb_to_lab, parse_palette, flat_mask, auto_palette (k-means), smooth_chroma
  unmix.py      unmix (two-color coverage fractions), blend_pairs, unmix_thin_blends
  vote.py       resize_alpha (BOX), directional_mean, straighten_runs, vote_knots
  cleanup.py    remove_islands, remove_shading_specks
  output.py     save_indexed (TIFF/BMP, index 0 reserved, dpi = ppm), write_palette_txt
  split.py      python -m img2texcelle.split: 2/4 parts cut on the mirror axes -> data/cropped_images/<name>/ (own argparse)
tests/          test_smoke.py (synthetic 2:3 design end to end), test_workspace.py, test_split.py, test_symmetry.py
```

## Pipeline (`pipeline.convert`)

The source is finer than the knot grid, so every knot takes the yarn covering most of its area. The order matters:

1. **Orientation, symmetry, aspect** (`grid.rotate_to_carpet`, `symmetry.find_and_centre`, `grid.fit_to_carpet`, `grid.source_scale`). If the image and the carpet have different orientations, rotate the image 90°. `symmetry.measure_axis` (shared with `img2texcelle.split --symmetric`) finds the mirror axis of each direction: on the greyscale reduced up to 8× (≥ 128 px on the short side) every axis position within ±25% of the size is tried, comparing only the rows within ±15% of the size around the candidate axis (the rows that meet at the cut; nothing wraps around), then refined at full resolution. Two numbers come out. `contrast` = error at the best axis / best error more than 32 px away (0 = perfect mirror, 1 = flat curve, no axis); an axis counts when it is below 0.7 (measured 2026-09-17: real design 0.00, WhatsApp scan 0.16, fom render 0.12 left/right and **0.57 top/bottom** with its medallion 128 px above the centre, Gemini quarter renders with no symmetry 0.79–0.99). `match` = whole-image error at that axis / error of a 32 px shift (the old whole-image criterion): below 0.35 the halves match everywhere (real design 0.00–0.02, Gemini left/right 0.07–0.27), otherwise only near the axis (fom top/bottom 1.12: the crowns and corner motifs were drawn 100+ px from their mirror positions). Whole-image matching alone could never find the fom axis, which is why the first version of this step failed on it. An off-centre axis is cropped to the centre of the knot grid (`crop_to_axis`; fom becomes 3392×4800, so the ratio check then needs `--fit stretch` or `--fit crop`: Gemini drew the halves with different heights, one of them has to give). A taken axis acts in two places: after cleanup the left/top half is copied onto the right/bottom (`mirror_copy`), which makes opposite motifs bit-identical (without it a Gemini output matched its own mirror on only 93.8% of the knots); when the halves also match everywhere (`match` < 0.35) the knot-grid coverage maps are first averaged with their mirror (`mirror_average`), never when they match only near the axis (that would blend the two different crowns into ghosts). `--symmetry lr/tb/both` force an axis at its measured position; an unclear forced axis (contrast > 0.7) stays at the centre with a warning. Caveat: a motif present on one side only is lost to the copy; use `--symmetry none` or force only the right axis. The image ratio must match the carpet ratio in cm or the knot-grid ratio within 2%, otherwise `--fit crop` / `--fit stretch` or an error. `compute_pixels` gives the knot grid plus the points per meter written into the header. `scale = sqrt(sx*sy)` = source px per knot must be > 1, otherwise an error.
2. **Optional median denoise.** Off by default because it breaks 1 px lines.
3. **Palette** (`color.auto_palette`, unless `--palette`). k-means in Lab, fit only on `flat_mask` pixels (low 3×3 contrast), so edge blends never become palette entries. Near-duplicate clusters are merged (`--merge`) and tiny ones dropped. At loom quality always pass `--palette`: with `--colors 15` the real-design round trip gives only 71%, because yarns used only for 1-knot lines and yarns within `--merge` of each other never enter the palette.
4. **Coverage unmixing** (`color.smooth_chroma` + `unmix.unmix` + `unmix.unmix_thin_blends`). a/b are smoothed with a joint bilateral filter guided by L (JPEG chroma is half resolution). Then every pixel is explained as one pure yarn color or a mix of two (the Lab segment passing closest), giving coverage fractions `alpha` per color; pure wins unless a mix is better by 3 ΔE. `unmix(..., reach=ceil(scale))` only allows a pair where both colors occur as nearest pure color within `reach` px: without this, with 15 yarns, a slightly desaturated magenta line was explained as 30% purple + 70% orange and the round trip dropped from 98% to 94%. `unmix_thin_blends` then unmixes thin strips of an in-between color (grey lies between blue and cream) that are not attached to a wide area of it into the two colors it blends; skipping it raised stroke errors from 19% to 34% on a non-integer-scale render (blurred 1-knot lines look like an in-between color).
5. **Coverage vote** (`vote.vote_knots`). `alpha` is resized to the knot grid with BOX (exact area average; bilinear blurred 2 px lines into their 2 px gaps), so every knot holds the fraction of its area covered by each yarn ("soft" coverage), and argmax'ed. Soft coverage beats the majority of one-hot pixel labels ("hard") on the round trip: 98.8% vs 98.2% at 2 px/knot, 99.3% vs 97.8% at a non-integer scale. Then `straighten_runs`: a straight band edge or a thin line that straddles a knot row covers every knot on that row by about half, so the per-knot argmax flips with JPEG noise and a straight edge came out jagged (the top border band of a Gemini render started on row 1 in 440 columns and row 2 in 254). Knots whose `directional_mean` (mean along the orientation of least variation) is undecided (max < 0.6, own coverage < 0.85 so clean dots and strokes are never touched) are grouped into runs along that orientation, and every run of ≥ 15 knots takes the majority of the *hard* coverage over the run (the soft mean ties on a line straddling two rows evenly). Cost on the round trip: 0.25% at 2 px/knot, none at the non-integer scale; min_run 9 costs 0.5%.
6. **Cleanup** (`cleanup.remove_islands`, then `remove_shading_specks` if `--specks`, then `mirror_copy`). Components smaller than `--min-area` take the most common color in their 1-knot ring, repeated until nothing changes (on the real design `remove_islands(4)` touches only 494 of 1.19 M knots). Don't add a mode filter or bump smoothing here: on a real loom grid the corner knot of every 1-knot diagonal staircase has 3 foreign neighbours, and `smooth_bumps` erased 3% of the real design.
7. **Output** (`output.save_indexed`, `write_palette_txt`). 8-bit `P` mode TIFF or BMP, uncompressed, index 0 reserved (black, unused) and yarns from 1, resolution fields = points per meter, plus `<name>_palette.txt` with one line per yarn: `index\tR\tG\tB\t#RRGGBB`. Keep both formats stable, because Texcelle consumes them.

## Verification

There is a small pytest suite (synthetic design end to end, folder rules), but the real defects are visual and numeric:

- **Look at the output**: crop the same region from the source (resized to the knot grid with BOX) and from the output, scale both up with NEAREST, compare side by side. On a Gemini render check a corner, the medallion and the top border band (straightness), and that the left and right halves are identical. Also check that the output has no connected components smaller than `--min-area` (8-connectivity, `scipy.ndimage.label`).
- **Round trip on the real design** (one number per change): render `data/real_design/003_200X300_397X50_X.bmp` as flat RGB at 2 px per knot (`convert("RGB").resize((1586, 3002), NEAREST)`, Gaussian blur 0.7, JPEG q90) and at a non-integer scale (`resize((1792, 2688), LANCZOS)`, JPEG q92); convert both with `--grid 793x1501 --reed 397 --density 500 --palette <the 15 colors of the real BMP palette>`; map output indices to the real palette by nearest RGB and count matching knots, separately for knots on 1-knot strokes (pixels failing a 2×2 opening). Levels on 2026-09-16 (also after the package refactor, which is pixel-identical to the old script): 98.71% (2 px/knot) and 99.29% (non-integer), stroke errors 5.8% / 2.9%, errors elsewhere ≤ 0.1%. The real design is mirror-symmetric both ways with halves that match everywhere, so `--symmetry auto` averages and copies there; `--symmetry none` measures the vote alone (98.6 / 99.3).
- **Off-centre axis on a Gemini render**: `data/fomggggggbro/fomggggggbro.jpg` (3392×5056, medallion 128 px above the centre) with `--reed 397 --density 500 --palette` from its `_palette.txt` `--format bmp --fit stretch` must print the top/bottom axis at row 2399.5 (contrast 0.57, copy only), the left/right axis at the centre (contrast 0.12, average + copy), and give an output that is mirror-symmetric both ways with no ghost motifs at the crowns (reference: `fomggggggbro_3.bmp`, 2026-09-17). `python -m img2texcelle.split ... --parts 2 --axis tb --symmetric` on the same image gives a 3392×2400 top and a 3392×2656 bottom part, and the top part mirrored at its bottom edge lines up with the medallion. The three Gemini quarter renders in `data/cropped_images/fomggggggbro/` must be rejected on both axes (contrast ≥ 0.79).
- **Regression on a Gemini render**: `data/sonGemini_Generated_Image_t4zyvst4zyvst4zy.jpeg` with `--reed 397 --density 500 --palette "#510A15,#FEF7D4,#D5A556,#774133" --specks 12` (and once with `--colors 8`) should stay pixel-identical to the previous output unless the change is meant to alter it; keep a copy of the previous output before touching the vote or cleanup.

Every earlier change in the vote logic fixed one region and broke another, so always look at all regions and run the round trip.

## Things tried and rejected

- Unsharp mask after LANCZOS upscaling: creates fake outlines along edges.
- RGB resize followed by quantization: gives fringe pixels of a third color between two yarns.
- Per-pixel nearest-color labeling + island removal: thin lines break into beads.
- Ridge/skeleton line detection (the old path B for coarse sources) run at source resolution and rasterized onto the knots: round trip 78% vs 98%; it fattens 1-knot lines in dense pixel art and adds highlight specks on shaded renders. Removed on 2026-09-16 together with the outline-color logic and `scikit-image`.
- A per-knot "coherent vote" (replace ambiguous knots by the 9-knot directional mean): −1.5% round trip, because straddling 1-knot lines tie in both rows.
- Gaussian smoothing of the source coverage: blurs 2 px lines into their gaps.
- `smooth_bumps` / mode filters on the knot grid: erase the corners of 1-knot diagonal staircases (3% of the real design).
- Averaging the four quadrants of a both-ways symmetric design does not always pick the best one, but exact symmetry is what the weaver notices first.
