"""Run: python tests/test_alloy.py   (no network, < 30 s)"""
import math, os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import alloy as A  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

c = A.compose("Fe-18Cr-10Ni-2Mo")
check("metallurgical notation", abs(c["Fe"] - 0.70) < 1e-9 and abs(c["Cr"] - 0.18) < 1e-9)
check("formula notation", abs(A.compose("Al90Cu5Ti5")["Cu"] - 0.05) < 1e-9)
check("at% -> wt%: Cu heavier than Al", A.compose("Al90Cu5Ti5", atomic=True)["Cu"] > 0.05)
check("Ti-6Al-4V", A.compose("Ti-6Al-4V") == {"Ti": 0.9, "Al": 0.06, "V": 0.04})
check("database rules (App. C)", A.database_for({"Ti": .9, "Al": .1}) == "TCTI6" and A.database_for({"Fe": .5, "Ni": .35, "Cr": .15}) == "TCNI12"
      and A.database_for({"Fe": .7, "Cr": .3}) == "TCFE14" and A.database_for({"Al": 1.0}) == "TCAL9"
      and A.database_for({"Co": .25, "Cr": .25, "Fe": .25, "Mn": .25}) == "TCHEA7")
eps = A.drude_absorptivity(1.3e-6)    # ~liquid steel resistivity
check(f"Drude absorptivity of molten steel ~0.3-0.4 ({eps:.3f})", 0.28 < eps < 0.42)
check("Drude: copper absorbs far less than steel", A.drude_absorptivity(2e-7) < 0.5 * eps)

m = A.material("SS316L")
d1, d2 = A.rosenthal_dims(200, 800, m), A.rosenthal_dims(400, 800, m)
check("Rosenthal width = 2 depth", math.isclose(d1["width_um"], 2 * d1["depth_um"]))
check("Rosenthal tail length = eps P / (2 pi k dT)", math.isclose(d1["tail_um"], 0.35 * 200 / (2 * math.pi * 8.9 * (1710.3 - 293)) * 1e6, rel_tol=1e-6))
check("more power -> wider pool", d2["width_um"] > d1["width_um"])
check("SS316L 200 W 800 mm/s width 80-200 um", 80 < d1["width_um"] < 200)
for P, V in [(150, 500), (200, 700), (250, 900), (300, 1100)]:   # Ahmed et al. high-density points cited in the paper
    check(f"SS316L {P} W/{V} mm/s outside LoF (hatch 50, layer 30)", not A.regimes(A.rosenthal_dims(P, V, m), 50, 30)["lack_of_fusion"])
check("SS316L 60 W/2000 mm/s is LoF", A.regimes(A.rosenthal_dims(60, 2000, m), 50, 30)["lack_of_fusion"])

import numpy as np
pm = A.process_map(m, 50, 30, np.arange(50, 501, 50), np.arange(200, 2001, 200))
f = {k: v["lack_of_fusion_fraction"] for k, v in pm["layers"].items()}
check("thicker layers -> larger LoF region", f["5"] <= f["30"] <= f["55"] and f["55"] > f["5"])
check("keyed output (no bare tuples)", all(set(p) >= {"power_W", "velocity_mm_s"} for p in pm["layers"]["30"]["lack_of_fusion_points"]))
r, _ = A.rank([A.material("IN625"), A.material("SS316L")], 50, 30, np.arange(100, 1001, 100), np.arange(100, 1001, 100))
check("IN625 ranked above SS316L (paper's corrosion case)", r["ranking"][0]["material"] == "IN625")
r, _ = A.rank([A.material("Cu"), A.material("SS316L")], 50, 30, np.arange(100, 1001, 100), np.arange(100, 1001, 100))
check("pure Cu (IR absorptivity) ranks last", r["ranking"][-1]["material"] == "Cu")

with tempfile.TemporaryDirectory() as d:   # the repository's unit slips are caught and fixed
    bad = {"name": "TI6AL4V", "density": {"magnitude": 4400847.7}, "specific_heat_capacity": {"magnitude": 29.55},
           "thermal_conductivity": {"magnitude": 10.79}, "temperature_solidus": {"magnitude": 1883}, "temperature_liquidus": {"magnitude": 1933},
           "absorptivity": {"magnitude": 0.46}}
    p = os.path.join(d, "ti.json"); json.dump(bad, open(p, "w"))
    mm = A.load_mat(p)
    check(f"g/m3 density fixed ({mm['properties']['density']:.0f})", 4000 < mm["properties"]["density"] < 4800)
    check(f"molar Cp converted ({mm['properties']['cp']:.0f} J/kg/K)", 550 < mm["properties"]["cp"] < 700)
    check("sanitized file passes check", mm["check"]["ok"])
est, meta = A.estimate_properties(A.compose("Fe-10Ni-10Ti"))
check("fallback flags low confidence for a far composition", meta["confidence"] == "low" and meta["warning"])
check("rule-of-mixtures density plausible", 6500 < est["density"] < 8000)
print(f"\n{ok} checks passed")
