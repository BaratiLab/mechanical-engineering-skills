#!/usr/bin/env python3
"""Tests for the Query2CAD loop tools. Runs the star-plate macros in FreeCAD if freecadcmd is available.
python tests/test_q2c.py   (set FREECAD_CMD to your freecadcmd if it is not on PATH)"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import q2c  # noqa: E402
FAILS = []
def expect(n, c, i=""):
    print(("PASS " if c else "FAIL ") + n + (f"  {i}" if i else "")); FAILS.append(n) if not c else None
t = tempfile.mkdtemp()
for k in range(1, 5):
    st = q2c.log(t + "/e", "error", f"e{k}")
expect("error budget: stop after 3 repairs", "stop" in st and k == 4)
q2c.log(t + "/m", "model", "pentagon", 0.05, "agent")
st = q2c.log(t + "/m", "accept", "star", 0.97, "agent")
expect("VQA >= 0.9 stops the loop", "threshold" in st.get("stop", ""))
ex = os.path.join(HERE, "..", "examples", "star_plate")
if q2c.freecad_cmd():
    r0 = q2c.run(os.path.join(ex, "v0.py"), os.path.join(t, "v0"))
    r2 = q2c.run(os.path.join(ex, "v2.py"), os.path.join(t, "v2"))
    expect("FreeCAD v0 (open outline) fails: no solid", not r0["ok"])
    expect("FreeCAD v2 star plate: valid solid, 12 faces, 4 mm thick", r2["ok"] and r2["valid"] and r2["faces"] == 12 and abs(r2["bbox"][2] - 4) < 1e-6)
else:
    print("SKIP FreeCAD execution (freecadcmd not found)")
print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}"); sys.exit(1 if FAILS else 0)
