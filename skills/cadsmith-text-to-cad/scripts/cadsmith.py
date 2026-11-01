#!/usr/bin/env python3
"""CADSmith tool belt (Barkley, Loghmani, Barati Farimani, arXiv:2603.26512).

  execute  python cadsmith.py execute part.py --out out/part          sandboxed run (60 s), STEP/STL, kernel metrics
  check    python cadsmith.py check  --plan plan.json --metrics out/part_metrics.json   deterministic plan-vs-kernel
  render   python cadsmith.py render out/part.stl --out out/part_views.png              3-view judge image
  kb       python cadsmith.py kb "fillet radius boolean" [--errors traceback.txt]      keyword RAG over KB1/KB2
  eval     python cadsmith.py eval gen.stl ref.stl                     CD / F1@1mm / IoU@1mm after ICP
  log      python cadsmith.py log --run runs/x --stage outer --note "..." [--passed]   loop ledger + budgets

A part script must assign `result` (cq.Workplane or Shape). Everything here is deterministic;
the agent supplies Planner/Coder/Refiner reasoning and an INDEPENDENT judge supplies the verdict.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "references")

RUNNER = r'''
import json, sys, traceback, runpy
out = sys.argv[2]
try:
    import cadquery as cq
    ns = runpy.run_path(sys.argv[1])
    res = ns.get("result")
    if res is None:
        raise RuntimeError("script did not assign `result`")
    shape = res.val() if isinstance(res, cq.Workplane) else res
    if isinstance(res, cq.Workplane) and len(res.vals()) > 1:
        shape = cq.Compound.makeCompound([v for v in res.vals() if isinstance(v, cq.Shape)])
    cq.exporters.export(res if isinstance(res, cq.Workplane) else cq.Workplane().add(shape), out + ".step")
    cq.exporters.export(res if isinstance(res, cq.Workplane) else cq.Workplane().add(shape), out + ".stl",
                        tolerance=0.01, angularTolerance=0.1)
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    _b = Bnd_Box(); BRepBndLib.AddOptimal_s(shape.wrapped, _b, False, False)
    x0, y0, z0, x1, y1, z1 = _b.Get()  # tight (optimal) box, not the tolerance-inflated default
    solids = shape.Solids()
    m = {"ok": True, "valid": bool(shape.isValid()), "n_solids": len(solids),
         "volume": shape.Volume(), "area": shape.Area(),
         "bbox": {"xlen": x1 - x0, "ylen": y1 - y0, "zlen": z1 - z0,
                  "min": [x0, y0, z0], "max": [x1, y1, z1]},
         "center_of_mass": list(cq.Shape.centerOfMass(shape).toTuple()),
         "faces": len(shape.Faces()), "edges": len(shape.Edges()), "vertices": len(shape.Vertices())}
    cyl = []
    for f in shape.Faces():
        if f.geomType() == "CYLINDER":
            try:
                cyl.append(round(f._geomAdaptor().Cylinder().Radius() * 2, 4))
            except Exception:
                pass
    m["cylindrical_face_diameters"] = sorted(cyl)
    m["watertight"] = m["valid"] and m["n_solids"] >= 1
    json.dump(m, open(out + "_metrics.json", "w"), indent=2)
    print(json.dumps(m))
except Exception as e:
    tb = traceback.format_exc()
    json.dump({"ok": False, "error_type": type(e).__name__, "error": str(e), "traceback": tb},
              open(out + "_metrics.json", "w"), indent=2)
    print(json.dumps({"ok": False, "error_type": type(e).__name__, "error": str(e)}))
    sys.exit(3)
'''


# ------------------------------------------------------------------ execute
def execute(script, out, timeout=60):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    runner = out + "_runner.py"
    open(runner, "w").write(RUNNER)
    try:
        p = subprocess.run([sys.executable, "-I", runner, os.path.abspath(script), os.path.abspath(out)],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        res = {"ok": False, "error_type": "Timeout", "error": f"execution exceeded {timeout} s"}
        json.dump(res, open(out + "_metrics.json", "w"), indent=2)
        return res
    finally:
        os.remove(runner)
    return json.load(open(out + "_metrics.json"))


# ------------------------------------------------------------------ check
def check(plan, m, tol_abs=0.5, tol_rel=0.01):
    """Deterministic plan-vs-kernel comparison. Hard fail if solid is not valid."""
    issues, ok = [], True
    if not m.get("ok"):
        return {"hard_fail": True, "passed": False, "issues": [f"execution failed: {m.get('error_type')}: {m.get('error')}"]}
    if not m["valid"] or m["n_solids"] < 1:
        return {"hard_fail": True, "passed": False, "issues": ["solid is not valid / not watertight (hard kernel check)"]}
    tb = plan.get("target_bbox")
    if tb:
        got = [m["bbox"]["xlen"], m["bbox"]["ylen"], m["bbox"]["zlen"]]
        for ax, t, g in zip("xyz", tb, got):
            if t is None:
                continue
            if abs(g - t) > max(tol_abs, tol_rel * t):
                ok = False
                issues.append(f"bbox {ax}: got {g:.3f} mm, target {t} mm (diff {g - t:+.3f})")
    if "n_solids" in plan and m["n_solids"] != plan["n_solids"]:
        ok = False
        issues.append(f"solid count {m['n_solids']} != expected {plan['n_solids']} (disconnected bodies / gaps?)")
    for h in plan.get("holes", []):
        d, n = h["diameter"], h["count"]
        found = sum(1 for x in m["cylindrical_face_diameters"] if abs(x - d) < 0.02)
        if found < n:
            ok = False
            issues.append(f"holes Ø{d}: found {found} cylindrical faces, expected ≥{n}")
    vr = plan.get("volume_range")
    if vr and not (vr[0] <= m["volume"] <= vr[1]):
        ok = False
        issues.append(f"volume {m['volume']:.1f} outside expected {vr}")
    return {"hard_fail": False, "passed": ok, "issues": issues,
            "note": "Kernel checks are necessary, not sufficient: the visual judge must still confirm shape and feature placement."}


# ------------------------------------------------------------------ render
VIEWS = [("Isometric", 35, 45), ("High-angle rear", 65, 220), ("Front profile", 10, 0)]


def render(stl, out, size=(2400, 800)):
    """VTK (z-buffered, Phong) when available, as in the paper; matplotlib fallback."""
    try:
        return render_vtk(stl, out, size)
    except Exception as e:  # no VTK / no off-screen context
        print(f"[render] VTK unavailable ({type(e).__name__}); using matplotlib fallback", file=sys.stderr)
        return render_mpl(stl, out, size)


def render_vtk(stl, out, size=(2400, 800)):
    import numpy as np
    import pyvista as pv
    from PIL import Image, ImageDraw
    pv.OFF_SCREEN = True
    mesh = pv.read(stl)
    c = np.array(mesh.center)
    r = np.linalg.norm(np.array(mesh.bounds[1::2]) - np.array(mesh.bounds[::2])) * 1.6
    w = size[0] // 3
    tiles = []
    for title, el, az in VIEWS:
        p = pv.Plotter(off_screen=True, window_size=(w, size[1]))
        p.set_background("white")
        p.add_mesh(mesh, color="#7f9cc9", smooth_shading=False, specular=0.3, specular_power=20,
                   ambient=0.2, diffuse=0.8, interpolation="phong", show_edges=False)
        e, z = np.radians(el), np.radians(az)
        d = np.array([np.cos(e) * np.cos(z), np.cos(e) * np.sin(z), np.sin(e)])
        p.camera.position = tuple(c + r * d)
        p.camera.focal_point = tuple(c)
        p.camera.up = (0, 0, 1) if abs(el) < 89 else (0, 1, 0)
        p.reset_camera_clipping_range()
        img = Image.fromarray(p.screenshot(return_img=True))
        p.close()
        ImageDraw.Draw(img).text((12, 10), f"{title} (el {el}, az {az})", fill=(30, 30, 30))
        tiles.append(img)
    canvas = Image.new("RGB", size, "white")
    for i, t in enumerate(tiles):
        canvas.paste(t, (i * w, 0))
    canvas.save(out)
    return out


def render_mpl(stl, out, size=(2400, 800)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    mesh = trimesh.load(stl, force="mesh")
    F = mesh.triangles
    n = mesh.face_normals
    lo, hi = mesh.bounds
    fig = plt.figure(figsize=(size[0] / 200, size[1] / 200), dpi=200)
    for k, (title, el, az) in enumerate(VIEWS):
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        e, z = np.radians(el), np.radians(az)
        cam = np.array([np.cos(e) * np.cos(z), np.cos(e) * np.sin(z), np.sin(e)])
        light = cam + np.array([0.3, 0.2, 0.6]); light /= np.linalg.norm(light)
        vis = n @ cam > 1e-6  # back-face culling: hidden interior faces must not paint over the surface
        Fv, nv = F[vis], n[vis]
        diff = np.clip(nv @ light, 0, 1)
        spec = np.clip(nv @ ((light + cam) / np.linalg.norm(light + cam)), 0, 1) ** 20  # Phong-like
        shade = np.clip(0.25 + 0.65 * diff + 0.25 * spec, 0, 1)
        col = np.c_[0.35 * shade + 0.1, 0.5 * shade + 0.1, 0.75 * shade + 0.1, np.ones_like(shade)]
        pc = Poly3DCollection(Fv, facecolors=np.clip(col, 0, 1), edgecolors="none")
        ax.add_collection3d(pc)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(np.maximum(hi - lo, 1e-3))
        ax.view_init(elev=el, azim=az)
        ax.set_title(f"{title} (el {el}°, az {az}°)", fontsize=8)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    return out


# ------------------------------------------------------------------ KB retrieval
def kb(query, errors_text=None, k=6):
    words = set(re.findall(r"[a-z_]{3,}", (query + " " + (errors_text or "")).lower()))
    api = open(os.path.join(REF, "kb_api.md")).read().split("\n### ")[1:]
    scored = []
    for sec in api:
        head, body = sec.split("\n", 1)
        kw = set(re.findall(r"[a-z_]{3,}", (head + " " + body[:400]).lower()))
        s = len(words & kw)
        if s:
            scored.append((s, "### " + head + "\n" + body.strip()))
    scored.sort(key=lambda x: -x[0])
    out = {"api": [t for _, t in scored[:k]]}
    if errors_text:
        pats = json.load(open(os.path.join(REF, "kb_errors.json")))
        hits = []
        low = errors_text.lower()
        for p in pats:
            s = sum(1 for t in p["triggers"] if t.lower() in low)
            if s:
                hits.append((s, p))
        hits.sort(key=lambda x: -x[0])
        out["error_patterns"] = [p for _, p in hits[:3]]
    return out


# ------------------------------------------------------------------ eval metrics
def eval_metrics(gen, ref, n=10000, tau=1.0, voxel=1.0, seed=0):
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
    A = trimesh.load(gen, force="mesh"); B = trimesh.load(ref, force="mesh")
    A.apply_translation(-A.bounds.mean(0)); B.apply_translation(-B.bounds.mean(0))
    pa, _ = trimesh.sample.sample_surface(A, n, seed=seed)
    pb, _ = trimesh.sample.sample_surface(B, n, seed=seed + 1)
    try:
        M, _, _ = trimesh.registration.icp(pa, pb, max_iterations=50, reflection=False, scale=False)
        A.apply_transform(M)
        pa = trimesh.transformations.transform_points(pa, M)
    except Exception:
        pass
    da, _ = cKDTree(pb).query(pa); db, _ = cKDTree(pa).query(pb)
    cd = float(np.mean(da ** 2) + np.mean(db ** 2))  # bidirectional squared NN distance (sum of means)
    prec, rec = float(np.mean(da < tau)), float(np.mean(db < tau))
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    ext = max(np.ptp(np.r_[A.bounds, B.bounds], axis=0))
    pitch = voxel if ext <= 100 else voxel * ext / 100  # adaptive coarsening
    lo = np.minimum(A.bounds[0], B.bounds[0]) - pitch

    def occ(mesh):  # filled voxel occupancy as a set of global grid indices
        v = mesh.voxelized(pitch).fill()
        return set(map(tuple, np.round((v.points - lo) / pitch).astype(int)))

    va, vb = occ(A), occ(B)
    iou = float(len(va & vb) / max(len(va | vb), 1))
    # sampling noise floor: the reference against itself with independent samples.
    # Identical parts cannot score CD=0 / F1=1 at 10k points; judge results relative to this.
    q1, _ = trimesh.sample.sample_surface(B, n, seed=seed + 2)
    q2, _ = trimesh.sample.sample_surface(B, n, seed=seed + 3)
    f1a, _ = cKDTree(q2).query(q1); f1b, _ = cKDTree(q1).query(q2)
    pf, rf = float(np.mean(f1a < tau)), float(np.mean(f1b < tau))
    floor = {"chamfer_distance": float(np.mean(f1a ** 2) + np.mean(f1b ** 2)),
             "f1": 2 * pf * rf / (pf + rf) if pf + rf else 0.0}
    return {"chamfer_distance": cd, "f1": f1, "precision": prec, "recall": rec, "iou": iou,
            "noise_floor_ref_vs_ref": floor,
            "tau_mm": tau, "voxel_mm": pitch, "space": "absolute mm, bbox-centered + ICP"}


# ------------------------------------------------------------------ ledger
def log(run, stage, note, passed, code=None):
    os.makedirs(run, exist_ok=True)
    p = os.path.join(run, "ledger.jsonl")
    rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    inner = sum(1 for r in rows if r["stage"] == "inner")
    outer = sum(1 for r in rows if r["stage"] == "outer")
    row = {"stage": stage, "note": note, "passed": passed,
           "inner_n": inner + (stage == "inner"), "outer_n": outer + (stage == "outer")}
    if code:
        row["code_sha"] = __import__("hashlib").sha1(open(code, "rb").read()).hexdigest()[:10]
    open(p, "a").write(json.dumps(row) + "\n")
    budget = {"inner_left": 3 - row["inner_n"], "outer_left": 5 - row["outer_n"],
              "escalate": row["outer_n"] >= 3,
              "escalation_hint": "Change construction strategy (different primitives/order/workplanes), "
                                 "do not keep nudging the same parameters." if row["outer_n"] >= 3 else None,
              "history": [r["note"] for r in rows[-4:]] + [note]}
    if budget["inner_left"] < 0:
        budget["stop"] = "inner loop exhausted (3 error repairs): report CODE_EXECUTION_FAILURE"
    if budget["outer_left"] < 0:
        budget["stop"] = "outer loop exhausted (5 refinements): return best attempt, flag as unconverged"
    return row | budget


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("execute"); s.add_argument("script"); s.add_argument("--out", required=True); s.add_argument("--timeout", type=int, default=60)
    s = sub.add_parser("check"); s.add_argument("--plan", required=True); s.add_argument("--metrics", required=True)
    s = sub.add_parser("render"); s.add_argument("stl"); s.add_argument("--out", required=True)
    s = sub.add_parser("kb"); s.add_argument("query"); s.add_argument("--errors")
    s = sub.add_parser("eval"); s.add_argument("gen"); s.add_argument("ref")
    s = sub.add_parser("log"); s.add_argument("--run", required=True); s.add_argument("--stage", choices=["inner", "outer"], required=True)
    s.add_argument("--note", required=True); s.add_argument("--passed", action="store_true"); s.add_argument("--code")
    a = ap.parse_args()
    if a.cmd == "execute":
        r = execute(a.script, a.out, a.timeout)
    elif a.cmd == "check":
        r = check(json.load(open(a.plan)), json.load(open(a.metrics)))
    elif a.cmd == "render":
        r = {"image": render(a.stl, a.out)}
    elif a.cmd == "kb":
        r = kb(a.query, open(a.errors).read() if a.errors else None)
        for t in r["api"]:
            print(t, "\n")
        for p in r.get("error_patterns", []):
            print(json.dumps(p, indent=2))
        return
    elif a.cmd == "eval":
        r = eval_metrics(a.gen, a.ref)
    else:
        r = log(a.run, a.stage, a.note, a.passed, a.code)
    print(json.dumps(r, indent=2))
    if a.cmd == "execute" and not r.get("ok"):
        sys.exit(3)


if __name__ == "__main__":
    main()
