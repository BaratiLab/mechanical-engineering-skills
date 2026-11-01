#!/usr/bin/env python3
"""Target curve -> planar linkage, built node by node with validation and bounded retries
(the LinkD inference procedure, arXiv:2601.04054, Algorithm 1), using optimization in place of
the trained diffusion sampler.

  python synth.py target.csv --out best.json [--max-nodes 8] [--invariant] [--seed 0] [--retries 25]
  python synth.py --preset ellipse|crescent|teardrop|bean --out best.json

Stage 1 fits a four-bar (5 nodes: crank pivot, crank tip, ground pivot, rocker joint, coupler point).
Stage 2 grows the mechanism: each proposal adds a dyad plus a coupler point (a six-bar step,
optionally with a new ground pivot); every added node attaches to exactly two known nodes, the
whole graph is validated through a full revolution, invalid proposals are re-sampled up to K
times, and growth is kept only if it improves the curve fit (>2%).
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import linkage as L  # noqa: E402

PRESETS = {
    "ellipse": lambda t: np.c_[2.0 * np.cos(t), 0.8 * np.sin(t)],
    "crescent": lambda t: np.c_[np.cos(t) + 0.45 * np.cos(2 * t), np.sin(t) + 0.15 * np.sin(2 * t)],
    "teardrop": lambda t: np.c_[np.sin(t / 2) ** 2 * 0 + np.cos(t), np.sin(t) * np.sin(t / 2) ** 1.5],
    "bean": lambda t: np.c_[np.cos(t) * (1 + 0.3 * np.cos(t)), 0.7 * np.sin(t) * (1 - 0.25 * np.cos(2 * t))],
}


def resample(C, n=200):
    C = np.asarray(C, float)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([C, C[:1]]), axis=0), axis=1))]
    s = np.linspace(0, seg[-1], n, endpoint=False)
    closed = np.vstack([C, C[:1]])
    return np.c_[np.interp(s, seg, closed[:, 0]), np.interp(s, seg, closed[:, 1])]


# ------------------------------------------------------------------ fast vectorized simulator
class Model:
    def __init__(self, m):
        self.m = m
        res, err = L.dyadic_order(m)
        self.err = err
        if not err:
            self.order, self.parents = res

    def run(self, X0, n=L.N_ANGLES):
        m = self.m
        if self.err:
            return None
        piv, tip = m["motor"]
        r = np.linalg.norm(X0[tip] - X0[piv])
        if r < 1e-6:
            return None
        th = math.atan2(*(X0[tip] - X0[piv])[::-1]) + np.linspace(0, 2 * np.pi, n, endpoint=False)
        X = np.repeat(X0[None], n, axis=0)
        X[:, tip] = X0[piv] + r * np.c_[np.cos(th), np.sin(th)]
        for k in self.order:
            i, j = self.parents[k]
            Gi, Gj = np.linalg.norm(X0[k] - X0[i]), np.linalg.norm(X0[k] - X0[j])
            d0, e0 = X0[j] - X0[i], X0[k] - X0[i]
            sgn = 1.0 if d0[0] * e0[1] - d0[1] * e0[0] >= 0 else -1.0
            v = X[:, j] - X[:, i]
            lij = np.linalg.norm(v, axis=1)
            if Gi < 1e-6 or np.any(lij < 1e-9):
                return None
            c = (lij ** 2 + Gi ** 2 - Gj ** 2) / (2 * lij * Gi)
            if np.any(np.abs(c) > 1 + 1e-9):
                return None                                    # branch defect somewhere in the revolution
            phi = sgn * np.arccos(np.clip(c, -1, 1))
            u = v / lij[:, None]
            X[:, k] = X[:, i] + Gi * np.c_[np.cos(phi) * u[:, 0] - np.sin(phi) * u[:, 1],
                                           np.sin(phi) * u[:, 0] + np.cos(phi) * u[:, 1]]
        return X


def score(curve, target_n, invariant):
    C = L.normalize(L.arclength(curve, 200))
    if not np.all(np.isfinite(C)) or np.ptp(C, axis=0).max() < 1e-6:
        return 1e3
    if invariant:
        return L.chamfer_invariant(target_n, C, n_rot=24)["chamfer_invariant"]
    return L.chamfer(target_n, C)


def four_bar_template():
    return {"fixed": [0, 2], "edges": [[0, 1], [1, 3], [2, 3], [1, 4], [3, 4]], "motor": [0, 1], "effector": 4}


LIMITS = {"max_link_ratio": 8.0, "min_ground_sep": 0.15, "max_extent": 6.0, "min_link_rel": 0.1}


def practicality(m, X, P):
    """Penalty for mechanisms nobody would build: extreme link ratios, coincident ground pivots,
    a footprint far larger than the path. Returns (penalty, report)."""
    lens = np.array([np.linalg.norm(X[a] - X[b]) for a, b in m["edges"]])
    ratio = lens.max() / max(lens.min(), 1e-9)
    curve = P[:, m["effector"]]
    size = max(np.ptp(curve, axis=0).max(), 1e-9)
    gs = [np.linalg.norm(X[a] - X[b]) / size for a in m["fixed"] for b in m["fixed"] if a < b]
    extent = np.ptp(P.reshape(-1, 2), axis=0).max() / size
    min_link = lens.min() / size
    pen = (max(0, ratio / LIMITS["max_link_ratio"] - 1) + max(0, LIMITS["min_ground_sep"] - min(gs, default=1)) * 5
           + max(0, extent / LIMITS["max_extent"] - 1) + max(0, LIMITS["min_link_rel"] - min_link) * 5)
    return pen, {"link_ratio": float(ratio), "min_ground_sep_rel": float(min(gs, default=np.inf)),
                 "extent_rel": float(extent), "min_link_rel": float(min_link)}


def fit_positions(m, X_init, free_idx, target_n, invariant, seed, iters=60, bounds=2.5, de_idx=None):
    """DE over `de_idx` (default: all free nodes), then Nelder-Mead polish over all free nodes."""
    from scipy.optimize import differential_evolution, minimize
    model = Model(m)
    if model.err:
        return None, 1e3

    def make_f(idx, base):
        def f(z):
            X = base.copy()
            X[idx] = z.reshape(-1, 2)
            P = model.run(X, n=100)
            if P is None:
                return 10.0
            pen, _ = practicality(m, X, P)
            return score(P[:, m["effector"]], target_n, invariant) + 0.2 * pen
        return f

    X = X_init.copy()
    if iters:
        idx = de_idx if de_idx is not None else free_idx
        x0 = X[idx].ravel()
        b = [(v - bounds, v + bounds) for v in x0]
        de = differential_evolution(make_f(idx, X), b, seed=seed, maxiter=iters, popsize=12, tol=1e-6,
                                    polish=False, init="latinhypercube", x0=x0)
        X[idx] = de.x.reshape(-1, 2)
    nm = minimize(make_f(free_idx, X), X[free_idx].ravel(), method="Nelder-Mead",
                  options={"maxiter": 2000, "xatol": 1e-5, "fatol": 1e-6})
    X[free_idx] = nm.x.reshape(-1, 2)
    return X, nm.fun


def synthesize(target, max_nodes=8, invariant=False, seed=0, retries=25, log=print):
    rng = np.random.default_rng(seed)
    T = L.normalize(L.arclength(target, 200))
    # stage 1: four-bar in normalized target coordinates
    best = None
    for attempt in range(retries):
        X0 = np.array([[-1.5, -1.0], [-1.5, -0.5], [1.5, -1.0], [0.5, 0.5], [0.0, 0.0]]) + rng.normal(0, 0.4, (5, 2))
        m = four_bar_template() | {"nodes": X0.tolist()}
        if Model(m).run(X0) is None:
            continue                                            # node-level retry: resample invalid proposal
        X, cd = fit_positions(m, X0, list(range(5)), T, invariant, seed + attempt, iters=50)
        if X is None:
            continue
        cand = m | {"nodes": X.tolist()}
        Pc = Model(cand).run(X)
        if Pc is None or practicality(cand, X, Pc)[0] > 0.05:
            continue
        if L.validate(cand)["valid"] and (best is None or cd < best[1]):
            best = (cand, cd)
            log(f"[four-bar] attempt {attempt}: CD = {cd:.4f}")
        if best and best[1] < 0.02:
            break
    if best is None:
        return None, {"error": f"no valid four-bar found in {retries} attempts"}
    history = [{"nodes": 5, "chamfer": best[1]}]
    # stage 2: autoregressive growth, one dyadic node at a time
    while len(best[0]["nodes"]) < max_nodes and best[1] > 0.02:
        m0, cd0 = best
        n = len(m0["nodes"])
        improved = None
        for attempt in range(retries):
            X = np.asarray(m0["nodes"], float)
            movers = [k for k in range(n) if k not in m0["fixed"]]
            nodes = X.tolist()
            fixed = list(m0["fixed"])
            edges = [list(e) for e in m0["edges"]]
            span = np.ptp(X, axis=0).max()
            # Compound proposal = a dyad from ground to the current end-effector's body plus a new coupler
            # point (a six-bar step). Joints on one rigid body cannot form a new loop, so the dyad is
            # anchored to ground (an existing pivot or a new one). The new coupler point starts next to the
            # old effector, so the six-bar begins near the four-bar's path and the search can only refine it.
            a = int(m0["effector"]) if rng.random() < 0.7 else int(rng.choice(movers))
            if rng.random() < 0.5:
                g = len(nodes); nodes.append((X[a] + rng.normal(0, 0.8 * span, 2)).tolist()); fixed.append(g)
            else:
                g = int(rng.choice(fixed))
            J = len(nodes); nodes.append(((X[a] + np.asarray(nodes[g])) / 2 + rng.normal(0, 0.25 * span, 2)).tolist())
            edges += [[g, J], [a, J]]
            E = len(nodes); nodes.append((X[a] + rng.normal(0, 0.05 * span, 2)).tolist())
            edges += [[J, E], [a, E]]
            new = E
            if len(nodes) > max_nodes:
                continue
            cand = {"nodes": nodes, "fixed": fixed, "edges": edges, "motor": m0["motor"], "effector": new}
            Xc = np.asarray(nodes, float)
            if Model(cand).run(Xc) is None:
                continue                                        # invalid proposal -> retry (bounded, K)
            free = [k for k in range(len(nodes)) if k not in (m0["motor"][0],)]
            newn = list(range(n, len(nodes)))                    # global search on the new node(s) only
            Xf, cd = fit_positions(cand, Xc, free, T, invariant, seed + 100 + attempt, iters=25, de_idx=newn)
            if Xf is None:
                continue
            cand["nodes"] = Xf.tolist()
            Pc = Model(cand).run(Xf)
            if Pc is None or practicality(cand, Xf, Pc)[0] > 0.05:
                continue
            if L.validate(cand)["valid"] and cd < cd0 * 0.98 and (improved is None or cd < improved[1]):
                improved = (cand, cd)
        if improved is None:
            log(f"[grow] no proposal improved the fit after {retries} retries; stopping at {n} nodes")
            break
        best = improved
        history.append({"nodes": len(best[0]["nodes"]), "chamfer": best[1]})
        log(f"[grow] {len(best[0]['nodes'])} nodes: CD = {best[1]:.4f}")
    m = best[0]
    P, _ = L.simulate(m)
    final = L.compare(target, P[:, m["effector"]], invariant=True)
    return m, {"history": history, "final": final, "nodes": len(m["nodes"]), "validation": L.validate(m),
               "practicality": practicality(m, np.asarray(m["nodes"], float), P)[1] | {"limits": LIMITS}}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?")
    ap.add_argument("--preset", choices=PRESETS)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-nodes", type=int, default=8)
    ap.add_argument("--invariant", action="store_true", help="allow rotated/mirrored match during search")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--retries", type=int, default=25)
    a = ap.parse_args()
    if a.preset:
        t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
        target = PRESETS[a.preset](t)
    else:
        target = np.loadtxt(a.target, delimiter=",", skiprows=1)
    m, info = synthesize(target, a.max_nodes, a.invariant, a.seed, a.retries, log=lambda s: print(s, file=sys.stderr))
    if m is None:
        print(json.dumps(info)); sys.exit(2)
    json.dump(m, open(a.out, "w"), indent=1)
    np.savetxt(os.path.splitext(a.out)[0] + "_target.csv", L.normalize(L.arclength(target, 200)), delimiter=",", header="x,y", comments="")
    print(json.dumps({"mechanism": a.out} | info, indent=2, default=float))


if __name__ == "__main__":
    main()
