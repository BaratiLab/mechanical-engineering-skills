# ThermoPore: notes for this skill

Pak, Ogoke, Polonsky, Garland, Bolintineanu, Moser, Arnhart, Madison, Ivanoff, Mitchell, Jared,
Salzbrenner, Heiden, Barati Farimani. *ThermoPore: Predicting part porosity based on thermal images
using deep learning.* Additive Manufacturing 95 (2024) 104503. arXiv:2404.16882. Sandia–CMU.

## Setup in the paper
- **Build:** a 3D Systems ProX DMP. Two staircase samples (Spacing, Velocity), each with 10 steps of
  16 layers at 30 µm. One parameter (hatch spacing or speed) changes per step.
- **In-situ data:** a two-colour pyrometer at 6–7 kHz with 90 µs exposure, 1000 frames per layer,
  65 × 80 px at about 21 µm/px. Empty frames (melt pool out of view) were removed by thresholding each
  frame's maximum; this left about 20 k frames per sample. Models use **200 frames of 64 × 64 per
  layer**.
- **Ex-situ data:** Zeiss micro-CT at 3.63 µm voxels, about 8–9 voxels per build layer.
  - Pores need at least 100 voxels (11.4 µm ESD).
  - An optional μ+σ ESD filter gives 53.19 µm (Spacing) and 46.79 µm (Velocity).
  - CT was aligned to the thermal images with X/Y offsets and a 5-layer Z offset, using the first
    step that is fully in view as the reference.
- **Quantification:**
  - Model: a CNN with the frames as channels, 4 conv layers (3×3, stride 2, pad 1, channels halved,
    BN + ReLU) and 2 fully connected layers. MSE loss; Adam at 1e-4 for 500 epochs. Predictions are
    rounded.
  - Labels: unique pores within 1, 2 or 3 layers below.
  - Split: 75/25 *within* each step, giving 120 training and 39 test layers per sample.
  - Best R² **0.57** (Spacing, no rotation); best RMSE **7.84** (Velocity, with rotation).
- **Localization:**
  - Model: a ViViT with spatial (4 layers) and temporal (5 layers) encoders, 8 heads, dim 256, then a
    feature-fusion dense head. BCE loss, cosine schedule with a 10-epoch warm-up, 1000 epochs.
  - Labels: CT layer (9 × 423 × 520 voxels) downsampled 24× to a 16 × 16 map.
  - Mean IoU **0.32**, max **1.0**. One example scores 0.672 without the ESD threshold and 0.323 with it.
- **Augmentation:** rotate the whole sequence, never the intensities, because absolute temperature
  carries the physics.

## Data availability
The pyrometry and CT data are not public, and the lab's code repository is private. This skill
therefore implements the pipeline from the paper and validates it on a **synthetic rehearsal
dataset** with the same shapes and split. Treat any number measured on synthetic data as a check
that the code works, not as a performance claim.

## What the rehearsal shows (10 steps × 16 layers, 200 frames, seed 0)

| Model | Count R² / RMSE | Localization IoU mean / max |
|---|---|---|
| Thermal-history baseline (random forest / gradient boosting on 16 × 16 peak, dwell and roughness maps) | 0.44 / 10.1 | 0.27 / 0.33 |
| CNN (`--small`, 150 epochs, CPU) | 0.07 / 13.0 | – |
| ViViT (`--small`, 40 epochs, CPU) | – | 0.24 / 0.31 |

With about 120 training layers, the interpretable baseline matches or beats the deep models. Run it
first on real data. The deep models need the paper's epoch counts and a GPU to be competitive, and
they are where more data pays off.
