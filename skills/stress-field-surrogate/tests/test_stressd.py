"""Run: python tests/test_stressd.py   (~1 min; model smoke tests skipped without torch)"""
import math, os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import stressd as S  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

# FEM vs Euler-Bernoulli on a slender strip: sigma_x = 6 P (L - x) / (t h^2) at the outer element centres
for h in (8, 12):
    g = np.zeros((S.NY, S.NX), bool); r0 = S.NY // 2 - h // 2; g[r0:r0 + h, :] = True
    sx, sy, _ = S.solve_unit(g)
    fem = np.abs(sy[r0:r0 + h, 16, 0]).max()
    th = 6 * (S.NX - 16.5) / h ** 2 * (h / 2 - 0.5) / (h / 2)
    check(f"Q4 FEM matches beam theory (h={h}: {fem / th:.3f})", abs(fem / th - 1) < 0.02)
g = S.random_geometry(np.random.default_rng(3), 1)
sx, sy, _ = S.solve_unit(g)
v1 = S.von_mises(sx * 0 + sy * 50) ; v2 = S.von_mises(sy * 100)
check("linear in load magnitude", np.allclose(v2, 2 * v1))
check("geometry stays connected to the clamp", S.keep_connected(g).sum() == g.sum())
c = S.channels(g, 90, 40)
check("5-channel input (geometry, BCx, BCy, Fx, Fy)", c.shape == (5, S.NY, S.NX) and c[2, :, 0].min() == -1 and abs(c[4].max() - 40) < 1e-6)
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "c.npz")
    info = S.dataset(p, n_geoms=6, angles=8, mags=3)
    check("dataset size = geoms x angles x mags", info["cases"] == 6 * 8 * 3)
    dd = np.load(p)
    tr, te = S.split(dd["geom"], "geometry")
    check("geometry split shares no geometry", not set(dd["geom"][tr]) & set(dd["geom"][te]))
    tr2, te2 = S.split(dd["geom"], "random")
    check("random split shares geometries (the leakage the paper's split has)", bool(set(dd["geom"][tr2]) & set(dd["geom"][te2])))
    m = S.metrics(dd["y"][:10], dd["y"][:10])
    check("metrics zero on perfect prediction", m["MAE_MPa"] == 0 and m["MAPE_peak_pct"] == 0)
    try:
        import torch  # noqa: F401
        for kind in ("regression", "diffusion"):
            S.train(p, kind, os.path.join(d, f"{kind}.pt"), epochs=1, T=20, base=8)
            r = S.predict(os.path.join(d, f"{kind}.pt"), p, os.path.join(d, f"{kind}_p.npz"), steps=5)
            q = np.load(os.path.join(d, f"{kind}_p.npz"))
            check(f"{kind} trains and predicts non-negative stress on test geometries", q["pred"].shape[0] == r["cases"] and q["pred"].min() >= 0)
        UNet, ScaleNet = S.torch_parts()
        import torch as T
        check("scale network runs on 32x24 inputs", ScaleNet()(T.zeros(2, 5, S.NY, S.NX)).shape == (2,))
    except ImportError:
        print("SKIP models (no torch)")
print(f"\n{ok} checks passed")
