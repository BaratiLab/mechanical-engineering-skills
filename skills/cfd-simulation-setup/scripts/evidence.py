#!/usr/bin/env python3
"""Deterministic evidence extraction from an OpenFOAM case (Foundation v11-v14 log formats).

  log      python evidence.py log      case/log.foamRun            -> solver health
  mesh     python evidence.py mesh     case/log.checkMesh          -> mesh validity / quality
  minmax   python evidence.py minmax   postProcessing/fieldMinMax/0/fieldMinMax.dat
  drift    python evidence.py drift    monitor.dat --col 1 --window 2e-3 [--ref-col 1]
  growth   python evidence.py growth   forces.dat  --col 3 --window 20
  closure  python evidence.py closure  mass.csv                   -> storage-aware mass balance
  front    python evidence.py front    line.csv --step-x 0.6      -> compression front + rises
  merge    python evidence.py merge    --family F --out evidence.json part1.json part2.json ...
           [--state t=4,end_time=4,iteration=1,refinements=0,max_co=0.2] [--criteria a,b]

Each command prints JSON. The agent never types evidence values by hand: it runs these
and merges their outputs. Names returned under "checks" match contract check names.
"""
import argparse
import json
import math
import re
import sys

import numpy as np

# A real fatal signature. The Foundation start-up banner line
#   "sigFpe : Enabling floating point exception trapping (FOAM_SIGFPE)."
# is NOT a failure; matching it caused a false REJECT in CFD Forge (paper Sec. 5.1).
FATAL = re.compile(r"FOAM FATAL (IO )?ERROR|Foam::sigFpe::sigHandler|Floating point exception \(core dumped\)"
                   r"|Segmentation fault|FOAM aborting|Maximum number of iterations exceeded.*nan", re.I)
BENIGN = re.compile(r"sigFpe\s*:\s*Enabling floating point exception trapping", re.I)
NUM = r"([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|nan|inf|-inf)"


def fnum(s):
    try:
        return float(s.rstrip("s"))
    except ValueError:
        return float("nan")


# ------------------------------------------------------------------ solver log
def parse_log(path):
    txt = open(path, errors="replace").read()
    lines = txt.splitlines()
    fatal = [l.strip() for l in lines if FATAL.search(l) and not BENIGN.search(l)]
    times = [fnum(m) for m in re.findall(r"^Time = (\S+)", txt, re.M)]
    co = [(fnum(a), fnum(b)) for a, b in re.findall(r"Courant Number mean: (\S+) max: (\S+)", txt)]
    cont = [fnum(g) for g in re.findall(r"continuity errors : sum local = \S+, global = (\S+),", txt)]
    tail = [l.strip() for l in lines if l.strip()][-3:]
    completed = any(l == "End" for l in tail) and not fatal
    co_max = max((b for _, b in co), default=None)
    return {"checks": {
                "solver_completed": completed,
                "no_fatal_error": not fatal,
                "courant_finite": all(math.isfinite(b) for _, b in co) if co else None,
            },
            "measurements": {"t_final": times[-1] if times else None, "n_steps": len(times),
                             "courant_max": co_max,
                             "continuity_global_max_abs": max((abs(c) for c in cont), default=None),
                             "fatal_lines": fatal[:5]},
            "state": {"t": times[-1] if times else None}}


# ------------------------------------------------------------------ checkMesh
def parse_checkmesh(path):
    txt = open(path, errors="replace").read()
    g = lambda pat, cast=float: (cast(m.group(1)) if (m := re.search(pat, txt)) else None)
    failed = g(r"Failed (\d+) mesh checks", int)
    sol_dirs = g(r"Mesh has (\d) solution \(non-empty\) directions", int)
    return {"checks": {"mesh_ok": ("Mesh OK." in txt) and not failed,
                       "two_solution_directions": (sol_dirs == 2) if sol_dirs is not None else None,
                       "max_non_orthogonality": g(r"Mesh non-orthogonality Max: " + NUM),
                       "max_skewness": g(r"Max skewness = " + NUM)},
            "measurements": {"cells": g(r"cells:\s+(\d+)", int),
                             "max_aspect_ratio": g(r"Max aspect ratio = " + NUM),
                             "solution_directions": sol_dirs, "failed_checks": failed or 0}}


# ------------------------------------------------------------------ .dat helpers
def load_dat(path):
    rows = []
    for line in open(path):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        toks = line.replace("(", " ").replace(")", " ").replace(",", " ").split()
        try:
            rows.append([fnum(t) for t in toks])
        except ValueError:
            continue
    w = min(len(r) for r in rows)
    return np.array([r[:w] for r in rows])


def window(a, w):
    t = a[:, 0]
    return a[t >= t[-1] - w]


def drift(path, col, w, ref_col=None):
    a = window(load_dat(path), w)
    t, y = a[:, 0], a[:, col]
    slope = np.polyfit(t, y, 1)[0]
    ref = a[:, ref_col] if ref_col is not None else y
    mean_ref = abs(ref.mean())
    rel = abs(slope) * (t[-1] - t[0]) / mean_ref if mean_ref > 0 else float("inf")
    return {"checks": {"monitor_drift": rel},
            "measurements": {"window": [float(t[0]), float(t[-1])], "mean": float(y.mean()),
                             "range_rel": float(np.ptp(y) / mean_ref) if mean_ref else None,
                             "n_samples": int(len(t))}}


def growth(path, col, w, drag_col=1):
    a = window(load_dat(path), w)
    t, z = a[:, 0], a[:, col]
    mid = t[0] + (t[-1] - t[0]) / 2
    h1, h2 = np.abs(z[t < mid]).mean(), np.abs(z[t >= mid]).mean()
    fx = a[:, drag_col]
    drifts = []
    for c in range(1, a.shape[1]):
        s = np.polyfit(t, a[:, c], 1)[0]
        drifts.append(abs(s) * (t[-1] - t[0]) / abs(fx.mean()))
    # supplementary cycle audit (not a registered check)
    up = np.where((z[:-1] < 0) & (z[1:] >= 0))[0]
    amps = [(z[i:j].max() - z[i:j].min()) / 2 for i, j in zip(up[:-1], up[1:])]
    amp_change = [abs(b - a_) / a_ for a_, b in zip(amps, amps[1:])] if len(amps) > 1 else []
    return {"checks": {"lateral_growth_ratio": float(h2 / h1) if h1 > 0 else float("inf"),
                       "force_drift_rel": float(max(drifts)),
                       "mean_lateral_rel": float(abs(z.mean()) / abs(fx.mean()))},
            "measurements": {"half_window_mean_abs": [float(h1), float(h2)],
                             "mean_drag_force": float(fx.mean()), "complete_cycles": len(amps),
                             "cycle_amplitude_changes": [round(x, 4) for x in amp_change],
                             "cycle_audit_ok_lt_10pct": all(x < 0.10 for x in amp_change) if amp_change else None}}


def minmax(path, fields=("p", "T", "rho")):
    mins = {}
    for line in open(path):
        if line.lstrip().startswith("#") or not line.strip():
            continue
        toks = line.replace("(", " ").replace(")", " ").split()
        name = toks[1]
        mins[name] = min(mins.get(name, float("inf")), fnum(toks[2]))
    ok = all(math.isfinite(mins[f]) and mins[f] > 0 for f in fields if f in mins)
    present = [f for f in fields if f in mins]
    return {"checks": {"fields_positive_finite": ok if present else None},
            "measurements": {"field_min": mins}}


# ------------------------------------------------------------------ transient mass closure
def closure(path):
    """CSV columns: t,dt,M,Phi[,segment][,inflow,outflow]. Residual r_n = (M_n-M_{n-1})/dt_n + Phi_n,
    normalized by max(|inflow|,|outflow|) (or |Phi| scale). Pairs across restart segments are skipped."""
    d = np.genfromtxt(path, delimiter=",", names=True)
    names = d.dtype.names
    seg = d["segment"] if "segment" in names else np.zeros(len(d))
    scale = (np.maximum(np.abs(d["inflow"]), np.abs(d["outflow"])) if "inflow" in names
             else np.full(len(d), np.abs(d["Phi"]).max() or 1.0))
    r = []
    for n in range(1, len(d)):
        if seg[n] != seg[n - 1]:
            continue  # never difference across a restart seam
        r.append(abs((d["M"][n] - d["M"][n - 1]) / d["dt"][n] + d["Phi"][n]) / scale[n])
    r = np.array(r)
    return {"checks": {"mass_closure_residual": float(r.max()) if r.size else None},
            "measurements": {"closure_p99": float(np.percentile(r, 99)) if r.size else None,
                             "pairs": int(r.size), "segments": int(len(set(seg.tolist())))}}


# ------------------------------------------------------------------ forward-step front
def front(path, step_x, min_x=0.05, frac=0.5):
    """CSV x,p,rho,T sampled along a line below the step height (e.g. y = h/2)."""
    d = np.genfromtxt(path, delimiter=",", names=True)
    x, p = d["x"], d["p"]
    up = x < step_x
    x, p, rho, T = x[up], p[up], d["rho"][up], d["T"][up]
    p_inf = np.median(p[: max(3, len(p) // 20)])
    thresh = p_inf + frac * (p.max() - p_inf)
    idx = np.argmax(p > thresh)
    xf = float(x[idx])
    measurable = bool(p.max() > 1.05 * p_inf and xf > min_x and idx > 2)
    out = {"checks": {"front_measurable": measurable}, "measurements": {"front_x": xf}}
    if measurable:
        a = (x < xf - 0.03)
        b = (x > xf + 0.03) & (x < xf + 0.15)
        if a.sum() and b.sum():
            ratio = lambda f: float(np.median(f[b]) / np.median(f[a]))
            out["checks"] |= {"p_rise_across_front": ratio(p), "rho_rise_across_front": ratio(rho),
                              "T_rise_across_front": ratio(T)}
    else:
        out["checks"] |= {"p_rise_across_front": None, "rho_rise_across_front": None, "T_rise_across_front": None}
    return out


# ------------------------------------------------------------------ merge
def merge(family, parts, state, criteria):
    ev = {"family": family, "request_criteria": criteria, "checks": {}, "measurements": {}, "state": {}}
    for p in parts:
        d = json.load(open(p))
        for k in ("checks", "measurements", "state"):
            ev[k].update({kk: vv for kk, vv in d.get(k, {}).items() if vv is not None or kk not in ev[k]})
    ev["state"].update(state)
    return ev


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("log").add_argument("path")
    sub.add_parser("mesh").add_argument("path")
    sub.add_parser("minmax").add_argument("path")
    s = sub.add_parser("drift"); s.add_argument("path"); s.add_argument("--col", type=int, default=1)
    s.add_argument("--window", type=float, required=True); s.add_argument("--ref-col", type=int)
    s = sub.add_parser("growth"); s.add_argument("path"); s.add_argument("--col", type=int, default=3)
    s.add_argument("--drag-col", type=int, default=1); s.add_argument("--window", type=float, default=20.0)
    sub.add_parser("closure").add_argument("path")
    s = sub.add_parser("front"); s.add_argument("path"); s.add_argument("--step-x", type=float, required=True)
    s = sub.add_parser("merge"); s.add_argument("parts", nargs="+"); s.add_argument("--family", required=True)
    s.add_argument("--out", required=True); s.add_argument("--state", default=""); s.add_argument("--criteria", default="")
    a = ap.parse_args()
    if a.cmd == "log": r = parse_log(a.path)
    elif a.cmd == "mesh": r = parse_checkmesh(a.path)
    elif a.cmd == "minmax": r = minmax(a.path)
    elif a.cmd == "drift": r = drift(a.path, a.col, a.window, a.ref_col)
    elif a.cmd == "growth": r = growth(a.path, a.col, a.window, a.drag_col)
    elif a.cmd == "closure": r = closure(a.path)
    elif a.cmd == "front": r = front(a.path, a.step_x)
    else:
        st = {}
        for kv in filter(None, a.state.split(",")):
            k, v = kv.split("=")
            st[k] = float(v) if k not in ("iteration", "refinements") else int(v)
        r = merge(a.family, a.parts, st, [c for c in a.criteria.split(",") if c])
        json.dump(r, open(a.out, "w"), indent=2)
    print(json.dumps(r, indent=2, default=float))


if __name__ == "__main__":
    sys.exit(main())
