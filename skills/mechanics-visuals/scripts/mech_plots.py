#!/usr/bin/env python3
"""Publication-quality mechanics teaching plots.

  mohr   --sx 80 --sy -40 --txy 30            (MPa)  2-D Mohr's circle + principal values
  beam   --L 2000 --support simply|cantilever --point 1000:5000 --udl 0:2000:3
                                                 shear / moment / deflection diagrams
  sn     --Sut 690 --Se 280 [--f 0.86]          S-N curve (Basquin, Shigley 10^3-10^6)
  ss     --E 205000 --sy 350 --Sut 480 --n 0.18 Ramberg-Osgood stress-strain curve
All write <out>.png (and .svg) and print key numbers as JSON.
"""
import argparse
import json
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BLUE, RED, GRAY = "#1f4e79", "#c0392b", "#7f8c8d"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, out):
    fig.tight_layout()
    fig.savefig(out + ".png", dpi=200)
    fig.savefig(out + ".svg")


def mohr(a):
    c = (a.sx + a.sy) / 2
    R = math.hypot((a.sx - a.sy) / 2, a.txy)
    s1, s2 = c + R, c - R
    thp = 0.5 * math.degrees(math.atan2(2 * a.txy, a.sx - a.sy))
    fig, ax = plt.subplots(figsize=(6, 6))
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(c + R * np.cos(t), R * np.sin(t), color=BLUE)
    # Convention: plot (sx, -txy) as point X (cw shear positive, Shigley)
    X, Y = (a.sx, -a.txy), (a.sy, a.txy)
    ax.plot(*zip(X, Y), color=GRAY, ls="--")
    ax.plot(*X, "o", color=RED); ax.annotate(f"x ({a.sx}, {a.txy})", X, xytext=(6, -12), textcoords="offset points")
    ax.plot(*Y, "o", color=RED); ax.annotate(f"y ({a.sy}, {-a.txy})", Y, xytext=(6, 6), textcoords="offset points")
    for s, lab in ((s1, "σ₁"), (s2, "σ₂")):
        ax.plot(s, 0, "s", color=BLUE); ax.annotate(f"{lab} = {s:.1f}", (s, 0), xytext=(4, 8), textcoords="offset points")
    ax.plot(c, R, "^", color=BLUE); ax.annotate(f"τmax = {R:.1f}", (c, R), xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="k", lw=0.6); ax.axvline(0, color="k", lw=0.6)
    ax.set_aspect("equal"); ax.set_xlabel("σ (MPa)"); ax.set_ylabel("τ (MPa, cw ↓)")
    ax.invert_yaxis()
    ax.set_title("Mohr's circle (plane stress)")
    save(fig, a.out)
    return {"center": c, "R": R, "sigma1": s1, "sigma2": s2, "tau_max_inplane": R,
            "theta_p_deg_ccw_from_x": thp,
            "tau_max_absolute": max(R, abs(s1) / 2, abs(s2) / 2)}


def beam(a):
    L, EI = a.L, a.E * a.I
    x = np.linspace(0, L, 2001)
    loads = []  # (type, params)
    for p in a.point or []:
        pos, P = map(float, p.split(":")); loads.append(("P", pos, P))
    for u in a.udl or []:
        x0, x1, w = map(float, u.split(":")); loads.append(("w", x0, x1, w))
    # Reactions
    Ptot = sum(l[2] for l in loads if l[0] == "P") + sum(l[3] * (l[2] - l[1]) for l in loads if l[0] == "w")
    Mo = sum(l[2] * l[1] for l in loads if l[0] == "P") + sum(l[3] * (l[2] - l[1]) * (l[1] + l[2]) / 2 for l in loads if l[0] == "w")
    if a.support == "simply":
        RB = Mo / L; RA = Ptot - RB; M0 = 0.0
    else:  # cantilever fixed at x=0
        RA = Ptot; M0 = -Mo; RB = 0.0
    V = np.full_like(x, RA); M = M0 + RA * x
    for l in loads:
        if l[0] == "P":
            V -= l[2] * (x >= l[1]); M -= l[2] * np.clip(x - l[1], 0, None)
        else:
            _, x0, x1, w = l
            seg = np.clip(x, x0, x1) - x0
            V -= w * seg
            M -= w * seg * (x - x0 - seg / 2)
    # Deflection: integrate M/EI twice, apply BCs
    th = np.concatenate([[0], np.cumsum((M[1:] + M[:-1]) / 2 * np.diff(x))]) / EI
    y = np.concatenate([[0], np.cumsum((th[1:] + th[:-1]) / 2 * np.diff(x))])
    if a.support == "simply":
        y -= y[-1] * x / L  # y(0)=y(L)=0
    fig, axs = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
    for ax, data, lab, col in zip(axs, (V, M / 1e3, y), ("Shear V (N)", "Moment M (N·m)", "Deflection (mm)"), (BLUE, RED, GRAY)):
        ax.fill_between(x, data, color=col, alpha=0.25); ax.plot(x, data, color=col)
        ax.axhline(0, color="k", lw=0.6); ax.set_ylabel(lab)
    axs[-1].set_xlabel("x (mm)")
    axs[0].set_title(f"{'Simply supported' if a.support == 'simply' else 'Cantilever'} beam, L = {L:g} mm")
    save(fig, a.out)
    i = int(np.argmax(np.abs(M)))
    return {"RA_N": RA, "RB_N": RB, "M_fixed_Nmm": M0, "Mmax_Nmm": float(M[i]), "x_Mmax_mm": float(x[i]),
            "Vmax_N": float(np.max(np.abs(V))), "ymax_mm": float(y[np.argmax(np.abs(y))]),
            "sign_convention": "loads +down; deflection +up; sagging moment +"}


def sn(a):
    f = a.f
    a_ = (f * a.Sut) ** 2 / a.Se
    b = -math.log10(f * a.Sut / a.Se) / 3
    N = np.logspace(0, 8, 400)
    S = np.where(N < 1e3, a.Sut * N ** (math.log10(f) / 3),  # low-cycle line from Sut at N=1 to f*Sut at 1e3
                 np.where(N <= 1e6, a_ * N ** b, a.Se))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogx(N, S, color=BLUE, lw=2)
    ax.axhline(a.Se, color=GRAY, ls="--"); ax.text(2e6, a.Se * 1.03, f"Se = {a.Se:g} MPa", color=GRAY)
    ax.axvline(1e3, color=GRAY, lw=0.5); ax.axvline(1e6, color=GRAY, lw=0.5)
    ax.set_xlabel("Cycles to failure N"); ax.set_ylabel("Fully reversed stress amplitude (MPa)")
    ax.set_title("S–N curve (steel, Basquin fit)")
    save(fig, a.out)
    return {"a_MPa": a_, "b": b, "S_at_1e3": f * a.Sut, "Se": a.Se}


def ss(a):
    s = np.linspace(0, a.Sut, 400)
    eps = s / a.E + 0.002 * (s / a.sy) ** (1 / a.n)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(eps * 100, s, color=BLUE, lw=2)
    e_off = np.linspace(0.002, 0.002 + a.sy / a.E * 1.1, 50)
    ax.plot(e_off * 100, a.E * (e_off - 0.002), color=GRAY, ls="--", label="0.2% offset")
    ax.plot(eps[np.argmin(abs(s - a.sy))] * 100, a.sy, "o", color=RED); ax.annotate(f"σy = {a.sy:g}", (eps[np.argmin(abs(s - a.sy))] * 100, a.sy), xytext=(6, -12), textcoords="offset points")
    ax.set_xlabel("Strain (%)"); ax.set_ylabel("Stress (MPa)"); ax.legend()
    ax.set_title("Engineering stress–strain (Ramberg–Osgood)")
    save(fig, a.out)
    return {"strain_at_Sut": float(eps[-1]), "n": a.n}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mohr"); m.add_argument("--sx", type=float, required=True); m.add_argument("--sy", type=float, required=True); m.add_argument("--txy", type=float, required=True)
    b = sub.add_parser("beam"); b.add_argument("--L", type=float, required=True); b.add_argument("--support", choices=["simply", "cantilever"], default="simply")
    b.add_argument("--point", action="append", help="pos_mm:load_N (down +)"); b.add_argument("--udl", action="append", help="x0:x1:w_N_per_mm")
    b.add_argument("--E", type=float, default=205000, help="MPa"); b.add_argument("--I", type=float, default=1e6, help="mm^4")
    s = sub.add_parser("sn"); s.add_argument("--Sut", type=float, required=True); s.add_argument("--Se", type=float, required=True); s.add_argument("--f", type=float, default=0.9)
    t = sub.add_parser("ss"); t.add_argument("--E", type=float, default=205000); t.add_argument("--sy", type=float, required=True); t.add_argument("--Sut", type=float, required=True); t.add_argument("--n", type=float, default=0.15)
    for sp in (m, b, s, t):
        sp.add_argument("--out", default=None)
    a = p.parse_args()
    a.out = a.out or a.cmd
    res = {"mohr": mohr, "beam": beam, "sn": sn, "ss": ss}[a.cmd](a)
    print(json.dumps(res | {"files": [a.out + ".png", a.out + ".svg"]}, indent=2))


if __name__ == "__main__":
    main()
