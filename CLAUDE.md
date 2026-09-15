# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`img2texcelle.py` converts a finished carpet design image (jpg/png) into an indexed TIFF for Texcelle (carpet/weaving CAD). Every palette entry is one yarn, and every pixel is one knot/point. So the output must contain only palette colors, with no speckles, no one-pixel noise, and no in-between blend colors at edges. The user judges results by zooming into the TIFF, and they communicate in Turkish.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # pillow, numpy, scipy, scikit-image (Arch: system pip is blocked)

# square density (points per m^2)
.venv/bin/python img2texcelle.py data.jpg --width 200 --height 300 --points 1000000 --colors 8
# reed / density (points per m horizontally / vertically)
.venv/bin/python img2texcelle.py data.jpg --width 200 --height 300 --reed 1000 --density 1200 --colors 8
# fixed yarn colors instead of an auto palette
.venv/bin/python img2texcelle.py data.jpg ... --palette "#F9F6E8,#5D757C,#6A5C4E"
# keep the dark contour lines as a 5th yarn instead of erasing them
.venv/bin/python img2texcelle.py data.jpg ... --outline-mode keep
```

Tuning flags: `--merge` (delta E for merging auto colors), `--min-area` (px), `--outline` (`auto` / `none` / hex colors), `--outline-mode` (`drop` / `keep`), `--line-width` (0 = measured), `--no-lines`, `--denoise` (median size, default off), `--no-rotate`, `--out`, `--debug-dir` (writes `regions.png` and `lines.png`, the label maps before and after line drawing).

A full run on `data.jpg` takes ~45 s.

There is no test suite. Verify changes by looking at the output: crop the same region from the source and from the TIFF, scale both up with NEAREST, and compare them side by side (good regions to check on `data.jpg`, in output coordinates: border `(1741,1528)+222×199`, field `(1443,2304)+238×144`, medallion `(1330,1330)+240×160`, center `(900,1400)+240×160`). Also check that the TIFF has no connected components smaller than `--min-area` (8-connectivity, via `scipy.ndimage.label`). Checking only numbers is not enough, because the defects are visual. Every change in the line logic so far has fixed one region and broken another, so always look at all of them.

## Pipeline (`convert()`)

The design is treated as **regions + thin lines**, not as independent pixels. The source has ~1 source px = 2 knots, and the design's lines (brown border lines, blue tendrils, dark contours) are 1 source px wide, so per-pixel nearest-color labeling broke them into beads and left brown/grey specks. The order matters:

1. **Orientation.** If the image and the carpet have different orientations, rotate the image 90°, then warn about any remaining aspect mismatch. `compute_pixels()` gives the target grid: cm / 100 × points per meter.
2. **Optional median denoise.** Off by default because it breaks 1px lines.
3. **Palette** (`auto_palette`). k-means in Lab, fit only on `flat_mask` pixels (low 3×3 contrast), so edge blends never become palette entries. Near-duplicate clusters are merged (`--merge`) and tiny ones dropped. `--colors` is an upper bound. `auto_outline` then takes pixels clearly darker than the darkest yarn (they only exist on thin contours and line cores) and splits them into up to two dark colors (on `data.jpg`: a neutral/bluish one and a warm one). These outline colors are never region colors.
4. **Coverage unmixing** (`smooth_chroma` + `unmix` + `unmix_thin_blends`). a/b are smoothed with a joint bilateral filter guided by L (JPEG chroma is half resolution). Then every pixel is explained as one pure region color or a mix of two (the Lab segment passing closest), giving coverage fractions `alpha` per color; pure wins unless a mix is better by 3 ΔE, so wide areas of an in-between color (grey lies between blue and cream) stay that color. Thin strips of an in-between color that are not attached to a wide area of it, or that touch both colors it blends, are unmixed into those two colors. Dense clusters of thin strips (hatching) are left alone. Outline colors are **not** in this unmixing: a blurred blue line is desaturated and would be explained as dark+cream.
5. **Resize the coverage maps** (`resize_alpha`), never the RGB image.
6. **Regions.** argmax of lightly smoothed coverage. Then holes: parts thinner than 3 knots (3×3 opening), plus line-like strips thinner than 5 knots (5×5 opening where `lineness` > 0.15), are removed and refilled from the nearest remaining pixel (`fill_holes`). Lines are redrawn in the next step; leaving the region fragments produced beaded lines and cream halo slivers next to brown outlines.
7. **Lines** (`detect_lines` → `classify_lines` → `thicken`). Per coverage map (region colors and outline colors): scale-normalised Hessian ridge strength at σ 1.5/2.5, gated by `lineness` (the pixel must stand above both sides in some direction; this rejects the edges of wide areas, which otherwise became saw-tooth borders) and followed with hysteresis so a line blurred below 50% stays in one piece. Skeletonize, prune spurs ≤ 6 px (wedge-shaped strips gave branchy "4"-shaped lines), drop pieces < 12 px, and measure each line's width as the coverage integral across it (blur-invariant). Then every connected line gets **one** color: its mean source color is fitted as `background + s·(color − background)` where the background is the mean region color on a ring 3–4 px out (taken from the region labels, so a neighbouring parallel line cannot leak in). `s` comes from L only, because JPEG loses the chroma of thin lines; the a/b shift only needs the right direction with attenuation ratio in [0.35, 1.5] (a candidate that needs *more* chroma than observed is penalised, and for tiny predicted shifts the ratio is shrunk to 1). In-between colors get +4, outline colors get −3 when the ring holds two region colors (dominance < 0.8) and +4 when the line runs inside one color; this is what keeps blue tendrils in cream from being called "dark contour" and dark contours on cream/blue boundaries from being called brown. A region-color line whose skeleton lies ≥ 60% under an outline-classified line is a duplicate and is dropped. Lines are stamped at their width, highest ridge strength wins. `--outline-mode drop` (default) erases contour lines (neighbours close over them); `keep` draws them as one extra yarn — on `data.jpg` that looked messy in the medallion because brown outline cores are as dark as the contour.
8. **Cleanup** (`remove_islands` → `smooth_bumps` → `remove_islands`). Components smaller than `--min-area` (default 20 px) take the most common color in their 1px surrounding ring, repeated until nothing changes. After that, one pass repaints any pixel whose 4-neighbors include at least 3 of one other color. Don't use a mode filter here: it erodes thin lines.
9. **Output.** 8-bit `P` mode TIFF, uncompressed, plus `<out>_palette.txt` with one line per used color: `index\tR\tG\tB\t#RRGGBB`. Keep both formats stable, because Texcelle consumes them.

## Things tried and rejected

- Unsharp mask after LANCZOS upscaling: creates fake blue/brown outlines along grey/cream edges.
- RGB LANCZOS resize followed by quantization: gives brown or grey fringe pixels between blue and cream.
- Per-pixel nearest-color labeling + island removal (the previous pipeline): thin lines break into beads, dark contours become brown specks, cream halos become slivers.
- Including the outline color in the pixel unmixing: it steals every blurred blue line.
- Deciding "contour vs design line" by geometry alone (different region colors on the two sides): brown arcs next to blue shapes and blue tendrils touching blue blobs are also two-sided, so they got erased. It only works as a bonus/penalty on top of the color fit.
- Ridge detection without the `lineness` gate: region edges become saw-toothed.

## Input caveat

The sample `data.jpg` is a soft 1531×980 JPEG that gets upscaled about 2× for a 200×300 cm carpet at 1000 points per meter. Fine hatching and 1px details cannot be recovered cleanly from it, and a higher-resolution or vector source helps more than any tuning. Known remaining flaws on it: hatched (grey/brown) leaves become plain grey blobs, and the light gap between the double rings in the medallion is drawn as a clumsy cream wedge.
