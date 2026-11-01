#!/usr/bin/env python3
"""2-D truss FEM evaluator matching the conventions of
'Large Language Model Agent as a Mechanical Designer' (Jadhav & Barati Farimani,
arXiv:2404.17525; J. Eng. Design 2026) and its reference code
(github.com/BaratiLab/LLLM-Agent-Mechanical-Designer, truss_y.py).

Conventions (kept identical so results are comparable with the paper):
  load      {"node_3": [magnitude, angle_deg]}  ->  Fx = m cos(a), Fy = m sin(a)
            e.g. [-10, -45] gives Fx = -7.07, Fy = +7.07 (as in the paper's Task 1)
  supports  "pinned" fixes x,y ; "roller" fixes y only
  members   {"member_1": ["node_1", "node_3", "4"]}  (area id from the area table)
  stress    sigma = E/L * (u_end - u_start) . e     (tension +), E = 29.6e6
  mass      sum(L_e * A_e)  using the area VALUE of each member's id

  python truss_fem.py design.json --task t1v1        -> JSON evaluation
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tasks import AREA, TASKS  # noqa: E402

E_MOD = 29.6e6


def validate(design, task):
    errs = []
    nodes = design.get("node_dict", {})
    mem = design.get("member_dict", {})
    for n, xy in task["nodes"].items():
        if n not in nodes:
            errs.append(f"fixed node {n} missing")
        elif any(abs(a - b) > 1e-9 for a, b in zip(nodes[n][:2], xy)):
            errs.append(f"load/support node {n} was moved from {xy} to {nodes[n][:2]}")
    coords = {}
    for n, xy in nodes.items():
        key = (round(float(xy[0]), 6), round(float(xy[1]), 6))
        if key in coords:
            errs.append(f"duplicate node position {key}: {coords[key]} and {n}")
        coords[key] = n
    seen = set()
    for m, (a, b, aid) in mem.items():
        if a not in nodes or b not in nodes:
            errs.append(f"{m} references a missing node")
        if a == b:
            errs.append(f"{m} connects a node to itself")
        pair = tuple(sorted((a, b)))
        if pair in seen:
            errs.append(f"duplicate member {pair}")
        seen.add(pair)
        if str(aid) not in AREA:
            errs.append(f"{m} uses unknown area id {aid}")
    used = {x for a, b, _ in mem.values() for x in (a, b)}
    floating = sorted(set(nodes) - used)
    if floating:
        errs.append(f"unconnected nodes: {floating}")
    return errs


def solve(design, task):
    nodes = {k: (float(v[0]), float(v[1])) for k, v in design["node_dict"].items()}
    names = list(nodes)
    idx = {n: i for i, n in enumerate(names)}
    ndof = 2 * len(names)
    K = np.zeros((ndof, ndof))
    geo = {}
    for m, (a, b, aid) in design["member_dict"].items():
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        L = math.hypot(x2 - x1, y2 - y1)
        c, s = (x2 - x1) / L, (y2 - y1) / L
        A = AREA[str(aid)]
        k = A * E_MOD / L * np.array([[c*c, c*s, -c*c, -c*s], [c*s, s*s, -c*s, -s*s],
                                      [-c*c, -c*s, c*c, c*s], [-c*s, -s*s, c*s, s*s]])
        dofs = [2*idx[a], 2*idx[a]+1, 2*idx[b], 2*idx[b]+1]
        K[np.ix_(dofs, dofs)] += k
        geo[m] = (a, b, L, c, s, A)
    F = np.zeros(ndof)
    for n, (mag, ang) in task["load"].items():
        F[2*idx[n]] += mag * math.cos(math.radians(ang))
        F[2*idx[n]+1] += mag * math.sin(math.radians(ang))
    fixed = []
    for n, t in task["supports"].items():
        fixed += [2*idx[n], 2*idx[n]+1] if t == "pinned" else [2*idx[n]+1]
    free = [d for d in range(ndof) if d not in fixed]
    Kr = K[np.ix_(free, free)]
    cond = np.linalg.cond(Kr) if Kr.size else math.inf
    if not Kr.size or cond > 1e12:
        return None, cond
    u = np.zeros(ndof)
    u[free] = np.linalg.solve(Kr, F[free])
    stress, mass = {}, {}
    for m, (a, b, L, c, s, A) in geo.items():
        du = np.array([-c, -s, c, s]) @ np.r_[u[2*idx[a]:2*idx[a]+2], u[2*idx[b]:2*idx[b]+2]]
        stress[m] = float(E_MOD / L * du)
        mass[m] = float(L * A)
    return {"stress": stress, "member_mass": mass, "displacement": {n: u[2*i:2*i+2].tolist() for n, i in idx.items()}}, cond


def evaluate(design, task):
    errs = validate(design, task)
    out = {"valid": not errs, "errors": errs}
    if errs:
        out |= {"feasible": False, "max_abs_stress": None, "total_mass": None, "swr": None}
        return out
    res, cond = solve(design, task)
    if res is None:
        out |= {"valid": False, "errors": [f"mechanism / unstable structure (stiffness condition {cond:.2e})"],
                "feasible": False, "max_abs_stress": None, "total_mass": None, "swr": None}
        return out
    smax = max(abs(v) for v in res["stress"].values())
    mtot = sum(res["member_mass"].values())
    swr = smax / mtot
    c = task["constraints"]
    viol = []
    if "max_stress" in c and smax > c["max_stress"]:
        viol.append(f"max |stress| {smax:.3f} > {c['max_stress']}")
    if "max_mass" in c and mtot > c["max_mass"]:
        viol.append(f"total mass {mtot:.3f} > {c['max_mass']}")
    if "max_swr" in c and swr > c["max_swr"]:
        viol.append(f"stress-to-weight {swr:.4f} > {c['max_swr']}")
    worst = sorted(res["stress"].items(), key=lambda kv: -abs(kv[1]))[:3]
    out |= {"feasible": not viol, "violations": viol, "max_abs_stress": smax, "total_mass": mtot, "swr": swr,
            "objective": smax if task["objective"] == "min_max_stress" else swr,
            "critical_members": [{"member": k, "stress": round(v, 4), "area_id": design["member_dict"][k][2]} for k, v in worst],
            "member_stress": {k: round(v, 4) for k, v in res["stress"].items()},
            "member_mass": {k: round(v, 4) for k, v in res["member_mass"].items()},
            "stiffness_condition": cond}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("design")
    ap.add_argument("--task", required=True, choices=TASKS)
    a = ap.parse_args()
    print(json.dumps(evaluate(json.load(open(a.design)), TASKS[a.task]), indent=2))


if __name__ == "__main__":
    main()
