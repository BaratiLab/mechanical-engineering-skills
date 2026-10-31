#!/usr/bin/env python3
"""1-D tolerance stack-up: worst-case, RSS, and Monte Carlo.

Input CSV columns: name,nominal,plus,minus,direction[,dist][,cpk]
  direction: +1 or -1 (sense of the dimension around the loop)
  plus/minus: positive numbers (e.g. 0.05,0.05 for +/-0.05)
  dist: normal (default) | uniform | triangular
  cpk:  process capability for normal dists (default 1.0 -> tol = 3 sigma)

Usage:
  python stackup.py chain.csv --lsl 0.1 --usl 0.6 --out stack
Outputs <out>.json and <out>_contrib.png / <out>_hist.png.
"""
import argparse
import csv
import json
import math

import numpy as np


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append(dict(
                name=r["name"], nominal=float(r["nominal"]),
                plus=abs(float(r["plus"])), minus=abs(float(r["minus"])),
                direction=float(r["direction"]),
                dist=(r.get("dist") or "normal").strip(),
                cpk=float(r.get("cpk") or 1.0)))
    return rows


def analyse(rows, lsl, usl, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    nominal_gap = sum(r["direction"] * r["nominal"] for r in rows)
    # Mean shift for asymmetric tolerances
    mean_gap = sum(r["direction"] * (r["nominal"] + (r["plus"] - r["minus"]) / 2) for r in rows)
    part_half = [(r["plus"] + r["minus"]) / 2 for r in rows]
    half = [abs(r["direction"]) * h for r, h in zip(rows, part_half)]  # effect on gap
    wc = sum(half)
    rss = math.sqrt(sum(h ** 2 for h in half))
    samples = np.zeros(n)
    for r, h in zip(rows, part_half):
        mu = r["nominal"] + (r["plus"] - r["minus"]) / 2
        if r["dist"] == "uniform":
            x = rng.uniform(mu - h, mu + h, n)
        elif r["dist"] == "triangular":
            x = rng.triangular(mu - h, mu, mu + h, n)
        else:
            sigma = h / (3 * r["cpk"])
            x = rng.normal(mu, sigma, n)
        samples += r["direction"] * x
    res = {
        "nominal_gap": nominal_gap, "mean_gap": mean_gap,
        "worst_case": {"min": mean_gap - wc, "max": mean_gap + wc, "half_range": wc},
        "rss": {"min": mean_gap - rss, "max": mean_gap + rss, "half_range": rss},
        "monte_carlo": {"n": n, "mean": float(samples.mean()), "std": float(samples.std()),
                        "p0.135": float(np.percentile(samples, 0.135)),
                        "p99.865": float(np.percentile(samples, 99.865))},
        "contributors": sorted(
            [{"name": r["name"], "half_tol": h, "pct_rss": 100 * h ** 2 / rss ** 2}
             for r, h in zip(rows, half)], key=lambda d: -d["pct_rss"]),
    }
    if lsl is not None or usl is not None:
        lo = -np.inf if lsl is None else lsl
        hi = np.inf if usl is None else usl
        fail = float(np.mean((samples < lo) | (samples > hi)))
        res["spec"] = {"lsl": lsl, "usl": usl,
                       "worst_case_ok": (lsl is None or mean_gap - wc >= lsl) and (usl is None or mean_gap + wc <= usl),
                       "rss_ok": (lsl is None or mean_gap - rss >= lsl) and (usl is None or mean_gap + rss <= usl),
                       "mc_reject_rate": fail, "mc_reject_ppm": fail * 1e6}
    return res, samples


def plot(res, samples, out, lsl, usl):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = res["contributors"]
    fig, ax = plt.subplots(figsize=(7, 0.4 * len(c) + 1.5))
    ax.barh([d["name"] for d in c][::-1], [d["pct_rss"] for d in c][::-1], color="#3b6ea5")
    ax.set_xlabel("% contribution to RSS variance")
    ax.set_title("Tolerance contributors")
    fig.tight_layout()
    fig.savefig(f"{out}_contrib.png", dpi=150)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(samples, bins=120, color="#3b6ea5", alpha=0.8)
    for v, lab in ((lsl, "LSL"), (usl, "USL")):
        if v is not None:
            ax.axvline(v, color="#c0392b", ls="--")
            ax.text(v, ax.get_ylim()[1] * 0.95, lab, color="#c0392b", ha="center")
    ax.set_xlabel("Gap")
    ax.set_title("Monte Carlo gap distribution")
    fig.tight_layout()
    fig.savefig(f"{out}_hist.png", dpi=150)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--lsl", type=float)
    p.add_argument("--usl", type=float)
    p.add_argument("--n", type=int, default=200_000)
    p.add_argument("--out", default="stack")
    a = p.parse_args()
    rows = load(a.csv)
    res, s = analyse(rows, a.lsl, a.usl, a.n)
    plot(res, s, a.out, a.lsl, a.usl)
    with open(f"{a.out}.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
