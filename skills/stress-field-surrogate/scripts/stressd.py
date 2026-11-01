#!/usr/bin/env python3
"""Fast von Mises stress fields from geometry, supports and loads, after StressD (Jadhav, Berthel, Hu, Panat, Beuth,
Barati Farimani, "StressD: 2D stress estimation using denoising diffusion model", CMAME 416 (2023) 116343).

StressD = (1) a conditional DDPM that generates the stress map normalised to [-1, 1] per sample, plus (2) an auxiliary
network (ViT in the paper) that predicts the min/max needed to un-normalise it. Inputs follow Nie et al.'s
cantilever format: 5 channels on a 32 x 24 grid (geometry, BC-x, BC-y, load-x, load-y), output von Mises stress.

  dataset   python stressd.py dataset --out cant.npz [--geoms 80 --angles 72 --mags 20]       2D plane-stress FEM (Q4)
  fem       python stressd.py fem --geom shape.png|--random 3 [--angle 30 --load 50] --out vm.npy    one solve
  train     python stressd.py train --data cant.npz --model diffusion|regression --out m.pt [--split geometry|random]
  predict   python stressd.py predict --model m.pt --data cant.npz --out pred.npz [--steps 50]
  metrics   python stressd.py metrics --pred pred.npz               MAE, MSE, peak-stress abs. error, MAPE (paper Table)
  plot      python stressd.py plot --pred pred.npz --out cases.png

Plane stress, E = 200 GPa, nu = 0.3, thickness 1 mm, element size 1 mm (edit MATERIAL). Load magnitudes in N.
"""
import argparse
import json
import math
import os

import numpy as np

NX, NY = 32, 24
MATERIAL = {"E": 200e3, "nu": 0.3, "t": 1.0}     # MPa, -, mm  (element size h = 1 mm)


# ------------------------------------------------------------------ geometry families (cantilever, fixed left edge)
def random_geometry(rng, kind=None):
    """Six families like Nie et al.'s groups: plain, holes, notches, tapered, slotted, truss-like openings."""
    g = np.ones((NY, NX), bool)
    yy, xx = np.mgrid[0:NY, 0:NX]
    kind = kind if kind is not None else int(rng.integers(0, 6))
    if kind == 1:   # circular holes
        for _ in range(rng.integers(1, 4)):
            cx, cy, r = rng.uniform(6, NX - 4), rng.uniform(5, NY - 5), rng.uniform(2, 4.5)
            g &= (xx - cx) ** 2 + (yy - cy) ** 2 > r ** 2
    elif kind == 2:   # edge notches
        for _ in range(rng.integers(1, 3)):
            x0, w, d = int(rng.integers(5, NX - 6)), int(rng.integers(2, 5)), int(rng.integers(3, 9))
            if rng.random() < 0.5:
                g[:d, x0:x0 + w] = False
            else:
                g[NY - d:, x0:x0 + w] = False
    elif kind == 3:   # taper towards the tip
        tip = rng.uniform(0.3, 0.7)
        half = (NY / 2) * (1 - (1 - tip) * xx / (NX - 1))
        g &= np.abs(yy - (NY - 1) / 2) <= half
    elif kind == 4:   # rectangular slots
        for _ in range(rng.integers(1, 3)):
            x0, y0 = int(rng.integers(5, NX - 10)), int(rng.integers(4, NY - 8))
            g[y0:y0 + int(rng.integers(2, 5)), x0:x0 + int(rng.integers(4, 9))] = False
    elif kind == 5:   # triangular truss openings
        n = int(rng.integers(2, 4))
        for i in range(n):
            x0 = 4 + i * (NX - 6) / n
            w = (NX - 6) / n - 2
            for x in range(int(x0), int(x0 + w)):
                h = int((x - x0) / w * (NY - 8)) if i % 2 == 0 else int((1 - (x - x0) / w) * (NY - 8))
                g[4:4 + h, x] = False
    g[:, 0:2] = True                    # solid clamp region
    g[NY // 2 - 2:NY // 2 + 2, NX - 2:] = True   # solid load pad at the tip
    return keep_connected(g)


def keep_connected(g):
    from scipy import ndimage as ndi
    lab, n = ndi.label(g)
    keep = set(lab[:, 0][lab[:, 0] > 0])
    return np.isin(lab, list(keep))


# ------------------------------------------------------------------ Q4 plane-stress FEM on the pixel grid
def _ke(E, nu, t):
    """Bilinear quad stiffness, unit square element, 2x2 Gauss."""
    D = E / (1 - nu ** 2) * np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    K = np.zeros((8, 8)); Bs = []
    g = 1 / math.sqrt(3)
    for xi in (-g, g):
        for eta in (-g, g):
            dN = 0.25 * np.array([[-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)], [-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)]])
            J = dN @ np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
            dNx = np.linalg.solve(J, dN)
            B = np.zeros((3, 8)); B[0, 0::2] = dNx[0]; B[1, 1::2] = dNx[1]; B[2, 0::2] = dNx[1]; B[2, 1::2] = dNx[0]
            K += B.T @ D @ B * np.linalg.det(J) * t
            Bs.append(B)
    dNc = 2 * 0.25 * np.array([[-1, 1, 1, -1], [-1, -1, 1, 1]])   # centre derivatives; x 2 = inverse Jacobian of the unit element
    Bc = np.zeros((3, 8)); Bc[0, 0::2] = dNc[0]; Bc[1, 1::2] = dNc[1]; Bc[2, 0::2] = dNc[1]; Bc[2, 1::2] = dNc[0]
    return K, D, Bc


def solve_unit(g, mat=MATERIAL):
    """Two solves (unit Fx and unit Fy on the tip pad nodes). By linearity any load (F, angle) is a combination,
    which is how a 120k-case dataset costs only 2 solves per geometry."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    Ke, D, Bc = _ke(mat["E"], mat["nu"], mat["t"])
    ny, nx = g.shape
    nid = lambda i, j: i * (nx + 1) + j          # node at row i (y), col j (x)
    els = [(i, j) for i in range(ny) for j in range(nx) if g[i, j]]
    rows, cols, vals = [], [], []
    edofs = []
    for i, j in els:
        n = [nid(i, j), nid(i, j + 1), nid(i + 1, j + 1), nid(i + 1, j)]
        dof = np.array([[2 * k, 2 * k + 1] for k in n]).ravel()
        edofs.append(dof)
        rows += np.repeat(dof, 8).tolist(); cols += np.tile(dof, 8).tolist(); vals += Ke.ravel().tolist()
    N = 2 * (ny + 1) * (nx + 1)
    K = coo_matrix((vals, (rows, cols)), shape=(N, N)).tocsr()
    used = np.unique(np.concatenate(edofs))
    fixed = np.array([d for i in range(ny + 1) for d in (2 * nid(i, 0), 2 * nid(i, 0) + 1)])
    free = np.setdiff1d(used, fixed)
    load_nodes = sorted({nid(i, nx) for i in range(ny + 1) if (i < ny and g[i, nx - 1]) or (i > 0 and g[i - 1, nx - 1])})
    pad = [n for n in load_nodes if abs(n // (nx + 1) - ny / 2) <= 2]
    out = []
    for comp in (0, 1):
        F = np.zeros(N)
        for n in pad:
            F[2 * n + comp] = 1.0 / len(pad)
        u = np.zeros(N); u[free] = spsolve(K[free][:, free], F[free])
        s = np.zeros((ny, nx, 3))
        for (i, j), dof in zip(els, edofs):
            s[i, j] = D @ Bc @ u[dof]
        out.append(s)
    return out[0], out[1], pad


def von_mises(s):
    sx, sy, txy = s[..., 0], s[..., 1], s[..., 2]
    return np.sqrt(np.clip(sx ** 2 - sx * sy + sy ** 2 + 3 * txy ** 2, 0, None))


def channels(g, angle_deg, mag, pad_rows=None):
    """Nie et al. 5-channel input: geometry (1 material), BC-x and BC-y (-1 at the clamp), load-x, load-y at the tip."""
    c = np.zeros((5, NY, NX), np.float32)
    c[0] = g
    c[1, :, 0] = -1; c[2, :, 0] = -1
    rows = slice(NY // 2 - 2, NY // 2 + 2)
    c[3, rows, NX - 1] = mag * math.cos(math.radians(angle_deg))
    c[4, rows, NX - 1] = mag * math.sin(math.radians(angle_deg))
    return c


def dataset(out, n_geoms=80, angles=72, mags=20, seed=0):
    """Nie et al. dataset analogue: n_geoms geometries x angles (0..355 by 5 deg) x magnitudes (5..100 N by 5)."""
    rng = np.random.default_rng(seed)
    X, Y, G = [], [], []
    for gi in range(n_geoms):
        g = random_geometry(rng, gi % 6)
        sx, sy, _ = solve_unit(g)
        for a in np.arange(0, 360, 360 / angles):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            base = von_mises(sx * ca + sy * sa)          # unit-magnitude field at this angle
            for m in np.linspace(100 / mags, 100, mags):
                X.append(channels(g, a, m)); Y.append((base * m * g).astype(np.float32)); G.append(gi)
    X, Y, G = np.stack(X), np.stack(Y), np.array(G)
    np.savez_compressed(out, x=X, y=Y, geom=G, material=json.dumps(MATERIAL))
    return {"cases": len(X), "geometries": n_geoms, "shape": list(X.shape), "max_vm_MPa": float(Y.max())}


def split(G, kind="geometry", test=0.2, seed=0):
    rng = np.random.default_rng(seed)
    if kind == "random":             # paper: 80/20 over cases (geometries shared between train and test)
        te = rng.random(len(G)) < test
    else:                            # unseen geometries only: the honest test of a surrogate
        ug = np.unique(G); tg = set(rng.choice(ug, max(1, round(test * len(ug))), replace=False).tolist())
        te = np.isin(G, list(tg))
    return ~te, te


# ------------------------------------------------------------------ models
def torch_parts():
    import torch
    import torch.nn as nn
    import torch.nn.functional as Fn

    def temb(t, dim):
        half = dim // 2
        f = torch.exp(-math.log(10000) * torch.arange(half, device=t.device) / half)
        a = t[:, None].float() * f[None]
        return torch.cat([a.sin(), a.cos()], 1)

    class Block(nn.Module):
        def __init__(s, ci, co, td):
            super().__init__()
            s.c1, s.c2 = nn.Conv2d(ci, co, 3, padding=1), nn.Conv2d(co, co, 3, padding=1)
            s.n1, s.n2 = nn.GroupNorm(8, co), nn.GroupNorm(8, co)
            s.t = nn.Linear(td, co) if td else None
            s.sk = nn.Conv2d(ci, co, 1) if ci != co else nn.Identity()

        def forward(s, x, te=None):
            h = Fn.silu(s.n1(s.c1(x)))
            if s.t is not None:
                h = h + s.t(te)[:, :, None, None]
            return Fn.silu(s.n2(s.c2(h))) + s.sk(x)

    class UNet(nn.Module):
        """Conditional U-Net: [noisy map (1) + encoded condition (1)] for diffusion, condition only for regression.
        Paper: a CNN encoder maps the 4-5 condition channels to one context channel before the U-Net."""
        def __init__(s, diffusion=True, base=32, td=128):
            super().__init__()
            s.diff, s.td = diffusion, td if diffusion else 0
            s.enc = nn.Sequential(nn.Conv2d(5, 16, 3, padding=1), nn.SiLU(), nn.Conv2d(16, 1, 3, padding=1))
            s.tm = nn.Sequential(nn.Linear(td, td), nn.SiLU(), nn.Linear(td, td)) if diffusion else None
            ci = 2 if diffusion else 1
            c = [base, base * 2, base * 4]
            s.inp = nn.Conv2d(ci + 5, c[0], 3, padding=1)
            s.d1, s.d2, s.mid = Block(c[0], c[0], s.td), Block(c[0], c[1], s.td), Block(c[1], c[2], s.td)
            s.u2, s.u1 = Block(c[2] + c[1], c[1], s.td), Block(c[1] + c[0], c[0], s.td)
            s.out = nn.Conv2d(c[0], 1, 3, padding=1)

        def forward(s, cond, x=None, t=None):
            ctx = s.enc(cond)
            h = torch.cat([x, ctx, cond], 1) if s.diff else torch.cat([ctx, cond], 1)
            te = s.tm(temb(t, s.td)) if s.diff else None
            h0 = s.d1(s.inp(h), te)
            h1 = s.d2(Fn.avg_pool2d(h0, 2), te)
            m = s.mid(Fn.avg_pool2d(h1, 2), te)
            u = s.u2(torch.cat([Fn.interpolate(m, size=h1.shape[-2:]), h1], 1), te)
            u = s.u1(torch.cat([Fn.interpolate(u, size=h0.shape[-2:]), h0], 1), te)
            return s.out(u)

    class ScaleNet(nn.Module):
        """Auxiliary network: predicts log(max stress) from the condition (paper: ViT with 4x4 patches)."""
        def __init__(s, dim=96, heads=4, layers=3, patch=4):
            super().__init__()
            s.p = patch; n = (NY // patch) * (NX // patch)
            s.emb = nn.Linear(5 * patch * patch, dim); s.pos = nn.Parameter(torch.zeros(1, n, dim))
            s.tf = nn.TransformerEncoder(nn.TransformerEncoderLayer(dim, heads, dim * 2, 0.0, batch_first=True), layers,
                                         enable_nested_tensor=False)
            s.head = nn.Sequential(nn.LayerNorm(dim), nn.Linear(dim, 1))

        def forward(s, c):
            B = c.shape[0]; p = s.p
            t = c.unfold(2, p, p).unfold(3, p, p).permute(0, 2, 3, 1, 4, 5).reshape(B, -1, 5 * p * p)
            return s.head(s.tf(s.emb(t) + s.pos).mean(1)).squeeze(-1)
    return UNet, ScaleNet


def _cond(x, lscale):
    import torch
    c = torch.tensor(x, dtype=torch.float32)
    c[:, 3:] = c[:, 3:] / lscale          # loads to O(1)
    return c


def train(data, kind, out, split_kind="geometry", epochs=60, T=500, lr=3e-4, batch=128, base=32, seed=0, max_minutes=None, max_cases=None):
    """Diffusion: noise the per-sample normalised map (cosine schedule, T = 500 as in the paper), predict the noise;
    ScaleNet learns log max stress. Regression: U-Net predicts log1p(stress) directly (StressNet-like baseline)."""
    import time
    import torch
    torch.manual_seed(seed)
    UNet, ScaleNet = torch_parts()
    d = np.load(data)
    X, Y, G = d["x"], d["y"], d["geom"]
    tr, te = split(G, split_kind, seed=seed)
    idx = np.where(tr)[0]
    if max_cases and len(idx) > max_cases:
        idx = np.random.default_rng(seed).choice(idx, max_cases, replace=False)
    lscale = float(np.abs(X[:, 3:]).max())
    C = _cond(X[idx], lscale)
    Yt = torch.tensor(Y[idx])[:, None]
    mask = C[:, :1]
    net = UNet(kind == "diffusion", base)
    params = list(net.parameters())
    if kind == "diffusion":
        smax = Yt.amax((1, 2, 3)).clamp_min(1e-6)
        target = (Yt / smax[:, None, None, None]) * 2 - 1           # per-sample normalisation to [-1, 1]
        sn = ScaleNet(); params += list(sn.parameters())
        s = torch.linspace(0, T, T + 1) / T
        abar = torch.cos((s + 0.008) / 1.008 * math.pi / 2) ** 2; abar = (abar / abar[0])[1:].clamp(1e-5, 1)
    opt = torch.optim.Adam(params, lr)
    t0, hist = time.time(), []
    for ep in range(epochs):
        perm = torch.randperm(len(C)); tot = 0.0
        for i in range(0, len(C), batch):
            b = perm[i:i + batch]
            if kind == "diffusion":
                t = torch.randint(0, T, (len(b),)); eps = torch.randn_like(target[b])
                ab = abar[t][:, None, None, None]
                xt = ab.sqrt() * target[b] + (1 - ab).sqrt() * eps
                loss = torch.nn.functional.l1_loss(net(C[b], xt, t), eps)          # paper: L1 loss
                loss = loss + torch.nn.functional.mse_loss(sn(C[b]), torch.log(smax[b]))
            else:
                loss = torch.nn.functional.l1_loss(net(C[b]) * mask[b], torch.log1p(Yt[b]) * mask[b])
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item() * len(b)
        hist.append(tot / len(C))
        if max_minutes and time.time() - t0 > 60 * max_minutes:
            break
    ck = {"kind": kind, "unet": net.state_dict(), "base": base, "T": T, "lscale": lscale, "split": split_kind, "seed": seed,
          "epochs_done": len(hist), "loss": hist}
    if kind == "diffusion":
        ck["scale"] = sn.state_dict()
    torch.save(ck, out)
    return {"saved": out, "kind": kind, "split": split_kind, "train_cases": int(len(idx)), "epochs_done": len(hist),
            "final_loss": round(hist[-1], 5), "minutes": round((time.time() - t0) / 60, 1)}


def predict(model, data, out, steps=50, limit=None, seed=0):
    import torch
    UNet, ScaleNet = torch_parts()
    ck = torch.load(model, weights_only=False)
    d = np.load(data)
    X, Y, G = d["x"], d["y"], d["geom"]
    tr, te = split(G, ck["split"], seed=ck["seed"])
    idx = np.where(te)[0]
    if limit and len(idx) > limit:
        idx = np.random.default_rng(seed).choice(idx, limit, replace=False)
    C = _cond(X[idx], ck["lscale"]); mask = C[:, :1]
    net = UNet(ck["kind"] == "diffusion", ck["base"]); net.load_state_dict(ck["unet"]); net.eval()
    outs = []
    with torch.no_grad():
        if ck["kind"] != "diffusion":
            for i in range(0, len(C), 256):
                outs.append((torch.expm1(net(C[i:i + 256])).clamp_min(0) * mask[i:i + 256])[:, 0].numpy())
        else:
            sn = ScaleNet(); sn.load_state_dict(ck["scale"]); sn.eval()
            T = ck["T"]; s = torch.linspace(0, T, T + 1) / T
            abar = torch.cos((s + 0.008) / 1.008 * math.pi / 2) ** 2; abar = (abar / abar[0])[1:].clamp(1e-5, 1)
            ts = list(np.linspace(T - 1, 0, steps).round().astype(int))
            g = torch.Generator().manual_seed(seed)
            for i in range(0, len(C), 256):
                c = C[i:i + 256]
                x = torch.randn((len(c), 1, NY, NX), generator=g)
                for k, t in enumerate(ts):           # DDIM (eta = 0) sampling; paper compares DDPM and DDIM
                    tt = torch.full((len(c),), int(t), dtype=torch.long)
                    eps = net(c, x, tt); ab = abar[t]
                    x0 = ((x - (1 - ab).sqrt() * eps) / ab.sqrt()).clamp(-1, 1)
                    if k == len(ts) - 1:
                        x = x0; break
                    abp = abar[ts[k + 1]]
                    x = abp.sqrt() * x0 + (1 - abp).sqrt() * eps
                smax = torch.exp(sn(c))[:, None, None, None]
                outs.append((((x + 1) / 2).clamp(0, 1) * smax * mask[i:i + 256])[:, 0].numpy())
    P = np.concatenate(outs)
    np.savez_compressed(out, pred=P.astype(np.float32), true=Y[idx], x=X[idx], geom=G[idx], kind=ck["kind"], split=ck["split"])
    return {"saved": out, "cases": len(idx), "kind": ck["kind"], "split": ck["split"], "test_geometries": int(len(np.unique(G[idx])))}


def metrics(pred, true, geom_mask=None):
    """Paper metrics: MAE and MSE over the material domain, peak-stress absolute error, and percentage peak error."""
    m = geom_mask if geom_mask is not None else (true > 0) | (pred > 0)
    err = (pred - true)
    mae = float(np.abs(err)[m].mean()); mse = float((err ** 2)[m].mean())
    pk_t, pk_p = true.reshape(len(true), -1).max(1), pred.reshape(len(pred), -1).max(1)
    pae = np.abs(pk_p - pk_t)
    return {"MAE_MPa": round(mae, 4), "MSE": round(mse, 4), "peak_abs_err_MPa": round(float(pae.mean()), 4),
            "MAPE_peak_pct": round(float((pae / np.maximum(pk_t, 1e-9)).mean() * 100), 3),
            "mean_true_vm_MPa": round(float(true[m].mean()), 3), "cases": int(len(true)),
            "paper_reference_coarse_random_split": {"StressD": {"MAE": 0.0418, "MSE": 0.0125, "MAPE_pct": 0.02},
                                                    "StressNet": {"MAE": 0.19, "MSE": 0.13, "MAPE_pct": 0.14}}}


def plot(pred_file, out, n=4):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = np.load(pred_file)
    P, Yt, X = d["pred"], d["true"], d["x"]
    rng = np.random.default_rng(1); ids = rng.choice(len(P), n, replace=False)
    fig, ax = plt.subplots(n, 3, figsize=(9, 2.2 * n))
    for r, i in enumerate(ids):
        vmax = Yt[i].max()
        mk = X[i, 0] > 0
        for c, (img, t) in enumerate([(Yt[i], "FEM"), (P[i], f"{d['kind']}"), (np.abs(P[i] - Yt[i]), "|error|")]):
            im = ax[r, c].imshow(np.where(mk, img, np.nan), cmap="jet" if c < 2 else "magma", vmin=0, vmax=vmax if c < 2 else max(vmax * 0.2, 1e-9))
            ax[r, c].set_xticks([]); ax[r, c].set_yticks([])
            if r == 0:
                ax[r, c].set_title(t, fontsize=9)
        ax[r, 0].set_ylabel(f"F {math.hypot(X[i, 3].max() + X[i, 3].min(), X[i, 4].max() + X[i, 4].min()):.0f} N", fontsize=8)
    fig.suptitle(f"held-out cases ({d['split']} split); colour scale per row = FEM max", fontsize=8)
    fig.tight_layout(); fig.savefig(out, dpi=130)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dataset"); s.add_argument("--out", required=True); s.add_argument("--geoms", type=int, default=80)
    s.add_argument("--angles", type=int, default=72); s.add_argument("--mags", type=int, default=20); s.add_argument("--seed", type=int, default=0)
    s = sub.add_parser("fem"); s.add_argument("--random", type=int, default=0); s.add_argument("--geom")
    s.add_argument("--angle", type=float, default=270); s.add_argument("--load", type=float, default=50); s.add_argument("--out", required=True)
    s = sub.add_parser("train"); s.add_argument("--data", required=True); s.add_argument("--model", choices=["diffusion", "regression"], default="diffusion")
    s.add_argument("--out", required=True); s.add_argument("--split", choices=["geometry", "random"], default="geometry")
    s.add_argument("--epochs", type=int, default=60); s.add_argument("--lr", type=float, default=3e-4); s.add_argument("--base", type=int, default=32)
    s.add_argument("--max-minutes", type=float); s.add_argument("--max-cases", type=int)
    s = sub.add_parser("predict"); s.add_argument("--model", required=True); s.add_argument("--data", required=True)
    s.add_argument("--out", required=True); s.add_argument("--steps", type=int, default=50); s.add_argument("--limit", type=int)
    s = sub.add_parser("metrics"); s.add_argument("--pred", required=True)
    s = sub.add_parser("plot"); s.add_argument("--pred", required=True); s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "dataset":
        r = dataset(a.out, a.geoms, a.angles, a.mags, a.seed)
    elif a.cmd == "fem":
        if a.geom:
            from PIL import Image
            g = np.asarray(Image.open(a.geom).convert("L").resize((NX, NY))) > 127
        else:
            g = random_geometry(np.random.default_rng(a.random))
        sx, sy, _ = solve_unit(g)
        ca, sa = math.cos(math.radians(a.angle)), math.sin(math.radians(a.angle))
        vm = von_mises(sx * ca + sy * sa) * a.load * g
        np.save(a.out, vm)
        r = {"saved": a.out, "max_vm_MPa": round(float(vm.max()), 3), "elements": int(g.sum())}
    elif a.cmd == "train":
        r = train(a.data, a.model, a.out, a.split, a.epochs, lr=a.lr, base=a.base, max_minutes=a.max_minutes, max_cases=a.max_cases)
    elif a.cmd == "predict":
        r = predict(a.model, a.data, a.out, a.steps, a.limit)
    elif a.cmd == "metrics":
        d = np.load(a.pred); r = {"kind": str(d["kind"]), "split": str(d["split"]), **metrics(d["pred"], d["true"], d["x"][:, 0] > 0)}
    else:
        r = {"plot": plot(a.pred, a.out)}
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
