"""Run: python tests/test_glu3d.py   (~1-2 min; model smoke tests skipped without torch)"""
import os, sys, tempfile
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import glu3d as G  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

# --- homogenisation against exact answers -------------------------------------------------------
C = G.homogenize(np.ones((6, 6, 6)), 0.3)
check("solid cell returns the material stiffness exactly", np.abs(C - G.iso_D(1, 0.3)).max() < 1e-10)
n = 8; E = np.ones((n, n, n)); E[:, :, n // 2:] = 0.1          # 50/50 laminate stacked along z
C = G.homogenize(E, 0.3)
D1, D2 = G.iso_D(1, .3), G.iso_D(.1, .3)
c33 = 1 / (0.5 / D1[2, 2] + 0.5 / D2[2, 2]); c44 = 1 / (0.5 / D1[3, 3] + 0.5 / D2[3, 3])
r = lambda D: D[0, 2] / D[2, 2]
c11 = 0.5 * (D1[0, 0] - D1[0, 2] * r(D1)) + 0.5 * (D2[0, 0] - D2[0, 2] * r(D2)) \
    + (0.5 * r(D1) + 0.5 * r(D2)) ** 2 * c33
check("laminate C33, C44, C11 match the exact layered-medium formulas",
      all(abs(a / b - 1) < 1e-6 for a, b in [(C[2, 2], c33), (C[3, 3], c44), (C[0, 0], c11)]))

f = G.cell_field({"families": ["gyroid"], "h": 0.25}, 25)
Cg, k, vf, parts = G.cell_stiffness(f)
check("sheet gyroid is cubic-symmetric (E1=E2=E3, no shear coupling)",
      k["E_spread"] < 1e-6 and np.abs(Cg[:3, 3:]).max() < 1e-8)
check(f"sheet gyroid stiffness in the published range (vf {vf:.2f}, E/Es {k['E1']:.3f})",
      0.2 < vf < 0.3 and 0.25 < k["E1"] / vf < 0.45)
fa = G.cell_field({"families": ["gyroid"], "h": 0.25, "freq": [1, 1, 2]}, 33)
_, ka, _, _ = G.cell_stiffness(fa, hres=32)
check(f"two periods along z make the cell anisotropic (E3/E1 = {ka['E3'] / ka['E1']:.2f})",
      G.periodicity(fa) == 0 and ka["E3"] < 0.5 * ka["E1"] and abs(ka["E1"] - ka["E2"]) < 1e-9)
Ct = G.target_C([0.05, 0.06, 0.07], [0.02, 0.021, 0.022], 0.3)
kc = G.constants(Ct)
check("target_C -> constants round trip", abs(kc["E2"] - 0.06) < 1e-9 and abs(kc["G12"] - 0.022) < 1e-9)

# --- geometry, filters, scaling ------------------------------------------------------------------
per = [G.periodicity(G.cell_field({"families": [fam], "h": 0.2}, 33)) for fam in G.FAMILIES]
check(f"all {len(G.FAMILIES)} families are periodic (opposite faces identical)", max(per) == 0)
hy = G.cell_field({"families": ["gyroid", "diamond", "iwp"], "mode": "H3", "t": 0.4, "h": 0.2}, 33)
check("hybrid (Eq. 5) cell is periodic", G.periodicity(hy) == 0)
bar = np.zeros((10, 10, 10), np.uint8); bar[:, 4:6, 4:6] = 1; bar[0:2, :, :] = 0; bar[8:, :, :] = 0
bar[:, 4:6, 4:6] = 0; bar[0:3, 4:6, 4:6] = 1; bar[7:, 4:6, 4:6] = 1        # two pieces joined by the wrap
check("connected components respect periodic wrap", G.periodic_components(bar)[0] == 1)
cube = np.ones((17, 17, 17)); cube[6:11, 6:11, 6:11] = -1               # solid cube floating in void
check("floating material is rejected", not G.printable(cube)[0])
shell = -np.ones((17, 17, 17)); shell[6:11, 6:11, 6:11] = 1             # sealed cavity
check("sealed internal cavity is rejected", G.printable(shell, vmax=1.0)[1].get("reason", "").startswith("closed"))
s = G.tanh_scale(f, 0.75)
check("tanh scaling keeps the zero level set and maps the minimum to -0.75",
      np.array_equal(s < 0, f < 0) and abs(s.min() + 0.75) < 1e-9 and s.max() < 1)

# --- meshes and metrics --------------------------------------------------------------------------
f49 = G.cell_field({"families": ["gyroid"], "h": 0.25}, 49)
try:
    import trimesh  # noqa: F401  (skip mesh checks without it)
    with tempfile.TemporaryDirectory() as d:
        m = G.save_stl(*G.mesh(f49, cell_mm=10, tiles=(2, 1, 1)), os.path.join(d, "x.stl"))
    vbox = 2000 * G.voxels(f49)[:-1, :-1, :-1].mean()
    check(f"tiled STL is watertight with volume = vfrac x box ({m.volume:.0f} vs {vbox:.0f} mm3)",
          m.is_watertight and abs(m.volume / vbox - 1) < 0.03)
    pts = G.surface_points(f, 500)
    check("Chamfer/Hausdorff of a cell with itself are ~0", G.chamfer_hausdorff(pts, pts)[1] == 0)
except ImportError:
    print("SKIP mesh checks (no trimesh)")
check("Dice of identical voxels = 1", G.dice(G.voxels(f), G.voxels(f)) == 1)

# --- dataset, search and models ------------------------------------------------------------------
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "ds.npz")
    info = G.make_dataset(6, 17, p, seed=2, hres=16)
    ds = G.load_dataset(p)
    check("dataset stores fields, C and specs", info["accepted"] == 6 and ds["C"].shape == (6, 6, 6))
    best = G.search({"E1": 0.08, "E2": 0.08, "E3": 0.08}, p, res=17, hres=12, budget=6)
    check("search returns ranked candidates", len(best) >= 1 and
          best[0]["score_log_err"] <= best[-1]["score_log_err"])
    try:
        import torch  # noqa: F401  (skip model checks without it)
        mp = os.path.join(d, "m.pt")
        G.train_diffusion(p, mp, epochs=1, size=16, chans=(1, 4, 8), T=20, batch=3)
        F = G.sample(mp, ds["C"][:2], ds["vfrac"][:2], steps=5)
        check("diffusion samples exactly periodic 3D fields in [-1, 1] (circular padding)",
              F.shape == (2, 17, 17, 17) and np.abs(F).max() <= 1 and all(G.periodicity(f) == 0 for f in F))
        sp = os.path.join(d, "s.pt")
        rep = G.train_surrogate(p, sp, epochs=1, size=16)
        check("surrogate trains (small, < 25k params like the paper's 19.8k)", rep["params"] < 25000)
        G.train_diffusion(p, mp, epochs=1, size=16, chans=(1, 4, 8), T=20, batch=3, surrogate=sp)
        check("diffusion trains with frozen-surrogate guidance", os.path.exists(mp))
    except ImportError:
        print("SKIP models (no torch)")
print(f"\n{ok} checks passed")
