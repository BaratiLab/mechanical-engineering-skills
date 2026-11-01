#!/usr/bin/env python3
"""Regression tests for linkage-synthesis.  python tests/test_linkage.py   (~20 s)"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import linkage as L  # noqa: E402
import synth as S  # noqa: E402

FAILS = []


def expect(n, c, i=""):
    print(("PASS " if c else "FAIL ") + n + (f"  {i}" if i is not None and str(i) else ""))
    if not c:
        FAILS.append(n)


m = json.load(open(os.path.join(HERE, "..", "examples", "fourbar.json")))
v = L.validate(m)
expect("four-bar valid; link lengths preserved over 200 angles", v["valid"] and v["max_link_length_drift"] < 1e-9)
P, _ = L.simulate(m)
Pv = S.Model(m).run(np.asarray(m["nodes"], float))
expect("vectorized simulator == reference", np.abs(P - Pv).max() < 1e-9)
G, meta = L.encode(m)
expect("LinkD N x 24 encoding", G.shape == (20, 24) and np.allclose(G[3, :9], [1, 0, 0.6, 0.35, 0, 1, 1, 0, 0]), G[3, :9].tolist())
expect("decode(encode) is valid", L.validate(L.decode(G))["valid"])
over = dict(m, edges=m["edges"] + [[0, 4]])
expect("over-constrained rejected", "over-constrained" in (L.validate(over)["error"] or ""))
nond = dict(m, edges=[[0, 1], [1, 3], [2, 3], [3, 4]])
expect("non-dyadic rejected", "non-dyadic" in (L.validate(nond)["error"] or ""))
br = dict(m, nodes=[[0, 0], [1.2, 0], [2.0, 0], [1.6, 0.3], [0.9, 1.9]])
expect("branch defect rejected", "branch defect" in (L.validate(br)["error"] or ""))
C = P[:, m["effector"]]
expect("arc-length protocol: exact path vs itself (reversed) ~ 0", L.compare(C, C[::-1])["chamfer_normalized"] < 0.02)
rot = C @ np.array([[0, -1], [1, 0]]).T * np.array([1, -1])
inv = L.compare(C, rot, invariant=True)
expect("rotation/reflection-invariant CD finds the match", inv["chamfer_invariant"] < 0.02 and inv["chamfer_normalized"] > 0.1, inv)
mech, info = S.synthesize(C, max_nodes=5, seed=0, log=lambda s: None)
expect("synthesis recovers the four-bar path (CD < 0.005), valid and practical",
       info["final"]["chamfer_normalized"] < 0.005 and info["validation"]["valid"] and info["practicality"]["link_ratio"] <= 8,
       f"CD {info['final']['chamfer_normalized']:.5f}")
print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
