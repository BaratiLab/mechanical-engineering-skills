#!/usr/bin/env python3
"""Machine element sizing calculator (SI units: N, mm, MPa, N*mm, rpm).

Subcommands: bolt, shaft, bearing, spring, weld, gear.
Every command prints a JSON block with inputs, intermediate values, results
and pass/fail checks so the agent can show its work.

References: Shigley's Mechanical Engineering Design (11th ed.) ch. 6-8, 10, 13;
ISO 898-1; ISO 281; AISC 360.
"""
import argparse
import json
import math
import sys

# ---------------------------------------------------------------- data tables
ISO_BOLT_GRADES = {  # Sp, Sut, Sy, Se (fully corrected endurance, rolled threads)
    "8.8": dict(Sp=600, Sut=830, Sy=660, Se=129),
    "9.8": dict(Sp=650, Sut=900, Sy=720, Se=140),
    "10.9": dict(Sp=830, Sut=1040, Sy=940, Se=162),
    "12.9": dict(Sp=970, Sut=1220, Sy=1100, Se=190),
}
METRIC_COARSE_AT = {  # tensile stress area, mm^2
    "M3": 5.03, "M4": 8.78, "M5": 14.2, "M6": 20.1, "M8": 36.6, "M10": 58.0,
    "M12": 84.3, "M14": 115, "M16": 157, "M20": 245, "M24": 353, "M30": 561,
    "M36": 817,
}
SURFACE_FACTOR = {  # ka = a * Sut^b (Sut in MPa)
    "ground": (1.58, -0.085), "machined": (4.51, -0.265),
    "cold-drawn": (4.51, -0.265), "hot-rolled": (57.7, -0.718),
    "forged": (272.0, -0.995),
}
RELIABILITY_KE = {0.5: 1.0, 0.9: 0.897, 0.95: 0.868, 0.99: 0.814,
                  0.999: 0.753, 0.9999: 0.702}
ISO281_A1 = {0.90: 1.0, 0.95: 0.64, 0.96: 0.55, 0.97: 0.47, 0.98: 0.37,
             0.99: 0.25}
SPRING_WIRE = {  # Sut = A / d^m (d mm, Sut MPa), G MPa
    "music-wire": dict(A=2211, m=0.145, G=81700),
    "hard-drawn": dict(A=1783, m=0.190, G=80000),
    "oil-tempered": dict(A=1855, m=0.187, G=77200),
    "chrome-vanadium": dict(A=2005, m=0.168, G=77200),
    "chrome-silicon": dict(A=1974, m=0.108, G=77200),
}
LEWIS_Y_20DEG = [(12, .245), (13, .261), (14, .277), (15, .290), (16, .296),
                 (17, .303), (18, .309), (19, .314), (20, .322), (21, .328),
                 (22, .331), (24, .337), (26, .346), (28, .353), (30, .359),
                 (34, .371), (38, .384), (43, .397), (50, .409), (60, .422),
                 (75, .435), (100, .447), (150, .460), (300, .472), (400, .480)]
ELECTRODE_SUT = {"E60": 427, "E70": 482, "E80": 551, "E90": 620,
                 "E100": 689, "E120": 827}


def check(name, value, target, higher_is_better=True):
    ok = value >= target if higher_is_better else value <= target
    return {"check": name, "value": round(value, 3), "target": target,
            "status": "PASS" if ok else "FAIL"}


def interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


# ---------------------------------------------------------------- bolt
def bolt(a):
    g = ISO_BOLT_GRADES[a.grade]
    At = METRIC_COARSE_AT[a.size] if a.At is None else a.At
    C = a.C
    Fi = a.preload_frac * At * g["Sp"]
    P = a.load / a.n_bolts  # external tensile load per bolt
    Pb = C * P
    sigma_b = (Pb + Fi) / At
    n_proof = (g["Sp"] * At - Fi) / Pb if Pb > 0 else math.inf
    n_sep = Fi / (P * (1 - C)) if P > 0 else math.inf
    out = {"inputs": vars(a) | {"At_mm2": At},
           "values": {"Fi_N": Fi, "P_per_bolt_N": P, "bolt_share_N": Pb,
                      "max_bolt_stress_MPa": sigma_b}}
    checks = [check("load factor vs proof (n_L)", n_proof, a.target),
              check("joint separation factor (n_0)", n_sep, a.target)]
    if a.fatigue:
        # Load cycles 0 -> P
        sa = C * P / (2 * At)
        si = Fi / At
        nf = g["Se"] * (g["Sut"] - si) / (sa * (g["Sut"] + g["Se"]))
        out["values"] |= {"sigma_a_MPa": sa, "sigma_i_MPa": si}
        checks.append(check("Goodman fatigue factor (n_f)", nf, a.target))
    out["checks"] = checks
    out["method"] = ("Shigley ch.8: Fi = k*At*Sp; n_L=(Sp*At-Fi)/(C*P); "
                     "n_0=Fi/(P(1-C)); fatigue Goodman with Se from ISO grade table")
    return out


# ---------------------------------------------------------------- shaft
def marin_Se(Sut, d, surface, reliability, kc=1.0, kd=1.0):
    Se_prime = 0.5 * Sut if Sut <= 1400 else 700.0
    aa, bb = SURFACE_FACTOR[surface]
    ka = aa * Sut ** bb
    if d <= 2.79:
        kb = 1.0
    elif d <= 51:
        kb = 1.24 * d ** -0.107
    else:
        kb = 1.51 * d ** -0.157
    ke = RELIABILITY_KE[reliability]
    return Se_prime * ka * kb * kc * kd * ke, dict(Se_prime=Se_prime, ka=ka,
                                                   kb=kb, kc=kc, kd=kd, ke=ke)


def shaft(a):
    d = a.d_guess
    for _ in range(50):
        Se, marin = marin_Se(a.Sut, d, a.surface, a.reliability)
        A = math.sqrt(4 * (a.Kf * a.Ma) ** 2 + 3 * (a.Kfs * a.Ta) ** 2)
        B = math.sqrt(4 * (a.Kf * a.Mm) ** 2 + 3 * (a.Kfs * a.Tm) ** 2)
        d_new = (16 * a.n / math.pi * (A / Se + B / a.Sut)) ** (1 / 3)
        if abs(d_new - d) < 1e-4:
            break
        d = d_new
    d = d_new
    # Yield check, first-cycle (von Mises, max stresses)
    sig = 32 * a.Kf * (a.Mm + a.Ma) / (math.pi * d ** 3)
    tau = 16 * a.Kfs * (a.Tm + a.Ta) / (math.pi * d ** 3)
    vm = math.sqrt(sig ** 2 + 3 * tau ** 2)
    ny = a.Sy / vm
    return {"inputs": vars(a),
            "values": {"Se_MPa": Se, "marin": marin, "d_required_mm": d},
            "checks": [check("Langer first-cycle yield (n_y)", ny, 1.0)],
            "method": "DE-Goodman (Shigley eq. 7-8), iterating size factor kb on d",
            "note": "Round d up to a standard size, then re-check Kf/Kfs at the "
                    "new fillet geometry."}


# ---------------------------------------------------------------- bearing
def bearing(a):
    exp = 3.0 if a.type == "ball" else 10 / 3
    P = a.P if a.P is not None else a.X * a.Fr + a.Y * a.Fa
    P *= a.af  # application factor
    a1 = ISO281_A1[a.reliability]
    out = {"inputs": vars(a), "values": {"P_equiv_N": P, "a1": a1,
                                        "life_exponent": exp}}
    if a.C is not None:
        L = a1 * (a.C / P) ** exp * 1e6
        hours = L / (60 * a.rpm)
        out["values"] |= {"life_revs": L, "life_hours": hours}
        if a.hours:
            out["checks"] = [check("life vs target hours", hours, a.hours)]
    if a.hours:
        Lreq = a.hours * 60 * a.rpm
        C_req = P * (Lreq / (a1 * 1e6)) ** (1 / exp)
        out["values"]["C_required_N"] = C_req
    out["method"] = "ISO 281 basic rating life L = a1 (C/P)^p x 1e6 rev"
    return out


# ---------------------------------------------------------------- spring
def spring(a):
    w = SPRING_WIRE[a.material]
    d, D = a.d, a.D
    C = D / d
    KB = (4 * C + 2) / (4 * C - 3)
    Sut = w["A"] / d ** w["m"]
    Ssy = a.ssy_frac * Sut
    k = d ** 4 * w["G"] / (8 * D ** 3 * a.Na)
    tau = KB * 8 * a.F * D / (math.pi * d ** 3)
    defl = a.F / k
    checks = [check("spring index 4<=C<=12 (lower bound)", C, 4),
              check("spring index (upper bound)", C, 12, higher_is_better=False),
              check("static shear safety (Ssy/tau)", Ssy / tau, a.target)]
    if a.Fsolid:
        tau_s = KB * 8 * a.Fsolid * D / (math.pi * d ** 3)
        checks.append(check("solid-height safety", Ssy / tau_s, 1.2))
    return {"inputs": vars(a),
            "values": {"C": C, "KB": KB, "Sut_MPa": Sut, "Ssy_MPa": Ssy,
                       "k_N_per_mm": k, "tau_MPa": tau, "deflection_mm": defl},
            "checks": checks,
            "method": "Helical compression, Bergstrasser factor; Sut=A/d^m (Shigley tab. 10-4)"}


# ---------------------------------------------------------------- weld
def weld(a):
    Sut = ELECTRODE_SUT[a.electrode]
    allow = 0.30 * Sut
    throat = 0.707 * a.h
    tau_primary = a.F / (throat * a.L)
    tau = tau_primary
    vals = {"throat_mm": throat, "tau_primary_MPa": tau_primary}
    if a.M:
        # Line-weld section modulus for two parallel lines in bending: Iu = b d^2/2 ... use
        # simple case: weld lines of total length L, depth d (user-supplied Su/unit)
        if a.Iu is None or a.c is None:
            sys.exit("bending requires --Iu (unit 2nd moment, mm^3) and --c (mm)")
        I = throat * a.Iu
        tau_b = a.M * a.c / I
        tau = math.hypot(tau_primary, tau_b)
        vals |= {"tau_bending_MPa": tau_b}
    vals["tau_combined_MPa"] = tau
    vals["allowable_MPa"] = allow
    return {"inputs": vars(a), "values": vals,
            "checks": [check("weld safety (allow/tau)", allow / tau, a.target)],
            "method": "Fillet weld on throat; AISC allowable 0.30 Sut(electrode)"}


# ---------------------------------------------------------------- gear
def gear(a):
    d = a.module * a.N
    Wt = 2 * a.T / d
    V = math.pi * d * a.rpm / 60000  # m/s
    Kv = {"cast": (3.05 + V) / 3.05, "cut": (6.1 + V) / 6.1,
          "hobbed": (3.56 + math.sqrt(V)) / 3.56,
          "ground": math.sqrt((5.56 + math.sqrt(V)) / 5.56)}[a.profile]
    Y = interp(LEWIS_Y_20DEG, a.N)
    sigma = Kv * Wt / (a.F * a.module * Y)
    return {"inputs": vars(a),
            "values": {"pitch_dia_mm": d, "Wt_N": Wt, "V_m_s": V, "Kv": Kv,
                       "Y": Y, "sigma_bending_MPa": sigma},
            "checks": [check("Lewis bending safety (Sy/sigma)", a.Sy / sigma, a.target),
                       check("face width 3p<=F<=5p (lower)", a.F, 3 * math.pi * a.module),
                       check("face width (upper)", a.F, 5 * math.pi * a.module, False)],
            "method": "Lewis equation with Barth velocity factor (screening only; "
                      "use AGMA 2001 / ISO 6336 for final design)"}


# ---------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bolt", help="preloaded bolted joint in tension")
    b.add_argument("--size", default="M10", choices=METRIC_COARSE_AT)
    b.add_argument("--At", type=float, help="override tensile stress area mm^2")
    b.add_argument("--grade", default="8.8", choices=ISO_BOLT_GRADES)
    b.add_argument("--load", type=float, required=True, help="total external tensile load N")
    b.add_argument("--n-bolts", dest="n_bolts", type=int, default=1)
    b.add_argument("--C", type=float, default=0.25, help="joint stiffness constant kb/(kb+km)")
    b.add_argument("--preload-frac", dest="preload_frac", type=float, default=0.75,
                   help="0.75 reusable, 0.90 permanent")
    b.add_argument("--fatigue", action="store_true", help="load cycles 0->P")
    b.add_argument("--target", type=float, default=1.5)
    b.set_defaults(fn=bolt)

    s = sub.add_parser("shaft", help="shaft diameter, DE-Goodman fatigue")
    for k in ("Ma", "Mm", "Ta", "Tm"):
        s.add_argument(f"--{k}", type=float, default=0.0, help="N*mm")
    s.add_argument("--Kf", type=float, default=1.0)
    s.add_argument("--Kfs", type=float, default=1.0)
    s.add_argument("--Sut", type=float, required=True)
    s.add_argument("--Sy", type=float, required=True)
    s.add_argument("--surface", default="machined", choices=SURFACE_FACTOR)
    s.add_argument("--reliability", type=float, default=0.99, choices=RELIABILITY_KE)
    s.add_argument("--n", type=float, default=1.5)
    s.add_argument("--d-guess", dest="d_guess", type=float, default=25.0)
    s.set_defaults(fn=shaft)

    br = sub.add_parser("bearing", help="rolling bearing L10 life / required C")
    br.add_argument("--type", choices=["ball", "roller"], default="ball")
    br.add_argument("--P", type=float, help="equivalent load N (else from Fr/Fa/X/Y)")
    br.add_argument("--Fr", type=float, default=0.0)
    br.add_argument("--Fa", type=float, default=0.0)
    br.add_argument("--X", type=float, default=1.0)
    br.add_argument("--Y", type=float, default=0.0)
    br.add_argument("--af", type=float, default=1.0, help="application factor")
    br.add_argument("--C", type=float, help="catalog dynamic rating N")
    br.add_argument("--rpm", type=float, required=True)
    br.add_argument("--hours", type=float, help="target life hours")
    br.add_argument("--reliability", type=float, default=0.90, choices=ISO281_A1)
    br.set_defaults(fn=bearing)

    sp = sub.add_parser("spring", help="helical compression spring")
    sp.add_argument("--d", type=float, required=True, help="wire dia mm")
    sp.add_argument("--D", type=float, required=True, help="mean coil dia mm")
    sp.add_argument("--Na", type=float, required=True, help="active coils")
    sp.add_argument("--F", type=float, required=True, help="working force N")
    sp.add_argument("--Fsolid", type=float, help="force at solid height N")
    sp.add_argument("--material", default="music-wire", choices=SPRING_WIRE)
    sp.add_argument("--ssy-frac", dest="ssy_frac", type=float, default=0.45)
    sp.add_argument("--target", type=float, default=1.2)
    sp.set_defaults(fn=spring)

    w = sub.add_parser("weld", help="fillet weld, primary shear (+ optional bending)")
    w.add_argument("--F", type=float, required=True, help="shear force N")
    w.add_argument("--h", type=float, required=True, help="leg size mm")
    w.add_argument("--L", type=float, required=True, help="total weld length mm")
    w.add_argument("--M", type=float, help="bending moment N*mm")
    w.add_argument("--Iu", type=float, help="unit second moment of weld group mm^3")
    w.add_argument("--c", type=float, help="distance to extreme weld mm")
    w.add_argument("--electrode", default="E70", choices=ELECTRODE_SUT)
    w.add_argument("--target", type=float, default=1.0)
    w.set_defaults(fn=weld)

    g = sub.add_parser("gear", help="spur gear Lewis bending screen")
    g.add_argument("--module", type=float, required=True, help="mm")
    g.add_argument("--N", type=int, required=True, help="teeth")
    g.add_argument("--F", type=float, required=True, help="face width mm")
    g.add_argument("--T", type=float, required=True, help="torque N*mm")
    g.add_argument("--rpm", type=float, required=True)
    g.add_argument("--Sy", type=float, required=True)
    g.add_argument("--profile", default="cut", choices=["cast", "cut", "hobbed", "ground"])
    g.add_argument("--target", type=float, default=2.0)
    g.set_defaults(fn=gear)

    a = p.parse_args()
    fn = a.fn
    del a.fn, a.cmd
    res = fn(a)
    print(json.dumps(res, indent=2, default=lambda x: round(x, 4) if isinstance(x, float) else str(x)))


if __name__ == "__main__":
    main()
