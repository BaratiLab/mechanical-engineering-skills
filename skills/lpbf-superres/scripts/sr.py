#!/usr/bin/env python3
"""Low-cost webcam -> high-resolution layer images for L-PBF monitoring, after Ogoke et al.,
"Deep learning based optical image super-resolution via generative diffusion models for layerwise in-situ
LPBF monitoring", Additive Manufacturing 107 (2025) 104790.

  synth     python sr.py synth --out plate/ [--layers 30 --parts 9]                 rehearsal build plates (HR + LR)
  register  python sr.py register --hr hr/ --lr lr/ --out aligned/               part-centre homography + deformation map
  patches   python sr.py patches --aligned aligned/ --out pairs.npz [--size 64 --per-layer 115 --split layer|part]
  train     python sr.py train --pairs pairs.npz --model diffusion|cnn --out sr.pt [--epochs 300 --steps 200]
  predict   python sr.py predict --model sr.pt --pairs pairs.npz --out pred.npz [--samples 1]
  metrics   python sr.py metrics --pred pred.npz                                   PSNR, SSIM, MAE, wavelet covariance distance
  rough     python sr.py rough --stack aligned/ --which hr|lr|pred [--pred pred_plate.npz] --px-um 10   part area / IoU / Ra, Rq

Everything is in "the same pixel grid, different detail" form, as in the paper: HR images are registered to the
webcam view and both are compared at the HR pixel size (LR is bicubic-upsampled), so a model learns detail,
not interpolation.
"""
import argparse
import glob
import json
import math
import os

import numpy as np


# ------------------------------------------------------------------ synthetic build plates
def synth(out, layers=30, parts=9, hr=768, scale=4, seed=0):
    """Ring-shaped parts (as in the paper's build) on a powder bed. HR: scan-track texture, powder speckle, rough
    edges that change layer to layer. LR: small perspective warp + blur + downsample + noise + JPEG (a webcam)."""
    import cv2
    rng = np.random.default_rng(seed)
    os.makedirs(os.path.join(out, "hr"), exist_ok=True); os.makedirs(os.path.join(out, "lr"), exist_ok=True)
    n = int(math.ceil(math.sqrt(parts)))
    centers = [((i + 0.5) * hr / n + rng.normal(0, 6), (j + 0.5) * hr / n + rng.normal(0, 6)) for i in range(n) for j in range(n)][:parts]
    r_out, r_in = hr / n * 0.32, hr / n * 0.16
    yy, xx = np.mgrid[0:hr, 0:hr].astype(np.float32)
    H = np.array([[1.0, 0.02, 6.0], [-0.015, 0.99, -4.0], [1.2e-5, -0.8e-5, 1.0]])      # fixed camera pose
    for l in range(layers):
        img = 0.42 + 0.06 * rng.standard_normal((hr, hr)).astype(np.float32)          # powder speckle
        img = cv2.GaussianBlur(img, (0, 0), 0.8)
        ang = (l % 2) * (math.pi / 2) + 0.3
        track = 0.5 + 0.5 * np.sin((xx * math.cos(ang) + yy * math.sin(ang)) * 2 * math.pi / 7.0)   # ~7 px hatch
        mask = np.zeros((hr, hr), bool)
        for cx, cy in centers:
            th = np.arctan2(yy - cy, xx - cx); rr = np.hypot(xx - cx, yy - cy)
            k = rng.normal(0, 1, 12)                                                   # edge roughness, this layer
            wob = sum(k[i] * np.sin((i + 3) * th + k[i + 6]) for i in range(6)) * 0.9
            mask |= (rr < r_out + wob) & (rr > r_in - wob)
        part = 0.72 + 0.12 * track + 0.04 * rng.standard_normal((hr, hr)).astype(np.float32)
        img = np.where(mask, part, img)
        img = np.clip(cv2.GaussianBlur(img.astype(np.float32), (0, 0), 0.6), 0, 1)
        cv2.imwrite(os.path.join(out, "hr", f"layer_{l:04d}.png"), (img * 255).astype(np.uint8))
        lr = cv2.warpPerspective(img, H, (hr, hr), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        lr = cv2.GaussianBlur(lr, (0, 0), scale * 0.7)
        lr = cv2.resize(lr, (hr // scale, hr // scale), interpolation=cv2.INTER_AREA)
        lr = np.clip(lr * 0.9 + 0.05 + rng.normal(0, 0.015, lr.shape), 0, 1)
        ok, enc = cv2.imencode(".jpg", (lr * 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 70])
        cv2.imwrite(os.path.join(out, "lr", f"layer_{l:04d}.png"), cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE))
    json.dump({"layers": layers, "parts": parts, "hr_px": hr, "scale": scale, "synthetic": True, "true_homography_hr": H.tolist()},
              open(os.path.join(out, "meta.json"), "w"))
    return {"out": out, "layers": layers, "parts": parts, "hr": [hr, hr], "lr": [hr // scale, hr // scale]}


# ------------------------------------------------------------------ segmentation and registration
def segment(img, block=None, offset=-0.04, min_area=None):
    """Part vs powder: local (adaptive) threshold + cleanup, as in the paper's first stage (Fig. 4). The paper adds
    Segment Anything prompted from this mask; plug SAM in here if available (see references/sam.md)."""
    import cv2
    from scipy import ndimage as ndi
    f = img.astype(np.float32)
    f = (f - f.min()) / (np.ptp(f) + 1e-9)
    block = block or (max(31, (min(f.shape) // 6) | 1))
    loc = cv2.GaussianBlur(f, (0, 0), block / 4)
    m = f > loc - offset
    glob_t = cv2.threshold((f * 255).astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0] / 255
    m &= f > glob_t
    m = ndi.binary_opening(m, iterations=2); m = ndi.binary_closing(m, iterations=3)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    min_area = min_area or 0.002 * m.size
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= min_area])
    return keep


def part_centres(mask):
    from scipy import ndimage as ndi
    filled = ndi.binary_fill_holes(mask)              # rings -> discs, so centres are the ring centres
    lab, n = ndi.label(filled)
    return np.array(ndi.center_of_mass(filled, lab, range(1, n + 1)))[:, ::-1] if n else np.zeros((0, 2))   # (x, y)


def register_pair(hr, lr):
    """Paper Sec. 2.5 / Fig. 5: (1) warp HR towards the LR view with a homography fitted on matched part centres,
    (2) interpolate the remaining centre offsets across the plate into a deformation map and apply it.
    Returns HR resampled onto the LR view at HR pixel size, and the LR image bicubic-upsampled to that size."""
    import cv2
    from scipy.interpolate import RBFInterpolator
    from scipy.optimize import linear_sum_assignment
    s = hr.shape[0] / lr.shape[0]
    lr_up = cv2.resize(lr.astype(np.float32), hr.shape[::-1], interpolation=cv2.INTER_CUBIC)
    ch, cl = part_centres(segment(hr)), part_centres(segment(lr_up))
    if len(ch) < 4 or len(cl) < 4:
        raise RuntimeError(f"need >=4 parts in both views to register (found {len(ch)} HR, {len(cl)} LR)")
    cost = np.linalg.norm(ch[:, None] - cl[None], axis=2)
    i, j = linear_sum_assignment(cost)
    good = cost[i, j] < 0.15 * hr.shape[0]
    i, j = i[good], j[good]
    Hm, inl = cv2.findHomography(ch[i].astype(np.float32), cl[j].astype(np.float32), cv2.RANSAC, 8.0)
    warped = cv2.warpPerspective(hr.astype(np.float32), Hm, hr.shape[::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    resid = part_centres(segment(warped))
    cost2 = np.linalg.norm(resid[:, None] - cl[None], axis=2)
    a, b = linear_sum_assignment(cost2)
    ok = cost2[a, b] < 0.05 * hr.shape[0]
    if ok.sum() >= 4:
        d = cl[b[ok]] - resid[a[ok]]                                   # remaining shift at each part centre
        rbf = RBFInterpolator(cl[b[ok]], d, kernel="thin_plate_spline", smoothing=1.0)
        yy, xx = np.mgrid[0:hr.shape[0]:8, 0:hr.shape[1]:8]
        D = rbf(np.c_[xx.ravel(), yy.ravel()]).reshape(*xx.shape, 2)
        Dx = cv2.resize(D[..., 0].astype(np.float32), hr.shape[::-1]); Dy = cv2.resize(D[..., 1].astype(np.float32), hr.shape[::-1])
        gy, gx = np.mgrid[0:hr.shape[0], 0:hr.shape[1]].astype(np.float32)
        warped = cv2.remap(warped, gx - Dx, gy - Dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        final = part_centres(segment(warped))
        c3 = np.linalg.norm(final[:, None] - cl[None], axis=2)
        err = float(np.median(c3.min(1)))
    else:
        err = float(np.median(cost2[a, b]))
    return warped, lr_up, {"matched_parts": int(len(i)), "centre_error_px_after": round(err, 2), "scale": round(s, 3)}


def register(hr_dir, lr_dir, out):
    import cv2
    os.makedirs(out, exist_ok=True)
    hs, ls = sorted(glob.glob(os.path.join(hr_dir, "*.png"))), sorted(glob.glob(os.path.join(lr_dir, "*.png")))
    if len(hs) != len(ls) or not hs:
        raise SystemExit(f"need matching layer images: {len(hs)} HR vs {len(ls)} LR")
    HR, LR, log = [], [], []
    for h, l in zip(hs, ls):
        hr = cv2.imread(h, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
        lr = cv2.imread(l, cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
        w, u, info = register_pair(hr, lr)
        HR.append(w.astype(np.float16)); LR.append(u.astype(np.float16)); log.append({"layer": os.path.basename(h), **info})
    np.save(os.path.join(out, "hr.npy"), np.stack(HR)); np.save(os.path.join(out, "lr_up.npy"), np.stack(LR))
    json.dump(log, open(os.path.join(out, "registration.json"), "w"), indent=1)
    return {"layers": len(log), "median_centre_error_px": float(np.median([x["centre_error_px_after"] for x in log])),
            "worst_layer": max(log, key=lambda x: x["centre_error_px_after"])}


# ------------------------------------------------------------------ patches
def patches(aligned, out, size=64, per_layer=115, split="layer", test=0.2, seed=0, part_fraction=0.6):
    """64x64 patches (paper Sec. 3.1), 115 per layer, 80/20 split by layer; split='part' holds out whole parts
    (paper Sec. 3.2, avoids leakage between neighbouring patches of the same part)."""
    from scipy import ndimage as ndi
    rng = np.random.default_rng(seed)
    HR, LR = np.load(os.path.join(aligned, "hr.npy")), np.load(os.path.join(aligned, "lr_up.npy"))
    L, S, _ = HR.shape
    test_layers = set(rng.choice(L, max(1, round(test * L)), replace=False).tolist())
    mask0 = segment(HR[0].astype(np.float32))
    lab, n = ndi.label(ndi.binary_fill_holes(mask0))
    test_parts = set(rng.choice(np.arange(1, n + 1), max(1, round(test * n)), replace=False).tolist()) if n else set()
    X, Y, is_test, where = [], [], [], []
    for l in range(L):
        partmask = segment(HR[l].astype(np.float32))
        for _ in range(per_layer):
            for _try in range(20):     # bias towards patches that contain part (that is where detail matters)
                y0, x0 = rng.integers(0, S - size, 2)
                frac = partmask[y0:y0 + size, x0:x0 + size].mean()
                if frac > 0.05 or rng.random() > part_fraction:
                    break
            ctr_part = lab[y0 + size // 2, x0 + size // 2]
            X.append(LR[l, y0:y0 + size, x0:x0 + size]); Y.append(HR[l, y0:y0 + size, x0:x0 + size])
            t = (l in test_layers) if split == "layer" else (ctr_part in test_parts)
            is_test.append(t); where.append((l, y0, x0))
    X, Y = np.stack(X).astype(np.float16), np.stack(Y).astype(np.float16)
    np.savez_compressed(out, lr=X, hr=Y, test=np.array(is_test), where=np.array(where), split=split, size=size)
    return {"pairs": len(X), "test": int(np.sum(is_test)), "split": split, "patch": size}


# ------------------------------------------------------------------ metrics
def psnr(a, b, rng=1.0):
    mse = float(np.mean((a.astype(np.float64) - b) ** 2))
    return 99.0 if mse == 0 else 10 * math.log10(rng ** 2 / mse)


def ssim(a, b):
    from skimage.metrics import structural_similarity
    return float(structural_similarity(a.astype(np.float64), b.astype(np.float64), data_range=1.0))


def wavelet_cov(img, levels=3, wavelet="db2"):
    """Covariance of log-energies of wavelet detail coefficients across scales x orientations, computed over
    local windows. A light stand-in for the paper's phase-harmonic wavelet covariance (Sec. 2.6, ref [55]):
    it measures whether the multi-scale texture statistics (scan tracks, powder, edge roughness) are present."""
    import pywt
    c = pywt.wavedec2(img.astype(np.float64), wavelet, level=levels)
    feats = []
    for det in c[1:]:
        for band in det:
            e = band ** 2
            k = max(1, e.shape[0] // 4)
            pooled = e[:k * 4, :k * 4].reshape(4, k, 4, k).mean((1, 3)).ravel()       # 16 local windows
            feats.append(np.log(pooled + 1e-8))
    F = np.array(feats)                       # [scales*orientations, windows]
    return F.mean(1), np.cov(F)


def cov_distance(a, b):
    """Normalised covariance distance (nCVD-like): ||C_a - C_b||_F / ||C_a||_F plus mean-energy mismatch."""
    ma, Ca = wavelet_cov(a); mb, Cb = wavelet_cov(b)
    return float(np.linalg.norm(Ca - Cb) / (np.linalg.norm(Ca) + 1e-12) + np.abs(ma - mb).mean() / (np.abs(ma).mean() + 1e-12))


def metrics(hr, lr, sr=None):
    out = {}
    for name, pred in [("HR|LR", lr)] + ([("HR|SR", sr)] if sr is not None else []):
        ps, ss, ma, cv = [], [], [], []
        for h, p in zip(hr, pred):
            h, p = h.astype(np.float32), np.clip(p.astype(np.float32), 0, 1)
            ps.append(psnr(h, p)); ss.append(ssim(h, p)); ma.append(float(np.abs(h - p).mean())); cv.append(cov_distance(h, p))
        f = lambda v: [round(float(np.mean(v)), 4), round(float(np.std(v)), 4)]
        out[name] = {"PSNR_dB": f(ps), "SSIM": f(ss), "MAE": f(ma), "wavelet_cov_dist": f(cv), "n": len(ps)}
    out["paper_reference_patch_A"] = {"HR|LR": {"MAE": 0.241, "PSNR_dB": 12.3, "SSIM": 0.742, "nCVD": 0.898},
                                      "HR|SR (latent diffusion)": {"MAE": 0.023, "PSNR_dB": 30.2, "SSIM": 0.814, "nCVD": 0.347}}
    return out


# ------------------------------------------------------------------ models (PyTorch)
def torch_parts():
    import torch
    import torch.nn as nn
    import torch.nn.functional as Fn

    def tembed(t, dim):
        half = dim // 2
        f = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
        a = t[:, None].float() * f[None]
        return torch.cat([a.sin(), a.cos()], 1)

    class Block(nn.Module):
        def __init__(self, cin, cout, tdim):
            super().__init__()
            self.c1, self.c2 = nn.Conv2d(cin, cout, 3, padding=1), nn.Conv2d(cout, cout, 3, padding=1)
            self.n1, self.n2 = nn.GroupNorm(8, cout), nn.GroupNorm(8, cout)
            self.t = nn.Linear(tdim, cout) if tdim else None
            self.skip = nn.Conv2d(cin, cout, 1) if cin != cout else nn.Identity()

        def forward(self, x, te=None):
            h = Fn.silu(self.n1(self.c1(x)))
            if self.t is not None:
                h = h + self.t(te)[:, :, None, None]
            return Fn.silu(self.n2(self.c2(h))) + self.skip(x)

    class UNet(nn.Module):
        """Small U-Net. Diffusion: input [x_t, LR] (2 ch) + timestep; CNN baseline: input LR (1 ch), no timestep."""
        def __init__(self, cin=2, base=32, tdim=128):
            super().__init__()
            self.tdim = tdim
            self.tm = nn.Sequential(nn.Linear(tdim, tdim), nn.SiLU(), nn.Linear(tdim, tdim)) if tdim else None
            c = [base, base * 2, base * 4]
            self.inp = nn.Conv2d(cin, c[0], 3, padding=1)
            self.d1, self.d2, self.mid = Block(c[0], c[0], tdim), Block(c[0], c[1], tdim), Block(c[1], c[2], tdim)
            self.u2, self.u1 = Block(c[2] + c[1], c[1], tdim), Block(c[1] + c[0], c[0], tdim)
            self.out = nn.Conv2d(c[0], 1, 3, padding=1)

        def forward(self, x, t=None):
            te = self.tm(tembed(t, self.tdim)) if self.tm is not None else None
            h0 = self.d1(self.inp(x), te)
            h1 = self.d2(Fn.avg_pool2d(h0, 2), te)
            m = self.mid(Fn.avg_pool2d(h1, 2), te)
            u = self.u2(torch.cat([Fn.interpolate(m, scale_factor=2), h1], 1), te)
            u = self.u1(torch.cat([Fn.interpolate(u, scale_factor=2), h0], 1), te)
            return self.out(u)
    return UNet


def schedule(T):
    import torch
    b = torch.linspace(1e-4, 0.02 * 1000 / T, T)
    a = torch.cumprod(1 - b, 0)
    return b, a


def train(pairs, model_kind="diffusion", out="sr.pt", epochs=300, T=200, lr=1e-4, batch=32, base=32, seed=0, max_minutes=None):
    """Conditional DDPM (paper: T = 200, lr 1e-5 for 300 epochs, in a learned latent space; here pixel space, which
    the paper reports as equally accurate but ~13x slower at inference) or a deterministic CNN baseline (L1)."""
    import time
    import torch
    torch.manual_seed(seed)
    UNet = torch_parts()
    d = np.load(pairs)
    tr = ~d["test"]
    X = torch.tensor(d["lr"][tr].astype(np.float32))[:, None] * 2 - 1
    Y = torch.tensor(d["hr"][tr].astype(np.float32))[:, None] * 2 - 1
    net = UNet(2 if model_kind == "diffusion" else 1, base, 128 if model_kind == "diffusion" else 0)
    opt = torch.optim.AdamW(net.parameters(), lr)
    betas, abar = schedule(T)
    t0, hist = time.time(), []
    for ep in range(epochs):
        perm = torch.randperm(len(X))
        tot = 0.0
        for i in range(0, len(X), batch):
            b = perm[i:i + batch]
            x, y = X[b], Y[b]
            if model_kind == "diffusion":
                t = torch.randint(0, T, (len(b),))
                eps = torch.randn_like(y)
                ab = abar[t][:, None, None, None]
                yt = ab.sqrt() * y + (1 - ab).sqrt() * eps
                loss = torch.nn.functional.mse_loss(net(torch.cat([yt, x], 1), t), eps)
            else:
                loss = torch.nn.functional.l1_loss(x + net(x), y)          # residual on the upsampled LR
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(b)
        hist.append(tot / len(X))
        if max_minutes and time.time() - t0 > 60 * max_minutes:
            break
    torch.save({"state": net.state_dict(), "kind": model_kind, "T": T, "base": base, "epochs_done": len(hist), "loss": hist}, out)
    return {"saved": out, "kind": model_kind, "epochs_done": len(hist), "final_loss": round(hist[-1], 5),
            "minutes": round((time.time() - t0) / 60, 1)}


def sample(ck, lr_batch, steps=None, seed=0):
    """DDPM ancestral sampling (or DDIM-like strided sampling when steps < T)."""
    import torch
    UNet = torch_parts()
    kind = ck["kind"]
    net = UNet(2 if kind == "diffusion" else 1, ck["base"], 128 if kind == "diffusion" else 0)
    net.load_state_dict(ck["state"]); net.eval()
    x = torch.tensor(lr_batch.astype(np.float32))[:, None] * 2 - 1
    with torch.no_grad():
        if kind != "diffusion":
            return ((x + net(x)).clamp(-1, 1)[:, 0].numpy() + 1) / 2
        T = ck["T"]; betas, abar = schedule(T)
        g = torch.Generator().manual_seed(seed)
        y = torch.randn(x.shape, generator=g)
        ts = list(range(T - 1, -1, -1)) if not steps or steps >= T else list(np.linspace(T - 1, 0, steps).round().astype(int))
        for k, t in enumerate(ts):
            tt = torch.full((len(x),), t, dtype=torch.long)
            eps = net(torch.cat([y, x], 1), tt)
            ab = abar[t]
            y0 = ((y - (1 - ab).sqrt() * eps) / ab.sqrt()).clamp(-1, 1)
            if k == len(ts) - 1:
                y = y0; break
            ab_prev = abar[ts[k + 1]]
            # DDIM (eta = 0) update; equals deterministic DDPM-mean path when using all steps
            y = ab_prev.sqrt() * y0 + (1 - ab_prev).sqrt() * eps
        return ((y.clamp(-1, 1)[:, 0].numpy()) + 1) / 2


def predict(model, pairs, out, steps=50, which="test", limit=None):
    import torch
    ck = torch.load(model, weights_only=False)
    d = np.load(pairs)
    sel = d["test"] if which == "test" else ~d["test"]
    lr, hr = d["lr"][sel].astype(np.float32), d["hr"][sel].astype(np.float32)
    if limit:
        lr, hr = lr[:limit], hr[:limit]
    sr = np.concatenate([sample(ck, lr[i:i + 64], steps) for i in range(0, len(lr), 64)])
    np.savez_compressed(out, lr=lr.astype(np.float16), hr=hr.astype(np.float16), sr=sr.astype(np.float16), kind=ck["kind"])
    return {"saved": out, "n": len(sr), "kind": ck["kind"], "sampling_steps": steps if ck["kind"] == "diffusion" else 1}


# ------------------------------------------------------------------ part reconstruction and roughness
def roughness(masks, px_um, smooth_px=15):
    """Edge roughness of segmented parts layer by layer: deviation of each part's outer contour from a smoothed
    (net-shape) contour. Ra = mean |dev|, Rq = rms(dev), in um. The paper builds a 3D height map from stacked
    masks and reports Ra 30.7 um (HR) vs 32.8 um (diffusion) vs the much smoother LR/bicubic reconstructions."""
    import cv2
    from scipy.ndimage import gaussian_filter1d
    devs = []
    for m in masks:
        cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        for c in cs:
            c = c[:, 0, :].astype(np.float64)
            if len(c) < 4 * smooth_px:
                continue
            sm = np.stack([gaussian_filter1d(c[:, k], smooth_px, mode="wrap") for k in range(2)], 1)
            t = np.gradient(sm, axis=0); nrm = np.stack([t[:, 1], -t[:, 0]], 1); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
            dev = ((c - sm) * nrm).sum(1)
            devs.append(dev - dev.mean())          # remove the shrinkage bias of smoothing a curved contour
    dv = np.concatenate(devs) * px_um if devs else np.array([0.0])
    return {"Ra_um": round(float(np.abs(dv).mean()), 2), "Rq_um": round(float(np.sqrt((dv ** 2).mean())), 2), "edge_points": int(len(dv))}


def plate_compare(aligned, px_um, model=None, steps=30, tile=64, layers=None):
    """Whole-plate comparison: segment HR, LR-bicubic and (optionally) model-upscaled plates; report part IoU vs HR and
    edge roughness for each. Model upscaling is done tile by tile (paper: patch-wise over the build plate)."""
    HR, LR = np.load(os.path.join(aligned, "hr.npy")), np.load(os.path.join(aligned, "lr_up.npy"))
    sel = range(len(HR)) if layers is None else layers
    out = {}
    imgs = {"HR": [HR[l].astype(np.float32) for l in sel], "LR_bicubic": [LR[l].astype(np.float32) for l in sel]}
    if model:
        import torch
        ck = torch.load(model, weights_only=False)
        ups = []
        for l in sel:
            im = LR[l].astype(np.float32); S = im.shape[0] - im.shape[0] % tile
            tiles = im[:S, :S].reshape(S // tile, tile, S // tile, tile).transpose(0, 2, 1, 3).reshape(-1, tile, tile)
            p = sample(ck, tiles, steps).reshape(S // tile, S // tile, tile, tile).transpose(0, 2, 1, 3).reshape(S, S)
            full = im.copy(); full[:S, :S] = p; ups.append(full)
        imgs["SR_" + ck["kind"]] = ups
    masks = {k: [segment(i) for i in v] for k, v in imgs.items()}
    for k in imgs:
        ious = [float((a & b).sum() / max((a | b).sum(), 1)) for a, b in zip(masks[k], masks["HR"])]
        area = [float(abs(a.sum() - b.sum()) / max(b.sum(), 1)) for a, b in zip(masks[k], masks["HR"])]
        out[k] = {"part_IoU_vs_HR": round(float(np.mean(ious)), 4), "area_error_vs_HR": round(float(np.mean(area)), 4),
                  **roughness(masks[k], px_um)}
    return out, imgs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth"); s.add_argument("--out", required=True); s.add_argument("--layers", type=int, default=30)
    s.add_argument("--parts", type=int, default=9); s.add_argument("--hr", type=int, default=768); s.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("register"); s.add_argument("--hr", required=True); s.add_argument("--lr", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("patches"); s.add_argument("--aligned", required=True); s.add_argument("--out", required=True)
    s.add_argument("--size", type=int, default=64); s.add_argument("--per-layer", type=int, default=115)
    s.add_argument("--split", choices=["layer", "part"], default="layer")
    s = sub.add_parser("train"); s.add_argument("--pairs", required=True); s.add_argument("--model", choices=["diffusion", "cnn"], default="diffusion")
    s.add_argument("--out", required=True); s.add_argument("--epochs", type=int, default=300); s.add_argument("--steps", type=int, default=200)
    s.add_argument("--lr", type=float, default=1e-4); s.add_argument("--base", type=int, default=32); s.add_argument("--max-minutes", type=float)
    s = sub.add_parser("predict"); s.add_argument("--model", required=True); s.add_argument("--pairs", required=True)
    s.add_argument("--out", required=True); s.add_argument("--steps", type=int, default=50); s.add_argument("--limit", type=int)
    s = sub.add_parser("metrics"); s.add_argument("--pred", required=True)
    s = sub.add_parser("plate"); s.add_argument("--aligned", required=True); s.add_argument("--px-um", type=float, required=True)
    s.add_argument("--model"); s.add_argument("--steps", type=int, default=30); s.add_argument("--layers", help="e.g. 0,5,10")
    a = ap.parse_args()
    if a.cmd == "synth":
        r = synth(a.out, a.layers, a.parts, a.hr, seed=a.seed)
    elif a.cmd == "register":
        r = register(a.hr, a.lr, a.out)
    elif a.cmd == "patches":
        r = patches(a.aligned, a.out, a.size, a.per_layer, a.split)
    elif a.cmd == "train":
        r = train(a.pairs, a.model, a.out, a.epochs, a.steps, a.lr, base=a.base, max_minutes=a.max_minutes)
    elif a.cmd == "predict":
        r = predict(a.model, a.pairs, a.out, a.steps, limit=a.limit)
    elif a.cmd == "metrics":
        d = np.load(a.pred)
        r = metrics(d["hr"], d["lr"], d["sr"])
    else:
        r, _ = plate_compare(a.aligned, a.px_um, a.model, a.steps, layers=[int(x) for x in a.layers.split(",")] if a.layers else None)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
