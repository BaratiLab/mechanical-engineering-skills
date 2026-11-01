"""Run: python tests/test_meltpool.py   (downloads MeltpoolNet once; ~2 min)"""
import os, sys, tempfile, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import meltpool as M  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

# Rosenthal: depth scales as sqrt(P/V), width = 2 depth, length independent of V
a = M.rosenthal(200, 800, 8000, 500, 16.3, 1688, 0.35)
b = M.rosenthal(400, 800, 8000, 500, 16.3, 1688, 0.35)
c = M.rosenthal(200, 1600, 8000, 500, 16.3, 1688, 0.35)
check("rosenthal depth ~ sqrt(P)", math.isclose(b["depth_um"] / a["depth_um"], math.sqrt(2), rel_tol=1e-9))
check("rosenthal depth ~ 1/sqrt(V)", math.isclose(a["depth_um"] / c["depth_um"], math.sqrt(2), rel_tol=1e-9))
check("rosenthal width = 2 depth", math.isclose(a["width_um"], 2 * a["depth_um"]))
check("rosenthal length independent of V", math.isclose(a["length_um"], c["length_um"]))
check("rosenthal magnitude (SS316L 200 W, 800 mm/s, eta .35) 40-100 um deep", 40 < a["depth_um"] < 100)
check("absorptivity1 in (0, 0.7)", 0 < M.absorptivity1(200, 800, 80, 8000, 500, 1688, 0.33) < 0.7)

# power-law identification satisfies dimensional analysis exactly
r = M.identify("depth")
check("identified exponents are dimensionally consistent", max(abs(v) for v in r["dimension_residual"]) < 1e-6)
check("identified depth beats Rosenthal on same rows", r["R2"] > r["rosenthal_R2_same_rows"])
check("power exponent near Rosenthal's 1/2", 0.3 < r["exponents"]["P"] < 0.7)

# benchmark: random split informative, leave-paper-out much harder, calibration helps
rnd = M.benchmark("depth", ["energy"], "random", ("gb",))
pap = M.benchmark("depth", ["energy"], "paper", ("gb",))
cal = M.benchmark("depth", ["energy"], "paper", ("gb",), calibrate=5)
check(f"random split R2 > 0.6 ({rnd['models']['gb']['R2']})", rnd["models"]["gb"]["R2"] > 0.6)
check("leave-paper-out is much harder", pap["models"]["gb"]["R2"] < rnd["models"]["gb"]["R2"] - 0.3)
check(f"5 calibration tracks per paper recover R2 > 0.4 ({cal['models']['gb']['R2']})", cal["models"]["gb"]["R2"] > 0.4)

# train / predict round trip with own-data calibration
with tempfile.TemporaryDirectory() as d:
    import pandas as pd
    extra = os.path.join(d, "mine.csv")
    pd.DataFrame({"Material": ["SS316L"] * 4, "Power": [150, 200, 250, 300], "Velocity": [800] * 4, "beam D": [80] * 4,
                  "depth of meltpool": [70, 95, 130, 170]}).to_csv(extra, index=False)
    p = os.path.join(d, "depth.joblib")
    M.train("depth", ["energy"], "gb", p, extra=extra)
    lo = M.predict([p], "SS316L", 150, 800, 80)["depth_um"]
    hi = M.predict([p], "SS316L", 300, 800, 80)["depth_um"]
    check(f"more power -> deeper ({lo} -> {hi})", hi > lo)
    check("calibrated model lands near own measurement (200 W: 95 um)", abs(M.predict([p], "SS316L", 200, 800, 80)["depth_um"] - 95) < 40)
print(f"\n{ok} checks passed")
