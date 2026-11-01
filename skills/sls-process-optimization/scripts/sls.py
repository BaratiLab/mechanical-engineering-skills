#!/usr/bin/env python3
"""Batch-to-batch process optimization for polymer selective laser sintering (SLS), after Pak, Alvarado &
Barati Farimani, "AI Agentic Selective Laser Sintering Process Optimization" (arXiv:2608.25928, 2026).

The paper's agent (Claude, MCP tools, PostgreSQL memory) proposed the next batch's fill energy density, hotspot
overlap and surface temperature from earlier ASTM D638/D790 results on an SLS4All Inova Mk1, reaching
TDS-comparable properties for PA11 Onyx in 4 batches and a PA12 blend in 3. Here you are the agent; this script
is the memory, the test-data reduction and a bounded Bayesian suggestion engine.

  init      python sls.py init --db builds.sqlite [--seed-paper]                 create the build history
  material  python sls.py material --db builds.sqlite --name "PA11 Onyx" --tds Et=1680,UTS=55,Ef=1290,sf=54.2 --tmelt 189
  batch     python sls.py batch --db builds.sqlite --material "PA11 Onyx" --id Q --fill 32 --overlap 50 --tsurf 186 [--outline 32,22] [--notes ".."]
  astm      python sls.py astm --test d638 --type 4 --csv sample1.csv [--width 6 --thick 4] | --test d790 --csv flex1.csv [--span 51.2]
  result    python sls.py result --db builds.sqlite --batch Q --Et 1323 --UTS 22.1 [--Ef 867 --sf 31.3] [--from astm.json]
  history   python sls.py history --db builds.sqlite --material "PA11 Onyx" [--plot progress.png]
  suggest   python sls.py suggest --db builds.sqlite --material "PA11 Onyx" [--objective UTS|Et|score] [--n 3]

Energy density here is the Inova's line energy (mJ/mm). Mechanical properties: Et, Ef in MPa; UTS, sf in MPa.
"""
import argparse
import json
import math
import os
import sqlite3
import sys

import warnings

import numpy as np

warnings.filterwarnings("ignore", module="sklearn")

# Paper Tables 1-3 (best-specimen values; H not reproducible, flagged). Inova Mk1, 100 um layers, 145 C chamber.
PAPER_BATCHES = [
    # material, id, fill, overlap, tsurf, Et, UTS, Ef, sf, note
    ("PA12 GF", "A", 14, 25, 172, 397, 3.5, None, None, ""), ("PA12 GF", "B", 20, 25, 172, 609, 4.4, None, None, ""),
    ("PA12 GF", "C", 20, 25, 172, 651, 4.6, 404, 11.0, ""), ("PA12 GF", "D", 20, 50, 173, 1193, 8.0, 938, 22.4, ""),
    ("PA12 GF", "E", 20, 50, 173, 1402, 11.2, 1232, 26.9, ""), ("PA12 GF", "F", 24, 50, 173, 1609, 12.1, 1560, 32.3, ""),
    ("PA12 GF", "G", 24, 50, 173, 1981, 14.3, 1634, 34.0, ""),
    ("PA12 GF", "H", 24, 50, 173, 2817, 29.6, 2773, 68.5, "not reproducible (paper: removed from consideration)"),
    ("PA12 GF", "I", 28, 50, 173, 2349, 21.6, 1684, 43.7, ""), ("PA12 GF", "J", 32, 50, 178, 2482, 23.0, 1177, 24.2, ""),
    ("PA12 GF", "K", 32, 50, 173, 2036, 16.7, 1233, 28.1, ""), ("PA12 GF", "L", 40, 25, 173, 1187, 7.8, 2130, 55.4, ""),
    ("PA12 GF", "M", 40, 25, 176, 1002, 6.9, 915, 20.6, ""), ("PA12 GF", "N", 24, 50, 173, 1040, 6.7, 770, 13.6, ""),
    ("PA11 Onyx", "O", 36, 50, 186, 934, 15.7, None, None, "significant warping, 3 samples survived"),
    ("PA11 Onyx", "P", 32, 33, 186, 827, 16.6, 425, 16.6, ""), ("PA11 Onyx", "Q", 32, 50, 186, 1323, 22.1, 867, 31.3, ""),
    ("PA11 Onyx", "R", 34, 50, 188, 1571, 36.3, 1093, 42.5, ""),
    ("PA12 Blend", "S", 48, 50, 168, 1092, 14.4, None, None, "build ended early, 7 tensile samples"),
    ("PA12 Blend", "T", 56, 50, 168, 1675, 35.2, 1439, 47.3, "brittle samples bottom-right of bed"),
    ("PA12 Blend", "U", 56, 50, 172, 1678, 44.4, 1830, 60.6, ""),
]
PAPER_MATERIALS = {   # manufacturer TDS targets quoted in the paper; tmelt = approximate DSC melting peak (C), user-editable
    "PA12 GF": ({"Et": 2800, "UTS": 38.0}, 186),
    "PA11 Onyx": ({"Et": 1680, "UTS": 55.0, "Ef": 1290, "sf": 54.2}, 201),
    "PA12 Blend": ({"Et": 1950, "UTS": 47.0}, 186),   # 25% PA12 GF + 75% PA12 White by volume; target: PA12 White TDS
}
# Bounds for suggestions: the Inova Mk1 (10 W blue diode), and one-batch step limits so the next result is interpretable.
BOUNDS = {"fill": (8, 70), "overlap": (25, 50), "tsurf_below_melt": (25, 3)}   # tsurf in [tmelt-25, tmelt-3] C
STEP = {"fill": 8.0, "tsurf": 3.0}
OVERLAPS = (25, 33, 50)


# ------------------------------------------------------------------ database
SCHEMA = """
create table if not exists materials(name text primary key, tds text, tmelt real, notes text);
create table if not exists batches(id text primary key, material text, fill real, outline text, overlap real, tsurf real,
   layer_um real default 100, chamber_c real default 145, notes text, created text default current_timestamp);
create table if not exists results(batch text, Et real, UTS real, Ef real, sf real, n_tensile int, n_flex int, stat text,
   excluded int default 0, source text);
"""


def connect(db):
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    return con


def init(db, seed=False):
    con = connect(db)
    if seed:
        for n, (tds, tm) in PAPER_MATERIALS.items():
            con.execute("insert or replace into materials values (?,?,?,?)", (n, json.dumps(tds), tm, "from arXiv:2608.25928"))
        for m, i, f, o, t, Et, U, Ef, sf, note in PAPER_BATCHES:
            con.execute("insert or replace into batches(id, material, fill, overlap, tsurf, notes) values (?,?,?,?,?,?)", (i, m, f, o, t, note))
            con.execute("delete from results where batch=?", (i,))
            con.execute("insert into results values (?,?,?,?,?,?,?,?,?,?)",
                        (i, Et, U, Ef, sf, None, None, "best specimen", 1 if "not reproducible" in note else 0, "paper Table"))
    con.commit()
    return {"db": db, "materials": [r[0] for r in con.execute("select name from materials")],
            "batches": con.execute("select count(*) from batches").fetchone()[0]}


def history(db, material):
    con = connect(db)
    row = con.execute("select tds, tmelt from materials where name=?", (material,)).fetchone()
    if not row:
        raise SystemExit(f"material '{material}' not in the database; add it with `material`")
    tds, tmelt = json.loads(row[0]), row[1]
    rows = con.execute("""select b.id, b.fill, b.overlap, b.tsurf, b.notes, r.Et, r.UTS, r.Ef, r.sf, r.excluded, r.stat
                          from batches b left join results r on r.batch=b.id where b.material=? order by b.created, b.id""",
                       (material,)).fetchall()
    out = []
    for i, f, o, t, n, Et, U, Ef, sf, ex, st in rows:
        rec = {"batch": i, "fill_mJ_mm": f, "overlap_pct": o, "tsurf_C": t, "Et": Et, "UTS": U, "Ef": Ef, "sf": sf,
               "excluded": bool(ex), "stat": st, "notes": n}
        rec["score"] = score(rec, tds)
        out.append(rec)
    return {"material": material, "tds": tds, "tmelt_C": tmelt, "batches": out}


def score(rec, tds):
    """Mean fraction of each TDS property reached (capped at 1.2), over the properties both measured and specified."""
    fr = [min(rec[k] / v, 1.2) for k, v in tds.items() if rec.get(k) is not None and v]
    return round(float(np.mean(fr)), 4) if fr else None


# ------------------------------------------------------------------ ASTM data reduction
D638 = {1: {"width": 13.0, "thick": 3.2, "gauge": 50.0}, 4: {"width": 6.0, "thick": 4.0, "gauge": 25.0}}   # mm (paper Fig. 6)
D790 = {"width": 12.7, "thick": 3.2, "length": 80.0}


def _load(csv):
    a = np.genfromtxt(csv, delimiter=",", names=True)
    names = [n.lower() for n in a.dtype.names]
    f = a[a.dtype.names[[i for i, n in enumerate(names) if n.startswith(("load", "force"))][0]]]
    x = a[a.dtype.names[[i for i, n in enumerate(names) if n.startswith(("ext", "disp", "strain", "deflect"))][0]]]
    return np.asarray(x, float), np.asarray(f, float)


def linear_slope(x, y, frac=(0.05, 0.5), win=15):
    """Steepest secant slope over a sliding window in the early part of the curve (tangent-modulus style)."""
    n = len(x)
    i0, i1 = int(frac[0] * np.argmax(y)), max(int(frac[1] * np.argmax(y)), win + 2)
    best = 0.0
    for i in range(i0, max(i0 + 1, i1 - win)):
        sl = np.polyfit(x[i:i + win], y[i:i + win], 1)[0]
        best = max(best, sl)
    return best


def astm(test, csv, typ=4, width=None, thick=None, gauge=None, span=None, strain_input=False):
    """D638: stress = F/A, strain = extension/gauge (or a strain column); modulus = initial slope, UTS = max stress.
    D790 (3-point): sf = 3PL/(2bd^2), ef = 6Dd/L^2, Ef = L^3 m / (4 b d^3) with span L = 16 d by default."""
    x, F = _load(csv)
    if test == "d638":
        g = D638[typ]; b, d, L0 = width or g["width"], thick or g["thick"], gauge or g["gauge"]
        stress = F / (b * d)
        strain = x if strain_input else x / L0
        E = linear_slope(strain, stress)
        return {"test": "ASTM D638 Type %d" % typ, "Et_MPa": round(E, 1), "UTS_MPa": round(float(stress.max()), 2),
                "strain_at_break": round(float(strain[np.argmax(stress)]), 4), "area_mm2": b * d}
    b, d = width or D790["width"], thick or D790["thick"]
    L = span or 16 * d
    m = linear_slope(x, F)
    return {"test": "ASTM D790 3-point", "Ef_MPa": round(L ** 3 * m / (4 * b * d ** 3), 1),
            "sf_MPa": round(float(3 * F.max() * L / (2 * b * d ** 2)), 2), "span_mm": L,
            "note": "D790 stops at 5% outer-fibre strain; report sf at break or at 5% strain, whichever first"}


def summarize(specimens):
    """Paper reports the best specimen; report mean +- sd as well so scatter is visible."""
    out = {}
    for k in ("Et_MPa", "UTS_MPa", "Ef_MPa", "sf_MPa"):
        v = [s[k] for s in specimens if k in s]
        if v:
            out[k] = {"best": max(v), "mean": round(float(np.mean(v)), 2), "sd": round(float(np.std(v, ddof=1)) if len(v) > 1 else 0.0, 2), "n": len(v)}
    return out


# ------------------------------------------------------------------ suggestion engine
def suggest(db, material, objective="score", n=3, seed=0, explore=0.01):
    """Gaussian-process expected improvement over (fill, overlap, tsurf), within machine bounds and one-batch step
    limits from the best non-excluded batch. Returns ranked candidates for the agent (you) to reason over."""
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel as C
    from scipy.stats import norm
    h = history(db, material)
    tm = h["tmelt_C"]
    data = [b for b in h["batches"] if not b["excluded"] and (b[objective] if objective != "score" else b["score"]) is not None]
    if not data:
        return {"material": material, "note": "no results yet: start from the material's datasheet or a 5x5 patch test",
                "start": {"fill_mJ_mm": 24, "overlap_pct": 50, "tsurf_C": tm - 13}}
    y = np.array([b[objective] if objective != "score" else b["score"] for b in data], float)
    X = np.array([[b["fill_mJ_mm"], b["overlap_pct"], b["tsurf_C"]] for b in data], float)
    best = data[int(np.argmax(y))]
    lo_t, hi_t = tm - BOUNDS["tsurf_below_melt"][0], tm - BOUNDS["tsurf_below_melt"][1]
    fills = np.arange(max(BOUNDS["fill"][0], best["fill_mJ_mm"] - STEP["fill"]), min(BOUNDS["fill"][1], best["fill_mJ_mm"] + STEP["fill"]) + 1e-9, 1.0)
    tsurfs = np.arange(max(lo_t, best["tsurf_C"] - STEP["tsurf"]), min(hi_t, best["tsurf_C"] + STEP["tsurf"]) + 1e-9, 1.0)
    cand = np.array([[f, o, t] for f in fills for o in OVERLAPS for t in tsurfs])
    tried = {tuple(r) for r in X}
    cand = np.array([c for c in cand if tuple(c) not in tried]) if len(cand) else cand
    scale = np.array([10.0, 15.0, 4.0])
    ys = (y - y.mean()) / (y.std() + 1e-9)
    if len(y) >= 3:
        gp = GaussianProcessRegressor(C(1.0) * RBF([1.0, 1.0, 1.0], (0.2, 20)) + WhiteKernel(0.1, (1e-3, 1)), normalize_y=False,
                                      random_state=seed, n_restarts_optimizer=3).fit(X / scale, ys)
        mu, sd = gp.predict(cand / scale, return_std=True)
        z = (mu - ys.max() - explore) / (sd + 1e-9)
        ei = (mu - ys.max() - explore) * norm.cdf(z) + sd * norm.pdf(z)
        order = np.argsort(-ei)
        mu_y, sd_y = mu * y.std() + y.mean(), sd * y.std()
    else:   # too little data for a model: move one lever at a time from the best batch
        order = np.argsort(np.abs(cand - [best["fill_mJ_mm"] + 4, 50, best["tsurf_C"]]).sum(1))
        mu_y = sd_y = ei = np.full(len(cand), np.nan)
    picks = []
    for i in order:
        c = cand[i]
        if len(picks) == n:
            break
        if any(np.abs(c - p["x"]).sum() < 1.5 for p in picks):
            continue
        changes = [k for k, a, b in zip(("fill", "overlap", "tsurf"), c, [best["fill_mJ_mm"], best["overlap_pct"], best["tsurf_C"]]) if abs(a - b) > 1e-9]
        picks.append({"x": c, "fill_mJ_mm": float(c[0]), "overlap_pct": float(c[1]), "tsurf_C": float(c[2]),
                      "predicted_" + objective: None if np.isnan(mu_y[i]) else round(float(mu_y[i]), 3),
                      "uncertainty": None if np.isnan(sd_y[i]) else round(float(sd_y[i]), 3),
                      "expected_improvement": None if np.isnan(ei[i]) else round(float(ei[i]), 4),
                      "levers_changed_vs_best": changes})
    for p in picks:
        p.pop("x")
    return {"material": material, "objective": objective, "tds_target": h["tds"], "batches_used": len(data),
            "best_so_far": {k: best[k] for k in ("batch", "fill_mJ_mm", "overlap_pct", "tsurf_C", "Et", "UTS", "score")},
            "bounds": {"fill_mJ_mm": [float(fills.min()), float(fills.max())], "tsurf_C": [float(tsurfs.min()) if len(tsurfs) else None, float(tsurfs.max()) if len(tsurfs) else None],
                       "overlap_pct": list(OVERLAPS), "note": f"surface temperature kept {BOUNDS['tsurf_below_melt'][1]}-{BOUNDS['tsurf_below_melt'][0]} C below the melt peak ({tm} C); fill within +-{STEP['fill']} mJ/mm of the best batch"},
            "candidates": picks,
            "warnings": [b["batch"] + ": " + b["notes"] for b in h["batches"] if b["notes"]]}


def plot_history(h, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    b = [x for x in h["batches"] if x["Et"] is not None]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
    for a, k in zip(ax, ("Et", "UTS")):
        xs = range(len(b))
        a.plot(xs, [x[k] for x in b], "o-", color="#2c7fb8")
        for i, x in enumerate(b):
            a.annotate(f"{x['batch']}\n{x['fill_mJ_mm']:g}/{x['overlap_pct']:g}/{x['tsurf_C']:g}", (i, x[k]), fontsize=6, ha="center",
                       xytext=(0, 6), textcoords="offset points", color="#c0392b" if x["excluded"] else "k")
        if k in h["tds"]:
            a.axhline(h["tds"][k], ls="--", color="#2e8b57", label=f"TDS {h['tds'][k]}")
            a.legend(fontsize=8)
        a.set_xticks(list(xs)); a.set_xticklabels([x["batch"] for x in b]); a.set_ylabel(k + " (MPa)")
    fig.suptitle(f"{h['material']}: batch history (labels: fill mJ/mm / overlap % / surface C)", fontsize=9)
    fig.tight_layout(); fig.savefig(out, dpi=140)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="builds.sqlite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--seed-paper", action="store_true")
    s = sub.add_parser("material"); s.add_argument("--name", required=True); s.add_argument("--tds", required=True)
    s.add_argument("--tmelt", type=float, required=True); s.add_argument("--notes", default="")
    s = sub.add_parser("batch"); s.add_argument("--material", required=True); s.add_argument("--id", required=True)
    s.add_argument("--fill", type=float, required=True); s.add_argument("--overlap", type=float, required=True)
    s.add_argument("--tsurf", type=float, required=True); s.add_argument("--outline", default=""); s.add_argument("--notes", default="")
    s = sub.add_parser("astm"); s.add_argument("--test", choices=["d638", "d790"], required=True); s.add_argument("--csv", nargs="+", required=True)
    s.add_argument("--type", type=int, default=4); s.add_argument("--width", type=float); s.add_argument("--thick", type=float)
    s.add_argument("--gauge", type=float); s.add_argument("--span", type=float); s.add_argument("--strain", action="store_true")
    s = sub.add_parser("result"); s.add_argument("--batch", required=True)
    for k in ("Et", "UTS", "Ef", "sf"):
        s.add_argument(f"--{k}", type=float)
    s.add_argument("--from", dest="src"); s.add_argument("--exclude", action="store_true")
    s = sub.add_parser("history"); s.add_argument("--material", required=True); s.add_argument("--plot")
    s = sub.add_parser("suggest"); s.add_argument("--material", required=True); s.add_argument("--objective", default="score")
    s.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "init":
        r = init(a.db, a.seed_paper)
    elif a.cmd == "material":
        tds = {k: float(v) for k, v in (kv.split("=") for kv in a.tds.split(","))}
        con = connect(a.db); con.execute("insert or replace into materials values (?,?,?,?)", (a.name, json.dumps(tds), a.tmelt, a.notes)); con.commit()
        r = {"material": a.name, "tds": tds, "tmelt_C": a.tmelt}
    elif a.cmd == "batch":
        con = connect(a.db)
        if not con.execute("select 1 from materials where name=?", (a.material,)).fetchone():
            raise SystemExit(f"add material '{a.material}' first")
        tm = con.execute("select tmelt from materials where name=?", (a.material,)).fetchone()[0]
        if a.tsurf > tm - BOUNDS["tsurf_below_melt"][1]:
            raise SystemExit(f"surface temperature {a.tsurf} C is within {BOUNDS['tsurf_below_melt'][1]} C of the melt peak {tm} C: "
                             "risk of caking the whole powder bed. Lower it or update tmelt from DSC.")
        con.execute("insert or replace into batches(id, material, fill, outline, overlap, tsurf, notes) values (?,?,?,?,?,?,?)",
                    (a.id, a.material, a.fill, a.outline, a.overlap, a.tsurf, a.notes)); con.commit()
        r = {"recorded_batch": a.id}
    elif a.cmd == "astm":
        sp = [astm(a.test, c, a.type, a.width, a.thick, a.gauge, a.span, a.strain) for c in a.csv]
        r = {"specimens": sp, "summary": summarize(sp)}
    elif a.cmd == "result":
        v = {k: getattr(a, k) for k in ("Et", "UTS", "Ef", "sf")}
        if a.src:
            sm = json.load(open(a.src))["summary"]
            for k, key in (("Et", "Et_MPa"), ("UTS", "UTS_MPa"), ("Ef", "Ef_MPa"), ("sf", "sf_MPa")):
                if key in sm and v[k] is None:
                    v[k] = sm[key]["best"]
        con = connect(a.db)
        con.execute("insert into results values (?,?,?,?,?,?,?,?,?,?)", (a.batch, v["Et"], v["UTS"], v["Ef"], v["sf"], None, None,
                                                                         "best specimen", int(a.exclude), a.src or "manual"))
        con.commit(); r = {"batch": a.batch, **v}
    elif a.cmd == "history":
        r = history(a.db, a.material)
        if a.plot:
            r["plot"] = plot_history(r, a.plot)
    else:
        r = suggest(a.db, a.material, a.objective, a.n)
    print(json.dumps(r, indent=1, default=str))


if __name__ == "__main__":
    main()
