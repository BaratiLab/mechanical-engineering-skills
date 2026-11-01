#!/usr/bin/env python3
"""Regression tests for llm-mechanical-designer.  python tests/test_truss.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, S)
from tasks import TASKS  # noqa: E402
from truss_fem import evaluate  # noqa: E402

FAILS = []


def expect(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {info}" if info else ""))
    if not cond:
        FAILS.append(name)


# Stresses from the paper's reference implementation (truss_y.py) for this truss and t1 loading
REF = {"member_1": -6.1639, "member_2": -1.34, "member_3": 3.432, "member_4": 4.971,
       "member_5": 1.895, "member_6": -7.2338, "member_7": -2.5575}
D = {"node_dict": {"node_1": [0, 0], "node_2": [6, 0], "node_3": [2, 0], "node_4": [2, 2.5], "node_5": [4, 2.0]},
     "member_dict": {"member_1": ["node_1", "node_3", "3"], "member_2": ["node_3", "node_2", "3"],
                     "member_3": ["node_1", "node_4", "3"], "member_4": ["node_4", "node_5", "2"],
                     "member_5": ["node_5", "node_2", "3"], "member_6": ["node_3", "node_4", "2"],
                     "member_7": ["node_3", "node_5", "2"]}}
r = evaluate(D, TASKS["t1v1"])
diff = max(abs(r["member_stress"][k] - v) for k, v in REF.items())
expect("stresses match reference code", diff < 1e-3, f"max diff {diff:.2e}")
expect("mass matches reference code (26.9397)", abs(r["total_mass"] - 26.9397) < 1e-3)

mech = {"node_dict": {"node_1": [0, 0], "node_2": [6, 0], "node_3": [2, 0], "node_4": [2, 2.5]},
        "member_dict": {"m1": ["node_1", "node_3", "3"], "m2": ["node_3", "node_2", "3"], "m3": ["node_3", "node_4", "3"]}}
expect("mechanism flagged invalid", not evaluate(mech, TASKS["t1v1"])["valid"])
moved = json.loads(json.dumps(D)); moved["node_dict"]["node_3"] = [2.5, 0]
expect("moving a load node is rejected", not evaluate(moved, TASKS["t1v1"])["valid"])
dup = json.loads(json.dumps(D)); dup["member_dict"]["member_8"] = ["node_3", "node_1", "1"]
expect("duplicate member rejected", not evaluate(dup, TASKS["t1v1"])["valid"])

# tutorial run (t1v1): final design from docs/tutorials/llm-mechanical-designer.md
fin = {"node_dict": {"node_1": [0, 0], "node_2": [6, 0], "node_3": [2, 0], "node_4": [2, 3.0]},
       "member_dict": {"member_1": ["node_1", "node_3", "4"], "member_2": ["node_3", "node_2", "2"],
                       "member_3": ["node_1", "node_4", "3"], "member_4": ["node_4", "node_2", "3"],
                       "member_5": ["node_3", "node_4", "3"]}}
rf = evaluate(fin, TASKS["t1v1"])
expect("tutorial final design feasible, max|s| 4.0199, mass 29.7982",
       rf["feasible"] and abs(rf["max_abs_stress"] - 4.0199) < 1e-3 and abs(rf["total_mass"] - 29.7982) < 1e-3)

# loop: stop refused when infeasible
with tempfile.TemporaryDirectory() as t:
    run = os.path.join(t, "run")
    subprocess.run([sys.executable, os.path.join(S, "design_loop.py"), "init", "--task", "t1v1", "--run", run], check=True, capture_output=True)
    bad = json.loads(json.dumps(fin)); bad["stop"] = True
    for m in bad["member_dict"].values():
        m[2] = "1"
    p = os.path.join(t, "bad.json"); json.dump(bad, open(p, "w"))
    out = json.loads(subprocess.run([sys.executable, os.path.join(S, "design_loop.py"), "eval", "--run", run, p],
                                    check=True, capture_output=True, text=True).stdout)
    expect("stop refused on infeasible design; CONSTRAINT prompt next", out["stop"] is False and out["mode_next"] == "CONSTRAINT")
    expect("next prompt written", os.path.exists(os.path.join(run, "prompt_next.md")))

print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
