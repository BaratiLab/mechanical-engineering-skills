#!/usr/bin/env python3
"""Layer-wise porosity from in-situ thermal images (L-PBF), after ThermoPore
(Pak, Ogoke, ..., Heiden, Barati Farimani, Additive Manufacturing 95 (2024) 104503).

ThermoPore pairs, for every build layer, a sequence of 200 pyrometry frames (64x64 px, ~21 um/px) with
ex-situ micro-CT of the same part. Two tasks:
  * quantification: number of pores (CT) in the layer (+ optionally 1-2 layers below) -> CNN regression
  * localization:   16x16 binary porosity map of the layer (CT downsampled 24x) -> ViViT + dense head
Pores are filtered by equivalent spherical diameter (ESD); the paper used >=100 voxels and, optionally, mu+sigma.

  synth     python thermopore.py synth --out run/ [--layers-per-step 16 --steps 10 --frames 200]   rehearsal data
  prepare   python thermopore.py prepare --frames frames/ --pores pores.csv --out run/ [--esd-min 0|musigma|<um>]
  baseline  python thermopore.py baseline --data run/ [--task count|localize] [--depth 1]        CPU, interpretable
  train     python thermopore.py train --data run/ --task count|localize [--epochs 200] [--small]   PyTorch CNN / ViViT
  map       python thermopore.py map --data run/ --layer 40 --out layer40.png                          thermal maps vs pores

Data layout written by synth/prepare (run/):
  frames.npy   float16 [L, F, 64, 64]  temperature (C) per frame, empty frames removed, resampled to F
  pores.csv    pore_id, layer, x_um, y_um, esd_um     (layer = build layer index after CT-to-thermal alignment)
  meta.json    px_um, n_layers, step (process group) per layer, params per layer, cells (16)
"""
import argparse
import json
import math
import os
import sys

import numpy as np

CELLS = 16


# ------------------------------------------------------------------ synthetic rehearsal data
def synth(out, steps=10, layers_per_step=16, frames=200, px_um=21.0, size=64, seed=0, vary="velocity"):
    """A crude but physically ordered stand-in for the ThermoPore build (10 steps x 16 layers, one process
    parameter varied per step). A melt pool rasters the field of view; local absorbed-power fluctuations
    ("powder events") cool or overheat cells. Lack-of-fusion pores follow cold cells and wide hatches, keyhole
    pores hot cells and slow scans, gas pores are random and small. Labels therefore *can* be learned from
    the thermal history -- which is what a pipeline check needs. It is not a substitute for real data."""
    rng = np.random.default_rng(seed)
    os.makedirs(out, exist_ok=True)
    L = steps * layers_per_step
    if vary == "velocity":
        V = np.repeat(np.linspace(600, 2000, steps), layers_per_step); H = np.full(L, 50.0)
    else:
        H = np.repeat(np.linspace(40, 130, steps), layers_per_step); V = np.full(L, 1000.0)
    P = np.full(L, 200.0)
    allf = np.zeros((L, frames, size, size), np.float16)
    pores, pid = [], 0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cell = size // CELLS
    for l in range(L):
        ev = rng.normal(0, 1, (CELLS, CELLS))
        ev = np.where(rng.random((CELLS, CELLS)) < 0.12, ev * 3.0, ev * 0.3)          # sparse strong events
        E = P[l] / (V[l] * H[l] * 1e-3 * 0.03)                                         # J/mm^3 (30 um layer)
        Tpk0 = 1250 + 3.0 * E                                                          # nominal peak (C)
        hatch_px = max(H[l] / px_um, 1.2)
        rows = np.arange(hatch_px / 2, size, hatch_px)
        horizontal = (l % 2 == 0)
        path = []
        for r_i, r in enumerate(rows):                                                 # boustrophedon raster
            xs = np.arange(0, size, 0.7)
            xs = xs if r_i % 2 == 0 else xs[::-1]
            path += [(x, r) if horizontal else (r, x) for x in xs]
        path = np.array(path)
        sub = np.array_split(np.arange(len(path)), frames)                             # camera integrates sub-steps
        trail = np.zeros((size, size), np.float32)
        for f, seg in enumerate(sub):
            img = np.zeros((size, size), np.float32)
            for i in seg[::2]:
                cx, cy = path[i]
                ci, cj = min(int(cy) // cell, CELLS - 1), min(int(cx) // cell, CELLS - 1)
                tpk = Tpk0 * (1 + 0.09 * ev[ci, cj]) + rng.normal(0, 15)
                w = 1.6 + 0.0009 * (tpk - 1300)
                spot = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * w ** 2)))
                trail = 0.97 * trail + 0.03 * spot * tpk
                img = np.maximum(img, (tpk - 25) * spot)
            allf[l, f] = (25 + np.maximum(img, 0.4 * trail) + rng.normal(0, 6, (size, size))).astype(np.float16)
        # pores, cell by cell
        lof_risk = np.clip((H[l] - 70) / 60, 0, 1) * 0.15 + np.clip(-(ev - 0.4), 0, None) * 0.35 + np.clip((V[l] - 1500) / 500, 0, 1) * 0.1
        kh_risk = np.clip((ev - 0.4), 0, None) * 0.3 + np.clip((900 - V[l]) / 300, 0, 1) * 0.12
        for ci in range(CELLS):
            for cj in range(CELLS):
                for kind, risk, esd_mu in (("lof", lof_risk[ci, cj], 75), ("keyhole", kh_risk[ci, cj], 50), ("gas", 0.04, 18)):
                    for _ in range(rng.poisson(risk)):
                        pid += 1
                        esd = max(8.0, rng.normal(esd_mu, esd_mu * 0.3))
                        x = (cj + rng.random()) * cell * px_um; y = (ci + rng.random()) * cell * px_um
                        layer = l + (rng.integers(0, 2) if kind == "keyhole" else 0)       # keyholes can sit below
                        pores.append((pid, min(layer, L - 1), round(x, 1), round(y, 1), round(esd, 1), kind))
    np.save(os.path.join(out, "frames.npy"), allf)
    import csv
    with open(os.path.join(out, "pores.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["pore_id", "layer", "x_um", "y_um", "esd_um", "kind_synthetic"]); w.writerows(pores)
    meta = {"px_um": px_um, "n_layers": L, "frames": frames, "size": size, "cells": CELLS, "synthetic": True,
            "step": [int(i // layers_per_step) for i in range(L)],
            "params": [{"power_W": float(P[i]), "velocity_mm_s": float(V[i]), "hatch_um": float(H[i])} for i in range(L)]}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"))
    return {"out": out, "layers": L, "pores": len(pores), "frames_shape": list(allf.shape)}


# ------------------------------------------------------------------ preparing real data
def filter_frames(stack, min_peak=None, n=200):
    """Drop 'empty' frames (melt pool out of view) by a threshold on each frame's maximum temperature, then
    resample to n frames (paper: 1000 frames/layer captured, empty ones removed, 200 used)."""
    peaks = stack.reshape(len(stack), -1).max(1)
    thr = min_peak if min_peak is not None else np.percentile(peaks, 10) + 0.5 * (np.median(peaks) - np.percentile(peaks, 10))
    keep = stack[peaks >= thr]
    if len(keep) == 0:
        return None, thr
    sel = np.linspace(0, len(keep) - 1, n).round().astype(int)
    return keep[sel], float(thr)


def prepare(frames_dir, pores_csv, out, n=200, min_peak=None, px_um=21.0, z_offset=0, xy_offset=(0.0, 0.0), voxel_um=None):
    """frames_dir: one .npy (or .tif stack) per build layer, sorted by name. pores_csv: pore_id, x_um, y_um, and
    either layer or z_um (+ --voxel-um/--layer-um to convert), esd_um (or voxels + voxel_um).
    Alignment (paper Sec. 2.2.1): CT x/y offsets to the thermal field of view and a z offset in build layers."""
    import glob
    import pandas as pd
    files = sorted(glob.glob(os.path.join(frames_dir, "*.npy")) + glob.glob(os.path.join(frames_dir, "*.tif*")))
    if not files:
        raise SystemExit(f"no .npy/.tif layer stacks in {frames_dir}")
    stacks, thr = [], []
    for f in files:
        s = np.load(f) if f.endswith(".npy") else __import__("tifffile").imread(f)
        k, t = filter_frames(s.astype(np.float32), min_peak, n)
        if k is None:
            raise SystemExit(f"{f}: every frame below the empty-frame threshold")
        stacks.append(k.astype(np.float16)); thr.append(t)
    os.makedirs(out, exist_ok=True)
    np.save(os.path.join(out, "frames.npy"), np.stack(stacks))
    p = pd.read_csv(pores_csv)
    if "esd_um" not in p and "voxels" in p:
        p["esd_um"] = (6 * p["voxels"] / math.pi) ** (1 / 3) * voxel_um
    p["x_um"] = p["x_um"] - xy_offset[0]; p["y_um"] = p["y_um"] - xy_offset[1]
    p["layer"] = p["layer"] - z_offset
    p = p[(p.layer >= 0) & (p.layer < len(files))]
    p.to_csv(os.path.join(out, "pores.csv"), index=False)
    size = stacks[0].shape[-1]
    json.dump({"px_um": px_um, "n_layers": len(files), "frames": n, "size": size, "cells": CELLS, "synthetic": False,
               "step": [0] * len(files), "empty_frame_threshold": thr, "files": [os.path.basename(f) for f in files]},
              open(os.path.join(out, "meta.json"), "w"))
    return {"layers": len(files), "pores_in_view": int(len(p)), "frames_per_layer": n}


# ------------------------------------------------------------------ labels
def esd_threshold(p, rule):
    if rule in (None, "0", 0):
        return 0.0
    if rule == "musigma":                       # paper: mean + 1 std of ESD
        return float(p.esd_um.mean() + p.esd_um.std())
    return float(rule)


def labels(data, depth=1, esd_min=None):
    """count[l]   = unique pores in layers l .. l+depth-1 with ESD >= threshold (paper: 1, 2 or 3 layers)
       maps[l]    = 16x16 binary map: any pore of layer l in the cell"""
    import pandas as pd
    meta = json.load(open(os.path.join(data, "meta.json")))
    p = pd.read_csv(os.path.join(data, "pores.csv"))
    thr = esd_threshold(p, esd_min)
    p = p[p.esd_um >= thr]
    L, fov = meta["n_layers"], meta["size"] * meta["px_um"]
    count = np.zeros(L)
    by_layer = p.groupby("layer").size()
    for l in range(L):
        count[l] = sum(by_layer.get(j, 0) for j in range(l, min(l + depth, L)))
    maps = np.zeros((L, CELLS, CELLS), np.float32)
    ci = np.clip((p.y_um / fov * CELLS).astype(int), 0, CELLS - 1); cj = np.clip((p.x_um / fov * CELLS).astype(int), 0, CELLS - 1)
    for l, i, j in zip(p.layer.astype(int), ci, cj):
        maps[l, i, j] = 1
    return count, maps, thr, meta


def split(meta, seed=0, test=0.25):
    """Paper: 75/25 split *within* each process step, so both sets see every parameter combination."""
    rng = np.random.default_rng(seed)
    steps = np.array(meta["step"])
    te = np.zeros(len(steps), bool)
    for s in np.unique(steps):
        idx = np.where(steps == s)[0]
        te[rng.choice(idx, max(1, round(test * len(idx))), replace=False)] = True
    return ~te, te


def thermal_maps(frames, cells=CELLS, hot=None):
    """Per-layer spatial thermal history, the physics summary behind both tasks:
       peak T, mean T, time above a melt threshold (dwell), and peak-T roughness, pooled to cells x cells."""
    f = frames.astype(np.float32)
    hot = hot if hot is not None else np.percentile(f, 99.0)
    peak, mean = f.max(1), f.mean(1)
    dwell = (f > 0.6 * hot).mean(1)
    L, S = f.shape[0], f.shape[-1]
    k = S // cells
    pool = lambda a: a[:, :cells * k, :cells * k].reshape(L, cells, k, cells, k)
    feats = np.stack([pool(peak).mean((2, 4)), pool(peak).min((2, 4)), pool(mean).mean((2, 4)),
                      pool(dwell).mean((2, 4)), pool(peak).std((2, 4))], 1)        # [L, 5, cells, cells]
    return feats, float(hot)


# ------------------------------------------------------------------ metrics
def iou(pred, true):
    inter = np.logical_and(pred, true).sum(); union = np.logical_or(pred, true).sum()
    return 1.0 if union == 0 else float(inter / union)


def reg_metrics(y, yp):
    from sklearn.metrics import r2_score
    yp = np.rint(yp)                                       # paper rounds predicted counts
    return {"RMSE": round(float(np.sqrt(np.mean((y - yp) ** 2))), 3), "R2": round(float(r2_score(y, yp)), 3)}


# ------------------------------------------------------------------ CPU baselines
def baseline(data, task="count", depth=1, esd_min=None, seed=0):
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
    frames = np.load(os.path.join(data, "frames.npy"), mmap_mode="r")
    count, maps, thr, meta = labels(data, depth, esd_min)
    F, hot = thermal_maps(np.asarray(frames))
    tr, te = split(meta, seed)
    res = {"task": task, "esd_min_um": round(thr, 2), "train_layers": int(tr.sum()), "test_layers": int(te.sum()),
           "synthetic_data": meta.get("synthetic", False)}
    if task == "count":
        def summ(Fl):  # global statistics + cold/hot cell counts
            peak, pmin, mean, dwell, rough = Fl
            med = np.median(peak)
            return [peak.mean(), peak.std(), pmin.min(), mean.mean(), dwell.mean(), rough.mean(),
                    (peak < med - 2 * peak.std()).sum(), (peak > med + 2 * peak.std()).sum()]
        X = np.array([summ(F[l]) for l in range(len(F))])
        m = RandomForestRegressor(400, random_state=seed, min_samples_leaf=2).fit(X[tr], count[tr])
        res.update(reg_metrics(count[te], m.predict(X[te])))
        res["paper_reference"] = {"best_R2": 0.57, "best_RMSE": 7.84, "note": "CNN on real pyrometry + CT"}
    else:
        # per-cell classifier on the cell's thermal features + layer-relative anomalies
        rel = F - np.median(F, axis=(2, 3), keepdims=True)
        X = np.concatenate([F, rel], 1).transpose(0, 2, 3, 1)                 # [L, c, c, 10]
        Xtr, ytr = X[tr].reshape(-1, X.shape[-1]), maps[tr].reshape(-1)
        clf = GradientBoostingClassifier(random_state=seed).fit(Xtr, ytr)
        prob = clf.predict_proba(X[te].reshape(-1, X.shape[-1]))[:, 1].reshape(-1, CELLS, CELLS)
        t = best_threshold(clf.predict_proba(Xtr)[:, 1].reshape(-1, CELLS, CELLS), maps[tr])
        ious = [iou(p > t, m > 0) for p, m in zip(prob, maps[te])]
        res.update({"threshold": t, "IoU_mean": round(float(np.mean(ious)), 3), "IoU_max": round(float(np.max(ious)), 3),
                    "positive_cell_fraction": round(float(maps.mean()), 3),
                    "paper_reference": {"IoU_mean": 0.32, "IoU_max": 1.0, "IoU_unthresholded_example": 0.672}})
    return res


def best_threshold(prob, maps):
    ts = np.linspace(0.05, 0.9, 18)
    return float(ts[int(np.argmax([np.mean([iou(p > t, m > 0) for p, m in zip(prob, maps)]) for t in ts]))])


# ------------------------------------------------------------------ deep models (PyTorch)
def torch_models():
    import torch
    import torch.nn as nn

    class CountCNN(nn.Module):
        """Paper Fig. 5: frames as channels; 4 conv layers (3x3, stride 2, pad 1), channels halved each layer,
        BatchNorm + ReLU, then 2 fully connected layers -> pore count."""
        def __init__(self, frames=200, size=64):
            super().__init__()
            ch, layers = frames, []
            for _ in range(4):
                layers += [nn.Conv2d(ch, max(ch // 2, 4), 3, 2, 1), nn.BatchNorm2d(max(ch // 2, 4)), nn.ReLU()]
                ch = max(ch // 2, 4)
            self.conv = nn.Sequential(*layers)
            self.fc = nn.Sequential(nn.Flatten(), nn.Linear(ch * (size // 16) ** 2, 64), nn.ReLU(), nn.Linear(64, 1))

        def forward(self, x):
            return self.fc(self.conv(x)).squeeze(-1)

    class ViViT(nn.Module):
        """Factorised video transformer (paper Fig. 6): spatial encoder over 8x8 patches of each frame, temporal
        encoder over frames per patch, then a dense head to a 16x16 porosity logit map.
        Paper: spatial 4 layers, temporal 5 layers, 8 heads, dim 256. --small uses 2/2/4/64 for CPU."""
        def __init__(self, frames=200, size=64, patch=8, dim=256, heads=8, s_layers=4, t_layers=5, t_stride=4):
            super().__init__()
            self.p, self.ts, self.n = patch, t_stride, (size // patch)
            self.embed = nn.Linear(patch * patch, dim)
            self.pos_s = nn.Parameter(torch.zeros(1, self.n ** 2, dim)); self.pos_t = nn.Parameter(torch.zeros(1, frames // t_stride, dim))
            enc = lambda k: nn.TransformerEncoder(nn.TransformerEncoderLayer(dim, heads, dim * 2, 0.1, batch_first=True, norm_first=True), k, enable_nested_tensor=False)
            self.spatial, self.temporal = enc(s_layers), enc(t_layers)
            self.head = nn.Sequential(nn.Conv2d(dim, dim // 2, 3, padding=1), nn.ReLU(),
                                      nn.Upsample(size=(CELLS, CELLS), mode="bilinear", align_corners=False),
                                      nn.Conv2d(dim // 2, 1, 1))

        def forward(self, x):                       # x [B, T, H, W]
            x = x[:, ::self.ts]
            B, T, H, W = x.shape
            p = self.p
            t = x.reshape(B, T, H // p, p, W // p, p).permute(0, 1, 2, 4, 3, 5).reshape(B * T, self.n ** 2, p * p)
            t = self.spatial(self.embed(t) + self.pos_s)                         # [B*T, N, D]
            t = t.reshape(B, T, self.n ** 2, -1).permute(0, 2, 1, 3).reshape(B * self.n ** 2, T, -1)
            t = self.temporal(t + self.pos_t[:, :T]).mean(1)                       # [B*N, D]
            t = t.reshape(B, self.n, self.n, -1).permute(0, 3, 1, 2)
            return self.head(t).squeeze(1)                                         # [B, 16, 16]
    return CountCNN, ViViT


def train(data, task, depth=1, esd_min=None, epochs=200, small=False, seed=0, rotate=False, out=None):
    import torch
    torch.manual_seed(seed)
    CountCNN, ViViT = torch_models()
    frames = np.load(os.path.join(data, "frames.npy"))
    count, maps, thr, meta = labels(data, depth, esd_min)
    tr, te = split(meta, seed)
    mu, sd = float(frames.astype(np.float32).mean()), float(frames.astype(np.float32).std())
    X = torch.tensor((frames.astype(np.float32) - mu) / sd)
    L, T, S, _ = X.shape
    if task == "count":
        model = CountCNN(T, S); y = torch.tensor(count, dtype=torch.float32)
        lossf = torch.nn.MSELoss(); lr = 1e-4 if not small else 1e-3                      # paper: Adam 1e-4, 500 epochs
    else:
        cfg = dict(dim=64, heads=4, s_layers=2, t_layers=2, t_stride=8) if small else {}
        model = ViViT(T, S, **cfg); y = torch.tensor(maps)
        pos = float(maps[tr].mean()); lossf = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor((1 - pos) / max(pos, 1e-3)))
        lr = 1e-4 if not small else 5e-4                                                   # paper: BCE, cosine, warm-up
    opt = torch.optim.Adam(model.parameters(), lr)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda e: min(1, (e + 1) / 10) * 0.5 * (1 + math.cos(math.pi * e / epochs)))
    idx_tr = np.where(tr)[0]
    for ep in range(epochs):
        model.train()
        for b in np.array_split(np.random.default_rng(ep).permutation(idx_tr), max(1, len(idx_tr) // 16)):
            xb, yb = X[b], y[b]
            if rotate:   # paper: rotate the whole sequence (and the label map) together; never change intensities
                k = int(np.random.default_rng(ep * 7 + b[0]).integers(0, 4))
                xb = torch.rot90(xb, k, (2, 3)); yb = torch.rot90(yb, k, (1, 2)) if task != "count" else yb
            opt.zero_grad(); loss = lossf(model(xb), yb); loss.backward(); opt.step()
        sched.step()
    model.eval()
    with torch.no_grad():
        pred = torch.cat([model(X[i:i + 16]) for i in range(0, L, 16)]).numpy()
    res = {"task": task, "esd_min_um": round(thr, 2), "epochs": epochs, "small": small, "rotate": rotate,
           "synthetic_data": meta.get("synthetic", False)}
    if task == "count":
        res.update(reg_metrics(count[te], pred[te]))
    else:
        prob = 1 / (1 + np.exp(-pred))
        t = best_threshold(prob[tr], maps[tr])
        ious = [iou(p > t, m > 0) for p, m in zip(prob[te], maps[te])]
        res.update({"threshold": t, "IoU_mean": round(float(np.mean(ious)), 3), "IoU_max": round(float(np.max(ious)), 3)})
    if out:
        torch.save({"state": model.state_dict(), "task": task, "norm": [mu, sd], "result": res}, out)
    return res


def plot_layer(data, layer, out, esd_min=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    frames = np.load(os.path.join(data, "frames.npy"), mmap_mode="r")
    F, _ = thermal_maps(np.asarray(frames[layer:layer + 1]))
    _, maps, thr, meta = labels(data, 1, esd_min)
    fr = np.asarray(frames[layer]).astype(np.float32)
    fig, ax = plt.subplots(1, 4, figsize=(15, 3.8))
    ax[0].imshow(fr[len(fr) // 2], cmap="inferno"); ax[0].set_title(f"layer {layer}: one frame (C)")
    for a, (img, t) in zip(ax[1:3], [(fr.max(0), "peak temperature over the layer"), (F[0, 3], "dwell above melt threshold (16x16)")]):
        im = a.imshow(img, cmap="inferno"); a.set_title(t, fontsize=9); fig.colorbar(im, ax=a, fraction=0.046)
    ax[3].imshow(maps[layer], cmap="Greys", vmin=0, vmax=1); ax[3].set_title(f"CT pores (ESD >= {thr:.0f} um), 16x16")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    pr = meta.get("params", [{}] * (layer + 1))[layer]
    fig.suptitle(("SYNTHETIC rehearsal data - " if meta.get("synthetic") else "") + ", ".join(f"{k} {v:g}" for k, v in pr.items()), fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=130)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth"); s.add_argument("--out", required=True); s.add_argument("--steps", type=int, default=10)
    s.add_argument("--layers-per-step", type=int, default=16); s.add_argument("--frames", type=int, default=200)
    s.add_argument("--vary", choices=["velocity", "hatch"], default="velocity"); s.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("prepare"); s.add_argument("--frames", required=True); s.add_argument("--pores", required=True)
    s.add_argument("--out", required=True); s.add_argument("--n", type=int, default=200); s.add_argument("--min-peak", type=float)
    s.add_argument("--px-um", type=float, default=21.0); s.add_argument("--z-offset", type=int, default=0)
    s.add_argument("--xy-offset", default="0,0"); s.add_argument("--voxel-um", type=float)
    for name in ("baseline", "train"):
        s = sub.add_parser(name); s.add_argument("--data", required=True); s.add_argument("--task", choices=["count", "localize"], default="count")
        s.add_argument("--depth", type=int, default=1); s.add_argument("--esd-min", default=None, help="um, or 'musigma' (paper)")
        if name == "train":
            s.add_argument("--epochs", type=int, default=200); s.add_argument("--small", action="store_true")
            s.add_argument("--rotate", action="store_true"); s.add_argument("--out")
    s = sub.add_parser("map"); s.add_argument("--data", required=True); s.add_argument("--layer", type=int, required=True)
    s.add_argument("--out", required=True); s.add_argument("--esd-min")
    a = ap.parse_args()
    if a.cmd == "synth":
        r = synth(a.out, a.steps, a.layers_per_step, a.frames, vary=a.vary, seed=a.seed)
    elif a.cmd == "prepare":
        r = prepare(a.frames, a.pores, a.out, a.n, a.min_peak, a.px_um, a.z_offset, tuple(map(float, a.xy_offset.split(","))), a.voxel_um)
    elif a.cmd == "baseline":
        r = baseline(a.data, a.task, a.depth, a.esd_min)
    elif a.cmd == "train":
        r = train(a.data, a.task, a.depth, a.esd_min, a.epochs, a.small, rotate=a.rotate, out=a.out)
    else:
        r = {"map": plot_layer(a.data, a.layer, a.out, a.esd_min)}
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
