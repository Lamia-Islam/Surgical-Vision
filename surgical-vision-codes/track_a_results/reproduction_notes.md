# Reproduction and provenance notes — Track A

This note documents exactly how the Track A numbers in `results.md` are
produced from the code in this repository, and is explicit about one
implementation detail that affects how the replacement-segmentation
accuracy figure should be read.

## Dataset generation

`generate_wounds.py` builds the 45-image benchmark (15 healthy / 15
concerning / 15 critical, filenames `_01`-`_15` per class) under a fixed
NumPy PCG64 seed (`np.random.default_rng(2024)`), via an explicit
`N_PER_CLASS = 15` constant. Regenerating the dataset from this script
reproduces the committed CSVs (`raw_original.csv`, `raw_fixed.csv`)
exactly - verified pixel-for-pixel on `healthy_01.jpg` (contour area
804.5 px^2, solidity 0.1665 under the original pipeline) and confirmed at
the full-dataset level: **3/45 = 6.7%** original-pipeline accuracy.

## Original segmentation

`abcde_analyzer.preprocess` (grayscale, Gaussian blur, adaptive threshold,
morphological close/open) is run unmodified. Its 6.7% (3/45) accuracy is
directly and exactly reproducible from the committed code with no free
parameters.

## Replacement segmentation - implementation provenance

`preprocess_fixed()`, in `surgical_vision/compare_segmentation.py`,
implements the color-distance method described in `results.md`: HSV
conversion, background color sampled from the four image corners,
Euclidean HSV-distance thresholded via Otsu, then a close-then-open
morphological pass to remove thin high-frequency clutter (sutures) while
preserving the wound blob.

The method description leaves some implementation choices unspecified
(mean vs. median for the corner-sampled background color, exact patch
size, exact morphological kernel size and iteration counts). Because of
this, the four free parameters (`CORNER_PATCH_PX = 20`,
`MORPH_KERNEL = 13`, `CLOSE_ITERS = 2`, `OPEN_ITERS = 1`) were selected by
grid search against the one number-level reference point available: the
reported `healthy_01.jpg` result (area 25,225 px^2, solidity 0.9735). The
resulting implementation reaches area 25,236 px^2, solidity 0.971 on that
image - within 0.04% of the reference, not a bit-for-bit match.

**Why this matters for how to read the 64.4% figure:** the algorithm
(HSV distance + Otsu + morphology) is specified and run independently; the
specific parameter values were fit to match one known target measurement
rather than chosen a priori. The 45-image accuracy that follows from this
implementation should be read as "this algorithm, with parameters
consistent with the one available reference point" rather than as an
untuned, independently-arrived-at result. Anyone re-deriving the same
algorithm from the prose description with different reasonable choices
(e.g., mean instead of median for the background color) may get a
slightly different accuracy figure; a 1-image swing (28<->29 out of 45) is
within the range that plausible parameter choices produce.

## Result

Running both pipelines end-to-end on the 45-image benchmark via
`compare_segmentation.py` gives:
- Original: 3/45 = 6.7%
- Replacement: 29/45 = 64.4%

Healthy and critical classes are cleanly separated (14/15 and 15/15
correct respectively). All 15 concerning-class images are predicted as
"healthy" - see `results.md` for the threshold-calibration explanation of
this failure mode.

**This is the figure reported in `results.md` and the manuscript: 6.7% ->
64.4%, n=45.** It is the one that reproduces directly from the code
committed in this repository via `compare_segmentation.py`.
