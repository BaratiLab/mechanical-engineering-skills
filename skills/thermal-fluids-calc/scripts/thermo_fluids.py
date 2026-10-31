#!/usr/bin/env python3
"""Thermal-fluids design calculator (SI: m, kg, s, K or degC, Pa, W).

Subcommands
  props  fluid properties at T, P via CoolProp
  pipe   pressure drop: Darcy-Weisbach + Colebrook + minor losses (K sum)
  hx     heat exchanger: rating (eps-NTU) or sizing (UA for duty)
  fin    straight rectangular / pin fin efficiency and heat rate

All commands print JSON with inputs, intermediate values, and results.
"""
import argparse
import json
import math
import sys


def props(fluid, T_C, P_Pa):
    try:
        from CoolProp.CoolProp import PropsSI
    except ImportError:
        sys.exit("CoolProp missing: pip install CoolProp")
    T = T_C + 273.15
    g = lambda k: PropsSI(k, "T", T, "P", P_Pa, fluid)
    return {"fluid": fluid, "T_C": T_C, "P_Pa": P_Pa, "rho": g("D"), "mu": g("V"),
            "cp": g("C"), "k": g("L"), "Pr": g("Prandtl")}


def colebrook(Re, rel_rough):
    if Re < 2300:
        return 64 / Re, "laminar"
    # Haaland as initial guess, then iterate Colebrook
    f = (-1.8 * math.log10((rel_rough / 3.7) ** 1.11 + 6.9 / Re)) ** -2
    for _ in range(50):
        f_new = (-2 * math.log10(rel_rough / 3.7 + 2.51 / (Re * math.sqrt(f)))) ** -2
        if abs(f_new - f) < 1e-10:
            break
        f = f_new
    return f_new, "turbulent" if Re > 4000 else "transitional (treat with caution)"


ROUGHNESS_M = {"drawn-tubing": 1.5e-6, "commercial-steel": 4.5e-5, "galvanized": 1.5e-4,
               "cast-iron": 2.6e-4, "concrete": 1e-3, "pvc": 1.5e-6}


def cmd_pipe(a):
    pr = props(a.fluid, a.T, a.P)
    A = math.pi * a.D ** 2 / 4
    if a.Q is not None:
        V = a.Q / A
    else:
        V = a.mdot / (pr["rho"] * A)
    Re = pr["rho"] * V * a.D / pr["mu"]
    eps = ROUGHNESS_M.get(a.roughness) if a.roughness in ROUGHNESS_M else float(a.roughness)
    f, regime = colebrook(Re, eps / a.D)
    q = 0.5 * pr["rho"] * V ** 2
    dp_major = f * a.L / a.D * q
    dp_minor = a.K * q
    dp_elev = pr["rho"] * 9.81 * a.dz
    dp = dp_major + dp_minor + dp_elev
    Qv = V * A
    return {"props": pr, "values": {"V_m_s": V, "Re": Re, "regime": regime, "f": f,
                                    "eps_m": eps, "dp_major_Pa": dp_major,
                                    "dp_minor_Pa": dp_minor, "dp_elev_Pa": dp_elev,
                                    "dp_total_Pa": dp, "dp_total_kPa": dp / 1000,
                                    "pump_power_W_ideal": dp * Qv,
                                    "head_m": dp / (pr["rho"] * 9.81)},
            "checks": [{"check": "velocity in typical liquid range 0.5-3 m/s",
                        "status": "PASS" if 0.5 <= V <= 3 else "REVIEW"}],
            "method": "Darcy-Weisbach, Colebrook-White friction factor"}


def eps_ntu(NTU, Cr, arr):
    if Cr < 1e-9:
        return 1 - math.exp(-NTU)
    if arr == "counterflow":
        if abs(Cr - 1) < 1e-9:
            return NTU / (1 + NTU)
        e = math.exp(-NTU * (1 - Cr))
        return (1 - e) / (1 - Cr * e)
    if arr == "parallel":
        return (1 - math.exp(-NTU * (1 + Cr))) / (1 + Cr)
    if arr == "shell-tube-1":
        s = math.sqrt(1 + Cr ** 2)
        e = math.exp(-NTU * s)
        return 2 / (1 + Cr + s * (1 + e) / (1 - e))
    if arr == "crossflow-unmixed":
        return 1 - math.exp((1 / Cr) * NTU ** 0.22 * (math.exp(-Cr * NTU ** 0.78) - 1))
    raise ValueError(arr)


def ntu_from_eps(eps, Cr, arr):
    lo, hi = 1e-6, 50.0
    if eps >= eps_ntu(hi, Cr, arr):
        return math.inf
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if eps_ntu(mid, Cr, arr) < eps:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cmd_hx(a):
    Ch = a.mh * a.cph
    Cc = a.mc * a.cpc
    Cmin, Cmax = min(Ch, Cc), max(Ch, Cc)
    Cr = Cmin / Cmax
    qmax = Cmin * (a.Thi - a.Tci)
    out = {"inputs": vars(a), "values": {"Ch_W_K": Ch, "Cc_W_K": Cc, "Cr": Cr, "qmax_W": qmax}}
    if a.UA is not None:  # rating
        NTU = a.UA / Cmin
        eps = eps_ntu(NTU, Cr, a.arrangement)
        q = eps * qmax
    else:  # sizing for a required duty
        q = a.q
        eps = q / qmax
        NTU = ntu_from_eps(eps, Cr, a.arrangement)
        out["values"]["UA_required_W_K"] = NTU * Cmin
        if a.U:
            out["values"]["area_required_m2"] = NTU * Cmin / a.U
    Tho = a.Thi - q / Ch
    Tco = a.Tci + q / Cc
    if a.arrangement == "parallel":
        d1, d2 = a.Thi - a.Tci, Tho - Tco
    else:
        d1, d2 = a.Thi - Tco, Tho - a.Tci
    lmtd = (d1 - d2) / math.log(d1 / d2) if d1 > 0 and d2 > 0 and abs(d1 - d2) > 1e-9 else d1
    out["values"] |= {"NTU": NTU, "effectiveness": eps, "q_W": q, "Th_out": Tho,
                      "Tc_out": Tco, "LMTD_counterflow_basis": lmtd}
    out["checks"] = [{"check": "no temperature cross", "status": "PASS" if Tco <= a.Thi and Tho >= a.Tci else "FAIL"},
                     {"check": "duty achievable", "status": "PASS" if eps < 1 and NTU != math.inf else "FAIL"}]
    out["method"] = "epsilon-NTU (Incropera Table 11.3/11.4)"
    return out


def cmd_fin(a):
    if a.shape == "rect":
        P = 2 * (a.w + a.t)
        Ac = a.w * a.t
    else:  # pin
        P = math.pi * a.t
        Ac = math.pi * a.t ** 2 / 4
    m = math.sqrt(a.h * P / (a.k * Ac))
    Lc = a.L + (a.t / 2 if a.shape == "rect" else a.t / 4)  # corrected length
    eta = math.tanh(m * Lc) / (m * Lc)
    Af = P * Lc
    q = eta * a.h * Af * (a.Tb - a.Tinf)
    q_nofin = a.h * Ac * (a.Tb - a.Tinf)
    return {"inputs": vars(a),
            "values": {"m_1_per_m": m, "Lc_m": Lc, "mLc": m * Lc, "efficiency": eta,
                       "q_per_fin_W": q, "fin_effectiveness": q / q_nofin},
            "checks": [{"check": "fin effectiveness >= 2 (fin is worthwhile)",
                        "status": "PASS" if q / q_nofin >= 2 else "FAIL"},
                       {"check": "mLc <= ~2.5 (longer adds little)",
                        "status": "PASS" if m * Lc <= 2.5 else "REVIEW"}],
            "method": "Straight fin, corrected-length convective tip (Incropera 3.6)"}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("props")
    s.add_argument("--fluid", default="Water")
    s.add_argument("--T", type=float, required=True, help="degC")
    s.add_argument("--P", type=float, default=101325)

    s = sub.add_parser("pipe")
    s.add_argument("--fluid", default="Water")
    s.add_argument("--T", type=float, default=20)
    s.add_argument("--P", type=float, default=101325)
    s.add_argument("--D", type=float, required=True, help="inner diameter m")
    s.add_argument("--L", type=float, required=True, help="length m")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--Q", type=float, help="volumetric flow m^3/s")
    g.add_argument("--mdot", type=float, help="mass flow kg/s")
    s.add_argument("--roughness", default="commercial-steel",
                   help=f"one of {list(ROUGHNESS_M)} or a number in m")
    s.add_argument("--K", type=float, default=0.0, help="sum of minor-loss coefficients")
    s.add_argument("--dz", type=float, default=0.0, help="elevation rise m")

    s = sub.add_parser("hx")
    s.add_argument("--mh", type=float, required=True)
    s.add_argument("--cph", type=float, required=True)
    s.add_argument("--mc", type=float, required=True)
    s.add_argument("--cpc", type=float, required=True)
    s.add_argument("--Thi", type=float, required=True)
    s.add_argument("--Tci", type=float, required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--UA", type=float, help="rating mode: known UA W/K")
    g.add_argument("--q", type=float, help="sizing mode: required duty W")
    s.add_argument("--U", type=float, help="overall U W/m2K, to report area in sizing mode")
    s.add_argument("--arrangement", default="counterflow",
                   choices=["counterflow", "parallel", "shell-tube-1", "crossflow-unmixed"])

    s = sub.add_parser("fin")
    s.add_argument("--shape", choices=["rect", "pin"], default="rect")
    s.add_argument("--k", type=float, required=True, help="W/mK")
    s.add_argument("--h", type=float, required=True, help="W/m2K")
    s.add_argument("--L", type=float, required=True, help="fin length m")
    s.add_argument("--t", type=float, required=True, help="thickness (rect) or diameter (pin) m")
    s.add_argument("--w", type=float, default=1.0, help="width m (rect)")
    s.add_argument("--Tb", type=float, required=True)
    s.add_argument("--Tinf", type=float, required=True)

    a = p.parse_args()
    if a.cmd == "props":
        res = props(a.fluid, a.T, a.P)
    else:
        res = {"pipe": cmd_pipe, "hx": cmd_hx, "fin": cmd_fin}[a.cmd](a)
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
