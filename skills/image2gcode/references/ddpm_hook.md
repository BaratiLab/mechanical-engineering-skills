# Plugging in the Image2Gcode diffusion model

The paper's generator is not bundled: the authors provide data on request (Additive Manufacturing Letters 17, 2026, 100374, "Data availability"). This skill reproduces the model's input and output contract, so trained weights drop in without changing anything else.

## Input contract
- A grayscale slice image, 224 × 224, with the part white on black, centred, projected along +Z. `i2g.py preprocess` produces this from photos and sketches. The paper used edge detection plus contour extraction for real-world inputs; Slice-100K slices are PyVista renders at the G-code layer heights.

## Output contract
- `X0 ∈ R^{Nmax×3}`, keypoints (X, Y, E) in [−1, 1], with a binary mask for valid steps.
  - X, Y are centred on the layer's bbox midpoint and divided by half the larger extent (aspect preserved).
  - E is cumulative extrusion, min–max normalized per layer to [−1, 1]. Constant E between consecutive keypoints means a travel move.
- `i2g.py keypoints` writes exactly this format (`keypoints`, `mask`, `params` in an .npz) from any G-code, so you can build training or evaluation sets from your own slicer output.

## Model summary (for re-implementation)
| Component | Setting |
|---|---|
| Encoder | DinoV2-Small, 14×14 patches, 384-d, 12 layers; last 2 layers fine-tuned; 256 patch tokens |
| Denoiser | 1-D U-Net, C_in = 128 (1×1 conv embed), channel mults (2, 2, 4, 6, 8), GroupNorm + SiLU, FiLM timestep conditioning |
| Conditioning | multi-scale cross-attention, queries = keypoint features, keys/values = 256 patch tokens, head dim 32; no conditioning dropout |
| Diffusion | x0-prediction, cosine schedule, T = 500 |
| Loss | masked MSE, channel weights (X, Y, E) = (1.3, 1.3, 0.4) × SNR timestep weighting |
| Training | AdamW 1e-4, wd 1e-2, ReduceLROnPlateau (0.9, patience 20, min 1e-8), batch 64/GPU, 800 epochs, grad clipping |
| Data | Slice-100K (100k+ STL–G-code pairs), per-layer pairs, 10% validation split |

## Using model samples
```python
import numpy as np, json
np.savez_compressed("ddpm_kp.npz", keypoints=samples[None],      # (layers, Nmax, 3) in [-1,1]
                    mask=mask[None].astype(np.uint8),
                    params=json.dumps([{"mid": [0, 0], "half": 20.0, "emin": 0.0, "emax": E_max_mm, "z": 0.2, "n": int(mask.sum())}]))
```
Then `python i2g.py emit ddpm_kp.npz --layer 0 --size-mm 40 --out layer.gcode` and `python i2g.py validate layer.gcode`. `emax` sets the deposited filament per layer. Estimate it as path length × layer height × line width / filament area, or scale it with `--flow-mult` for your printer.

## Paper results to compare against
Mean travel distance per validation layer was 417.73 (generated) vs 427.98 (slicer ground truth), a 2.40% reduction. Generated infill can differ from ground truth (concentric becoming rectilinear or triangular) while covering the area comparably. That's acceptable, since the mapping from boundary to toolpath is many-to-one.
