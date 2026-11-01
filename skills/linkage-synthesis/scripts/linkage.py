#!/usr/bin/env python3
"""Planar 1-DoF linkage toolkit following LinkD (Jadhav & Barati Farimani, arXiv:2601.04054).

Mechanism JSON:
  {"nodes": [[x, y], ...],            # joint positions at the reference pose
   "fixed": [0, 2],                   # grounded joints (type 1); others revolute (type 0)
   "edges": [[0, 1], [1, 3], ...],    # rigid links
   "motor": [0, 1],                   # crank: node 1 rotates about fixed node 0
   "effector": 4}                     # end-effector (coupler point); default = last node

  validate   python linkage.py validate mech.json                topology (dyadic) + kinematics (200 angles)
  simulate   python linkage.py simulate mech.json --out curve.csv
  encode     python linkage.py encode mech.json --out mech.npy   N x 24 LinkD matrix (N=20)
  decode     python linkage.py decode mech.npy --out mech.json
  compare    python linkage.py compare target.csv curve.csv [--invariant]   Chamfer distance (LinkD Eq. 7)
  plot       python linkage.py plot mech.json --target target.csv --out mech.png
"""
import argparse
import json
import math
import sys

import numpy as np

NMAX, FEAT = 20, 24          # LinkD: N x 24 = [validity, type, x, y, 20 lower-triangular adjacency entries]
N_ANGLES = 200


# ------------------------------------------------------------------ representation
def load(path):
    m = json.load(open(path))
    m.setdefault("motor", [m["fixed"][0], 1])
    m.setdefault("effector", len(m["nodes"]) - 1)
    return m


def adjacency(m):
    n = len(m["nodes"])
    A = np.zeros((n, n), int)
    for i, j in m["edges"]:
        A[i, j] = A[j, i] = 1
    return A


def encode(m, nmax=NMAX):
    """LinkD graph matrix: row t = [V_t, T_t, x_t, y_t, E_{t,0..nmax-1}] (lower-triangular: E_{t,j}=0 for j>=t)."""
    n = len(m["nodes"])
    if n > nmax:
        raise ValueError(f"{n} nodes > NMAX={nmax}")
    X = np.asarray(m["nodes"], float)
    c = (X.max(0) + X.min(0)) / 2
    s = max(np.abs(X - c).max(), 1e-9)
    Xn = (X - c) / s                                   # normalized to [-1, 1]
    A = adjacency(m)
    G = np.zeros((nmax, 4 + nmax))
    G[:, 0], G[:, 1] = 0, -1                           # padding: validity 0, type -1
    G[:n, 4:] = 0
    G[n:, 4:] = -1                                     # padded adjacency entries
    for t in range(n):
        G[t, 0] = 1
        G[t, 1] = 1 if t in m["fixed"] else 0
        G[t, 2:4] = Xn[t]
        G[t, 4:4 + t] = A[t, :t]
    return G, {"center": c.tolist(), "scale": float(s)}


def decode(G, motor=None, effector=None):
    valid = [t for t in range(G.shape[0]) if G[t, 0] > 0.5]
    nodes = [G[t, 2:4].tolist() for t in valid]
    fixed = [t for t in valid if G[t, 1] > 0.5]
    edges = [[j, t] for t in valid for j in range(t) if G[t, 4 + j] > 0.5]
    m = {"nodes": nodes, "fixed": fixed, "edges": edges}
    m["motor"] = motor or [fixed[0], next((t for t in valid if t not in fixed), 1)]
    m["effector"] = effector if effector is not None else valid[-1]
    return m


# ------------------------------------------------------------------ validation (LinkD Eq. 4-6)
def dyadic_order(m):
    """Assembly order by trilateration: each new node must have EXACTLY two known neighbours."""
    A = adjacency(m)
    n = len(m["nodes"])
    known = set(m["fixed"]) | {m["motor"][1]}
    order, parents = [], {}
    if m["motor"][0] not in m["fixed"]:
        return None, "motor pivot is not a fixed node"
    if A[m["motor"][0], m["motor"][1]] != 1:
        return None, "motor link (pivot-tip) is not an edge"
    while len(known) < n:
        progress = False
        for i in range(n):
            if i in known:
                continue
            nb = [j for j in known if A[i, j]]
            if len(nb) > 2:
                return None, f"node {i} over-constrained ({len(nb)} known neighbours)"
            if len(nb) == 2:
                parents[i] = tuple(sorted(nb))
                order.append(i)
                known.add(i)
                progress = True
        if not progress:
            return None, f"non-dyadic: nodes {sorted(set(range(n)) - known)} cannot be trilaterated"
    # extra edges between known nodes (beyond the dyad pairs + motor) over-constrain the mechanism
    used = {tuple(sorted(m["motor"]))} | {tuple(sorted((k, p))) for k, ps in parents.items() for p in ps}
    extra = [e for e in map(lambda e: tuple(sorted(e)), m["edges"]) if e not in used and not
             (e[0] in m["fixed"] and e[1] in m["fixed"])]
    if extra:
        return None, f"over-constrained links {extra} (not part of any dyad)"
    return (order, parents), None


def simulate(m, n_angles=N_ANGLES, closed=True):
    """Forward kinematics over a full crank revolution. Returns (positions[θ, node, 2], error_or_None)."""
    res, err = dyadic_order(m)
    if err:
        return None, "topology: " + err
    order, parents = res
    X0 = np.asarray(m["nodes"], float)
    n = len(X0)
    piv, tip = m["motor"]
    r = np.linalg.norm(X0[tip] - X0[piv])
    th0 = math.atan2(*(X0[tip] - X0[piv])[::-1])
    G = {}
    sign = {}
    for k in order:
        i, j = parents[k]
        G[(i, k)] = np.linalg.norm(X0[k] - X0[i]); G[(j, k)] = np.linalg.norm(X0[k] - X0[j])
        d = X0[j] - X0[i]; e = X0[k] - X0[i]
        sign[k] = 1.0 if d[0] * e[1] - d[1] * e[0] >= 0 else -1.0     # branch (assembly mode) kept fixed
    thetas = th0 + np.linspace(0, 2 * np.pi if closed else np.pi, n_angles, endpoint=False)
    P = np.zeros((n_angles, n, 2))
    for a, th in enumerate(thetas):
        X = X0.copy()
        X[tip] = X0[piv] + r * np.array([math.cos(th), math.sin(th)])
        for k in order:
            i, j = parents[k]
            v = X[j] - X[i]
            lij = np.linalg.norm(v)
            if lij < 1e-12:
                return None, f"kinematics: coincident joints {i},{j} at step {a}"
            c = (lij ** 2 + G[(i, k)] ** 2 - G[(j, k)] ** 2) / (2 * lij * G[(i, k)])
            if c < -1 - 1e-9 or c > 1 + 1e-9:
                return None, f"kinematics: branch defect at node {k}, angle step {a} (cos φ = {c:.3f})"
            phi = sign[k] * math.acos(max(-1, min(1, c)))
            R = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
            X[k] = X[i] + G[(i, k)] * (R @ (v / lij))
        P[a] = X
    return P, None


def validate(m):
    P, err = simulate(m)
    out = {"topology_valid": not (err or "").startswith("topology"), "kinematic_valid": err is None, "error": err}
    if P is not None:
        X0 = np.asarray(m["nodes"], float)
        lens = {tuple(e): float(np.linalg.norm(X0[e[0]] - X0[e[1]])) for e in m["edges"]}
        drift = max(abs(np.linalg.norm(P[:, a] - P[:, b], axis=1) - L).max() for (a, b), L in lens.items())
        min_sep = min(np.linalg.norm(P[:, a] - P[:, b], axis=1).min() for a in range(len(X0)) for b in range(a))
        out |= {"max_link_length_drift": float(drift), "min_joint_separation": float(min_sep),
                "degenerate": bool(min_sep < 1e-3 * np.ptp(X0, axis=0).max())}
        out["valid"] = out["kinematic_valid"] and not out["degenerate"]
    else:
        out["valid"] = False
    return out


# ------------------------------------------------------------------ curves & metric
def arclength(C, n=400):
    """Resample a closed curve uniformly by arc length. Crank-angle sampling bunches points where the
    end-effector moves slowly, which shifts the centroid/scale used by normalization and inflates CD
    even for the exact mechanism, so curves are compared after arc-length resampling."""
    C = np.asarray(C, float)
    closed = np.vstack([C, C[:1]])
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(closed, axis=0), axis=1))]
    if seg[-1] <= 0:
        return C
    s = np.linspace(0, seg[-1], n, endpoint=False)
    return np.c_[np.interp(s, seg, closed[:, 0]), np.interp(s, seg, closed[:, 1])]


def normalize(C):
    C = np.asarray(C, float)
    c = C.mean(0)
    s = np.sqrt(((C - c) ** 2).sum(1).mean()) or 1.0
    return (C - c) / s


def chamfer(C1, C2):
    """LinkD Eq. 7: mean nearest-neighbour L2 distance, both directions (not squared)."""
    from scipy.spatial import cKDTree
    d1, _ = cKDTree(C2).query(C1)
    d2, _ = cKDTree(C1).query(C2)
    return float(d1.mean() + d2.mean())


def chamfer_invariant(C1, C2, n_rot=72):
    """Rotation/reflection-invariant variant: LinkD notes CD penalises curves that match up to rotation
    or mirror. Report both; a mechanism can be rotated/mirrored at installation."""
    A, B = normalize(C1), normalize(C2)
    best = (math.inf, 0.0, False)
    for refl in (False, True):
        Bm = B * np.array([1, -1]) if refl else B
        for th in np.linspace(0, 2 * np.pi, n_rot, endpoint=False):
            R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
            d = chamfer(A, Bm @ R.T)
            if d < best[0]:
                best = (d, math.degrees(th), refl)
    return {"chamfer_invariant": best[0], "rotation_deg": best[1], "reflected": best[2]}


def compare(target, curve, invariant=False, raw=False):
    """Default: arc-length resampled + normalized. raw=True: LinkD's protocol (200 uniform motor angles
    on both curves, normalized), only meaningful when both curves come from mechanisms."""
    if not raw:
        target, curve = arclength(target), arclength(curve)
    out = {"chamfer_normalized": chamfer(normalize(target), normalize(curve)),
           "protocol": "raw uniform-angle (LinkD)" if raw else "arc-length resampled (400 pts)"}
    if invariant:
        out |= chamfer_invariant(target, curve)
    return out


def plot(m, out, target=None, P=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    if P is None:
        P, err = simulate(m)
    X0 = np.asarray(m["nodes"], float)
    fig, axs = plt.subplots(1, 2 if target is not None else 1, figsize=(11 if target is not None else 6, 5))
    axs = np.atleast_1d(axs)
    ax = axs[0]
    if P is not None:
        for k in range(len(X0)):
            if k not in m["fixed"]:
                ax.plot(P[:, k, 0], P[:, k, 1], lw=0.6, color="#bbbbbb")
        ax.plot(P[:, m["effector"], 0], P[:, m["effector"], 1], color="#2e8b57", lw=2, label="end-effector path")
    for a, b in m["edges"]:
        ax.plot(*X0[[a, b]].T, color="#2c3e50", lw=2.5)
    for k, (x, y) in enumerate(X0):
        ax.plot(x, y, "s" if k in m["fixed"] else "o", color="#c0392b" if k in m["fixed"] else "#2c3e50", ms=8)
        ax.annotate(str(k), (x, y), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set_aspect("equal"); ax.set_title(f"mechanism ({len(X0)} nodes, {len(m['edges'])} links)", fontsize=10)
    ax.legend(fontsize=8, loc="best")
    if target is not None and P is not None:
        ax = axs[1]
        T, C = normalize(arclength(target)), normalize(arclength(P[:, m["effector"]]))
        ax.plot(*T.T, "--", color="#8b1a1a", label="target (normalized)")
        ax.plot(*C.T, color="#2e8b57", lw=2, label="generated (normalized)")
        ax.set_aspect("equal"); ax.legend(fontsize=8)
        ax.set_title(f"Chamfer distance {chamfer(T, C):.3f}", fontsize=10)
    fig.tight_layout(); fig.savefig(out, dpi=150)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").add_argument("mech")
    s = sub.add_parser("simulate"); s.add_argument("mech"); s.add_argument("--out", required=True)
    s = sub.add_parser("encode"); s.add_argument("mech"); s.add_argument("--out", required=True)
    s = sub.add_parser("decode"); s.add_argument("npy"); s.add_argument("--out", required=True)
    s = sub.add_parser("compare"); s.add_argument("target"); s.add_argument("curve"); s.add_argument("--invariant", action="store_true"); s.add_argument("--raw", action="store_true")
    s = sub.add_parser("plot"); s.add_argument("mech"); s.add_argument("--target"); s.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "validate":
        r = validate(load(a.mech))
    elif a.cmd == "simulate":
        m = load(a.mech); P, err = simulate(m)
        if err:
            sys.exit(err)
        np.savetxt(a.out, P[:, m["effector"]], delimiter=",", header="x,y", comments="")
        r = {"curve": a.out, "points": N_ANGLES}
    elif a.cmd == "encode":
        G, meta = encode(load(a.mech)); np.save(a.out, G); r = {"shape": list(G.shape)} | meta
    elif a.cmd == "decode":
        m = decode(np.load(a.npy)); json.dump(m, open(a.out, "w"), indent=1); r = {"mech": a.out, "nodes": len(m["nodes"])}
    elif a.cmd == "compare":
        rd = lambda p: np.loadtxt(p, delimiter=",", skiprows=1)
        r = compare(rd(a.target), rd(a.curve), a.invariant, a.raw)
    else:
        t = np.loadtxt(a.target, delimiter=",", skiprows=1) if a.target else None
        r = {"plot": plot(load(a.mech), a.out, t)}
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
