#!/usr/bin/env python3
"""3D-printed hobby high-power rocket design checks, after RocketSmith (Pak, Barkley, Loghmani, Baich, Pamal,
Barati Farimani, arXiv:2606.00097, 2026; code: github.com/ppak10/RocketSmith).

Scope: airframe, nose cone and fin design for COMMERCIAL, CERTIFIED motors (NAR/TRA), stability (Barrowman CP vs
CG), 1-D flight simulation, recovery descent rate, printed-part mass and printable CAD. Out of scope, by design:
motor, propellant, igniter or ejection-charge design/sizing -- follow the motor manufacturer, your certification
level and the Range Safety Officer.

  motors     python rocket.py motors                                     built-in certified-motor summaries
  check      python rocket.py check design.json [--motor H100W | --eng file.eng] [--cd 0.55 --rail 1.83]
  simulate   python rocket.py simulate design.json [...] [--plot flight.png]
  cad        python rocket.py cad design.json --out parts/              nose cone + fin can STEP/STL (CadQuery)
  calibrate  python rocket.py calibrate design.json --weighed nose=412,fincan=1265 [--cg 520]   measured masses -> re-check

design.json (mm, g):
{"name": "...", "diameter_mm": 101.6,
 "nose": {"shape": "ogive|conical|vonkarman|elliptical", "length_mm": 300, "wall_mm": 2.4, "shoulder_mm": 50},
 "body": [{"name": "fincan", "length_mm": 550, "wall_mm": 6.35}],
 "fins": {"count": 3, "root_mm": 150, "tip_mm": 60, "span_mm": 90, "sweep_mm": 70, "thickness_mm": 5, "from_aft_mm": 10},
 "motor": "H100W", "motor_mount_mm": 38,
 "masses": [{"name": "parachute 36in", "mass_g": 150, "x_mm": 450}, ...],     # x measured from the nose tip
 "print": {"material": "PETG", "infill": 0.15, "walls": 4, "line_mm": 0.45},
 "recovery": {"parachute_diameter_in": 36, "cd": 1.5}}
"""
import argparse
import json
import math
import os
import sys

import numpy as np

G0 = 9.80665
DENSITY = {"PLA": 1240, "PETG": 1270, "ABS": 1040, "ASA": 1070, "PA-CF": 1150, "PC": 1200}   # kg/m3 filament
# Certified-motor summaries (manufacturer/TRA certification data via thrustcurve.org): diameter mm, length mm,
# total mass g, propellant mass g, total impulse Ns, average thrust N, max thrust N, burn time s.
# For real work download the RASP .eng file from thrustcurve.org and pass --eng.
MOTORS = {
    "H100W": (38, 153, 261, 121, 226.8, 97.7, 137.8, 2.3),
    "J425R": (38, 356, 631, 364, 680.3, 417.6, 473.3, 1.6),
}
CLASSES = [("A", 2.5), ("B", 5), ("C", 10), ("D", 20), ("E", 40), ("F", 80), ("G", 160), ("H", 320), ("I", 640),
           ("J", 1280), ("K", 2560), ("L", 5120), ("M", 10240), ("N", 20480), ("O", 40960)]
CERT = {"H": "L1", "I": "L1", "J": "L2", "K": "L2", "L": "L2", "M": "L3", "N": "L3", "O": "L3"}
CLASS2_LIMIT = 40960.0   # N*s, upper bound of Class 2 (high power) rocketry


# ------------------------------------------------------------------ motors
class Motor:
    def __init__(self, name, d_mm, L_mm, m_tot_g, m_prop_g, t, F):
        self.name, self.d, self.L, self.m_tot, self.m_prop = name, d_mm, L_mm, m_tot_g / 1000, m_prop_g / 1000
        self.t, self.F = np.asarray(t, float), np.asarray(F, float)
        self.I = float(np.trapezoid(self.F, self.t))
        self.burn = float(self.t[-1])

    def thrust(self, t):
        return float(np.interp(t, self.t, self.F, left=0.0, right=0.0))

    def mass(self, t):
        if t <= 0:
            return self.m_tot
        if t >= self.burn:
            return self.m_tot - self.m_prop
        tt = np.append(self.t[self.t < t], t); ff = np.append(self.F[self.t < t], self.thrust(t))
        used = float(np.trapezoid(ff, tt))
        return self.m_tot - self.m_prop * min(1.0, used / self.I)

    def letter(self):
        for c, lim in CLASSES:
            if self.I <= lim:
                return c
        return ">O"


def motor_from_summary(name):
    d, L, mt, mp, I, Favg, Fmax, tb = MOTORS[name]
    # Shape: quick rise to Fmax, then decline; scaled so the integral equals the certified total impulse.
    t = np.array([0, 0.05, 0.15, 0.5 * tb, 0.9 * tb, tb])
    f = np.array([0, Fmax, 0.95 * Fmax, Favg, 0.7 * Favg, 0])
    f *= I / np.trapezoid(f, t)
    return Motor(name + " (shape from cert. summary)", d, L, mt, mp, t, f)


def motor_from_eng(path):
    """RASP .eng: header 'NAME DIA LEN DELAYS PROPMASS(kg) TOTMASS(kg) MFR' then 'time thrust' lines."""
    lines = [l.strip() for l in open(path) if l.strip() and not l.strip().startswith(";")]
    h = lines[0].split()
    pts = [tuple(map(float, l.split()[:2])) for l in lines[1:]]
    t, F = zip(*pts)
    t, F = (0.0,) + t, (0.0,) + F
    return Motor(h[0], float(h[1]), float(h[2]), float(h[5]) * 1000, float(h[4]) * 1000, t, F)


# ------------------------------------------------------------------ geometry, mass, CG
def nose_profile(shape, L, R, n=200):
    x = np.linspace(0, L, n)
    if shape == "conical":
        r = R * x / L
    elif shape == "elliptical":
        r = R * np.sqrt(np.clip(1 - ((L - x) / L) ** 2, 0, 1))
    elif shape == "vonkarman":
        th = np.arccos(1 - 2 * x / L)
        r = R / math.sqrt(math.pi) * np.sqrt(th - np.sin(2 * th) / 2)
    else:  # tangent ogive
        rho = (R ** 2 + L ** 2) / (2 * R)
        r = np.sqrt(np.clip(rho ** 2 - (L - x) ** 2, 0, None)) + R - rho
    return x, np.clip(r, 0, None)


def printed_density(thick_mm, pr):
    """FDM effective density: perimeters (2 x walls x line width) are solid, the rest is infill."""
    rho = DENSITY.get(pr.get("material", "PETG"), 1250)
    solid = min(1.0, 2 * pr.get("walls", 4) * pr.get("line_mm", 0.45) / max(thick_mm, 1e-9))
    return rho * (solid + pr.get("infill", 0.15) * (1 - solid))


def components(des):
    """Masses (kg) and centroid positions (m from nose tip) of printed structure, motor and listed masses."""
    D = des["diameter_mm"] / 1000; R = D / 2
    pr = des.get("print", {})
    comps = []
    n = des["nose"]; Ln = n["length_mm"] / 1000; w = n["wall_mm"] / 1000
    x, r = nose_profile(n.get("shape", "ogive"), Ln, R)
    ri = np.clip(r - w, 0, None)
    dV = math.pi * (r ** 2 - ri ** 2)
    V = float(np.trapezoid(dV, x)); xc = float(np.trapezoid(dV * x, x) / V)
    sh = n.get("shoulder_mm", 0) / 1000
    if sh:
        Vs = math.pi * ((R - w) ** 2 - (R - 2 * w) ** 2) * sh
        xc = (V * xc + Vs * (Ln + sh / 2)) / (V + Vs); V += Vs
    comps.append({"name": "nose cone (printed)", "m": V * printed_density(n["wall_mm"], pr), "x": xc})
    pos = Ln
    for b in des["body"]:
        Lb, wb = b["length_mm"] / 1000, b["wall_mm"] / 1000
        Vb = math.pi * (R ** 2 - (R - wb) ** 2) * Lb
        comps.append({"name": f"{b['name']} tube (printed)", "m": Vb * printed_density(b["wall_mm"], pr), "x": pos + Lb / 2})
        pos += Lb
    L_total = pos
    f = des["fins"]
    a, bt, s, m_sw, t = (f[k] / 1000 for k in ("root_mm", "tip_mm", "span_mm", "sweep_mm", "thickness_mm"))
    area = 0.5 * (a + bt) * s
    xr = L_total - f.get("from_aft_mm", 0) / 1000 - a                      # root leading edge from nose tip
    xcf = xr + (a ** 2 + a * bt + bt ** 2 + m_sw * (a + 2 * bt)) / (3 * (a + bt))     # trapezoid area centroid (chordwise)
    comps.append({"name": f"{f['count']} fins (printed)", "m": f["count"] * area * t * printed_density(f["thickness_mm"], pr), "x": xcf})
    mm = des.get("motor_mount_mm")
    if mm:   # printed motor tube region along the motor length
        Lm = des.get("_motor_len_mm", 300) / 1000; wmt = 0.003
        Vm = math.pi * ((mm / 2000 + wmt) ** 2 - (mm / 2000) ** 2) * Lm
        comps.append({"name": "motor mount (printed)", "m": Vm * printed_density(3, pr), "x": L_total - Lm / 2})
    for e in des.get("masses", []):
        comps.append({"name": e["name"], "m": e["mass_g"] / 1000, "x": e["x_mm"] / 1000})
    for c in comps:   # measured overrides
        ov = des.get("overrides", {}).get(c["name"].split(" (")[0].split(" ")[0])
        if ov:
            c["m"] = ov / 1000; c["name"] += " [weighed]"
    return comps, L_total


def cg(comps, motor=None, L_total=None, t=0.0):
    m = sum(c["m"] for c in comps); mx = sum(c["m"] * c["x"] for c in comps)
    if motor:
        mm = motor.mass(t); xm = L_total - motor.L / 2000
        m += mm; mx += mm * xm
    return mx / m, m


# ------------------------------------------------------------------ Barrowman CP (subsonic)
def barrowman(des, L_total):
    D = des["diameter_mm"] / 1000; R = D / 2
    n = des["nose"]; Ln = n["length_mm"] / 1000
    xn = {"conical": 2 / 3, "ogive": 0.466, "vonkarman": 0.5, "elliptical": 0.333}.get(n.get("shape", "ogive"), 0.466) * Ln
    CN_n = 2.0
    f = des["fins"]; N = f["count"]
    a, b, s, m_sw = (f[k] / 1000 for k in ("root_mm", "tip_mm", "span_mm", "sweep_mm"))
    lm = math.sqrt(s ** 2 + (m_sw + b / 2 - a / 2) ** 2)                    # mid-chord line length
    CN_f = (4 * N * (s / D) ** 2) / (1 + math.sqrt(1 + (2 * lm / (a + b)) ** 2))
    CN_f *= 1 + R / (s + R)                                                 # fin-body interference
    xr = L_total - f.get("from_aft_mm", 0) / 1000 - a
    xf = xr + m_sw * (a + 2 * b) / (3 * (a + b)) + (1 / 6) * (a + b - a * b / (a + b))
    CN = CN_n + CN_f
    return {"cp_m": (CN_n * xn + CN_f * xf) / CN, "CN_alpha": CN, "nose": {"CN": CN_n, "x_m": xn}, "fins": {"CN": CN_f, "x_m": xf}}


# ------------------------------------------------------------------ flight
def isa_rho(h):
    T = 288.15 - 0.0065 * h
    return 1.225 * (T / 288.15) ** 4.256


def simulate(des, motor, cd=0.55, rail_m=1.83, dt=0.005, wind_ms=0.0):
    comps, L = components(des)
    m_dry = sum(c["m"] for c in comps)
    A = math.pi * (des["diameter_mm"] / 2000) ** 2
    t, h, v = 0.0, 0.0, 0.0
    hist = []
    vrail = None; amax = 0.0; vmax = 0.0
    while True:
        m = m_dry + motor.mass(t)
        F = motor.thrust(t)
        Dg = 0.5 * isa_rho(max(h, 0)) * v * abs(v) * cd * A
        a_ = (F - Dg) / m - G0
        if h <= 0 and a_ < 0 and t < motor.burn:
            a_ = 0.0                                                        # still sitting on the pad
        v += a_ * dt; h += v * dt; t += dt
        amax = max(amax, a_); vmax = max(vmax, v)
        if vrail is None and h >= rail_m:
            vrail = v
        hist.append((t, h, v, a_))
        if t > motor.burn and v <= 0:
            break
        if t > 120:
            break
    H = np.array(hist)
    rec = des.get("recovery", {})
    Dp = rec.get("parachute_diameter_in", 36) * 0.0254
    m_land = m_dry + motor.mass(1e9)
    v_desc = math.sqrt(2 * m_land * G0 / (1.225 * rec.get("cd", 1.5) * math.pi * Dp ** 2 / 4))
    return {"apogee_m": round(float(H[:, 1].max()), 1), "time_to_apogee_s": round(float(H[H[:, 1].argmax(), 0]), 2),
            "max_velocity_m_s": round(vmax, 1), "max_mach": round(vmax / 340.3, 3), "max_accel_m_s2": round(amax, 1),
            "rail_exit_velocity_m_s": None if vrail is None else round(vrail, 1),
            "liftoff_mass_kg": round(m_dry + motor.m_tot, 3), "thrust_to_weight": round((motor.I / motor.burn) / ((m_dry + motor.m_tot) * G0), 2),
            "descent_rate_m_s": round(v_desc, 1), "cd_used": cd, "_hist": H}


def report(des, motor, cd=0.55, rail_m=1.83):
    des = dict(des); des["_motor_len_mm"] = motor.L
    comps, L = components(des)
    cp = barrowman(des, L)
    D = des["diameter_mm"] / 1000
    x_cg0, m0 = cg(comps, motor, L, 0.0)
    x_cgb, mb = cg(comps, motor, L, 1e9)
    if des.get("overrides", {}).get("cg_mm"):
        x_cg0 = des["overrides"]["cg_mm"] / 1000
    st0, stb = (cp["cp_m"] - x_cg0) / D, (cp["cp_m"] - x_cgb) / D
    fl = simulate(des, motor, cd, rail_m)
    letter = motor.letter()
    checks = []
    def chk(name, ok, detail, level="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "severity": "ok" if ok else level})
    chk("stability at liftoff 1.0-2.0 cal", 1.0 <= st0 <= 2.0, f"{st0:.2f} cal (paper target 1.00-1.25; flown 1.26-1.63)",
        "error" if st0 < 1.0 else "warning")
    chk("stability at burnout >= liftoff", stb >= st0 - 0.05, f"{stb:.2f} cal (CG moves forward as propellant burns)", "warning")
    chk("rail exit velocity >= 15 m/s", (fl["rail_exit_velocity_m_s"] or 0) >= 15, f"{fl['rail_exit_velocity_m_s']} m/s on a {rail_m} m rail", "error")
    chk("average thrust-to-weight >= 5", fl["thrust_to_weight"] >= 5, f"{fl['thrust_to_weight']}", "warning")
    chk("subsonic (Barrowman, printed fins)", fl["max_mach"] < 0.6, f"Mach {fl['max_mach']}", "warning")
    chk("descent rate 4.5-7 m/s under main", 4.5 <= fl["descent_rate_m_s"] <= 7.0, f"{fl['descent_rate_m_s']} m/s", "warning")
    chk("total impulse within Class 2 (<= 40,960 N*s)", motor.I <= CLASS2_LIMIT, f"{motor.I:.0f} N*s ({letter})", "error")
    mount = des.get("motor_mount_mm")
    chk("motor fits the mount", mount is None or abs(mount - motor.d) < 0.6, f"mount {mount} mm vs motor {motor.d} mm", "error")
    return {"rocket": des.get("name"), "motor": {"name": motor.name, "class": letter, "total_impulse_Ns": round(motor.I, 1),
                                                 "certification_needed": CERT.get(letter, "none (low power)"), "burn_s": motor.burn},
            "length_mm": round(L * 1000, 1), "diameter_mm": des["diameter_mm"],
            "mass_g": {"liftoff": round(m0 * 1000, 1), "burnout": round(mb * 1000, 1),
                       "components": [{"name": c["name"], "g": round(c["m"] * 1000, 1), "x_mm": round(c["x"] * 1000)} for c in comps]},
            "cg_mm": {"liftoff": round(x_cg0 * 1000, 1), "burnout": round(x_cgb * 1000, 1)},
            "cp_mm": round(cp["cp_m"] * 1000, 1), "stability_cal": {"liftoff": round(st0, 2), "burnout": round(stb, 2)},
            "flight": {k: v for k, v in fl.items() if not k.startswith("_")}, "checks": checks,
            "go_for_review": all(c["ok"] or c["severity"] == "warning" for c in checks),
            "reminder": "Design check only. Motor prep, ejection charges and flight approval are for the certified flyer and the RSO."}, fl["_hist"]


# ------------------------------------------------------------------ CAD (CadQuery)
def cad(des, out, motor=None):
    import cadquery as cq
    os.makedirs(out, exist_ok=True)
    D = des["diameter_mm"]; R = D / 2
    n = des["nose"]; Ln = n["length_mm"]; w = n["wall_mm"]; sh = n.get("shoulder_mm", 50)
    x, r = nose_profile(n.get("shape", "ogive"), Ln, R, 60)
    outer = [(float(rr), float(xx)) for xx, rr in zip(x, r)]
    inner = [(float(max(rr - w, 0.01)), float(xx)) for xx, rr in zip(x, r) if rr - w > 0.5]
    pts = [(0.0, 0.0)] + outer[1:] + [(R - w, Ln), (R - w, Ln + sh), (R - 2 * w, Ln + sh)] + \
          [(R - 2 * w, inner[-1][1])] + inner[::-1] + [(0.0, inner[0][1])]
    nose = cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
    files = {}
    for name, solid in [("nose", nose)]:
        p = os.path.join(out, f"{name}.step"); cq.exporters.export(solid, p); cq.exporters.export(solid, p.replace(".step", ".stl"))
        files[name] = p
    body = des["body"][-1]; Lb = body["length_mm"]; wb = body["wall_mm"]
    tube = cq.Workplane("XY").circle(R).circle(R - wb).extrude(Lb)
    f = des["fins"]; a, b, s, m_sw, t = (f[k] for k in ("root_mm", "tip_mm", "span_mm", "sweep_mm", "thickness_mm"))
    z0 = f.get("from_aft_mm", 0)
    fin = (cq.Workplane("XZ").polyline([(R - wb / 2, z0), (R - wb / 2, z0 + a), (R + s, z0 + a - m_sw), (R + s, z0 + a - m_sw - b)])
           .close().extrude(t / 2, both=True))
    for k in range(f["count"]):
        tube = tube.union(fin.rotate((0, 0, 0), (0, 0, 1), 360 * k / f["count"]))
    mm = des.get("motor_mount_mm")
    if mm:   # integrated motor mount: inner tube + two centring webs (thickened, consolidated as in the paper's HP3)
        Lm = (motor.L if motor else 300) + 10
        mt = cq.Workplane("XY").circle(mm / 2 + 3).circle(mm / 2 + 0.3).extrude(Lm)
        for zc in (5, Lm - 8):
            ring = cq.Workplane("XY").workplane(offset=zc).circle(R - wb + 0.1).circle(mm / 2 + 2).extrude(3)
            mt = mt.union(ring)
        tube = tube.union(mt)
    p = os.path.join(out, "fincan.step"); cq.exporters.export(tube, p); cq.exporters.export(tube, p.replace(".step", ".stl"))
    files["fincan"] = p
    vols = {k: cq.importers.importStep(v).val().Volume() for k, v in files.items()}
    pr = des.get("print", {})
    est = {k: round(v * 1e-9 * printed_density(des["nose"]["wall_mm"] if k == "nose" else des["body"][-1]["wall_mm"], pr) * 1000, 1)
           for k, v in vols.items()}
    return {"files": files, "solid_volume_cm3": {k: round(v / 1000, 1) for k, v in vols.items()},
            "printed_mass_estimate_g": est, "note": "Slice with your real profile (PrusaSlicer reports filament mass) and weigh "
                                                   "the printed parts; feed both back with `calibrate`."}


def size_fins(des, motor, target=1.25, lever="span_mm", lo=0.2, hi=3.0, cd=0.55):
    """Stability-analysis loop (RocketSmith skill): scale one fin dimension until liftoff stability hits the target.
    Bigger fins also add printed mass aft, which the loop accounts for."""
    base = des["fins"][lever]
    if lever == "span_mm":
        hi = max(hi, 2.0 * des["diameter_mm"] / base)        # allow spans up to two body diameters
    def st(k):
        d = json.loads(json.dumps(des)); d["fins"][lever] = base * k
        r, _ = report(d, motor, cd)
        return r["stability_cal"]["liftoff"], d
    s_lo, _ = st(lo); s_hi, _ = st(hi)
    if not (s_lo <= target <= s_hi):
        return {"ok": False, "detail": f"stability spans {s_lo:.2f}-{s_hi:.2f} cal for {lever} x{lo}-{hi}; change another lever "
                                       "(nose weight, longer airframe, fin root chord)"}
    for _ in range(40):
        mid = 0.5 * (lo + hi); s_mid, d = st(mid)
        if s_mid < target:
            lo = mid
        else:
            hi = mid
    s_fin, d = st(hi)
    return {"ok": True, "lever": lever, "from_mm": base, "to_mm": round(d["fins"][lever], 1), "stability_cal": s_fin, "design": d}


def fit_cd(des, motor, apogee_m, lo=0.2, hi=2.0):
    """Drag coefficient that reproduces a measured apogee (printed surfaces, rail buttons and weathercocking all show up
    as extra drag). Use it for the next flight's prediction on the same airframe."""
    d = dict(des); d["_motor_len_mm"] = motor.L
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if simulate(d, motor, mid)["apogee_m"] > apogee_m:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 3)


def load(path):
    return json.load(open(path))


def get_motor(des, name=None, eng=None):
    if eng:
        return motor_from_eng(eng)
    nm = name or des.get("motor")
    if nm in MOTORS:
        return motor_from_summary(nm)
    if nm and os.path.exists(nm):
        return motor_from_eng(nm)
    raise SystemExit(f"motor '{nm}': pass --eng with a RASP .eng file from thrustcurve.org (certified commercial motors only)")


def plot(hist, out, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.5))
    ax[0].plot(hist[:, 0], hist[:, 1]); ax[0].set_xlabel("t (s)"); ax[0].set_ylabel("altitude (m)")
    ax[1].plot(hist[:, 0], hist[:, 2], label="v (m/s)"); ax[1].plot(hist[:, 0], hist[:, 3], label="a (m/s²)")
    ax[1].set_xlabel("t (s)"); ax[1].legend(); fig.suptitle(title, fontsize=9); fig.tight_layout(); fig.savefig(out, dpi=130)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("motors")
    for name in ("check", "simulate", "calibrate", "cad", "fins"):
        s = sub.add_parser(name); s.add_argument("design"); s.add_argument("--motor"); s.add_argument("--eng")
        s.add_argument("--cd", type=float, default=0.55); s.add_argument("--rail", type=float, default=1.83)
        if name == "simulate":
            s.add_argument("--plot")
        if name == "cad":
            s.add_argument("--out", required=True)
        if name == "fins":
            s.add_argument("--target", type=float, default=1.25); s.add_argument("--lever", default="span_mm",
                                                                                choices=["span_mm", "root_mm", "tip_mm"])
            s.add_argument("--out", help="write the resized design JSON")
        if name == "calibrate":
            s.add_argument("--weighed", required=True, help="part=grams,... e.g. nose=412,fincan=1265")
            s.add_argument("--cg", type=float, help="measured liftoff CG from nose tip, mm (motor installed)")
            s.add_argument("--apogee", type=float, help="altimeter apogee (m) from a flight on this motor -> fitted drag coefficient")
    a = ap.parse_args()
    if a.cmd == "motors":
        r = {k: dict(zip(["diameter_mm", "length_mm", "total_g", "propellant_g", "total_impulse_Ns", "avg_thrust_N", "max_thrust_N", "burn_s"], v))
             for k, v in MOTORS.items()}
        r["_note"] = "Summaries only; for flight decisions use the manufacturer's RASP .eng file (thrustcurve.org) with --eng."
    else:
        des = load(a.design); m = get_motor(des, a.motor, a.eng)
        if a.cmd == "calibrate":
            des.setdefault("overrides", {}).update({k: float(v) for k, v in (kv.split("=") for kv in a.weighed.split(",") if kv)})
            if a.cg:
                des["overrides"]["cg_mm"] = a.cg
            if a.apogee:
                a.cd = fit_cd(des, m, a.apogee)
        if a.cmd == "cad":
            r = cad(des, a.out, m)
        elif a.cmd == "fins":
            r = size_fins(des, m, a.target, a.lever, cd=a.cd)
            if r.get("ok") and a.out:
                json.dump(r["design"], open(a.out, "w"), indent=1)
            r.pop("design", None)
        else:
            r, hist = report(des, m, a.cd, a.rail)
            if a.cmd == "simulate" and a.plot:
                r["plot"] = plot(hist, a.plot, f"{des.get('name')} on {m.name}: apogee {r['flight']['apogee_m']} m")
            if a.cmd == "calibrate":
                r["fitted_cd"] = a.cd if a.apogee else None
            if a.cmd == "check":
                r = {k: r[k] for k in ("rocket", "motor", "mass_g", "cg_mm", "cp_mm", "stability_cal", "checks", "go_for_review", "reminder")}
    print(json.dumps(r, indent=1, default=float))


if __name__ == "__main__":
    main()
