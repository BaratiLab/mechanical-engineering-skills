#!/usr/bin/env python3
"""Regression test: sketch -> silhouette -> G-code -> keypoints -> re-emit.  python tests/test_i2g.py"""
import json, os, subprocess, sys, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import i2g  # noqa: E402
FAILS = []
def expect(n, c, i=""):
    print(("PASS " if c else "FAIL ") + n + (f"  {i}" if i else "")); FAILS.append(n) if not c else None
t = tempfile.mkdtemp()
sk = os.path.join(t, "sketch.png"); subprocess.run([sys.executable, os.path.join(HERE, "..", "examples", "make_sketch.py"), sk], check=True)
i2g.preprocess(sk, os.path.join(t, "sil.png"))
g = i2g.generate(os.path.join(t, "sil.png"), os.path.join(t, "p.gcode"), size_mm=60, layers=15)
# true drawn area: stadium (r=130 px, 300 px straight) - hole (r=55) - slot (170x60), at 60 mm / 560 px
s = 60 / 560; truth = (np.pi * 130**2 + 300 * 260 - np.pi * 55**2 - 170 * 60) * s * s
expect("toolpath area within 2% of the drawn part", abs(g["area_mm2"] / truth - 1) < 0.02, f"{g['area_mm2']:.1f} vs {truth:.1f} mm2")
v = i2g.validate(os.path.join(t, "p.gcode"))
expect("G-code validates (bounds, monotonic E, layers)", v["ok"] and v["layers"] == 15, v["issues"])
L, _ = i2g.parse_gcode(os.path.join(HERE, "..", "examples", "tricky_modes.gcode"))
expect("parser: M82 + mid-layer G92 + G91 travel + M83", np.allclose(L[0]["kp"][-1], [5, 10, 3.5]) and np.allclose(L[1]["kp"][-1], [0, 0, 3.8]))
kn, p = i2g.normalize(L[0]["kp"])
expect("normalization: XY aspect preserved, E in [-1,1]", np.isclose(kn[:, 0].max(), 1) and np.isclose(kn[:, 1].max(), 2 / 3) and np.isclose(kn[:, 2].min(), -1))
i2g.to_keypoints(os.path.join(t, "p.gcode"), os.path.join(t, "kp.npz"))
i2g.emit(os.path.join(t, "kp.npz"), 0, os.path.join(t, "re.gcode"))
L0, _ = i2g.parse_gcode(os.path.join(t, "p.gcode")); L1, _ = i2g.parse_gcode(os.path.join(t, "re.gcode"))
expect("keypoints -> emit round-trip reproduces layer 0", np.allclose(L0[0]["kp"][:, :2], L1[0]["kp"][:, :2], atol=1e-3) and
       np.isclose(L0[0]["kp"][-1, 2] - L0[0]["kp"][0, 2], L1[0]["kp"][-1, 2] - L1[0]["kp"][0, 2], rtol=1e-3))
print("\nALL PASSED" if not FAILS else f"\n{len(FAILS)} FAILED: {FAILS}"); sys.exit(1 if FAILS else 0)
