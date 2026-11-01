#!/usr/bin/env python3
"""Query2CAD loop tools (Badagabettu, Yarlagadda, Barati Farimani, arXiv:2406.00144).

  run     python q2c.py run macro.py --out runs/q/v0            headless FreeCAD (freecadcmd) -> STEP/STL + report
  render  python q2c.py render runs/q/v0.stl --out runs/q/v0_iso.png   isometric capture (the paper's feedback image)
  score   python q2c.py score --image runs/q/v0_iso.png --query "..."  VQAScore = P("Yes" | image, question)
  log     python q2c.py log --run runs/q --kind error|model --note "..." [--score 0.93]   budgets + stop rule

Defaults from the paper: error_iter = 3, model refinement iterations = 3, VQA threshold = 0.9.
The paper drove the FreeCAD GUI with PyAutoGUI; here the macro runs headless and exports
geometry, which is then rendered for the caption/VQA feedback step.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ERROR_ITER, MODEL_ITER, THRESH = 3, 3, 0.9

WRAPPER = r'''
import sys, json, traceback
import FreeCAD as App
out = OUT_PREFIX
rep = {"ok": False}
try:
    App.newDocument("q2c")
    exec(compile(open(MACRO).read(), MACRO, "exec"), {"App": App, "FreeCAD": App, "__name__": "__main__"})
    doc = App.ActiveDocument
    doc.recompute()
    import Part, Mesh
    solids = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull() and o.Shape.Volume > 1e-9
              and not any(o in p.OutList for p in doc.Objects if p is not o and hasattr(p, "Shape"))]
    if not solids:
        raise RuntimeError("macro produced no solid objects")
    shape = solids[0].Shape if len(solids) == 1 else solids[0].Shape.fuse([s.Shape for s in solids[1:]])
    shape.exportStep(out + ".step")
    m = Mesh.Mesh(shape.tessellate(0.05)); m.write(out + ".stl")
    bb = shape.BoundBox
    rep = {"ok": True, "objects": [o.Name for o in solids], "valid": shape.isValid(),
           "n_solids": len(shape.Solids), "volume": shape.Volume,
           "bbox": [bb.XLength, bb.YLength, bb.ZLength], "faces": len(shape.Faces)}
except Exception as e:
    rep = {"ok": False, "error_type": type(e).__name__, "error": str(e), "traceback": traceback.format_exc()}
json.dump(rep, open(out + "_report.json", "w"), indent=2)
'''


def freecad_cmd():
    for c in (os.environ.get("FREECAD_CMD"), "freecadcmd", "FreeCADCmd", "freecad.cmd", "FreeCADCmd.exe"):
        if c and shutil.which(c):
            return shutil.which(c)
    return None


def run(macro, out, timeout=120):
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    exe = freecad_cmd()
    if not exe:
        rep = {"ok": False, "error_type": "FreeCADNotFound",
               "error": "freecadcmd not on PATH. Install FreeCAD (conda install -c conda-forge freecad, the AppImage, "
                        "or apt/brew) or set FREECAD_CMD. Fallback: build the same part with the cadsmith-text-to-cad skill."}
        json.dump(rep, open(out + "_report.json", "w"), indent=2)
        return rep
    w = out + "_wrapper.py"
    open(w, "w").write(f"OUT_PREFIX = {os.path.abspath(out)!r}\nMACRO = {os.path.abspath(macro)!r}\n" + WRAPPER)
    try:
        p = subprocess.run([exe, w], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        rep = {"ok": False, "error_type": "Timeout", "error": f"macro exceeded {timeout} s"}
        json.dump(rep, open(out + "_report.json", "w"), indent=2)
        return rep
    finally:
        if os.path.exists(w):
            os.remove(w)
    rp = out + "_report.json"
    if not os.path.exists(rp):
        rep = {"ok": False, "error_type": "FreeCADCrash", "error": (p.stderr or p.stdout)[-2000:]}
        json.dump(rep, open(rp, "w"), indent=2)
        return rep
    return json.load(open(rp))


def render(stl, out, size=900):
    """Isometric capture, as Query2CAD's feedback image (VTK; matplotlib fallback)."""
    import numpy as np
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
        mesh = pv.read(stl)
        p = pv.Plotter(off_screen=True, window_size=(size, size))
        p.set_background("white")
        p.add_mesh(mesh, color="#b8c4d6", specular=0.3, smooth_shading=False)
        p.add_mesh(mesh.extract_feature_edges(30), color="#333333", line_width=1.5)
        p.camera_position = "iso"
        p.camera.zoom(0.9)
        p.screenshot(out)
        p.close()
    except Exception:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import trimesh
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        m = trimesh.load(stl, force="mesh")
        cam = np.array([1, 1, 1]) / np.sqrt(3)
        vis = m.face_normals @ cam > 0
        fig = plt.figure(figsize=(6, 6)); ax = fig.add_subplot(projection="3d")
        sh = 0.35 + 0.6 * np.clip(m.face_normals[vis] @ cam, 0, 1)
        ax.add_collection3d(Poly3DCollection(m.triangles[vis], facecolors=np.c_[sh * .7, sh * .77, sh * .85, np.ones_like(sh)]))
        lo, hi = m.bounds
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(np.maximum(hi - lo, 1e-3)); ax.view_init(35.26, 45); ax.set_axis_off()
        fig.savefig(out, dpi=150, facecolor="white")
    return out


def score(image, query):
    """VQAScore with CLIP-FlanT5-XL (paper) via t2v_metrics, if installed."""
    question = f"Does this figure show {query}? Please answer yes or no."
    try:
        import t2v_metrics
        model = t2v_metrics.VQAScore(model="clip-flant5-xl")
        s = float(model(images=[image], texts=[query]).item())
        return {"vqascore": s, "model": "clip-flant5-xl", "question": question, "passed": s >= THRESH}
    except Exception as e:
        return {"vqascore": None, "question": question, "threshold": THRESH,
                "note": f"t2v_metrics unavailable ({type(e).__name__}). Answer the question yourself from the image as a "
                        "calibrated probability of 'Yes' (0-1) and log it with --score, labelled 'agent-judged'. "
                        "Install: pip install t2v-metrics (downloads CLIP-FlanT5-XL, ~3B params)."}


def log(run_dir, kind, note, sc=None, judged_by=None):
    os.makedirs(run_dir, exist_ok=True)
    p = os.path.join(run_dir, "ledger.jsonl")
    rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    row = {"kind": kind, "note": note, "score": sc, "judged_by": judged_by}
    rows.append(row)
    open(p, "a").write(json.dumps(row) + "\n")
    # error iterations reset whenever a model refinement starts a new macro version
    since_model = 0
    for r in reversed(rows):
        if r["kind"] == "model":
            break
        since_model += r["kind"] == "error"
    n_model = sum(r["kind"] == "model" for r in rows)
    scores = [r["score"] for r in rows if r["score"] is not None]
    st = {"error_iters_this_version": since_model, "error_left": ERROR_ITER - since_model,
          "model_refinements": n_model, "model_left": MODEL_ITER - n_model,
          "best_score": max(scores) if scores else None, "threshold": THRESH}
    if sc is not None and sc >= THRESH:
        st["stop"] = "VQA score crossed threshold: accept this model"
    elif since_model > ERROR_ITER:
        st["stop"] = "error refinement budget exhausted: failure = non-executable macro (the paper's dominant failure mode)"
    elif n_model > MODEL_ITER:
        st["stop"] = "model refinement budget exhausted: return best-scoring version"
    else:
        st["next"] = "error refinement" if kind == "error" else "model refinement (caption -> diff -> revised macro)"
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("run"); s.add_argument("macro"); s.add_argument("--out", required=True); s.add_argument("--timeout", type=int, default=120)
    s = sub.add_parser("render"); s.add_argument("stl"); s.add_argument("--out", required=True)
    s = sub.add_parser("score"); s.add_argument("--image", required=True); s.add_argument("--query", required=True)
    s = sub.add_parser("log"); s.add_argument("--run", required=True); s.add_argument("--kind", choices=["error", "model", "accept"], required=True)
    s.add_argument("--note", required=True); s.add_argument("--score", type=float); s.add_argument("--judged-by")
    a = ap.parse_args()
    if a.cmd == "run": r = run(a.macro, a.out, a.timeout)
    elif a.cmd == "render": r = {"image": render(a.stl, a.out)}
    elif a.cmd == "score": r = score(a.image, a.query)
    else: r = log(a.run, a.kind, a.note, a.score, a.judged_by)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
