# LPBF optical super-resolution: notes for this skill

Ogoke, Kalambettu Suresh, Adamczyk, Bolintineanu, Garland, Heiden, Barati Farimani. *Deep learning based
optical image super-resolution via generative diffusion models for layerwise in-situ LPBF monitoring.*
Additive Manufacturing 107 (2025) 104790. CMU and Sandia.

## Setup in the paper
- **Cameras:** a 3D Systems ProX DMP200 with a 1080p Logitech StreamCam webcam (LR) and a Basler
  scientific camera (HR), mounted at different angles. Small ring-shaped parts were built in two
  builds: 65 layers (dataset A) and 115 layers (dataset B).
- **Registration:** an initial perspective warp, then part centres located in both views, with
  centre offsets interpolated across the plate into a deformation map −Δs(x, y). The HR image is
  warped onto the LR view.
- **Model: conditional latent diffusion.**
  - Two autoencoders, one for HR and one for LR, each with a 16 × 16 latent. They were trained
    100 epochs with KL, perceptual and discriminator losses at lr 4.6e-5.
  - The LR latent is concatenated to the noisy HR latent. A U-Net denoiser runs T = 200 steps,
    trained 300 epochs at lr 1e-5.
  - Patches are 64 × 64, 115 per layer, split 80/20 by layer. A part-based split (80/20 of the
    parts in each layer, resized to 128 × 128) avoids leakage between patches of one part.
- **Metrics:** PSNR, SSIM, MAE, and a wavelet covariance distance (phase-harmonic bump-steerable
  wavelets, nCVD), which checks that high-frequency texture is recovered rather than smoothed.
- **Results (Table 1, patches):**

| Dataset | Pair | MAE | PSNR | SSIM | nCVD |
|---|---|---|---|---|---|
| A | HR vs LR | 0.241 | 12.3 dB | 0.742 | 0.898 |
| A | HR vs SR | 0.023 | 30.2 dB | 0.814 | 0.347 |
| B | HR vs LR | 0.133 | 17.4 dB | 0.746 | 0.528 |
| B | HR vs SR | 0.037 | 26.7 dB | 0.719 | 0.400 |

- **Pixel-space diffusion** scores about the same (PSNR 29.0, SSIM 0.737) but takes 0.13 s per
  sample against 0.01 s for latent diffusion.
- **Part reconstruction:** segmentation with an adaptive threshold, then Segment Anything prompted
  from it. Layers are stacked into a 3D surface and roughness is measured as Ra and Rq against the
  net shape. Ra is **30.7 µm** for HR and **32.8 µm** for diffusion; the LR and bicubic
  reconstructions are much smoother.
- **Zero-shot:** the model was trained on synthetically degraded HR (Gaussian blur σ = 3 plus
  noise ε = 0.01) and applied to unseen geometries.

## Data and code availability
The dataset link in the paper (github.com/BaratiLab/LPBF-Super-Resolution) is still a
placeholder: a README and licence, no data. This skill therefore ships the full pipeline:
- registration, patches and splits;
- a pixel-space conditional DDPM and a deterministic CNN baseline;
- the metrics, segmentation and roughness;
- a synthetic ring-part build plate to rehearse on.

Numbers measured on synthetic data check the code. They are not performance claims.

## Differences from the paper, on purpose
- The model is a **pixel-space** DDPM, not latent: no autoencoder pre-training, and the paper
  reports equal accuracy. Use `--steps` (DDIM-style strided sampling) to cut inference time.
- The wavelet metric is a covariance of log-energies over scales × orientations × local windows
  (PyWavelets). It is lighter than the phase-harmonic version; compare runs within this metric, not
  against the paper's nCVD values.
- Segmentation uses the adaptive threshold only. To add Segment Anything, prompt it with
  `segment()`'s components as box or point prompts, as in the paper's two-stage approach.

## What the rehearsal shows
Setup: synthetic plate, 20 layers, 2,300 patches, 4 held-out layers, CPU only (CNN 7 epochs, diffusion
15 epochs, 50 sampling steps).

| Pair | PSNR | SSIM | MAE | Wavelet texture distance |
|---|---|---|---|---|
| HR vs webcam (bicubic) | 27.3 dB | 0.65 | 0.033 | 1.49 |
| HR vs CNN (L1) | **31.5 dB** | **0.72** | **0.021** | 4.85 |
| HR vs diffusion | 26.4 dB | 0.59 | 0.036 | **0.65** |

Whole plate, layers 5 and 9, at 10 µm/px:

| Source | Part IoU vs HR | Edge Ra |
|---|---|---|
| HR | – | 8.1 µm |
| Bicubic | 0.981 | 7.7 µm |
| CNN | 0.983 | 7.7 µm |
| Diffusion | 0.960 | 8.9 µm |

This is the perception–distortion trade-off the paper argues from:
- The CNN wins pixel metrics with smooth, track-free images.
- The diffusion model restores scan-track texture (texture distance less than half the webcam's)
  and edge roughness on the HR side, as in the paper (Ra 32.8 µm vs HR 30.7 µm). It pays for that
  in PSNR, and an undertrained model adds noise.

Train longer on a GPU before comparing with the paper's 30.2 dB.
