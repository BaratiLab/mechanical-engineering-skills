#!/usr/bin/env python3
"""Run a CadQuery part script and export STEP, STL, SVG preview, and a properties report.

The part script must define `result` (a cq.Workplane or cq.Shape) and may
define a dict `PARAMS` describing its parameters.

  python build_part.py part.py --out out/flange [--set bore=22 --set n_bolts=6]
"""
import argparse
import json
import os
import runpy
import sys


def render_preview(shape, path):
    """Shaded isometric + top + front views from the tessellated solid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    verts, tris = shape.tessellate(0.05, 0.2)
    V = np.array([v.toTuple() for v in verts])
    T = np.array(tris)
    faces = V[T]
    n = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    fig = plt.figure(figsize=(12, 4.2))
    views = [("Isometric", 30, -55), ("Top (+Z)", 90, -90), ("Front (-Y)", 0, -90)]
    lo, hi = V.min(0), V.max(0)
    for k, (title, el, az) in enumerate(views):
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        e, z = np.radians(el), np.radians(az)
        cam = np.array([np.cos(e) * np.cos(z), np.cos(e) * np.sin(z), np.sin(e)])
        light = cam + np.array([0.3, 0.2, 0.6])
        light /= np.linalg.norm(light)
        shade = 0.35 + 0.65 * np.abs(n @ light)
        col = np.c_[0.30 * shade, 0.45 * shade, 0.65 * shade, np.ones_like(shade)]
        ax.add_collection3d(Poly3DCollection(faces, facecolors=col, edgecolors="none"))
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(np.maximum(hi - lo, 1e-3))
        ax.view_init(elev=el, azim=az)
        ax.set_title(title)
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("script")
    p.add_argument("--out", required=True, help="output path prefix")
    p.add_argument("--set", action="append", default=[], help="override PARAM=value")
    a = p.parse_args()
    try:
        import cadquery as cq
    except ImportError:
        sys.exit("cadquery missing: pip install cadquery")

    overrides = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        overrides[k] = v
    ns = runpy.run_path(a.script, init_globals={"OVERRIDES": overrides})
    result = ns["result"]
    shape = result.val() if isinstance(result, cq.Workplane) else result
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)

    cq.exporters.export(result, a.out + ".step")
    cq.exporters.export(result, a.out + ".stl", tolerance=0.01, angularTolerance=0.1)
    render_preview(shape, a.out + "_preview.png")

    bb = shape.BoundingBox()
    report = {
        "params": ns.get("PARAMS", {}) | overrides,
        "valid": shape.isValid(),
        "n_solids": len(shape.Solids()),
        "volume_mm3": shape.Volume(),
        "surface_area_mm2": shape.Area(),
        "bbox_mm": {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen},
        "center_of_mass": list(shape.Center().toTuple()),
        "files": [a.out + e for e in (".step", ".stl", "_preview.png")],
    }
    dens = ns.get("DENSITY_KG_M3")
    if dens:
        report["mass_kg"] = shape.Volume() * 1e-9 * dens
    with open(a.out + "_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    if not report["valid"] or report["n_solids"] != 1:
        print("WARNING: geometry invalid or not a single solid", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
