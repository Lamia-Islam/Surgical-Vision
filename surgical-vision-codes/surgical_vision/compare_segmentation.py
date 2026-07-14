"""
compare_segmentation.py
──────────────────────────────────────────────────────────────────────────────
Runs the Track A empirical comparison between the ORIGINAL segmentation
(grayscale adaptive thresholding, abcde_analyzer.preprocess) and the FIXED
segmentation (HSV color-distance from background, Otsu threshold, close-then-
open morphology) described in track_a_results/results.md.

NOTES ON THE FIXED-SEGMENTATION PARAMETERS
The color-distance method (background sampled from image corners, Euclidean
HSV distance, Otsu threshold, close then open) admits a few reasonable
implementation choices that aren't fully pinned down by the method
description alone (e.g. mean vs. median for the sampled background color,
exact patch size, exact morphological kernel/iteration counts). The values
below were chosen by grid search against a single known reference
measurement (contour area on healthy_01.jpg). See
track_a_results/reproduction_notes.md for the full account of this and for
why a ~1-image swing in the 45-image accuracy figure should be expected from
other reasonable parameter choices.

USAGE
    python3 surgical_vision/generate_wounds.py     # build sample_images/ (n=45)
    python3 surgical_vision/compare_segmentation.py

OUTPUT (written to ./track_a_results/)
    raw_original.csv, raw_fixed.csv        - per-image scores for each pipeline
    comparison_results.json                - machine-readable summary
    figures/confusion_matrices.png
    figures/accuracy_comparison.png
    figures/solidity_distributions.png
    figures/debug_contour.png              - original pipeline, healthy_01
    figures/debug_fixed_contour.png        - fixed pipeline, healthy_01
──────────────────────────────────────────────────────────────────────────────
"""

import os
import csv
import json
import glob

import cv2
import numpy as np

import os as _os
import sys as _sys

try:
    from surgical_vision import abcde_analyzer as A
except ImportError:
    # Allow running directly as `python3 surgical_vision/compare_segmentation.py`
    # from the repo root, without installing the package first.
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from surgical_vision import abcde_analyzer as A

SAMPLE_DIR = "sample_images"
OUT_DIR = "track_a_results"
FIG_DIR = os.path.join(OUT_DIR, "figures")

# ─── Fixed segmentation (reconstructed) ───────────────────────────────────────
# Parameters below were grid-searched to minimize the discrepancy against the
# originally reported healthy_01 result (area 25,225 px^2, solidity 0.9735).
CORNER_PATCH_PX = 20
MORPH_KERNEL = 13
CLOSE_ITERS = 2
OPEN_ITERS = 1


def preprocess_fixed(img: np.ndarray):
    """HSV color-distance segmentation vs. background, Otsu threshold,
    close-then-open morphology. See module docstring."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    c = CORNER_PATCH_PX
    corner_pixels = np.concatenate([
        hsv[:c, :c].reshape(-1, 3), hsv[:c, -c:].reshape(-1, 3),
        hsv[-c:, :c].reshape(-1, 3), hsv[-c:, -c:].reshape(-1, 3),
    ], axis=0)
    background_color = np.median(corner_pixels, axis=0)

    dist = np.linalg.norm(hsv - background_color, axis=2)
    dist_u8 = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, mask = cv2.threshold(dist_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL, MORPH_KERNEL))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=CLOSE_ITERS)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=OPEN_ITERS)
    return mask


def verdict_label(total_score: int) -> str:
    """Maps ABCDE total score to the 3-class verdict used for ground-truth
    comparison. Equivalent to abcde_analyzer.determine_verdict, relabeled
    PASS/CAUTION/FAIL -> healthy/concerning/critical."""
    if total_score <= 1:
        return "healthy"
    elif total_score <= 2:
        return "concerning"
    return "critical"


def run_pipeline(use_fixed: bool):
    paths = sorted(glob.glob(os.path.join(SAMPLE_DIR, "*.jpg")))
    if not paths:
        raise SystemExit(
            f"No images in {SAMPLE_DIR}/. Run generate_wounds.py first."
        )

    rows = []
    previous_area = None
    debug_contour_img = None

    for path in paths:
        filename = os.path.basename(path)
        ground_truth = filename.split("_")[0]

        img = cv2.imread(path)
        if img is None:
            continue

        mask = preprocess_fixed(img) if use_fixed else A.preprocess(img)[3]
        contour = A.extract_primary_contour(mask)
        if contour is None or cv2.contourArea(contour) < 200:
            continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        A_score, c_area, h_area = A.score_asymmetry(contour)
        solidity = c_area / h_area if h_area else 0.0
        B_score, _ = A.score_border(gray, contour)
        C_score, _ = A.score_color(img, contour)
        D_score, _ = A.score_diameter(contour)
        E_score, _ = A.score_evolution(c_area, previous_area)
        previous_area = c_area

        total = A_score + B_score + C_score + D_score + E_score
        predicted = verdict_label(total)

        rows.append({
            "file": filename,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "total_score": total,
            "solidity": round(solidity, 4),
            "contour_area": round(float(c_area), 1),
        })

        if filename == "healthy_01.jpg":
            debug_contour_img = draw_debug_contour(img, contour)

    return rows, debug_contour_img


def draw_debug_contour(img, contour):
    out = img.copy()
    cv2.drawContours(out, [contour], -1, (0, 255, 0), 2, cv2.LINE_AA)
    x, y, w, h = cv2.boundingRect(contour)
    cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 1)
    return out


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["file", "ground_truth", "predicted", "total_score",
                           "solidity", "contour_area"]
        )
        writer.writeheader()
        writer.writerows(rows)


def accuracy(rows):
    if not rows:
        return 0.0
    correct = sum(1 for r in rows if r["predicted"] == r["ground_truth"])
    return correct / len(rows)


def make_figures(rows_orig, rows_fixed, dbg_orig, dbg_fixed):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(FIG_DIR, exist_ok=True)
    classes = ["healthy", "concerning", "critical"]

    # Confusion matrices
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, rows, title in [
        (axes[0], rows_orig, "Original (adaptive threshold)"),
        (axes[1], rows_fixed, "Fixed (color-distance segmentation)"),
    ]:
        cm = np.zeros((3, 3), dtype=int)
        for r in rows:
            gt_i = classes.index(r["ground_truth"])
            pr_i = classes.index(r["predicted"])
            cm[gt_i, pr_i] += 1
        im = ax.imshow(cm, cmap="Blues")
        ax.set_xticks(range(3)); ax.set_xticklabels(classes, rotation=45)
        ax.set_yticks(range(3)); ax.set_yticklabels(classes)
        ax.set_xlabel("Predicted"); ax.set_ylabel("Ground truth")
        ax.set_title(title, fontsize=10)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, cm[i, j], ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "confusion_matrices.png"), dpi=150)
    plt.close(fig)

    # Accuracy comparison bar chart
    fig, ax = plt.subplots(figsize=(4.5, 4))
    accs = [accuracy(rows_orig) * 100, accuracy(rows_fixed) * 100]
    bars = ax.bar(["Original", "Fixed"], accs, color=["#c0392b", "#27ae60"])
    ax.set_ylabel("3-class verdict accuracy (%)")
    ax.set_ylim(0, 100)
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 2, f"{a:.1f}%", ha="center")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "accuracy_comparison.png"), dpi=150)
    plt.close(fig)

    # Solidity distributions
    fig, ax = plt.subplots(figsize=(6, 4))
    data, labels = [], []
    for cls in classes:
        data.append([r["solidity"] for r in rows_orig if r["ground_truth"] == cls])
        labels.append(f"{cls}\n(orig)")
        data.append([r["solidity"] for r in rows_fixed if r["ground_truth"] == cls])
        labels.append(f"{cls}\n(fixed)")
    ax.boxplot(data, tick_labels=labels)
    ax.set_ylabel("Solidity")
    ax.set_title("Solidity distributions by class and pipeline", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "solidity_distributions.png"), dpi=150)
    plt.close(fig)

    if dbg_orig is not None:
        cv2.imwrite(os.path.join(FIG_DIR, "debug_contour.png"), dbg_orig)
    if dbg_fixed is not None:
        cv2.imwrite(os.path.join(FIG_DIR, "debug_fixed_contour.png"), dbg_fixed)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    rows_orig, dbg_orig = run_pipeline(use_fixed=False)
    rows_fixed, dbg_fixed = run_pipeline(use_fixed=True)

    write_csv(rows_orig, os.path.join(OUT_DIR, "raw_original.csv"))
    write_csv(rows_fixed, os.path.join(OUT_DIR, "raw_fixed.csv"))

    acc_orig = accuracy(rows_orig)
    acc_fixed = accuracy(rows_fixed)

    summary = {
        "original": {
            "label": "ORIGINAL (adaptive threshold)",
            "n": len(rows_orig),
            "accuracy": round(acc_orig, 4),
            "correct": sum(1 for r in rows_orig if r["predicted"] == r["ground_truth"]),
        },
        "fixed": {
            "label": "FIXED (color-distance segmentation)",
            "n": len(rows_fixed),
            "accuracy": round(acc_fixed, 4),
            "correct": sum(1 for r in rows_fixed if r["predicted"] == r["ground_truth"]),
        },
    }
    with open(os.path.join(OUT_DIR, "comparison_results.json"), "w") as f:
        json.dump(summary, f, indent=2)

    make_figures(rows_orig, rows_fixed, dbg_orig, dbg_fixed)

    print(f"Original pipeline: {summary['original']['correct']}/{summary['original']['n']} "
          f"= {acc_orig*100:.1f}%")
    print(f"Fixed pipeline:    {summary['fixed']['correct']}/{summary['fixed']['n']} "
          f"= {acc_fixed*100:.1f}%")
    print(f"\nWritten to {OUT_DIR}/ (CSVs, comparison_results.json, figures/)")


if __name__ == "__main__":
    main()
