#!/usr/bin/env python3
"""Unit-checked calculation pattern. Copy, edit the INPUTS and STEPS, run.

Each step records symbol, equation (LaTeX), value with units, and reference,
and the script emits calc_steps.json + calc_steps.md for the report body.
Example: bracket bolt shear check.
"""
import json

import pint

u = pint.UnitRegistry()
Q = u.Quantity
steps, checks = [], []


def step(sym, latex, value, ref="", unit=None):
    v = value.to(unit) if unit else value.to_compact()
    steps.append({"symbol": sym, "equation": latex, "value": f"{v.magnitude:.4g}",
                  "unit": f"{v.units:~P}", "ref": ref})
    return value


def check(name, applied, allowable, fos=1.0):
    applied = applied.to(allowable.units)
    ms = (allowable / (applied * fos)).to("dimensionless").magnitude - 1
    checks.append({"check": name, "applied": f"{applied:~.4g}", "allowable": f"{allowable:~.4g}",
                   "FoS": fos, "MS": round(ms, 3), "status": "PASS" if ms >= 0 else "FAIL"})


# ------------------------------------------------------------ INPUTS
INPUTS = {
    "F": (Q(12, "kN"), "Load spec LS-004 rev B"),
    "n": (Q(4, ""), "Drawing 1001-A"),
    "d": (Q(8, "mm"), "M8 bolt, drawing 1001-A"),
    "Ssy": (Q(0.577 * 640, "MPa"), "ISO 898-1 8.8, Sy = 640 MPa; distortion energy"),
}
F, n, d, Ssy = (INPUTS[k][0] for k in ("F", "n", "d", "Ssy"))

# ------------------------------------------------------------ STEPS
A = step("A", r"A = \pi d^2 / 4", 3.14159 * d ** 2 / 4, "shank area (shear plane through shank)", "mm**2")
tau = step(r"\tau", r"\tau = F / (n A)", F / (n * A), "direct shear, single plane per bolt", "MPa")
check("Bolt shear", tau, Ssy, fos=2.0)

out = {"inputs": [{"symbol": k, "value": f"{v:~P}", "source": s} for k, (v, s) in INPUTS.items()],
       "steps": steps, "checks": checks}
json.dump(out, open("calc_steps.json", "w"), indent=2)
with open("calc_steps.md", "w") as f:
    for s in steps:
        f.write(f"**{s['symbol']}**: $${s['equation']}$$ = {s['value']} {s['unit']}  _{s['ref']}_\n\n")
    f.write("| Check | Applied | Allowable | FoS | MS | Status |\n|---|---|---|---|---|---|\n")
    for c in checks:
        f.write(f"| {c['check']} | {c['applied']} | {c['allowable']} | {c['FoS']} | {c['MS']} | {c['status']} |\n")
print(json.dumps(out, indent=2))
