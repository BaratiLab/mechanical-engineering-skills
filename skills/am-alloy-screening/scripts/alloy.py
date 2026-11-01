#!/usr/bin/env python3
"""Screen alloys for laser powder bed fusion: composition -> thermophysical properties -> melt pool ->
lack-of-fusion process map -> ranked recommendation. After Pak, Chandrasekhar & Barati Farimani,
"Agentic additive manufacturing alloy evaluation", Additive Manufacturing Letters 17 (2026) 100355
(code: github.com/BaratiLab/Agentic-Additive-Manufacturing-Alloy-Evaluation, MIT).

  known       python alloy.py known                                   list the built-in alloy table
  compose     python alloy.py compose "Fe-18Cr-10Ni-2Mo" | --json '{"Fe":0.7,...}' [--atomic]   -> mass fractions
  properties  python alloy.py properties --alloy SS316L | --comp comp.json [--thermocalc] --out mat.json
  check       python alloy.py check mat.json                            unit sanity (catches molar Cp, g/m3 density)
  meltpool    python alloy.py meltpool --material mat.json --power 200 --velocity 800 [--preheat 293]
  map         python alloy.py map --material mat.json --hatch 50 --layer 30 [--power 100:1000:100 --velocity 100:1000:100] --out map.png
  rank        python alloy.py rank --materials a.json b.json c.json --hatch 50 --layer 30 [--out ranking.png]

Units: SI in material files (kg/m3, J/kg/K, W/m/K, K); power W, velocity mm/s, hatch/layer/melt pool um.
"""
import argparse
import json
import math
import os
import re
import sys

import numpy as np

# ------------------------------------------------------------------ element data (molar mass g/mol, density kg/m3,
# Cp J/kg/K at 298 K, k W/m/K at 298 K, melting point K, electrical resistivity at 298 K in ohm*m)
ELEMENTS = {
    "Al": (26.982, 2700, 897, 237, 933, 2.65e-8), "Ti": (47.867, 4506, 523, 21.9, 1941, 4.2e-7),
    "V": (50.942, 6110, 489, 30.7, 2183, 1.97e-7), "Cr": (51.996, 7190, 449, 93.9, 2180, 1.25e-7),
    "Mn": (54.938, 7210, 479, 7.8, 1519, 1.44e-6), "Fe": (55.845, 7874, 449, 80.4, 1811, 9.7e-8),
    "Co": (58.933, 8900, 421, 100, 1768, 6.2e-8), "Ni": (58.693, 8908, 444, 90.9, 1728, 6.9e-8),
    "Cu": (63.546, 8960, 385, 401, 1358, 1.68e-8), "Zn": (65.38, 7140, 388, 116, 693, 5.9e-8),
    "Mg": (24.305, 1738, 1023, 156, 923, 4.4e-8), "Si": (28.085, 2329, 705, 149, 1687, 1e-3),
    "Zr": (91.224, 6520, 278, 22.6, 2128, 4.2e-7), "Nb": (92.906, 8570, 265, 53.7, 2750, 1.52e-7),
    "Mo": (95.95, 10280, 251, 138, 2896, 5.3e-8), "Ta": (180.95, 16690, 140, 57.5, 3290, 1.31e-7),
    "W": (183.84, 19250, 132, 173, 3695, 5.3e-8), "Sn": (118.71, 7310, 228, 66.8, 505, 1.15e-7),
    "C": (12.011, 2260, 709, 0, 3800, 1e-5), "B": (10.81, 2340, 1026, 27, 2349, 1e4),
    "Hf": (178.49, 13310, 144, 23, 2506, 3.3e-7), "Y": (88.906, 4472, 298, 17.2, 1799, 5.96e-7),
    "Sc": (44.956, 2985, 568, 15.8, 1814, 5.5e-7), "Re": (186.21, 21020, 137, 48, 3459, 1.93e-7),
    "Ag": (107.87, 10490, 235, 429, 1235, 1.59e-8), "N": (14.007, 1.25, 1040, 0, 63, 1e10),
    "O": (15.999, 1.43, 918, 0, 54, 1e10), "P": (30.974, 1823, 769, 0, 317, 1e10), "S": (32.06, 2070, 710, 0, 388, 1e10),
}

# Built-in alloys: nominal mass fractions and nominal room-temperature properties (typical datasheet / handbook
# values; solidus/liquidus in K). Verify against your powder supplier's data before relying on them.
KNOWN = {
    "SS316L": ({"Fe": 0.6736, "Cr": 0.1762, "Ni": 0.1244, "Mo": 0.0259}, dict(density=7910, cp=455, k=8.9, solidus=1683.7, liquidus=1710.3, absorptivity=0.35)),
    "AlSi10Mg": ({"Al": 0.8958, "Si": 0.1007, "Mg": 0.0035}, dict(density=2680, cp=896, k=121, solidus=848, liquidus=888, absorptivity=0.35)),
    "Ti-6Al-4V": ({"Ti": 0.90, "Al": 0.06, "V": 0.04}, dict(density=4430, cp=526, k=6.7, solidus=1878, liquidus=1928, absorptivity=0.40)),
    "IN718": ({"Ni": 0.5325, "Cr": 0.19, "Fe": 0.18, "Nb": 0.051, "Mo": 0.03, "Ti": 0.009, "Al": 0.0065}, dict(density=8190, cp=435, k=11.4, solidus=1533, liquidus=1609, absorptivity=0.40)),
    "IN625": ({"Ni": 0.615, "Cr": 0.215, "Mo": 0.09, "Nb": 0.0365, "Fe": 0.04, "Al": 0.002, "Ti": 0.002}, dict(density=8440, cp=410, k=9.8, solidus=1563, liquidus=1623, absorptivity=0.40)),
    "HastelloyX": ({"Ni": 0.455, "Cr": 0.2175, "Fe": 0.185, "Mo": 0.09, "Co": 0.015, "Mn": 0.01, "Si": 0.01, "W": 0.006, "Cu": 0.005, "Al": 0.005, "Ti": 0.0015}, dict(density=8243, cp=435, k=11.2, solidus=1540, liquidus=1625, absorptivity=0.35)),
    "SS17-4PH": ({"Fe": 0.746, "Cr": 0.16, "Ni": 0.045, "Cu": 0.04, "Nb": 0.003, "Mn": 0.003, "Si": 0.003}, dict(density=7780, cp=460, k=18.3, solidus=1677, liquidus=1713, absorptivity=0.35)),
    "H13": ({"Fe": 0.9075, "Cr": 0.0509, "Mo": 0.014, "V": 0.01, "Si": 0.01, "Mn": 0.004, "C": 0.0037}, dict(density=7800, cp=460, k=24.3, solidus=1588, liquidus=1727, absorptivity=0.40)),
    "MonelK500": ({"Ni": 0.7035, "Cu": 0.27, "Al": 0.023, "Ti": 0.0035}, dict(density=8440, cp=419, k=17.5, solidus=1588, liquidus=1623, absorptivity=0.30)),
    "Al7050": ({"Al": 0.8907, "Zn": 0.062, "Cu": 0.023, "Mg": 0.023, "Zr": 0.0012}, dict(density=2830, cp=860, k=157, solidus=761, liquidus=908, absorptivity=0.30)),
    "CuSn10": ({"Cu": 0.90, "Sn": 0.10}, dict(density=8780, cp=380, k=50, solidus=1124, liquidus=1270, absorptivity=0.30)),
    "Cu": ({"Cu": 1.0}, dict(density=8960, cp=385, k=401, solidus=1356, liquidus=1358, absorptivity=0.15)),
    "W": ({"W": 1.0}, dict(density=19250, cp=132, k=173, solidus=3695, liquidus=3695, absorptivity=0.40)),
    "CoCrMo": ({"Co": 0.64, "Cr": 0.28, "Mo": 0.06, "Si": 0.01, "Mn": 0.01}, dict(density=8300, cp=450, k=13, solidus=1623, liquidus=1683, absorptivity=0.35)),
}
SANE = {"density": (500, 25000), "cp": (100, 1500), "k": (1, 450), "solidus": (300, 4000), "liquidus": (300, 4000),
        "absorptivity": (0.02, 0.95)}


# ------------------------------------------------------------------ composition
def compose(text=None, js=None, atomic=False):
    """'Fe-18Cr-10Ni-2Mo' (balance first, wt%), 'Al90Cu5Ti5' (all given), or a JSON dict -> mass fractions."""
    if js:
        c = {k: float(v) for k, v in (json.loads(js) if isinstance(js, str) else js).items() if v}
    else:
        c, bal = {}, None
        t = text.replace(" ", "")
        if "-" in t:   # metallurgical notation: balance first, amounts before symbols ("Fe-18Cr-10Ni-2Mo", "Ti-6Al-4V")
            toks = t.split("-")
            for tok in toks:
                m = re.fullmatch(r"([0-9]*\.?[0-9]+)?([A-Z][a-z]?)([0-9]*\.?[0-9]+)?", tok)
                if not m:
                    raise ValueError(f"cannot parse '{tok}'")
                num = m.group(1) or m.group(3)
                if num:
                    c[m.group(2)] = c.get(m.group(2), 0) + float(num)
                elif bal is None:
                    bal = m.group(2)
                else:
                    raise ValueError(f"only one balance element allowed ({bal}, {m.group(2)})")
        else:          # formula notation, amounts after symbols ("Al90Cu5Ti5", "Fe95Cr5"; a bare symbol is the balance)
            for el, num in re.findall(r"([A-Z][a-z]?)([0-9]*\.?[0-9]*)", t):
                if num:
                    c[el] = c.get(el, 0) + float(num)
                elif bal is None:
                    bal = el
                else:
                    raise ValueError(f"only one balance element allowed ({bal}, {el})")
        if bal:
            tot = sum(c.values())
            if tot >= 100:
                raise ValueError("balance element but the listed amounts already reach 100")
            c[bal] = 100 - tot
    unknown = [e for e in c if e not in ELEMENTS]
    if unknown:
        raise ValueError(f"unknown elements {unknown}")
    if atomic:   # at% -> wt fraction
        c = {e: v * ELEMENTS[e][0] for e, v in c.items()}
    s = sum(c.values())
    return {e: v / s for e, v in sorted(c.items(), key=lambda kv: -kv[1])}


def molar_mass(w):
    """kg/mol of a composition given as mass fractions."""
    return 1e-3 / sum(f / ELEMENTS[e][0] for e, f in w.items())


def nearest_known(w):
    def dist(a, b):
        keys = set(a) | set(b)
        return math.sqrt(sum((a.get(k, 0) - b.get(k, 0)) ** 2 for k in keys))
    return min(((n, dist(w, c)) for n, (c, _) in KNOWN.items()), key=lambda x: x[1])


# ------------------------------------------------------------------ properties
def drude_absorptivity(resistivity_ohm_m, wavelength_m=1.07e-6):
    """Paper Eq. 2 (Hagen-Rubens/Drude series for normal emissivity = absorptivity of an opaque metal):
    eps = 0.365 sqrt(r/l) - 0.0667 (r/l) + 0.006 (r/l)^1.5, with r in ohm*cm and l in cm."""
    x = (resistivity_ohm_m * 100) / (wavelength_m * 100)
    return 0.365 * math.sqrt(x) - 0.0667 * x + 0.006 * x ** 1.5


def database_for(w):
    """Thermo-Calc database choice, paper Appendix C."""
    top = max(w, key=w.get)
    if len([e for e, f in w.items() if f >= 0.15]) >= 3 and top not in ("Ti",) and w.get("Ni", 0) < 0.30 and top != "Fe":
        pass
    if top == "Ti":
        return "TCTI6"
    if top == "Ni" or w.get("Ni", 0) >= 0.30:
        return "TCNI12"
    if top == "Fe":
        return "TCFE14"
    if top == "Al":
        return "TCAL9"
    if len(w) == 1:
        return "PURE5"
    return "TCHEA7"


def thermocalc_properties(w, t_min=500, t_max=3500, at_temperature=None):
    """CALPHAD route (paper Sec. 2.1) through TC-Python. Requires a Thermo-Calc licence and TC-Python.
    Liquid volume fraction from a 1-D temperature sweep -> solidus/liquidus; density, Cp, k and electrical
    resistivity at the melting point (mean of solidus and liquidus). Units are normalised and checked."""
    from tc_python import TCPython, ThermodynamicQuantity, CalculationAxis
    db = database_for(w)
    els = list(w)
    with TCPython() as s:
        sysb = s.select_database_and_elements(db, els).get_system()
        calc = sysb.with_property_diagram_calculation().with_axis(
            CalculationAxis(ThermodynamicQuantity.temperature()).set_min(t_min).set_max(t_max))
        dep = max(w, key=w.get)
        for e in els:
            if e != dep:
                calc = calc.set_condition(ThermodynamicQuantity.mass_fraction_of_a_component(e), w[e])
        res = calc.calculate()
        T, fl = res.get_values_of(ThermodynamicQuantity.temperature(), ThermodynamicQuantity.volume_fraction_of_a_phase("LIQUID"))
        T, fl = np.asarray(T), np.nan_to_num(np.asarray(fl))
        order = np.argsort(T); T, fl = T[order], fl[order]
        sol = float(T[np.argmax(fl > 0.01)]); liq = float(T[np.argmax(fl > 0.99)])
        tm = at_temperature or 0.5 * (sol + liq)
        eq = sysb.with_single_equilibrium_calculation().set_condition(ThermodynamicQuantity.temperature(), tm)
        for e in els:
            if e != dep:
                eq = eq.set_condition(ThermodynamicQuantity.mass_fraction_of_a_component(e), w[e])
        r = eq.calculate()
        raw = {"density": r.get_value_of("B/V"), "cp": r.get_value_of("HM.T"),
               "k": r.get_value_of("THCD"), "resistivity": r.get_value_of("ELRS")}
    p = {"solidus": sol, "liquidus": liq, "density": raw["density"], "cp": raw["cp"], "k": raw["k"]}
    p, notes = sanitize(p, w)
    p["absorptivity"] = drude_absorptivity(raw["resistivity"])
    return p, {"source": f"Thermo-Calc {db}", "raw": raw, "unit_fixes": notes}


def estimate_properties(w):
    """No-CALPHAD fallback. Density by inverse rule of mixtures, Cp by mass-weighted mixing (both decent);
    thermal conductivity and solidus/liquidus from the nearest built-in alloy if it is close, otherwise flagged."""
    rho = 1 / sum(f / ELEMENTS[e][1] for e, f in w.items())
    cp = sum(f * ELEMENTS[e][2] for e, f in w.items())
    name, d = nearest_known(w)
    ref = KNOWN[name][1]
    conf = "medium" if d < 0.05 else "low"
    if len(w) == 1:
        e = next(iter(w)); tm = ELEMENTS[e][4]
        p = dict(density=rho, cp=cp, k=ELEMENTS[e][3], solidus=tm, liquidus=tm,
                 absorptivity=min(0.6, max(0.05, drude_absorptivity(ELEMENTS[e][5] * 4))))   # ~4x resistivity near melt
        return p, {"source": "pure element data", "confidence": "medium"}
    p = dict(density=rho, cp=cp, k=ref["k"], solidus=ref["solidus"], liquidus=ref["liquidus"], absorptivity=ref["absorptivity"])
    return p, {"source": f"rule of mixtures (density, Cp) + nearest built-in alloy '{name}' (k, solidus, liquidus, absorptivity), "
                         f"composition distance {d:.3f}", "confidence": conf,
               "warning": None if conf == "medium" else "composition far from any built-in alloy: get solidus/liquidus and k "
                                                         "from Thermo-Calc (--thermocalc) or measurements before trusting the map"}


def sanitize(p, w=None):
    """Catch the unit slips seen in practice (paper repo results: density ~1000x, Cp in J/mol/K)."""
    notes = []
    if p.get("density") and p["density"] > 1e5:
        p["density"] /= 1000; notes.append("density /1000 (was g/m3 or similar)")
    if p.get("cp") and p["cp"] < 80:
        if not w:
            notes.append("Cp looks molar (J/mol/K) but no composition is known to convert it: fix the file")
        else:
            p["cp"] = p["cp"] / molar_mass(w); notes.append("Cp converted from J/mol/K to J/kg/K with the alloy molar mass")
    if p.get("solidus") and p.get("liquidus") and p["solidus"] > p["liquidus"]:
        p["solidus"], p["liquidus"] = p["liquidus"], p["solidus"]; notes.append("solidus/liquidus swapped")
    return p, notes


def check(p):
    bad = {k: p.get(k) for k, (lo, hi) in SANE.items() if p.get(k) is None or not (lo <= p[k] <= hi)}
    return {"ok": not bad, "out_of_range": bad, "diffusivity_m2_s": p["k"] / (p["density"] * p["cp"]) if not bad else None}


def material(name=None, comp=None, use_tc=False):
    if name:
        if name not in KNOWN:
            raise SystemExit(f"unknown alloy {name}; known: {', '.join(KNOWN)}")
        w, p = KNOWN[name]
        meta = {"source": "built-in nominal values"}
    else:
        w = comp
        if use_tc:
            p, meta = thermocalc_properties(w)
        else:
            p, meta = estimate_properties(w)
    p = dict(p); p["melting"] = 0.5 * (p["solidus"] + p["liquidus"])
    return {"name": name or "-".join(f"{e}{100 * f:.3g}" for e, f in w.items()), "composition_wt": w, "properties": p,
            "meta": meta, "check": check(p)}


# ------------------------------------------------------------------ melt pool (paper Sec. 2.2.1, Eqs. 4-5, App. B)
def rosenthal_dims(P, V_mm_s, mat, T0=293.0, use="liquidus", step_um=1.0):
    """Rosenthal moving point source. The melt boundary T = T_m satisfies z = R + (2 alpha / V) ln(2 pi k R dT / (eps P));
    sweeping R in 1 um steps up to the tail length R_tail = eps P / (2 pi k dT) gives the boundary.
    Width = 2 max(r), depth = max(r) (half-space), length = R_tail - min(z). Conduction mode only."""
    p = mat["properties"]
    eps, k = p["absorptivity"], p["k"]
    alpha = k / (p["density"] * p["cp"])
    Tm = p[use] if use in p else p["melting"]
    dT = Tm - T0
    V = V_mm_s * 1e-3
    if dT <= 0 or P <= 0 or V <= 0:
        return {"width_um": 0.0, "depth_um": 0.0, "length_um": 0.0}
    R_tail = eps * P / (2 * math.pi * k * dT)
    R = np.arange(step_um, R_tail * 1e6, step_um) * 1e-6
    if len(R) == 0:
        return {"width_um": 0.0, "depth_um": 0.0, "length_um": 0.0}
    z = R + (2 * alpha / V) * np.log(2 * math.pi * k * R * dT / (eps * P))
    r = np.sqrt(np.clip(R ** 2 - z ** 2, 0, None))
    zmin = z.min()
    return {"width_um": 2 * r.max() * 1e6, "depth_um": r.max() * 1e6, "length_um": (R_tail - zmin) * 1e6,
            "front_um": -zmin * 1e6, "tail_um": R_tail * 1e6}


def regimes(d, hatch_um, layer_um):
    W, D, L = d["width_um"], d["depth_um"], d["length_um"]
    if W <= 0 or D <= 0:
        return {"lack_of_fusion": True, "lof_value": float("inf"), "keyhole_indicative": False, "balling_indicative": False}
    lof = (hatch_um / W) ** 2 + (layer_um / D) ** 2
    return {"lack_of_fusion": lof > 1, "lof_value": lof,
            "keyhole_indicative": W / D < 1.5,     # always 2 for Rosenthal (W = 2D): conduction model cannot show keyholes
            "balling_indicative": L / W > math.pi}


def rng(s):
    a, b, c = (float(x) for x in s.split(":"))
    return np.arange(a, b + c / 2, c)


def process_map(mat, hatch_um, layer_um, powers, velocities, layer_offsets=(-25, 0, 25), T0=293.0, use="liquidus",
                ed_keyhole=None):
    """Paper Sec. 2.4.3: LoF regime for the prescribed layer and +-25 um. Structured output with explicit keys
    (the paper traced an LLM misreading to a bare list of (P, V) tuples)."""
    out = {"material": mat["name"], "hatch_um": hatch_um, "T0_K": T0, "temperature_used": use, "layers": {}}
    grid = [(float(P), float(V)) for P in powers for V in velocities]
    dims = {(P, V): rosenthal_dims(P, V, mat, T0, use) for P, V in grid}
    for off in layer_offsets:
        t = layer_um + off
        if t <= 0:
            continue
        lof = []
        for (P, V) in grid:
            r = regimes(dims[(P, V)], hatch_um, t)
            if r["lack_of_fusion"]:
                lof.append({"power_W": P, "velocity_mm_s": V, "lof_value": round(r["lof_value"], 3)})
        out["layers"][f"{t:g}"] = {"layer_um": t, "lack_of_fusion_points": lof, "lack_of_fusion_fraction": round(len(lof) / len(grid), 4),
                                   "safe_points": len(grid) - len(lof), "grid_points": len(grid)}
    if ed_keyhole:   # optional: user-supplied volumetric energy density (J/mm3) above which conduction dims are not valid
        out["keyhole_risk_above_J_mm3"] = ed_keyhole
        out["keyhole_risk_points"] = [{"power_W": P, "velocity_mm_s": V} for P, V in grid
                                      if P / (V * hatch_um * 1e-3 * layer_um * 1e-3) > ed_keyhole]
    out["melt_pool_um"] = [{"power_W": P, "velocity_mm_s": V, **{k: round(v, 1) for k, v in dims[(P, V)].items()}} for P, V in grid]
    out["note"] = ("Rosenthal conduction model: lack of fusion is conservative (melt pools are under-estimated at high energy); "
                   "keyholing and balling are not predicted by this model.")
    return out


def plot_maps(maps, out, powers, velocities):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(maps); cols = min(n, 3); rows = math.ceil(n / cols)
    fig, axs = plt.subplots(rows, cols, figsize=(4.3 * cols, 3.8 * rows), squeeze=False)
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    for ax, m in zip(axs.ravel(), maps):
        layers = sorted(m["layers"].values(), key=lambda x: -x["layer_um"])
        for i, L in enumerate(layers):
            pts = L["lack_of_fusion_points"]
            if pts:
                ax.scatter([p["velocity_mm_s"] for p in pts], [p["power_W"] for p in pts], s=110 - 30 * i, marker="s",
                           color=["#08306b", "#2171b5", "#9ecae1"][i % 3], label=f"LoF, layer {L['layer_um']:g} µm ({100 * L['lack_of_fusion_fraction']:.0f}%)")
        if m.get("keyhole_risk_points"):
            ax.scatter([p["velocity_mm_s"] for p in m["keyhole_risk_points"]], [p["power_W"] for p in m["keyhole_risk_points"]],
                       marker="x", color="#c0392b", s=25, label="above keyhole energy cutoff")
        ax.set_xlim(velocities.min() - 50, velocities.max() + 50); ax.set_ylim(powers.min() - 50, powers.max() + 50)
        ax.set_title(f"{m['material']} (hatch {m['hatch_um']:g} µm)", fontsize=9)
        ax.set_xlabel("scan velocity (mm/s)"); ax.set_ylabel("power (W)"); ax.legend(fontsize=6, loc="upper left")
    fig.tight_layout(); fig.savefig(out, dpi=140)
    return out


def rank(mats, hatch_um, layer_um, powers, velocities, use="liquidus"):
    rows = []
    maps = []
    for m in mats:
        pm = process_map(m, hatch_um, layer_um, powers, velocities, use=use)
        maps.append(pm)
        L = pm["layers"][f"{layer_um:g}"]
        allL = list(pm["layers"].values())
        mean_lof = float(np.mean([x["lack_of_fusion_fraction"] for x in allL]))
        # overlap margin: mean LoF criterion value at the prescribed layer (lower = more overlap headroom)
        t, h = layer_um, hatch_um
        margin = float(np.mean([regimes({k: q[k] for k in ("width_um", "depth_um", "length_um")}, h, t)["lof_value"]
                                for q in pm["melt_pool_um"]]))
        rows.append({"material": m["name"], "lack_of_fusion_fraction": L["lack_of_fusion_fraction"],
                     "lack_of_fusion_fraction_all_layers": round(mean_lof, 4), "mean_overlap_criterion": round(margin, 3),
                     "process_window_fraction": round(1 - L["lack_of_fusion_fraction"], 4),
                     "property_check_ok": m["check"]["ok"], "property_source": m["meta"].get("source"),
                     "confidence": m["meta"].get("confidence", "high" if "built-in" in m["meta"].get("source", "") or "Thermo" in m["meta"].get("source", "") else "low")})
    rows.sort(key=lambda r: (r["lack_of_fusion_fraction"], r["lack_of_fusion_fraction_all_layers"], r["mean_overlap_criterion"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {"criterion": "smallest lack-of-fusion region at the prescribed layer; ties broken by the region over all layers "
                         "(layer +-25 um), then by the mean overlap criterion (hatch/W)^2 + (t/D)^2 (lower = more headroom)",
            "hatch_um": hatch_um, "layer_um": layer_um, "ranking": rows}, maps


def load_mat(path):
    m = json.load(open(path))
    if "properties" not in m:   # accept additive-manufacturing package material files {"density": {"magnitude":..}}
        g = lambda k: (m[k]["magnitude"] if isinstance(m.get(k), dict) else m.get(k))
        p = dict(density=g("density"), cp=g("specific_heat_capacity"), k=g("thermal_conductivity"),
                 solidus=g("temperature_solidus"), liquidus=g("temperature_liquidus"), absorptivity=g("absorptivity"))
        comp = m.get("composition_wt")
        if not comp:   # match the file's name to a built-in alloy (e.g. TI6AL4V -> Ti-6Al-4V)
            key = re.sub(r"[^a-z0-9]", "", str(m.get("name", "")).lower()).replace("alloy", "").replace("aluminum", "al")
            key = {"inconel718": "in718", "inconel625": "in625", "hastelloy": "hastelloyx", "k500": "monelk500",
                   "h13toolsteel": "h13", "copper": "cu", "tungsten": "w"}.get(key, key)
            for n, (cw, _) in KNOWN.items():
                if re.sub(r"[^a-z0-9]", "", n.lower()) in key or key in re.sub(r"[^a-z0-9]", "", n.lower()):
                    comp = cw; break
        p, notes = sanitize(p, comp)
        p["melting"] = 0.5 * (p["solidus"] + p["liquidus"])
        m = {"name": m.get("name", os.path.basename(path)), "composition_wt": m.get("composition_wt"), "properties": p,
             "meta": {"source": path, "unit_fixes": notes}, "check": check(p)}
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("known")
    s = sub.add_parser("compose"); s.add_argument("text", nargs="?"); s.add_argument("--json"); s.add_argument("--atomic", action="store_true")
    s = sub.add_parser("properties"); s.add_argument("--alloy"); s.add_argument("--comp", help="composition JSON file or string")
    s.add_argument("--thermocalc", action="store_true"); s.add_argument("--out")
    s = sub.add_parser("check"); s.add_argument("material")
    s = sub.add_parser("meltpool"); s.add_argument("--material", required=True); s.add_argument("--power", type=float, required=True)
    s.add_argument("--velocity", type=float, required=True); s.add_argument("--preheat", type=float, default=293.0)
    for name in ("map", "rank"):
        s = sub.add_parser(name)
        if name == "map":
            s.add_argument("--material", required=True); s.add_argument("--keyhole-ed", type=float, help="J/mm3 cutoff (optional)")
        else:
            s.add_argument("--materials", nargs="+", required=True)
        s.add_argument("--hatch", type=float, default=50); s.add_argument("--layer", type=float, default=30)
        s.add_argument("--power", default="100:1000:100"); s.add_argument("--velocity", default="100:1000:100")
        s.add_argument("--use", choices=["liquidus", "melting", "solidus"], default="liquidus"); s.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "known":
        r = {n: {"composition_wt": c, **p} for n, (c, p) in KNOWN.items()}
    elif a.cmd == "compose":
        r = compose(a.text, a.json, a.atomic)
    elif a.cmd == "properties":
        comp = None
        if a.comp:
            comp = compose(js=open(a.comp).read()) if os.path.exists(a.comp) else (compose(js=a.comp) if a.comp.strip().startswith("{") else compose(a.comp))
        r = material(a.alloy, comp, a.thermocalc)
        if a.out:
            json.dump(r, open(a.out, "w"), indent=1)
    elif a.cmd == "check":
        m = load_mat(a.material); r = {"name": m["name"], **m["check"], "unit_fixes": m["meta"].get("unit_fixes")}
    elif a.cmd == "meltpool":
        m = load_mat(a.material); r = {k: round(v, 1) for k, v in rosenthal_dims(a.power, a.velocity, m, a.preheat).items()}
    elif a.cmd == "map":
        m = load_mat(a.material); P, V = rng(a.power), rng(a.velocity)
        r = process_map(m, a.hatch, a.layer, P, V, use=a.use, ed_keyhole=a.keyhole_ed)
        if a.out:
            plot_maps([r], a.out, P, V); r["plot"] = a.out
        r.pop("melt_pool_um")
        for L in r["layers"].values():
            L["lack_of_fusion_points"] = L["lack_of_fusion_points"][:12] + (["..."] if len(L["lack_of_fusion_points"]) > 12 else [])
    else:
        P, V = rng(a.power), rng(a.velocity)
        r, maps = rank([load_mat(p) for p in a.materials], a.hatch, a.layer, P, V, a.use)
        if a.out:
            plot_maps(maps, a.out, P, V); r["plot"] = a.out
    print(json.dumps(r, indent=1, default=float))


if __name__ == "__main__":
    main()
