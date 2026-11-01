#!/usr/bin/env python3
"""Regression tests for cadsmith-text-to-cad (the paper's T3 flanged shaft coupling).
python tests/test_cadsmith.py   (needs cadquery, trimesh, scipy)"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import cadsmith as C  # noqa: E402

EX = os.path.join(HERE, "..", "examples", "coupling")
FAILS = []


def expect(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


t = tempfile.mkdtemp()
plan = json.load(open(os.path.join(EX, "plan.json")))
m = C.execute(os.path.join(EX, "part.py"), os.path.join(t, "v0"))
expect("executes, valid single solid", m["ok"] and m["valid"] and m["n_solids"] == 1)
expect("tight bbox 50 x 50 x 60", all(abs(a - b) < 1e-6 for a, b in zip([m["bbox"]["xlen"], m["bbox"]["ylen"], m["bbox"]["zlen"]], [50, 50, 60])))
expect("plan check passes", C.check(plan, m)["passed"])

mb = C.execute(os.path.join(EX, "part_v0_bug.py"), os.path.join(t, "bug"))
cb = C.check(plan, mb)
expect("PCD-as-radius bug caught (bbox fine, holes missing)", not cb["passed"] and any("6.5" in i for i in cb["issues"]), cb["issues"])

silent = os.path.join(t, "silent.py"); open(silent, "w").write("import cadquery as cq\nresult = cq.Workplane().box(10,10,10).edges().fillet(6)\n")
ms = C.execute(silent, os.path.join(t, "silent"))
expect("oversized fillet: OCCT returns an INVALID solid silently -> hard kernel fail", ms["ok"] and not ms["valid"] and C.check({}, ms)["hard_fail"])
bad = os.path.join(t, "bad.py"); open(bad, "w").write("import cadquery as cq\nresult = cq.Workplane().box(10,10,10).faces('>Z').workplane().extrude(5)\n")
mx = C.execute(bad, os.path.join(t, "bad"))
expect("execution error captured (inner loop)", not mx["ok"] and bool(mx["error_type"]), mx.get("error_type"))
kb = C.kb("fillet", errors_text=mx.get("traceback", "") + " fillet BRep_API: command not done")
expect("KB2 retrieves the fillet pattern", any(p["id"] == "E01" for p in kb.get("error_patterns", [])))

C.execute(os.path.join(EX, "ref.py"), os.path.join(t, "ref"))
e_ok = C.eval_metrics(os.path.join(t, "v0.stl"), os.path.join(t, "ref.stl"))
e_bug = C.eval_metrics(os.path.join(t, "bug.stl"), os.path.join(t, "ref.stl"))
floor = e_ok["noise_floor_ref_vs_ref"]
expect("correct part at sampling noise floor", abs(e_ok["f1"] - floor["f1"]) < 0.02 and e_ok["iou"] > 0.99,
       f"F1 {e_ok['f1']:.3f} vs floor {floor['f1']:.3f}, IoU {e_ok['iou']:.3f}")
expect("bug part scores worse", e_bug["f1"] < e_ok["f1"] - 0.02 and e_bug["iou"] < e_ok["iou"] - 0.02,
       f"F1 {e_bug['f1']:.3f}, IoU {e_bug['iou']:.3f}")

for k in range(4):
    L = C.log(t + "/run", "outer", f"attempt {k}", False)
expect("escalation from outer iteration 3", L["escalate"] is True)

print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
