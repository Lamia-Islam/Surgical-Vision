# Surgical Vision ROS2
### Intraoperative Wound Assessment System with Variable Autonomy

---

## 🎬 Demo
https://github.com/user-attachments/assets/51900808-51cb-430f-9d7b-7dc6fdb46d1d
> FULL → REDUCED → HOLD autonomy switching in real-time based on wound state

---

## Overview

Surgical Vision ROS2 is a ROS2 Humble pipeline for intraoperative wound assessment. A vision
node scores a wound using a five-part ABCDE framework adapted from dermatology. A behavior
manager converts the score into one of three autonomy tiers for a MoveIt2-controlled arm: full
execution, reduced-speed execution with per-motion confirmation, and a hold state in which the
arm freezes until the operator types `CONFIRM`.

Built as an extension of the DecodeLabs Robotics & Automation Industrial Training Kit
(Project 2), recontextualized from gear defect detection to surgical wound monitoring.

---

## Empirical Results (Track A)

On a 45-image synthetic benchmark (15 healthy / 15 concerning / 15 critical), the original
grayscale-adaptive-threshold segmentation achieves **6.7% (3/45)** 3-class verdict accuracy — a
diagnosed, systematic failure (see `track_a_results/results.md`). A color-distance segmentation
fix improves this to **64.4% (29/45)**, with the healthy and critical classes cleanly separated;
the "concerning" class remains an open limitation, flagged honestly in the write-up. Fully
reproducible via `surgical_vision/compare_segmentation.py` — see
[Reproducing the Track A Empirical Results](#reproducing-the-track-a-empirical-results) below.

---

## Installation

### Dependencies

- Ubuntu 22.04
- ROS2 Humble
- Python 3 (bundled with ROS2 Humble)
- OpenCV
- MoveIt2
- RViz
- rclpy
- cv_bridge

### Steps

```bash
# 1. Install ROS2 Humble, MoveIt2, and RViz following the official ROS2 Humble
#    installation guide for Ubuntu 22.04.

# 2. Install remaining Python/ROS dependencies
sudo apt install ros-humble-cv-bridge ros-humble-rclpy python3-opencv

# 3. Clone into a ROS2 workspace
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/Lamia-Islam/surgical-vision-ros2.git surgical_vision

# 4. Build
cd ~/ros2_ws
colcon build --packages-select surgical_vision
source install/setup.bash
```

---

## Surgical ABCDE Framework

| Criterion | Surgical Meaning | Metric | Method |
|-----------|-----------------|--------|--------|
| **A** — Asymmetry | Irregular wound shape | Contour solidity | Convex hull ratio |
| **B** — Border | Wound edge clarity | Sharpness score | Laplacian variance |
| **C** — Color | Tissue health status | Healthy pink ratio | HSV pixel classification |
| **D** — Diameter | Wound size vs target | Bounding circle px | vs ±30% tolerance |
| **E** — Evolution | Change between frames | Area delta % | Frame comparison |

---

## Autonomy Tiers

| ABCDE Score | Mode | Arm Behavior |
|-------------|------|---------------|
| 0–1 / 10 | ✅ FULL | Immediate execution, 1.0x speed |
| 2–4 / 10 | ⚠️ REDUCED | Confirmation required, 0.5x speed |
| 5–10 / 10 | 🛑 HOLD | Arm frozen, type `CONFIRM` to resume |

- **FULL** — the wound score indicates a healthy, well-behaved surgical site. Commands from the
  surgeon console are forwarded to the arm without modification.
- **REDUCED** — the score indicates mild concern. Every motion is executed at half speed and
  requires an explicit confirmation from the operator before it runs.
- **HOLD** — the score indicates a critical wound state. The arm is frozen in place and will not
  accept new motion commands until the operator types `CONFIRM` at the surgeon console.

---

## ROS2 Architecture

```
Wound Image Feed
      ↓
lesion_detector_node  ──►  /scene_state  (PASS|CAUTION|FAIL + score + reason)
                                  ↓
                     behavior_manager_node  ──►  /autonomy_mode  (mode + speed factor)
                                                        ↓
                                            surgeon_console_node  ──►  /arm_command
                                                                              ↓
                                                                   moveit_bridge_node
                                                                              ↓
                                                                    MoveIt2 → RViz
```

---

## Running the Nodes

Each node is a separate console-script entry point. Run each in its own terminal (source
`install/setup.bash` first in each terminal), or launch the first three together with the
provided launch file.

```bash
# Terminal 1 — vision / scoring node
ros2 run surgical_vision lesion_detector

# Terminal 2 — autonomy-tier decision node
ros2 run surgical_vision behavior_manager

# Terminal 3 — operator console (accepts arm commands, CONFIRM input)
ros2 run surgical_vision surgeon_console

# Terminal 4 — bridge to MoveIt2 / RViz
ros2 run surgical_vision moveit_bridge
```

Or, to bring up the first three nodes together:

```bash
ros2 launch surgical_vision surgical_system.launch.py
```

Then start `moveit_bridge` (and your MoveIt2/RViz session) separately, since it depends on a
running MoveIt2 planning scene.

---

## Generating the Synthetic Benchmark

`generate_wounds.py` produces a 45-image synthetic benchmark (15 healthy, 15 concerning, 15
critical) simulating an overhead surgical camera view under OR lighting:

```bash
python3 surgical_vision/generate_wounds.py
```

Images are written to `./sample_images/`. No arguments are required. The generator uses a fixed
RNG seed (`np.random.default_rng(2024)`), so this is deterministic — rerunning it reproduces the
same 45 images every time.

---

## Reproducing the Track A Empirical Results

The original segmentation (`abcde_analyzer.preprocess`, grayscale adaptive thresholding) and a
fixed segmentation (HSV color-distance from background, Otsu threshold, morphological cleanup)
can be compared directly:

```bash
python3 surgical_vision/generate_wounds.py       # build sample_images/ (n=45)
python3 surgical_vision/compare_segmentation.py  # runs both pipelines, writes results
```

This writes per-image CSVs, a JSON summary, and comparison figures to `track_a_results/`. See
`track_a_results/results.md` for the write-up and `track_a_results/reproduction_notes.md` for
how the fixed-pipeline code was reconstructed and verified.

---

## License

MIT License. See [LICENSE](LICENSE).
