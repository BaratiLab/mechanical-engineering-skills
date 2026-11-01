#!/usr/bin/env python3
"""Melt-pool geometry and mode prediction for metal AM, after MeltpoolNet
(Akbari et al., Additive Manufacturing 55 (2022) 102817; data: github.com/BaratiLab/MeltpoolNet).

  rosenthal  python meltpool.py rosenthal --material SS316L --power 200 --velocity 800 [--absorptivity 0.35]
  identify   python meltpool.py identify --target depth|width|length        dimensionally consistent power law
  benchmark  python meltpool.py benchmark --target depth --features baseline,hatch,abs1,onehot,elemental \
                 [--split random|paper] [--models rf,gb,nn,ridge,lasso,svr,gp]
  train      python meltpool.py train --target depth --features baseline,abs1 --model gb --out depth.joblib
  predict    python meltpool.py predict --models depth.joblib,width.joblib --material Ti-6Al-4V --power 250 --velocity 1000 --beam 80
  classify   python meltpool.py classify --features baseline,abs1,hatch [--split random|paper]   mode: keyhole/LOF/balling/desirable

Units in and out: power W, velocity mm/s, beam diameter / hatch / layer / melt-pool dimensions um,
density kg/m3, Cp J/kgK, k W/mK, melting T in K (as in the MeltpoolNet CSVs).
"""
import argparse
import json
import math
import os
import sys

import numpy as np

CACHE = os.path.expanduser(os.environ.get("LPBF_CACHE", "~/.cache/me-design-skills/meltpoolnet"))
URLS = {"classification": "https://raw.githubusercontent.com/BaratiLab/MeltpoolNet/main/Data/meltpoolnet_classification.csv",
        "regression": "https://raw.githubusercontent.com/BaratiLab/MeltpoolNet/main/Data/meltpoolnet_regression.csv"}
TARGETS = {"depth": "depth of meltpool", "width": "width of melt pool", "length": "length of melt pool"}
T0 = 293.0
# element properties for "elemental featurization" (paper Table 2): Z, atomic volume (cm3/mol),
# 1st ionization energy (eV), heat of fusion (kJ/mol), electron affinity (eV), atomic weight  [mendeleev]
ELEM = {"Y": [39, 19.889, 6.2173, 11.5, 0.307, 88.906], "Zn": [30, 9.165, 9.3942, 7.28, 0.0, 65.38],
        "Mg": [12, 13.968, 7.6462, 9.2, 0.0, 24.305], "Si": [14, 12.056, 8.1517, 50.6, 1.3895, 28.085],
        "Al": [13, 9.993, 5.9858, 10.75, 0.4328, 26.982], "Sn": [50, 16.291, 7.3439, 7.07, 1.1121, 118.71],
        "Zr": [40, 13.991, 6.6341, 19.2, 0.426, 91.224], "W": [74, 9.525, 7.864, 35.0, 0.8163, 183.84],
        "Ti": [22, 10.623, 6.8281, 18.8, 0.079, 47.867], "V": [23, 8.49, 6.7462, 17.5, 0.525, 50.942],
        "Co": [27, 6.652, 7.881, 15.48, 0.6623, 58.933], "Cu": [29, 7.092, 7.7264, 13.01, 1.235, 63.546],
        "Ta": [73, 11.033, 7.5496, 24.7, 0.322, 180.95], "Nb": [41, 10.841, 6.7588, 26.8, 0.9174, 92.906],
        "Ni": [28, 6.595, 7.6399, 17.61, 1.156, 58.693], "Cr": [24, 7.272, 6.7665, 21.0, 0.666, 51.996],
        "Fe": [26, 7.096, 7.9025, 13.8, 0.151, 55.845], "Mn": [25, 7.526, 7.434, 13.4, 0.0, 54.938],
        "Mo": [42, 9.407, 7.0924, 28.0, 0.748, 95.95]}
ELEM_NAMES = ["Z", "atomic_volume", "ionization_energy", "heat_of_fusion", "electron_affinity", "atomic_weight"]
NUMCOLS = ["Power", "Velocity", "beam D", "Hatch spacing", "layer thickness", "density", "Cp", "k", "melting T",
           "minimum absorptivity", "minimal absorptivity", "depth of meltpool", "width of melt pool", "length of melt pool"]


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


def load(kind="regression", process="PBF"):
    import pandas as pd
    d = pd.read_csv(fetch()[kind])
    d = d.loc[:, [c for c in d.columns if not c.startswith("Unnamed")]]
    for c in NUMCOLS + [c for c in d.columns if "wt" in c]:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if "minimal absorptivity" in d and "minimum absorptivity" not in d:
        d["minimum absorptivity"] = d["minimal absorptivity"]
    if process:
        d = d[d["Process"] == process]
    d["group"] = d["paper ID"].astype(str) if "paper ID" in d else "all"
    return d.reset_index(drop=True)


def material_props(d=None):
    d = load() if d is None else d
    g = d.groupby("Material")[["density", "Cp", "k", "melting T", "minimum absorptivity"]].median()
    return {m: {k: (None if v != v else float(v)) for k, v in r.items()} for m, r in g.iterrows()}


# ------------------------------------------------------------------ physics
def absorptivity1(P, V, beam_um, rho, cp, Tm, eta_m, T0=T0):
    """Paper Eq. 2 (keyhole-aware absorptivity): 0.7[1 - exp(-0.6 eta_m P / ((Tm-T0) pi rho Cp V r0^2))], SI inside."""
    r0 = beam_um * 1e-6 / 2
    x = eta_m * P / ((Tm - T0) * math.pi * rho * cp * (V * 1e-3) * r0 ** 2) if r0 > 0 else np.nan
    return 0.7 * (1 - np.exp(-0.6 * x))


def absorptivity2(P, V, W_um, rho, cp, k, Tm, T0=T0):
    """Paper Eq. 3 (conduction-mode absorptivity from a MEASURED width). Uses W: never a feature when predicting W."""
    W = W_um * 1e-6
    return (math.pi * k * (Tm - T0) * W + math.e * math.pi * rho * cp * (Tm - T0) * (V * 1e-3) * W ** 2 / 8) / P


def rosenthal(P, V, rho, cp, k, Tm, absorptivity=None, material=None, T0=T0):
    """Rosenthal point-source estimates (paper Eqs. 8a-c), in um.  Q = absorptivity * P.
    A = 2.5 for AlSi10Mg, 2 otherwise (as in the paper)."""
    eta = 1.0 if absorptivity is None else absorptivity
    Q, v, dT = eta * P, V * 1e-3, Tm - T0
    A = 2.5 if material and "AlSi10Mg" in material else 2.0
    D = math.sqrt(A * Q / (math.e * math.pi * rho * cp * dT * v))
    return {"depth_um": D * 1e6, "width_um": 2 * D * 1e6, "length_um": Q / (2 * math.pi * k * dT) * 1e6,
            "absorbed_power_W": Q, "absorptivity_used": eta}


# ------------------------------------------------------------------ featurization (paper Table 1)
def featurize(d, feats, target=None):
    import pandas as pd
    X = pd.DataFrame(index=d.index)
    base = ["Power", "Velocity", "density", "Cp", "k", "melting T"]
    for c in base:
        X[c] = d[c]
    if "beam" in feats or "abs1" in feats:
        X["beam D"] = d["beam D"]
    if "hatch" in feats:
        X["Hatch spacing"] = d["Hatch spacing"]
    if "layer" in feats:
        X["layer thickness"] = d["layer thickness"]
    if "energy" in feats:
        X["line_energy"] = d["Power"] / d["Velocity"]
        X["norm_enthalpy"] = [absorptivity1(*a) if all(v == v for v in a) else np.nan for a in
                              zip(d.Power, d.Velocity, d["beam D"], d.density, d.Cp, d["melting T"], d["minimum absorptivity"])]
    if "abs1" in feats:
        X["absorptivity1"] = [absorptivity1(*a) if all(v == v for v in a) else np.nan for a in
                              zip(d.Power, d.Velocity, d["beam D"], d.density, d.Cp, d["melting T"], d["minimum absorptivity"])]
    if "abs2" in feats:
        if target in ("width", "depth", "length", None) and target is not None:
            print(f"WARNING: absorptivity2 is computed from the measured melt-pool WIDTH; using it to predict {target} "
                  "leaks the label (width) or a quantity strongly correlated with it.", file=sys.stderr)
        X["absorptivity2"] = [absorptivity2(*a) if all(v == v for v in a) else np.nan for a in
                              zip(d.Power, d.Velocity, d["width of melt pool"], d.density, d.Cp, d.k, d["melting T"])]
    if "onehot" in feats:
        for m in d["Material"].value_counts().index[:15]:
            X["mat_" + m] = (d["Material"] == m).astype(float)
    wt = [c for c in d.columns if "wt" in c]
    if "composition" in feats or "elemental" in feats:
        comp = d[wt].fillna(0.0)
        if "composition" in feats:
            for c in wt:
                X[c] = comp[c]
        if "elemental" in feats:  # composition-weighted element properties (paper Eq. 1)
            frac = comp.div(comp.sum(axis=1).replace(0, np.nan), axis=0)
            for j, name in enumerate(ELEM_NAMES):
                X["el_" + name] = sum(frac[c] * ELEM[c.split(" ")[0]][j] for c in wt if c.split(" ")[0] in ELEM)
    return X


# ------------------------------------------------------------------ models
def make_model(name, kind="reg", seed=0):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn import ensemble, linear_model, neural_network, svm, gaussian_process
    if kind == "reg":
        m = {"rf": ensemble.RandomForestRegressor(300, random_state=seed, n_jobs=-1),
             "gb": ensemble.GradientBoostingRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, random_state=seed),
             "nn": neural_network.MLPRegressor(hidden_layer_sizes=(128, 64), max_iter=3000, learning_rate_init=3e-3, random_state=seed),
             "ridge": linear_model.Ridge(1.0), "lasso": linear_model.Lasso(0.5, max_iter=20000),
             "svr": svm.SVR(C=300), "gp": gaussian_process.GaussianProcessRegressor(normalize_y=True, alpha=1e-2)}[name]
    else:
        m = {"rf": ensemble.RandomForestClassifier(300, random_state=seed, n_jobs=-1),
             "gb": ensemble.GradientBoostingClassifier(random_state=seed),
             "nn": neural_network.MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=3000, random_state=seed),
             "lr": linear_model.LogisticRegression(max_iter=5000), "svc": svm.SVC(probability=True),
             "gp": gaussian_process.GaussianProcessClassifier()}[name]
    return make_pipeline(StandardScaler(), m)   # paper Eq. 4: z-score normalisation


def _xy(target, feats, process="PBF"):
    d = load(process=process)
    col = TARGETS[target]
    X = featurize(d, feats, target)
    ok = X.notna().all(axis=1) & d[col].notna()
    return X[ok], d.loc[ok, col].values, d.loc[ok, "group"].values, d[ok]


def cv_splits(n, groups, split, k=5, seed=0):
    from sklearn.model_selection import GroupKFold, KFold
    if split == "paper":
        return list(GroupKFold(k).split(np.zeros(n), groups=groups))
    return list(KFold(k, shuffle=True, random_state=seed).split(np.zeros(n)))


def benchmark(target, feats, split="random", models=("rf", "gb", "nn", "ridge"), k=5, calibrate=0, seed=0):
    """split=paper holds out whole source papers (a new lab/machine). calibrate=n moves n measured tracks of each
    held-out paper into training -- the 'measure a few single tracks on your machine first' scenario."""
    from sklearn.metrics import mean_absolute_error, r2_score
    X, y, g, _ = _xy(target, feats)
    res = {"target": target, "features": feats, "split": split, "calibration_tracks_per_paper": calibrate,
           "n": int(len(y)), "papers": int(len(set(g))), "models": {}}
    rng = np.random.default_rng(seed)
    for name in models:
        yp = np.full(len(y), np.nan)
        for tr, te in cv_splits(len(y), g, split, k):
            tr, te = list(tr), np.asarray(te)
            if calibrate and split == "paper":
                ev = []
                for gg in set(g[te]):
                    idx = te[g[te] == gg]
                    pick = rng.choice(idx, min(calibrate, len(idx) - 1), replace=False)
                    tr += list(pick); ev += [i for i in idx if i not in set(pick)]
                te = np.asarray(ev, int)
            m = make_model(name); m.fit(X.iloc[tr], y[tr]); yp[te] = m.predict(X.iloc[te])
        ok = ~np.isnan(yp)
        res.setdefault("_pred", {})[name] = (y[ok], yp[ok])
        res["models"][name] = {"R2": round(float(r2_score(y[ok], yp[ok])), 4), "MAE_um": round(float(mean_absolute_error(y[ok], yp[ok])), 2)}
    res["best"] = max(res["models"], key=lambda n: res["models"][n]["R2"])
    return res


def parity_plot(results, out):
    """results: list of benchmark() outputs; one panel each, best model."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, len(results), figsize=(4.6 * len(results), 4.4), squeeze=False)
    for ax, r in zip(axs[0], results):
        yt, yp = r["_pred"][r["best"]]
        lim = [0, max(yt.max(), yp.max()) * 1.05]
        ax.scatter(yt, yp, s=7, alpha=0.5, color="#2c7fb8"); ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
        cal = f", {r['calibration_tracks_per_paper']} tracks/paper" if r.get("calibration_tracks_per_paper") else ""
        ax.set_title(f"{r['target']}: {r['split']} split{cal}\n{r['best']}  R² {r['models'][r['best']]['R2']:.2f}, "
                     f"MAE {r['models'][r['best']]['MAE_um']:.0f} µm", fontsize=9)
        ax.set_xlabel("measured (µm)"); ax.set_ylabel("predicted (µm)")
    fig.tight_layout(); fig.savefig(out, dpi=140)
    return out


def classify(feats, split="random", models=("rf", "gb", "nn", "lr"), k=5):
    from sklearn.metrics import accuracy_score, roc_auc_score
    d = load("classification")
    d = d[d["meltpool shape"].isin(["keyhole", "LOF", "balling", "desirable"])]
    X = featurize(d, feats + (["beam"] if "beam" not in feats else []))
    ok = X.notna().all(axis=1)
    X, y, g = X[ok], d.loc[ok, "meltpool shape"].values, d.loc[ok, "group"].values
    res = {"features": feats, "split": split, "n": int(len(y)), "class_counts": {c: int((y == c).sum()) for c in set(y)}, "models": {}}
    labels = sorted(set(y))
    for name in models:
        P = np.zeros((len(y), len(labels)))
        for tr, te in cv_splits(len(y), g, split, k):
            m = make_model(name, "clf"); m.fit(X.iloc[tr], y[tr])
            pr = m.predict_proba(X.iloc[te]); cls = list(m.classes_)
            for j, c in enumerate(labels):
                if c in cls:
                    P[te, j] = pr[:, cls.index(c)]
        yp = np.array(labels)[P.argmax(1)]
        try:
            auc = float(roc_auc_score(y, P, multi_class="ovr", labels=labels))
        except ValueError:
            auc = float("nan")
        res["models"][name] = {"accuracy": round(float(accuracy_score(y, yp)), 4), "auc_ovr_macro": round(auc, 4)}
    res["best"] = max(res["models"], key=lambda n: res["models"][n]["accuracy"])
    return res


# ------------------------------------------------------------------ explicit model identification (paper Sec. 3.6)
# y = w0 P^w1 V^w2 rho^w3 Cp^w4 k^w5 (Tm-T0)^w6, dimensions [kg, m, s, K] per Table 6
DIMS = np.array([[1, 2, -3, 0],    # P   W = kg m2 s-3
                 [0, 1, -1, 0],    # V   m s-1
                 [1, -3, 0, 0],    # rho kg m-3
                 [0, 2, -2, -1],   # Cp  m2 s-2 K-1
                 [1, 1, -3, -1],   # k   kg m s-3 K-1
                 [0, 0, 0, 1]])    # dT  K
NAMES = ["P", "V", "rho", "Cp", "k", "dT"]


def identify(target, refine=True):
    """Constrained power-law fit. Log-space least squares with the 4 dimensional-consistency equalities solved
    exactly (KKT), then optional refinement of the paper's linear-space L2 objective on the constraint manifold."""
    from sklearn.metrics import r2_score
    d = load()
    col = TARGETS[target]
    cols = ["Power", "Velocity", "density", "Cp", "k", "melting T", col]
    d = d.dropna(subset=cols)
    d = d[(d[cols[:-1]] > 0).all(axis=1) & (d["melting T"] > T0)]
    Xs = np.c_[d.Power, d.Velocity * 1e-3, d.density, d.Cp, d.k, d["melting T"] - T0]   # SI
    y = d[col].values * 1e-6                                                              # m
    L, ly = np.log(Xs), np.log(y)
    A = np.c_[np.ones(len(y)), L]                           # unknowns [log w0, w1..w6]
    C = np.c_[np.zeros(4), DIMS.T]                          # C @ w = b
    b = np.array([0, 1, 0, 0.0])                            # target dimension: metre
    K = np.block([[2 * A.T @ A, C.T], [C, np.zeros((4, 4))]])
    sol = np.linalg.solve(K, np.r_[2 * A.T @ ly, b])[:7]
    if refine:  # minimise ||y - f||^2 in linear space, parameterised in the null space of C
        from scipy.linalg import null_space
        from scipy.optimize import minimize
        N = null_space(C); p0 = np.zeros(N.shape[1])
        f = lambda p: np.sum((y - np.exp(A @ (sol + N @ p))) ** 2) / np.sum(y ** 2)
        r = minimize(f, p0, method="Nelder-Mead", options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-12})
        if f(r.x) < f(p0):
            sol = sol + N @ r.x
    yp = np.exp(A @ sol)
    w = dict(zip(NAMES, map(float, sol[1:])))
    res = {"target": target, "n": int(len(y)), "w0_SI": float(np.exp(sol[0])), "exponents": {k: round(v, 3) for k, v in w.items()},
           "dimension_residual": [round(float(v), 6) for v in DIMS.T @ sol[1:] - b],
           "R2": round(float(r2_score(y, yp)), 4),
           "equation": f"{target} [m] = {np.exp(sol[0]):.4g} * " + " * ".join(f"{n}^{w[n]:.3f}" for n in NAMES) + "   (SI units, dT = Tm - 293 K)"}
    # Rosenthal on the same rows (absorbed power = P, paper convention) for comparison
    ros = np.array([rosenthal(P, V, r, c, k, Tm, None, m)[f"{target}_um"] for P, V, r, c, k, Tm, m in
                    zip(d.Power, d.Velocity, d.density, d.Cp, d.k, d["melting T"], d.Material)]) * 1e-6
    res["rosenthal_R2_same_rows"] = round(float(r2_score(y, ros)), 4)
    res["paper_reference_R2"] = {"depth": {"rosenthal": 0.654, "identified": 0.787, "ml": 0.958},
                                 "width": {"rosenthal": 0.782, "identified": 0.991, "ml": 0.9773},
                                 "length": {"rosenthal": -0.15, "identified": 0.473, "ml": 0.9962}}[target]
    return res


def train(target, feats, model, out, extra=None, extra_weight=5.0):
    """extra: CSV of your own measured tracks (MeltpoolNet column names); up-weighted so the model adapts to your machine."""
    import joblib
    import pandas as pd
    X, y, g, d = _xy(target, feats)
    w = np.ones(len(y))
    if extra:
        e = pd.read_csv(extra)
        for c in NUMCOLS + ["Material"]:
            if c not in e:
                e[c] = np.nan
        mp = material_props()
        for c in ("density", "Cp", "k", "melting T", "minimum absorptivity"):   # fill properties from the database
            e[c] = [v if v == v else (mp.get(m) or {}).get(c, np.nan) for v, m in zip(e[c], e["Material"])]
        for c in [c for c in load().columns if "wt" in c]:
            e[c] = e[c] if c in e else np.nan
        Xe = featurize(e, feats, target)[list(X.columns)]
        ok = Xe.notna().all(axis=1) & e[TARGETS[target]].notna()
        X = pd.concat([X, Xe[ok]], ignore_index=True); y = np.r_[y, e.loc[ok, TARGETS[target]].values]
        w = np.r_[w, np.full(int(ok.sum()), extra_weight)]
    m = make_model(model)
    m.fit(X, y, **{f"{m.steps[-1][0]}__sample_weight": w} if model in ("rf", "gb") else {})
    joblib.dump({"model": m, "target": target, "features": feats, "columns": list(X.columns),
                 "props": material_props(), "cv_paper_split": benchmark(target, feats, "paper", (model,))["models"][model],
                 "train_range": {c: [float(X[c].min()), float(X[c].max())] for c in X.columns[:6]}}, out)
    return {"saved": out, "n": int(len(y))}


def predict(model_paths, material, power, velocity, beam=None, hatch=None, layer=None, props=None):
    import joblib
    import pandas as pd
    out = {"material": material, "power_W": power, "velocity_mm_s": velocity}
    for p in model_paths:
        b = joblib.load(p)
        mp = dict(b["props"].get(material, {}))
        mp.update(props or {})
        if not mp:
            raise SystemExit(f"unknown material {material}: pass --props density,Cp,k,Tm,eta_m")
        row = pd.DataFrame([{"Material": material, "Power": power, "Velocity": velocity, "beam D": beam, "Hatch spacing": hatch,
                             "layer thickness": layer, "density": mp["density"], "Cp": mp["Cp"], "k": mp["k"],
                             "melting T": mp["melting T"], "minimum absorptivity": mp.get("minimum absorptivity"),
                             "width of melt pool": np.nan, **{c: 0.0 for c in []}}])
        for c in [c for c in load().columns if "wt" in c]:
            row[c] = np.nan
        X = featurize(row, b["features"])[b["columns"]]
        if X.isna().any(axis=None):
            raise SystemExit(f"{p}: missing inputs for features {list(X.columns[X.isna().any()])}")
        rng = b["train_range"]
        oor = [c for c in rng if not (rng[c][0] <= float(X[c].iloc[0]) <= rng[c][1])]
        out[f"{b['target']}_um"] = round(float(b["model"].predict(X)[0]), 1)
        out.setdefault("validation_paper_split", {})[b["target"]] = b["cv_paper_split"]
        if oor:
            out.setdefault("outside_training_range", []).extend(oor)
    r = rosenthal(power, velocity, mp["density"], mp["Cp"], mp["k"], mp["melting T"], mp.get("minimum absorptivity"), material)
    out["rosenthal_um (Q = eta_m P)"] = {k: round(v, 1) for k, v in r.items() if k.endswith("_um")}
    if "depth_um" in out and "width_um" in out:
        out["width_over_depth"] = round(out["width_um"] / out["depth_um"], 2)
        out["keyhole_flag (W/D<1.5)"] = out["width_over_depth"] < 1.5
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("rosenthal")
    for a in ("power", "velocity"):
        s.add_argument(f"--{a}", type=float, required=True)
    s.add_argument("--material"); s.add_argument("--absorptivity", type=float)
    s.add_argument("--props", help="density,Cp,k,Tm(K)")
    s = sub.add_parser("identify"); s.add_argument("--target", choices=list(TARGETS), required=True)
    s.add_argument("--no-refine", action="store_true")
    for name in ("benchmark", "classify"):
        s = sub.add_parser(name)
        if name == "benchmark":
            s.add_argument("--target", choices=list(TARGETS), required=True)
        s.add_argument("--features", default="baseline"); s.add_argument("--split", choices=["random", "paper"], default="random")
        s.add_argument("--models")
        if name == "benchmark":
            s.add_argument("--calibrate", type=int, default=0, help="with --split paper: n tracks of each held-out paper join training")
            s.add_argument("--plot", help="parity plot PNG for the best model")
    s = sub.add_parser("train"); s.add_argument("--target", choices=list(TARGETS), required=True)
    s.add_argument("--features", default="baseline"); s.add_argument("--model", default="gb"); s.add_argument("--out", required=True)
    s.add_argument("--extra", help="CSV of your own measured tracks to adapt the model (MeltpoolNet column names)")
    s = sub.add_parser("predict"); s.add_argument("--models", required=True); s.add_argument("--material", required=True)
    for a in ("power", "velocity"):
        s.add_argument(f"--{a}", type=float, required=True)
    for a in ("beam", "hatch", "layer"):
        s.add_argument(f"--{a}", type=float)
    s.add_argument("--props", help="density,Cp,k,Tm(K),eta_m for alloys not in the data")
    a = ap.parse_args()
    feats = lambda: [f for f in a.features.split(",") if f and f != "baseline"]
    if a.cmd == "rosenthal":
        if a.props:
            rho, cp, k, tm = map(float, a.props.split(","))
        else:
            mp = material_props().get(a.material) or sys.exit(f"unknown material {a.material}; pass --props")
            rho, cp, k, tm = mp["density"], mp["Cp"], mp["k"], mp["melting T"]
            if a.absorptivity is None:
                a.absorptivity = mp.get("minimum absorptivity")
        r = rosenthal(a.power, a.velocity, rho, cp, k, tm, a.absorptivity, a.material)
    elif a.cmd == "identify":
        r = identify(a.target, not a.no_refine)
    elif a.cmd == "benchmark":
        r = benchmark(a.target, feats(), a.split, tuple(a.models.split(",")) if a.models else ("rf", "gb", "nn", "ridge"),
                      calibrate=a.calibrate)
        if a.plot:
            r["plot"] = parity_plot([r], a.plot)
        r.pop("_pred", None)
    elif a.cmd == "classify":
        r = classify(feats(), a.split, tuple(a.models.split(",")) if a.models else ("rf", "gb", "nn", "lr"))
    elif a.cmd == "train":
        r = train(a.target, feats(), a.model, a.out, a.extra)
    else:
        props = dict(zip(["density", "Cp", "k", "melting T", "minimum absorptivity"], map(float, a.props.split(",")))) if a.props else None
        r = predict(a.models.split(","), a.material, a.power, a.velocity, a.beam, a.hatch, a.layer, props)
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()
