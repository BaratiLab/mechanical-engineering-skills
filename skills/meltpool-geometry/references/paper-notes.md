# MeltpoolNet: notes for this skill

Akbari, Ogoke, Kao, Meidani, Yeh, Lee, Barati Farimani. *MeltpoolNet: Melt pool characteristic
prediction in Metal Additive Manufacturing using machine learning.* Additive Manufacturing 55 (2022)
102817. Data: github.com/BaratiLab/MeltpoolNet (CSV files; this skill downloads them at runtime).

## What the paper built
- **Data:** experiments collected from more than 80 metal AM papers covering process, material,
  melt-pool depth/width/length, melt-pool mode and flaw type.
  - Tasks: depth (~1400 rows), width (~1200), length (~320), and mode classification (~1200; classes
    keyhole / LOF / balling / desirable).
- **Featurization (Table 1):**
  - baseline: power, speed, density, Cp, k, melting T (plus beam diameter for classification)
  - other: hatch spacing, layer thickness
  - absorptivity 1, Eq. 2 (keyhole-aware): 0.7[1 − exp(−0.6 η_m P / ((Tm−T0) π ρ Cp V r0²))]
  - absorptivity 2, Eq. 3 (conduction, from the measured width): [πk(Tm−T0)W + eπρCp(Tm−T0)VW²/8] / P
  - material one-hot
  - wt% composition
  - elemental featurization (Eq. 1, composition-weighted Z, atomic volume, ionization energy,
    heat of fusion, electron affinity)
- **Models:** RF, GB, NN, ridge, lasso, SVR, GP, plus XGBoost for classification. Inputs are
  z-scored; evaluation is shuffled 5-fold CV.
- **Reported best (random 5-fold):**

| Task | Score | MAE |
|---|---|---|
| depth | R² 0.958 | 20.5 µm |
| width | R² 0.977 | 6.9 µm |
| length | R² 0.996 | 10.9 µm |
| classification | 88.4% accuracy, AUC 0.98 (with absorptivities + hatch); 85.8% for RF + one-hot | – |

- **Explicit models (Sec. 3.6, Tables 6–8):**
  - Form: y = w0 · P^w1 V^w2 ρ^w3 Cp^w4 k^w5 (Tm−T0)^w6, with four dimensional-consistency
    constraints. Solved with SciPy trust-region constrained optimisation.

| Task | Rosenthal R² | Identified equation R² |
|---|---|---|
| depth | 0.654 | 0.787 |
| width | 0.782 | 0.991 |
| length | −0.15 | 0.473 |

## What this skill finds on the public CSV (Oct 2026), and why it matters
1. **Random-split scores are lower than the paper's, and cross-paper scores are near zero.** With
   baseline + energy features and gradient boosting:

| Split | Depth R² | Width R² | Length R² | Classification accuracy |
|---|---|---|---|---|
| random 5-fold | 0.78 | 0.83 | 0.88 | 82.6% (RF) |
| **leave-paper-out** (whole source studies held out) | **−0.10** | 0.22 | ~0 | ~45% |

   The random split puts tracks from the same study (same machine, powder, measurement method) on
   both sides. Leave-paper-out is the realistic case for "predict my machine".
2. **A few of your own tracks fix most of it.** Moving 3 measured tracks per held-out study into
   training lifts depth R² from −0.10 to 0.52; 10 tracks lift it to 0.70. Use
   `benchmark --split paper --calibrate n` to reproduce this and `train --extra my_tracks.csv` to
   apply it.
3. **Absorptivity 2 leaks the label.** It is computed from the measured width, so as a feature for
   width (or depth/length, which correlate with width) it gives the answer away. The skill prints a
   warning when you request it.
4. **The published explicit equations do not reproduce on the current CSV.** We tried velocity in m/s
   and mm/s and outputs in m/mm/µm. The same constrained fit, re-run here (log-space KKT solve, then a
   linear-space L2 refinement on the constraint manifold), gives R² 0.24 / 0.64 / 0.57 for
   depth / width / length. Rosenthal on the same rows, with Q = P, is strongly negative. The fitted
   exponents still look physical: depth ∝ P^0.51 V^−0.22 ρ^−0.49 …, close to Rosenthal's √(P/V)
   scaling in P. Report the numbers you reproduce, not the paper's.
