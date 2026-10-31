#!/usr/bin/env python3
"""Ashby-style material selection.

  python rank_materials.py --index stiff-beam [--minimize-cost] [--Tmin 120]
                   [--sy-min 100] [--exclude ceramic,natural] [--top 8] [--out sel]

Ranks materials in references/materials.csv by the performance index
(larger is better), applies hard constraints, writes <out>.json, <out>_chart.png.
"""
import argparse
import csv
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "references", "materials.csv")

# index: (formula on E [Pa], sy [Pa], rho, description)
INDICES = {
    "stiff-tie": (lambda m: m["E"] / m["rho"], "E/rho", "light stiff tie (tension member)"),
    "stiff-beam": (lambda m: m["E"] ** 0.5 / m["rho"], "E^1/2/rho", "light stiff beam, free section size"),
    "stiff-panel": (lambda m: m["E"] ** (1 / 3) / m["rho"], "E^1/3/rho", "light stiff plate, free thickness"),
    "strong-tie": (lambda m: m["sy"] / m["rho"], "sy/rho", "light strong tie"),
    "strong-beam": (lambda m: m["sy"] ** (2 / 3) / m["rho"], "sy^2/3/rho", "light strong beam"),
    "strong-panel": (lambda m: m["sy"] ** 0.5 / m["rho"], "sy^1/2/rho", "light strong plate"),
    "spring": (lambda m: m["sy"] ** 2 / m["E"], "sy^2/E", "max elastic energy per volume"),
    "light-spring": (lambda m: m["sy"] ** 2 / (m["E"] * m["rho"]), "sy^2/(E rho)", "max elastic energy per mass"),
    "flexure-hinge": (lambda m: m["sy"] / m["E"], "sy/E", "elastic hinge / snap fit"),
    "damage-tolerant": (lambda m: m["KIC"] / m["sy"], "KIC/sy", "leak-before-break, flaw tolerance"),
    "heat-spreader": (lambda m: m["k"] / m["rho"], "k/rho", "light heat spreader"),
    "thermal-stability": (lambda m: m["k"] / m["alpha"], "k/alpha", "minimum thermal distortion"),
}


def load():
    rows = []
    with open(DB) as f:
        for r in csv.DictReader(f):
            rows.append({"name": r["name"], "family": r["family"],
                         "E": float(r["E_GPa"]) * 1e9, "rho": float(r["rho_kg_m3"]),
                         "sy": float(r["sy_MPa"]) * 1e6, "KIC": float(r["KIC_MPa_sqrtm"]),
                         "cost": float(r["cost_usd_kg"]), "k": float(r["k_W_mK"]),
                         "alpha": max(float(r["alpha_ue_K"]), 0.1), "Tmax": float(r["Tmax_C"]),
                         "notes": r["notes"]})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", required=True, choices=INDICES)
    p.add_argument("--minimize-cost", action="store_true", help="divide index by cost/kg (per-mass indices)")
    p.add_argument("--Tmin", type=float, help="required service temperature C")
    p.add_argument("--sy-min", type=float, help="MPa")
    p.add_argument("--E-min", type=float, help="GPa")
    p.add_argument("--KIC-min", type=float)
    p.add_argument("--exclude", default="", help="comma list of families")
    p.add_argument("--top", type=int, default=8)
    p.add_argument("--out", default="selection")
    a = p.parse_args()

    fn, formula, desc = INDICES[a.index]
    excl = {s.strip() for s in a.exclude.split(",") if s.strip()}
    passed, rejected = [], []
    for m in load():
        why = []
        if m["family"] in excl: why.append("family excluded")
        if a.Tmin is not None and m["Tmax"] < a.Tmin: why.append(f"Tmax {m['Tmax']}C < {a.Tmin}")
        if a.sy_min is not None and m["sy"] / 1e6 < a.sy_min: why.append("sy too low")
        if a.E_min is not None and m["E"] / 1e9 < a.E_min: why.append("E too low")
        if a.KIC_min is not None and m["KIC"] < a.KIC_min: why.append("KIC too low")
        if why:
            rejected.append({"name": m["name"], "reasons": why})
            continue
        M = fn(m)
        if a.minimize_cost:
            M /= m["cost"]
        passed.append({"name": m["name"], "family": m["family"], "index": M, "notes": m["notes"],
                       "E_GPa": m["E"] / 1e9, "sy_MPa": m["sy"] / 1e6, "rho": m["rho"],
                       "cost_usd_kg": m["cost"]})
    passed.sort(key=lambda d: -d["index"])
    best = passed[0]["index"] if passed else 1
    for d in passed:
        d["relative"] = d["index"] / best
    res = {"index": a.index, "formula": formula + (" / Cm" if a.minimize_cost else ""),
           "meaning": desc, "ranked": passed[: a.top], "rejected": rejected}

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"metal": "#3b6ea5", "polymer": "#e08a2c", "composite": "#2e8b57",
              "ceramic": "#8e44ad", "natural": "#8b5a2b"}
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for d in passed:
        ax.scatter(d["rho"], d["E_GPa"], s=60, color=colors.get(d["family"], "gray"))
        if d in passed[: a.top]:
            ax.annotate(d["name"], (d["rho"], d["E_GPa"]), fontsize=7, xytext=(4, 2), textcoords="offset points")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Density (kg/m³)"); ax.set_ylabel("Young's modulus (GPa)")
    ax.set_title(f"E–ρ chart, top {a.top} by {res['formula']} labelled")
    for fam, c in colors.items():
        ax.scatter([], [], color=c, label=fam)
    ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(f"{a.out}_chart.png", dpi=150)
    with open(f"{a.out}.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
