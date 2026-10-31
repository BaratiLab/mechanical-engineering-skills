#!/usr/bin/env python3
"""Reference physics computed by code (never by the model).

  python theory.py nozzle --p0 2e5 --T0 300 --rt 0.0326 --re 0.0354 [--pa 3e4]
  python theory.py shock  --M 2.0
  python theory.py choke  --M 3.0 --h 0.3          # forward-step choking estimate
  python theory.py compare --cfd cfd.json --ref ref.json --keys exit_mach,exit_p,mdot

Quasi-1-D isentropic flow, normal-shock relations, and the forward-step
post-shock choking estimate used in CFD Forge (arXiv:2610.14104, Sec. 5.3).
"""
import argparse
import json
import math


def area_ratio(M, g=1.4):
    return (1 / M) * ((2 / (g + 1)) * (1 + (g - 1) / 2 * M * M)) ** ((g + 1) / (2 * (g - 1)))


def mach_from_area(Ar, supersonic, g=1.4):
    if Ar < 1 - 1e-12:
        raise ValueError("A/A* < 1 is impossible")
    lo, hi = (1.0, 50.0) if supersonic else (1e-6, 1.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f = area_ratio(mid, g) - Ar
        if (f > 0) == supersonic:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def isentropic(M, g=1.4):
    t = 1 + (g - 1) / 2 * M * M
    return {"T_T0": 1 / t, "p_p0": t ** (-g / (g - 1)), "rho_rho0": t ** (-1 / (g - 1))}


def normal_shock(M1, g=1.4):
    M2 = math.sqrt((1 + (g - 1) / 2 * M1 ** 2) / (g * M1 ** 2 - (g - 1) / 2))
    p = 1 + 2 * g / (g + 1) * (M1 ** 2 - 1)
    rho = (g + 1) * M1 ** 2 / ((g - 1) * M1 ** 2 + 2)
    return {"M2": M2, "p2_p1": p, "rho2_rho1": rho, "T2_T1": p / rho,
            "p02_p01": (rho ** (g / (g - 1))) * (1 / p) ** (1 / (g - 1))}


def nozzle(p0, T0, rt, re, ri=None, pa=None, g=1.4, R=287.0):
    At, Ae = math.pi * rt ** 2, math.pi * re ** 2
    Me = mach_from_area(Ae / At, True, g)
    ise = isentropic(Me, g)
    mdot = p0 * At / math.sqrt(T0) * math.sqrt(g / R) * (2 / (g + 1)) ** ((g + 1) / (2 * (g - 1)))
    out = {"Ae_At": Ae / At, "throat_mach": 1.0, "exit_mach": Me, "exit_p": ise["p_p0"] * p0,
           "exit_T": ise["T_T0"] * T0, "mdot": mdot}
    if ri:
        Mi = mach_from_area((ri / rt) ** 2, False, g)
        out["inlet_mach"] = Mi
    if pa:
        pe = out["exit_p"]
        # design-condition classification; internal shock if pa above the shock-at-exit pressure
        ns = normal_shock(Me, g)
        p_shock_exit = pe * ns["p2_p1"]
        Me_sub = mach_from_area(Ae / At, False, g)
        p_subsonic = isentropic(Me_sub, g)["p_p0"] * p0
        if pa >= p_subsonic:
            regime = "subsonic throughout (not choked) or choked-subsonic exit"
        elif pa > p_shock_exit:
            regime = "normal shock inside diverging section"
        elif abs(pa - pe) / pe < 0.01:
            regime = "ideally expanded"
        elif pa < pe:
            regime = "underexpanded (supersonic exit, expansion outside)"
        else:
            regime = "overexpanded (supersonic exit, oblique shocks outside)"
        out |= {"p_ambient": pa, "regime": regime, "p_shock_at_exit": p_shock_exit}
    return out


def choke(M, h, g=1.4):
    ns = normal_shock(M, g)
    a_star_over_a = 1 / area_ratio(ns["M2"], g)
    return {"M": M, "h": h, "post_shock_M": ns["M2"], "Astar_over_A": a_star_over_a,
            "opening": 1 - h, "choked": a_star_over_a > 1 - h,
            "expectation": "front displaced toward inlet; may reach it" if a_star_over_a > 1 - h
            else "detached front stands off the step",
            "normal_shock_p_ratio": ns["p2_p1"]}


def compare(cfd, ref, keys):
    return {k: {"cfd": cfd[k], "ref": ref[k], "rel_diff": abs(cfd[k] - ref[k]) / abs(ref[k])} for k in keys}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nozzle")
    for k in ("p0", "T0", "rt", "re"):
        n.add_argument(f"--{k}", type=float, required=True)
    n.add_argument("--ri", type=float); n.add_argument("--pa", type=float)
    n.add_argument("--gamma", type=float, default=1.4); n.add_argument("--R", type=float, default=287.0)
    s = sub.add_parser("shock"); s.add_argument("--M", type=float, required=True); s.add_argument("--gamma", type=float, default=1.4)
    c = sub.add_parser("choke"); c.add_argument("--M", type=float, required=True); c.add_argument("--h", type=float, required=True)
    m = sub.add_parser("compare"); m.add_argument("--cfd", required=True); m.add_argument("--ref", required=True); m.add_argument("--keys", required=True)
    a = p.parse_args()
    if a.cmd == "nozzle":
        r = nozzle(a.p0, a.T0, a.rt, a.re, a.ri, a.pa, a.gamma, a.R)
    elif a.cmd == "shock":
        r = normal_shock(a.M, a.gamma)
    elif a.cmd == "choke":
        r = choke(a.M, a.h)
    else:
        r = compare(json.load(open(a.cfd)), json.load(open(a.ref)), a.keys.split(","))
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
