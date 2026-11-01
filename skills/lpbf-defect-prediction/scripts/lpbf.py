#!/usr/bin/env python3
"""L-PBF defect-regime prediction after AdditiveLLM (Pak & Barati Farimani, Additive Manufacturing
Letters 14 (2025) 100292), built on the MeltpoolNet data (Akbari et al., Addit. Manuf. 55 (2022) 102817).

  fetch     python lpbf.py fetch                      download MeltpoolNet CSVs (github.com/BaratiLab/MeltpoolNet)
  criteria  python lpbf.py criteria --depth 120 --width 150 --length 420 --hatch 100 --layer 40
  build     python lpbf.py build --out data.parquet  AdditiveLLM dataset: criteria labels + LoF augmentation
  train     python lpbf.py train --data data.parquet --model model.joblib [--split random|grouped]
  predict   python lpbf.py predict --model model.joblib --material SS316L --power 200 --velocity 800 \
                --beam 80 --hatch 100 --layer 30
  map       python lpbf.py map --model model.joblib --material Ti-6Al-4V --hatch 100 --layer 30 --beam 80 --out map.png

Labels (multi-label, not exclusive): Keyholing, Lack of Fusion, Balling, None.
Criteria (paper Eqs. 1-3), violated -> defect regime:
  Keyholing       width / depth < 1.5
  Lack of Fusion  (hatch / width)^2 + (layer / depth)^2 > 1
  Balling         length / width > pi
"""
import argparse
import json
import math
import os
import sys

import numpy as np

CACHE = os.path.expanduser(os.environ.get("LPBF_CACHE", "~/.cache/mechanical-engineering-skills/meltpoolnet"))
URLS = {"classification": "https://raw.githubusercontent.com/BaratiLab/MeltpoolNet/main/Data/meltpoolnet_classification.csv",
        "regression": "https://raw.githubusercontent.com/BaratiLab/MeltpoolNet/main/Data/meltpoolnet_regression.csv"}
LABELS = ["Keyholing", "Lack of Fusion", "Balling", "None"]
SHAPE_MAP = {"keyhole": "Keyholing", "LOF": "Lack of Fusion", "balling": "Balling", "desirable": "None"}
NUM = ["power", "velocity", "beam", "hatch", "layer", "density", "Cp", "k", "Tm"]
AUG_GRID = np.arange(0, 1000, 50.0)  # 20 hatch spacings x 20 layer heights, 0-950 um (paper Sec. 2.2.1)


# ------------------------------------------------------------------ criteria (Eqs. 1-3)
def criteria(depth=None, width=None, length=None, hatch=None, layer=None):
    out, why = {}, {}
    if depth and width:
        r = width / depth
        out["Keyholing"] = r < 1.5
        why["Keyholing"] = f"width/depth = {r:.2f} ({'<' if r < 1.5 else '>='} 1.5)"
    if depth and width and hatch is not None and layer is not None:
        v = (hatch / width) ** 2 + (layer / depth) ** 2
        out["Lack of Fusion"] = v > 1
        why["Lack of Fusion"] = f"(h/W)^2 + (t/D)^2 = {v:.2f} ({'>' if v > 1 else '<='} 1)"
    if length and width:
        r = length / width
        out["Balling"] = r > math.pi
        why["Balling"] = f"length/width = {r:.2f} ({'>' if r > math.pi else '<='} pi)"
    known = [k for k in ("Keyholing", "Lack of Fusion", "Balling") if k in out]
    out["None"] = bool(known) and not any(out[k] for k in known)
    return {"labels": [k for k in LABELS if out.get(k)], "evaluated": known, "explanation": why,
            "note": "Criteria not evaluated (missing dimensions) cannot be ruled out."}


# ------------------------------------------------------------------ data
def fetch():
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for k, u in URLS.items():
        p = os.path.join(CACHE, f"meltpoolnet_{k}.csv")
        if not os.path.exists(p):
            urllib.request.urlretrieve(u, p)
        out[k] = p
    return out


def baseline_text(r):
    """AdditiveLLM 'Baseline' input: ordered parameters separated by [SEP]; unknown -> empty string."""
    f = lambda v, u: "" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:g} {u}"
    return " [SEP] ".join([str(r["material"]), f(r["power"], "W"), f(r["velocity"], "mm/s"),
                           f(r["beam"], "microns"), f(r["hatch"], "microns"), f(r["layer"], "microns")])


def build(paths, augment=True):
    import pandas as pd
    c = pd.read_csv(paths["classification"]); r = pd.read_csv(paths["regression"])
    c, r = c[c["Process"] == "PBF"], r[r["Process"] == "PBF"]
    common = lambda d: pd.DataFrame({"material": d["Material"], "power": d["Power"], "velocity": d["Velocity"],
                                     "beam": d["beam D"], "hatch": d["Hatch spacing"], "layer": d["layer thickness"],
                                     "density": d["density"], "Cp": d["Cp"], "k": d["k"], "Tm": d["melting T"]}
                                    ).pipe(lambda x: x.assign(**{k: pd.to_numeric(x[k], errors="coerce") for k in NUM}))
    rows = []
    # direct classifications
    dc = common(c)
    for lab in LABELS:
        dc[lab] = 0
    for i, s in enumerate(c["meltpool shape"]):
        if s in SHAPE_MAP:
            dc.iloc[i, dc.columns.get_loc(SHAPE_MAP[s])] = 1
    dc = dc[c["meltpool shape"].isin(SHAPE_MAP).values]
    dc["source"] = "classification"; dc["group"] = ["c%d" % i for i in range(len(dc))]
    rows.append(dc)
    # melt-pool dimensions -> criteria labels
    dr = common(r)
    D, W, Lg = r["depth of meltpool"].values, r["width of melt pool"].values, r["length of melt pool"].values
    lab = {k: np.zeros(len(r), int) for k in LABELS}
    known = np.zeros(len(r), bool)
    for i in range(len(r)):
        res = criteria(D[i] if D[i] == D[i] else None, W[i] if W[i] == W[i] else None, Lg[i] if Lg[i] == Lg[i] else None,
                       dr["hatch"].iloc[i] if dr["hatch"].iloc[i] == dr["hatch"].iloc[i] else None,
                       dr["layer"].iloc[i] if dr["layer"].iloc[i] == dr["layer"].iloc[i] else None)
        if res["evaluated"]:
            known[i] = True
            for k in res["labels"]:
                lab[k][i] = 1
        elif r["meltpool shape"].iloc[i] in SHAPE_MAP:  # fall back to the reported mode
            known[i] = True
            lab[SHAPE_MAP[r["meltpool shape"].iloc[i]]][i] = 1
    for k in LABELS:
        dr[k] = lab[k]
    dr["source"] = "regression"; dr["group"] = ["r%d" % i for i in range(len(dr))]
    keep = known.copy()
    rows.append(dr[keep])
    if augment:  # Lack-of-Fusion augmentation: same melt pool, new hatch/layer combinations
        aug = []
        both = np.where(~np.isnan(D) & ~np.isnan(W))[0]
        H, T = np.meshgrid(AUG_GRID, AUG_GRID, indexing="ij")
        H, T = H.ravel(), T.ravel()
        for i in both:
            base = dr.iloc[i]
            n = len(H)
            a = pd.DataFrame({k: np.repeat(base[k], n) for k in ["material", "power", "velocity", "beam", "density", "Cp", "k", "Tm"]})
            a["hatch"], a["layer"] = H, T
            kh = int(W[i] / D[i] < 1.5)
            bl = int(Lg[i] / W[i] > math.pi) if Lg[i] == Lg[i] else 0
            lof = ((H / W[i]) ** 2 + (T / D[i]) ** 2 > 1).astype(int)
            a["Keyholing"], a["Balling"], a["Lack of Fusion"] = kh, bl, lof
            a["None"] = ((a["Keyholing"] + a["Balling"] + a["Lack of Fusion"]) == 0).astype(int)
            a["source"] = "augmented"; a["group"] = "r%d" % i
            aug.append(a)
        rows.append(pd.concat(aug, ignore_index=True))
    df = pd.concat(rows, ignore_index=True)
    df["text"] = [baseline_text(x) for x in df.to_dict("records")]
    return df


# ------------------------------------------------------------------ model
# Physics priors as monotonic constraints (+1 increasing, -1 decreasing) on the probability of each regime.
# Keyholing grows with energy input; lack of fusion grows with hatch, layer and speed and falls with power.
MONOTONE = {
    "Keyholing": {"power": 1, "velocity": -1, "line_energy": 1, "norm_beam_energy": 1},
    "Lack of Fusion": {"power": -1, "velocity": 1, "hatch": 1, "layer": 1, "line_energy": -1, "vol_energy": -1},
}
def features(df, materials=None):
    import pandas as pd
    X = df[NUM].astype(float).copy()
    X["line_energy"] = X["power"] / X["velocity"]                              # J/mm
    X["vol_energy"] = X["power"] / (X["velocity"] * X["hatch"].replace(0, np.nan) / 1e3 * X["layer"].replace(0, np.nan) / 1e3)
    X["norm_beam_energy"] = X["power"] / (X["velocity"] * X["beam"] / 1e3)
    mats = materials or sorted(df["material"].value_counts().index[:12])
    for mname in mats:
        X["mat_" + mname] = (df["material"] == mname).astype(float)
    return X, mats


def train(data, model_path, split="random", seed=0, monotone=True):
    import joblib
    import pandas as pd
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import f1_score
    df = pd.read_parquet(data) if data.endswith(".parquet") else pd.read_csv(data)
    rng = np.random.default_rng(seed)
    if split == "grouped":  # whole melt pools (and their augmentations) held out
        g = np.array(df["group"].unique(), dtype=object); rng.shuffle(g)
        n = len(g); gt, gs = set(g[: int(.75 * n)]), set(g[int(.75 * n): int(.9 * n)])
        part = df["group"].map(lambda x: "train" if x in gt else ("test" if x in gs else "val"))
    else:                   # paper: shuffle all entries, 75/15/10
        u = rng.random(len(df))
        part = pd.Series(np.where(u < .75, "train", np.where(u < .9, "test", "val")), index=df.index)
    X, mats = features(df)
    models, res = {}, {"split": split, "n": {p: int((part == p).sum()) for p in ("train", "test", "val")}}
    preds = {}
    for lab in LABELS:
        mono = [MONOTONE.get(lab, {}).get(c, 0) for c in X.columns]
        clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, max_leaf_nodes=63, random_state=seed,
                                             monotonic_cst=mono if monotone else None)
        clf.fit(X[part == "train"], df.loc[part == "train", lab])
        models[lab] = clf
        preds[lab] = clf.predict(X[part == "val"])
    Y = df.loc[part == "val", LABELS].values
    Yh = np.c_[[preds[l] for l in LABELS]].T
    res["exact_match_accuracy"] = float((Y == Yh).all(1).mean())
    res["per_label_accuracy"] = {l: float((Y[:, i] == Yh[:, i]).mean()) for i, l in enumerate(LABELS)}
    res["f1"] = {l: float(f1_score(Y[:, i], Yh[:, i], zero_division=0)) for i, l in enumerate(LABELS)}
    res["macro_f1"] = float(np.mean(list(res["f1"].values())))
    joblib.dump({"models": models, "materials": mats,
                 "material_props": df.groupby("material")[["density", "Cp", "k", "Tm"]].median().to_dict("index"),
                 "support": df.loc[df["source"] != "augmented", ["material", "power", "velocity"]].drop_duplicates()
                                .reset_index(drop=True),
                 "metrics": res}, model_path)
    return res


def _row(bundle, material, power, velocity, beam, hatch, layer, props=None):
    import pandas as pd
    p = (props or {}) or bundle["material_props"].get(material, {})
    if not p:
        raise SystemExit(f"unknown material '{material}': pass --props density,Cp,k,Tm (SI: kg/m3, J/kgK, W/mK, K or C as in data)")
    return pd.DataFrame([{"material": material, "power": power, "velocity": velocity, "beam": beam, "hatch": hatch,
                          "layer": layer, **{k: p.get(k, np.nan) for k in ("density", "Cp", "k", "Tm")}}])


def predict(model_path, material, power, velocity, beam=None, hatch=None, layer=None, props=None, threshold=0.5):
    import joblib
    b = joblib.load(model_path)
    df = _row(b, material, power, velocity, beam, hatch, layer, props)
    X, _ = features(df, b["materials"])
    prob = {l: float(b["models"][l].predict_proba(X)[0, 1]) for l in LABELS}
    defects = [l for l in LABELS[:3] if prob[l] >= threshold]
    labels = defects or ["None"]   # None is exclusive: decided by the three defect heads
    e = {"line_energy_J_per_mm": power / velocity}
    if hatch and layer:
        e["volumetric_energy_J_per_mm3"] = power / (velocity * hatch / 1e3 * layer / 1e3)
    return {"input": baseline_text(df.iloc[0].to_dict()), "probabilities": prob, "predicted": labels,
            "energy": e, "material_known": material in b["materials"],
            "model_validation": {k: b["metrics"][k] for k in ("split", "exact_match_accuracy", "macro_f1")}}


def process_map(model_path, material, hatch, layer, beam, out, pmax=None, vmax=None):
    import joblib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    b = joblib.load(model_path)
    P = np.linspace(50, pmax or 500, 60); V = np.linspace(100, vmax or 2500, 60)
    PP, VV = np.meshgrid(P, V, indexing="ij")
    p = b["material_props"].get(material)
    if p is None:
        raise SystemExit(f"unknown material '{material}'")
    df = pd.DataFrame({"material": material, "power": PP.ravel(), "velocity": VV.ravel(), "beam": beam, "hatch": hatch,
                       "layer": layer, **{k: p[k] for k in ("density", "Cp", "k", "Tm")}})
    X, _ = features(df, b["materials"])
    pr = {l: b["models"][l].predict_proba(X)[:, 1].reshape(PP.shape) for l in LABELS}
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    cols = {"Keyholing": "#c0392b", "Lack of Fusion": "#2c7fb8", "Balling": "#e6a117"}
    for l, c in cols.items():
        ax.contourf(VV, PP, pr[l], levels=[0.5, 1.01], colors=[c], alpha=0.35)
        ax.contour(VV, PP, pr[l], levels=[0.5], colors=[c], linewidths=1.5)
    worst = np.maximum.reduce([pr[l] for l in cols])  # defect-free = every defect head below 0.5
    ok = worst < 0.5
    ax.contourf(VV, PP, worst, levels=[-0.01, 0.5], colors=["#2e8b57"], alpha=0.25)
    for l, c in list(cols.items()) + [("None (defect-free)", "#2e8b57")]:
        ax.plot([], [], color=c, lw=6, alpha=0.5, label=l)
    if b.get("support") is not None:  # where the model actually saw this material (extrapolation is everywhere else)
        s = b["support"]; s = s[s["material"] == material]
        ax.scatter(s["velocity"], s["power"], s=10, facecolors="none", edgecolors="k", lw=0.6,
                   label=f"measured points ({len(s)})")
    ax.set_xlim(V[0], V[-1]); ax.set_ylim(P[0], P[-1])
    ax.set_xlabel("Scan velocity (mm/s)"); ax.set_ylabel("Laser power (W)")
    ax.set_title(f"{material}: predicted regimes (hatch {hatch} µm, layer {layer} µm, beam {beam} µm)", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(out, dpi=150)
    win = [(float(PP[i, j]), float(VV[i, j])) for i, j in zip(*np.nonzero(ok))]
    best = None
    if win:  # most robust point: highest P(None) with neighbours also defect-free
        from scipy.ndimage import uniform_filter
        sm = uniform_filter(1 - worst, 5)
        i, j = np.unravel_index(np.argmax(np.where(ok, sm, -1)), sm.shape)
        best = {"power_W": float(PP[i, j]), "velocity_mm_s": float(VV[i, j]), "margin_smoothed": float(sm[i, j])}
    return {"map": out, "defect_free_fraction": float(ok.mean()), "most_robust_point": best}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    s = sub.add_parser("criteria")
    for k in ("depth", "width", "length", "hatch", "layer"):
        s.add_argument(f"--{k}", type=float)
    s = sub.add_parser("build"); s.add_argument("--out", required=True); s.add_argument("--no-augment", action="store_true")
    s = sub.add_parser("train"); s.add_argument("--data", required=True); s.add_argument("--model", required=True)
    s.add_argument("--split", choices=["random", "grouped"], default="grouped")
    s.add_argument("--no-monotone", action="store_true", help="drop the physics monotonic constraints")
    for name in ("predict", "map"):
        s = sub.add_parser(name); s.add_argument("--model", required=True); s.add_argument("--material", required=True)
        s.add_argument("--beam", type=float); s.add_argument("--hatch", type=float); s.add_argument("--layer", type=float)
        if name == "predict":
            s.add_argument("--power", type=float, required=True); s.add_argument("--velocity", type=float, required=True)
            s.add_argument("--props", help="density,Cp,k,Tm for materials not in the data")
        else:
            s.add_argument("--out", required=True); s.add_argument("--pmax", type=float); s.add_argument("--vmax", type=float)
    a = ap.parse_args()
    if a.cmd == "fetch":
        r = fetch()
    elif a.cmd == "criteria":
        r = criteria(a.depth, a.width, a.length, a.hatch, a.layer)
    elif a.cmd == "build":
        df = build(fetch(), augment=not a.no_augment)
        (df.to_parquet if a.out.endswith(".parquet") else df.to_csv)(a.out, **({} if a.out.endswith(".parquet") else {"index": False}))
        r = {"rows": len(df), "by_source": df["source"].value_counts().to_dict(),
             "label_share": {l: round(float(df[l].mean()), 4) for l in LABELS}, "example_text": df["text"].iloc[0]}
    elif a.cmd == "train":
        r = train(a.data, a.model, a.split, monotone=not a.no_monotone)
    elif a.cmd == "predict":
        props = dict(zip(["density", "Cp", "k", "Tm"], map(float, a.props.split(",")))) if a.props else None
        r = predict(a.model, a.material, a.power, a.velocity, a.beam, a.hatch, a.layer, props)
    else:
        r = process_map(a.model, a.material, a.hatch, a.layer, a.beam, a.out, a.pmax, a.vmax)
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()
