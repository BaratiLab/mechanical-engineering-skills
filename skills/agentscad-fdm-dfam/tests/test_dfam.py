#!/usr/bin/env python3
"""Regression test: AgentsCAD birdhouse case.  python tests/test_dfam.py  (needs cadquery; pyvista for renders)"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import dfam  # noqa: E402
FAILS = []
def expect(n, c, i=""):
    print(("PASS " if c else "FAIL ") + n + (f"  {i}" if i else "")); FAILS.append(n) if not c else None
t = tempfile.mkdtemp(); step = os.path.join(t, "birdhouse.step")
subprocess.run([sys.executable, os.path.join(HERE, "..", "examples", "make_birdhouse.py"), step], check=True)
a = dfam.analyze(step)
expect("9 faces, 7 planar + 2 cylinders", a["part"]["n_faces"] == 9 and sum(f["surface_type"] == "Cylinder" for f in a["features"]) == 2)
expect("both bores flagged as -90 deg horizontal overhangs; bed face not flagged",
       sorted((o["face_id"], o["overhang_deg"]) for o in a["overhangs"]) == [(6, -90.0), (8, -90.0)])
L = dfam.lay_face(step, 3)
expect("lay_face(3) puts its normal at -Z", L["normal_after"][2] < -0.9999, L["normal_after"])
expect("laying face 3 leaves only the perch hole", [o["face_id"] for o in L["overhangs_after"]] == [6])
expect("lay_face on bed face returns zero rotation", dfam.lay_face(step, 0)["rx_deg"] == 0 and dfam.lay_face(step, 0)["ry_deg"] == 0)
c = dfam.candidates(step)
expect("orientation sub-phase recommends an end face on the bed", c["recommended"]["bed_face"] in (3, 4))
plan = json.load(open(os.path.join(HERE, "..", "examples", "birdhouse_mods.json")))
shape, log = dfam.modify(step, plan)
new = os.path.join(t, "new.step"); dfam.cq().exporters.export(dfam.cq().Workplane().add(shape), new)
expect("teardrop and reorient applied", [l["status"] for l in log] == ["APPLIED", "APPLIED (last)"])
b = dfam.analyze(new)
expect("zero actionable overhangs after DFAM", b["summary"]["actionable"] == 0, b["overhangs"])
expect("valid single solid, small volume change",
       shape.isValid() and len(shape.Solids()) == 1 and abs(b["part"]["volume_mm3"] / a["part"]["volume_mm3"] - 1) < 0.01)
expect("part sits on the bed (zmin = 0)", abs(shape.BoundingBox().zmin) < 1e-6)
print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}"); sys.exit(1 if FAILS else 0)
