# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`img2texcelle.py` converts a finished carpet design image (jpg/png) into an indexed TIFF or BMP for Texcelle (carpet/weaving CAD). Every palette entry is one yarn, and every pixel is one knot/point. So the output must contain only palette colors, with no speckles, no one-pixel noise, and no in-between blend colors at edges. The user judges results by zooming into the TIFF, and they communicate in Turkish.

## The real loom (ground truth)

`003_200X300_397X50_X.zip` holds a real, weave-ready Texcelle design for a 200×300 cm carpet. Everything the tool produces should look like it:

- **Grid**: 793×1501 knots = reed 397 points/m across × 500 rows/m along ("397X50" = 50 rows per 10 cm), ≈198 500 points/m². A knot is 2.52×2.00 mm, **not square**. `--reed 397 --density 500` gives 794×1500; `--grid 793x1501` forces the exact size of an existing file.
- **Header**: BMP pels-per-meter = 15630/19685, i.e. Texcelle writes reed/density into the resolution fields as if they were dpi (PIL reads `dpi == (397, 500)`). The tool writes the same (`dpi=(ppm_x, ppm_y)`) for BMP and TIFF.
- **Palette**: index 0 is black and unused; yarns are indices 1..15. The tool reserves index 0 the same way; `<out>_palette.txt` starts at 1.
- **Style**: flat symbolic colors (pink, orange, purple...), no shading; pixel art where 21% of all knots lie in 1-knot-wide strokes, 38% fail a 3×3 opening and 44% of the 10 314 connected components are under 20 knots. So at this quality `--min-area 20` and any "thinner than 3 knots is noise" rule destroy the design; the defaults now scale with knot size (see below).
- **Source discipline**: the source must be a flat-colored design (no shadows, gradients, bevels), have the carpet's aspect ratio (2:3, or knot-proportioned 793:1501), and its thinnest line should be ≥ 1 knot (≈4.5 px at 1792 px width). Best: render it at 2 px per knot (1586×3002) or directly on the knot grid. The Gemini renders in this folder (`wrxf4q...jpeg`, 1792×2390, 3:4, shaded) violate all three, which is where the lattice shadows turning into grey blobs and the 12.5% vertical stretch came from.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # pillow, numpy, scipy, scikit-image (Arch: system pip is blocked)

# real loom quality: reed (points per m across) / density (rows per m along)
.venv/bin/python img2texcelle.py design.jpg --width 200 --height 300 --reed 397 --density 500 --colors 8
# exact knot grid of an existing Texcelle file (reed/density only fill the header)
.venv/bin/python img2texcelle.py design.jpg --width 200 --height 300 --grid 793x1501 --reed 397 --density 500
# square density (points per m^2)
.venv/bin/python img2texcelle.py data.jpg --width 200 --height 300 --points 1000000 --colors 8 --fit stretch
# image/carpet aspect mismatch is an error unless --fit crop (center crop) or --fit stretch is given
# fixed yarn colors instead of an auto palette
.venv/bin/python img2texcelle.py data.jpg ... --palette "#F9F6E8,#5D757C,#6A5C4E"
# keep the dark contour lines as a 5th yarn instead of erasing them
.venv/bin/python img2texcelle.py data.jpg ... --outline-mode keep
# BMP instead of TIFF (also picked automatically from --out design.bmp)
.venv/bin/python img2texcelle.py data.jpg ... --format bmp
```

Tuning flags: `--merge` (delta E for merging auto colors), `--min-area` (knots; default 20 mm² of knots: 20 at 1M points/m², 4 at 397×500), `--fit` (`crop` / `stretch`), `--grid` (WxH), `--outline` (`auto` / `none` / hex colors), `--outline-mode` (`drop` / `keep`), `--line-width` (0 = measured), `--no-lines`, `--denoise` (median size, default off), `--no-rotate`, `--out`, `--format` (`tiff` / `bmp`; default from the `--out` extension, else `tiff`; a mismatch is an error), `--debug-dir` (writes `regions.png` and `lines.png`, the label maps before and after line drawing).

A full run on `data.jpg` takes ~45 s; `wrxf4qwrxf4qwrxf.jpeg` at 397×500 takes ~60 s.

There is no test suite. Verify changes by looking at the output: crop the same region from the source and from the TIFF, scale both up with NEAREST, and compare them side by side (good regions to check on `data.jpg`, in output coordinates: border `(1741,1528)+222×199`, field `(1443,2304)+238×144`, medallion `(1330,1330)+240×160`, center `(900,1400)+240×160`; on `wrxf4qwrxf4qwrxf.jpeg --reed 397 --density 500 --fit stretch`, resize the source to the knot grid with BOX first: corner `(20,20)-(220,170)`, medallion `(300,620)-(500,770)`, top border `(330,80)-(530,230)`). Also check that the TIFF has no connected components smaller than `--min-area` (8-connectivity, via `scipy.ndimage.label`). Checking only numbers is not enough, because the defects are visual. Every change in the line logic so far has fixed one region and broken another, so always look at all of them.

Two checks that do give numbers:

- **Regression on the upscale path**: `data.jpg --points 1000000 --colors 8 --fit stretch` must stay pixel-identical to the previous output (label map + 1 for the reserved index 0).
- **Round trip on the real-loom path**: render the real design as a flat RGB image at 2 px per knot (`convert("RGB").resize((1586, 3002), NEAREST)`, Gaussian blur 0.7, JPEG q90) and at a non-integer scale (`resize((1792, 2688), LANCZOS)`, JPEG q92), convert both back with `--grid 793x1501 --reed 397 --density 500 --palette <the real 15 colors from the BMP palette>`, map output indices to the real palette by nearest RGB and count matching knots, separately for knots on 1-knot strokes (pixels failing a 2×2 opening). Levels on 2026-09-16: 98.2% (2 px/knot) and 97.8% (non-integer), stroke errors 7–8%, errors elsewhere ≤ 1%. With `--colors 15` instead of `--palette` the same render gives only 71%: k-means only sees flat pixels, so yarns used only for 1-knot lines and yarns within `--merge` of each other never enter the palette. At loom quality always pass `--palette` (the loom's yarn colors are known anyway).

## Pipeline (`convert()`)

The design is treated as **regions + thin lines**, not as independent pixels. The source has ~1 source px = 2 knots, and the design's lines (brown border lines, blue tendrils, dark contours) are 1 source px wide, so per-pixel nearest-color labeling broke them into beads and left brown/grey specks. The order matters:

1. **Orientation and grid.** If the image and the carpet have different orientations, rotate the image 90°. The image ratio must then match the carpet ratio in cm (square pixels) or the knot-grid ratio (one pixel per knot) within 2%; otherwise it is an error unless `--fit crop` / `--fit stretch`. `compute_pixels()` gives the target grid (cm / 100 × points per meter, or `--grid`) plus the points per meter written into the header. `sx, sy` = source px per knot; `down = sqrt(sx*sy) > 1` selects **path A** (real loom quality, source finer than the grid: majority vote, no lines) versus **path B** (`data.jpg` at 1M points/m²: regions + lines, exactly the old pipeline). Steps 6–7 are path B only.
2. **Optional median denoise.** Off by default because it breaks 1px lines.
3. **Palette** (`auto_palette`). k-means in Lab, fit only on `flat_mask` pixels (low 3×3 contrast), so edge blends never become palette entries. Near-duplicate clusters are merged (`--merge`) and tiny ones dropped. `--colors` is an upper bound. `auto_outline` then takes pixels clearly darker than the darkest yarn (they only exist on thin contours and line cores) and splits them into up to two dark colors (on `data.jpg`: a neutral/bluish one and a warm one). These outline colors are never region colors.
4. **Coverage unmixing** (`smooth_chroma` + `unmix` + `unmix_thin_blends`). a/b are smoothed with a joint bilateral filter guided by L (JPEG chroma is half resolution). Then every pixel is explained as one pure region color or a mix of two (the Lab segment passing closest), giving coverage fractions `alpha` per color; pure wins unless a mix is better by 3 ΔE, so wide areas of an in-between color (grey lies between blue and cream) stay that color. Thin strips of an in-between color that are not attached to a wide area of it, or that touch both colors it blends, are unmixed into those two colors. Dense clusters of thin strips (hatching) are left alone. Outline colors are **not** in this unmixing: a blurred blue line is desaturated and would be explained as dark+cream. *Path A*: `unmix(..., reach=ceil(scale))` only allows a pair where both colors occur as nearest pure color within `reach` px. Without this, with 15 yarns, a slightly desaturated magenta line was explained as 30% purple + 70% orange (an exact fit on that Lab segment) and the round trip dropped from 98% to 94%. `unmix_thin_blends` stays on in both paths: skipping it on path A raised stroke errors from 19% to 34% on a non-integer-scale render (blurred 1-knot lines look like an in-between color, and this is what corrects them).
5. **Path A: majority vote.** The source labels (argmax of `alpha`, no smoothing) are one-hot resized to the knot grid with BOX (exact area average; bilinear blurred 2 px lines into their 2 px gaps) and argmax'ed: every knot takes the yarn covering most of it. Then straight to cleanup. Tried and rejected for this path: the ridge/skeleton line path from B run at source resolution and rasterized onto the knots (round trip 78% vs 98%; it fattens 1-knot lines in dense pixel art and adds highlight specks on shaded renders), Gaussian smoothing of the source coverage (blurs 2 px lines), `smooth_bumps` (erases 3% of the real design: the corner knot of every 1-knot diagonal staircase). *Path B*: resize the coverage maps (`resize_alpha`, bilinear) to the knot grid, never the RGB image.
6. **Regions (B).** argmax of lightly smoothed coverage. Then holes: parts thinner than 3 knots (3×3 opening), plus line-like strips thinner than 5 knots (5×5 opening where `lineness` > 0.15), are removed and refilled from the nearest remaining pixel (`fill_holes`). Lines are redrawn in the next step; leaving the region fragments produced beaded lines and cream halo slivers next to brown outlines.
7. **Lines (B)** (`detect_lines` → `classify_lines` → `thicken`). Per coverage map (region colors and outline colors): scale-normalised Hessian ridge strength at σ 1.5/2.5, gated by `lineness` (the pixel must stand above both sides in some direction; this rejects the edges of wide areas, which otherwise became saw-tooth borders) and followed with hysteresis so a line blurred below 50% stays in one piece. Skeletonize, prune spurs ≤ 6 px (wedge-shaped strips gave branchy "4"-shaped lines), drop pieces < 12 px, and measure each line's width as the coverage integral across it (blur-invariant). Then every connected line gets **one** color: its mean source color is fitted as `background + s·(color − background)` where the background is the mean region color on a ring 3–4 px out (taken from the region labels, so a neighbouring parallel line cannot leak in). `s` comes from L only, because JPEG loses the chroma of thin lines; the a/b shift only needs the right direction with attenuation ratio in [0.35, 1.5] (a candidate that needs *more* chroma than observed is penalised, and for tiny predicted shifts the ratio is shrunk to 1). In-between colors get +4, outline colors get −3 when the ring holds two region colors (dominance < 0.8) and +4 when the line runs inside one color; this is what keeps blue tendrils in cream from being called "dark contour" and dark contours on cream/blue boundaries from being called brown. A region-color line whose skeleton lies ≥ 60% under an outline-classified line is a duplicate and is dropped. Lines are stamped at their width, highest ridge strength wins. `--outline-mode drop` (default) erases contour lines (neighbours close over them); `keep` draws them as one extra yarn — on `data.jpg` that looked messy in the medallion because brown outline cores are as dark as the contour.
8. **Cleanup** (`remove_islands`, and on path B `smooth_bumps` → `remove_islands` again). Components smaller than `--min-area` (default 20 mm² worth of knots: 20 at 1M points/m², 4 at 397×500; on the real design `remove_islands(4)` touches only 494 of 1.19 M knots) take the most common color in their 1px surrounding ring, repeated until nothing changes. Path B then repaints any pixel whose 4-neighbors include at least 3 of one other color. Don't use a mode filter here: it erodes thin lines.
9. **Output.** 8-bit `P` mode TIFF or BMP (`--format`), uncompressed, index 0 reserved (black, unused) and yarns from 1, resolution fields = points per meter (`dpi=(ppm_x, ppm_y)`), plus `<out>_palette.txt` with one line per used color: `index\tR\tG\tB\t#RRGGBB`. Keep both formats stable, because Texcelle consumes them.

## Things tried and rejected

- Unsharp mask after LANCZOS upscaling: creates fake blue/brown outlines along grey/cream edges.
- RGB LANCZOS resize followed by quantization: gives brown or grey fringe pixels between blue and cream.
- Per-pixel nearest-color labeling + island removal (the previous pipeline): thin lines break into beads, dark contours become brown specks, cream halos become slivers.
- Including the outline color in the pixel unmixing: it steals every blurred blue line.
- Deciding "contour vs design line" by geometry alone (different region colors on the two sides): brown arcs next to blue shapes and blue tendrils touching blue blobs are also two-sided, so they got erased. It only works as a bonus/penalty on top of the color fit.
- Ridge detection without the `lineness` gate: region edges become saw-toothed.

## Input caveat

The sample `data.jpg` is a soft 1531×980 JPEG that gets upscaled about 2× for a 200×300 cm carpet at 1000 points per meter. Fine hatching and 1px details cannot be recovered cleanly from it, and a higher-resolution or vector source helps more than any tuning. Known remaining flaws on it: hatched (grey/brown) leaves become plain grey blobs, and the light gap between the double rings in the medallion is drawn as a clumsy cream wedge.
