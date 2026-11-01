# StressD: notes for this skill

Jadhav, Berthel, Hu, Panat, Beuth, Barati Farimani. *StressD: 2D Stress estimation using denoising diffusion model.*
Comput. Methods Appl. Mech. Engrg. 416 (2023) 116343. doi:10.1016/j.cma.2023.116343.

## Method
- **Input:** Nie et al.'s cantilever format, 5 channels: geometry (1 = material), BC-x and BC-y (−1 at
  the fixed left edge), load-x and load-y at the right end.
- **Diffusion model:** a CNN encoder maps the condition to one context channel. A U-Net DDPM denoises
  the stress map normalised to [−1, 1] per sample, with a cosine variance schedule, T = 500,
  sinusoidal time embedding, L1 loss and Adam with LR reduced on plateau.
- **Auxiliary network:** a ViT on the condition (4 × 4 patches coarse, 16 × 16 fine) predicts the
  min/max used to un-normalise. Its MAE is 0.01 MPa coarse and 0.48 MPa fine.
- **Datasets:**
  - Coarse: 80 geometries in 6 groups, 32 × 24; load angle 0–355° every 5°, magnitude 0–100 N every
    5 N; 120,960 cases.
  - Fine: 50k cases upsampled to 256 × 256.
  - Sparse: 5% stress samples, an inpainting task.
  - Hyperelastic: 49,750 cases.
- **Split:** 80/20 random over cases (coarse: about 100k train and 20k test).
- **Results (coarse):**

| Model | MAE | MSE | MAPE (peak) |
|---|---|---|---|
| StressD | 0.0418 | 0.0125 | 0.02% |
| StressNet | 0.19 | 0.13 | 0.14% |

  That is roughly a 78% MAE and 92% MSE improvement over earlier models.
- **Other results:**
  - DDIM sampling is faster but loses accuracy at few steps.
  - Fine mesh: about 25 s per sample against 45 s for FEM, or 2 s with 50 DDIM steps.
  - Unseen hyperelastic geometry: MAE 133 MPa, MAPE 1.7%.

## What this skill adds or changes
- **Its own data generator.** Nie et al.'s data isn't bundled. `dataset` builds the same layout (6
  families, 72 angles × 20 magnitudes) with a Q4 plane-stress FEM.
  - The FEM is verified against beam theory to within 1% (tested).
  - It is linear, so each geometry needs only 2 solves.
- **Geometry-held-out split by default.**
  - In the paper's random split every test geometry also appears in training under other loads.
  - Von Mises stress for a geometry is a fixed function of the two unit-load fields, so those cases
    are close to interpolation.
  - A design surrogate must handle new shapes, so the skill tests that. `--split random` reproduces
    the paper's protocol.
- **A regression U-Net baseline** (StressNet-like, predicting log1p stress), so the diffusion model
  has a bar to beat.

## CPU rehearsal (80 geometries, 115,200 cases; 30k training cases; minutes, not the paper's GPU budget)

| Model, split | Epochs | MAE (MPa) | MSE | Peak error | MAPE peak |
|---|---|---|---|---|---|
| Regression, random | 2 | 0.57 | 1.30 | 2.79 | 11.1% |
| Regression, **geometry** | 2 | 0.81 | 2.17 | 2.53 | 12.0% |
| Diffusion, geometry | 4 | 1.97 | 10.9 | 3.40 | 14.8% |

Mean true von Mises is about 5.5 MPa.
- Unseen geometries are harder than the random split, by 0.81 against 0.57 MAE at equal training.
- The diffusion model needs far more training than a CPU rehearsal gives. The paper trained to
  convergence on a GPU.
- Use these numbers to check the pipeline, not to compare methods.
