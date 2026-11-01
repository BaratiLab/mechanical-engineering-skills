#!/usr/bin/env python3
"""AgentsCAD toolkit: STEP -> LLM-readable blackboard -> grounded orientation tools ->
programmatic DFAM modifications -> verification (George, Keefe, Pak, Barati Farimani, arXiv:2607.02448).

  analyze      python dfam.py analyze part.step --out bb.json             faces / links / overhangs JSON
  orient       python dfam.py orient part.step --rx 90 --ry 0             check_orientation_overhangs
  lay          python dfam.py lay part.step --face 6                      lay_face_to_build_surface
  candidates   python dfam.py candidates part.step                        scripted orientation sub-phase (<=4)
  modify       python dfam.py modify part.step --plan mods.json --out new.step
  verify       python dfam.py verify part.step new.step --plan mods.json --out verify   (+ 2x2 render, VLM questions)
  memory       python dfam.py memory add|query --bb bb.json [--decision mods.json] [--store mem.jsonl]

Build direction is +Z, bed at the part's minimum Z. A face is an OVERHANG when it faces
downward more steeply than the threshold (default 45 deg from vertical) and is not on the bed.
Horizontal concave cylinders (bores) are flagged because their crown is an unsupported arch.
Rotations are applied as Rx then Ry (degrees) about the part's bounding-box centre.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

THRESH = 45.0
MIN_ACTIONABLE_BORE_D = 5.0  # mm; smaller horizontal holes usually bridge acceptably


def cq():
    import cadquery
    return cadquery


def load(path):
    return cq().importers.importStep(path).val()


def rot_matrix(rx, ry):
    a, b = math.radians(rx), math.radians(ry)
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    return Ry @ Rx  # Rx applied first


def rotate_shape(shape, rx, ry):
    C = cq()
    c = shape.BoundingBox().center
    s = shape
    if rx:
        s = s.rotate(c, c + C.Vector(1, 0, 0), rx)
    if ry:
        s = s.rotate(c, c + C.Vector(0, 1, 0), ry)
    return s


def face_props(f, i):
    """Per-face record from the paper: type, area, centroid, tilt angles, radius of gyration, elongation."""
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    t = f.geomType()
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(f.wrapped, g)
    area = g.Mass()
    c = g.CentreOfMass()
    M = g.MatrixOfInertia()
    I = sorted(np.linalg.eigvalsh(np.array([[M.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])).tolist())
    rg = math.sqrt(max(I[1], 0) / area) if area > 0 else 0.0
    elong = math.sqrt(I[2] / I[1]) if I[1] > 1e-12 else 1.0
    rec = {"id": i, "surface_type": {"PLANE": "Planar", "CYLINDER": "Cylinder", "CONE": "Cone"}.get(t, t.title()),
           "area_mm2": round(area, 3), "centroid": [round(c.X(), 3), round(c.Y(), 3), round(c.Z(), 3)],
           "radius_of_gyration_mm": round(rg, 3), "elongation_index": round(elong, 3)}
    if t == "PLANE":
        n = f.normalAt()
        n = np.array([n.x, n.y, n.z])
        rec["normal"] = [round(x, 4) for x in n]
        rec["tilt_about_x_deg"] = round(math.degrees(math.atan2(n[1], n[2])), 2)
        rec["tilt_about_y_deg"] = round(math.degrees(math.atan2(n[0], n[2])), 2)
    elif t == "CYLINDER":
        cyl = f._geomAdaptor().Cylinder()
        ax = cyl.Axis()
        d, p = ax.Direction(), ax.Location()
        axis = np.array([d.X(), d.Y(), d.Z()])
        loc = np.array([p.X(), p.Y(), p.Z()])
        from OCP.BRepTools import BRepTools
        from OCP.BRepGProp import BRepGProp_Face
        from OCP.gp import gp_Pnt, gp_Vec
        u0, u1, v0, v1 = BRepTools.UVBounds_s(f.wrapped)
        P, N = gp_Pnt(), gp_Vec()
        BRepGProp_Face(f.wrapped).Normal((u0 + u1) / 2, (v0 + v1) / 2, P, N)  # orientation-aware normal
        pm = np.array([P.X(), P.Y(), P.Z()])
        radial = (pm - loc) - axis * np.dot(pm - loc, axis)
        concave = float(np.dot([N.X(), N.Y(), N.Z()], radial)) < 0
        vs = np.array([[v.X, v.Y, v.Z] for v in f.Vertices()]) if f.Vertices() else pm[None]
        proj = (vs - loc) @ axis
        # sample the face's own normals (trim-aware 17x5 UV grid) for the downward-facing fraction
        from OCP.BRepClass import BRepClass_FaceClassifier
        from OCP.gp import gp_Pnt2d
        from OCP.TopAbs import TopAbs_IN, TopAbs_ON
        nz, gf = [], BRepGProp_Face(f.wrapped)
        for uu in np.linspace(u0, u1, 17):
            for vv in np.linspace(v0, v1, 5):
                if BRepClass_FaceClassifier(f.wrapped, gp_Pnt2d(uu, vv), 1e-6).State() not in (TopAbs_IN, TopAbs_ON):
                    continue
                q, w = gp_Pnt(), gp_Vec()
                gf.Normal(uu, vv, q, w)
                if w.Magnitude() > 0:
                    nz.append(w.Z() / w.Magnitude())
        rec["sampled_normal_z"] = [round(x, 4) for x in nz]
        rec |= {"radius_mm": round(cyl.Radius(), 4), "axis": [round(x, 4) for x in axis],
                "axis_point": [round(x, 4) for x in loc], "concave_hole": concave,
                "axial_span": [round(float(proj.min()), 4), round(float(proj.max()), 4)]}
    return rec


def links(shape):
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    faces = shape.Faces()
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape.wrapped, TopAbs_EDGE, TopAbs_FACE, m)
    out = set()
    for k in range(1, m.Extent() + 1):
        anc = [x for x in m.FindFromIndex(k)]
        ids = sorted({next(i for i, f in enumerate(faces) if f.wrapped.IsSame(a)) for a in anc})
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                out.add((ids[x], ids[y]))
    return [{"a": a, "b": b, "relation": "adjacent_to"} for a, b in sorted(out)]


def overhangs(recs, zmin, thresh=THRESH, up=np.array([0, 0, 1.0])):
    """Rule-based (deterministic floor): the LLM never has to reproduce this."""
    out = []
    for r in recs:
        if r["surface_type"] == "Planar":
            n = np.array(r["normal"])
            nz = float(n @ up)
            ang = math.degrees(math.asin(max(-1, min(1, -nz)))) if nz < 0 else 0.0  # 90 = flat ceiling
            on_bed = nz < -0.999 and abs(np.dot(r["centroid"], up) - zmin) < 0.05
            if ang > thresh + 0.5 and not on_bed:  # 0.5 deg tolerance: exact 45 deg teardrop flanks are printable
                out.append({"face_id": r["id"], "kind": "downward_planar", "overhang_deg": round(ang, 1),
                            "area_mm2": r["area_mm2"], "actionable": True})
        elif r["surface_type"] == "Cylinder" and r.get("concave_hole"):
            ax = np.array(r["axis"])
            tilt = math.degrees(math.acos(min(1, abs(float(ax @ up)))))  # 90 = horizontal bore
            nzs = np.array(r.get("sampled_normal_z") or [-1.0])  # sampled in the analysed (rotated) frame
            down_frac = float(np.mean(nzs < -math.sin(math.radians(thresh + 0.5))))
            if tilt > thresh and down_frac > 0.02:  # the crown (downward-facing arc) is still present
                d = 2 * r["radius_mm"]
                out.append({"face_id": r["id"], "kind": "horizontal_bore", "overhang_deg": -round(tilt, 1),
                            "diameter_mm": d, "area_mm2": round(r["area_mm2"] * down_frac, 3),
                            "downward_fraction": round(down_frac, 3),
                            "actionable": d >= MIN_ACTIONABLE_BORE_D,
                            "suggested_fix": "teardrop" if d >= MIN_ACTIONABLE_BORE_D else "bridge OK"})
    return out


def feature_hints(recs, lk):
    """Light-weight stand-in for the GraphSAGE labels: topology rules an engineer would apply."""
    adj = {}
    for l in lk:
        adj.setdefault(l["a"], set()).add(l["b"]); adj.setdefault(l["b"], set()).add(l["a"])
    hints = {}
    for r in recs:
        if r["surface_type"] == "Cylinder":
            hints[r["id"]] = "through_hole" if r.get("concave_hole") and len(adj.get(r["id"], ())) >= 2 else \
                             ("blind_hole" if r.get("concave_hole") else "boss_or_round")
    return hints


def analyze(path, rx=0.0, ry=0.0, thresh=THRESH):
    s = load(path)
    if rx or ry:
        s = rotate_shape(s, rx, ry)
    recs = [face_props(f, i) for i, f in enumerate(s.Faces())]
    bb = s.BoundingBox()
    lk = links(s)
    oh = overhangs(recs, bb.zmin, thresh)
    com = s.Center()
    return {"source": os.path.basename(path), "rotation_deg": {"rx": rx, "ry": ry}, "build_direction": "+Z",
            "overhang_threshold_deg": thresh,
            "part": {"bbox_mm": [round(bb.xlen, 3), round(bb.ylen, 3), round(bb.zlen, 3)],
                     "center_of_mass": [round(com.x, 3), round(com.y, 3), round(com.z, 3)],
                     "volume_mm3": round(s.Volume(), 3), "n_faces": len(recs), "valid": s.isValid()},
            "features": recs, "links": lk, "feature_hints": feature_hints(recs, lk),
            "overhangs": oh,
            "summary": {"actionable": sum(o["actionable"] for o in oh),
                        "actionable_area_mm2": round(sum(o["area_mm2"] for o in oh if o["actionable"]), 2)}}


def lay_face(path, fid):
    """Exact rx, ry (Rx then Ry) that put face `fid`'s outward normal at -Z (face on the bed)."""
    s = load(path)
    f = s.Faces()[fid]
    if f.geomType() != "PLANE":
        raise SystemExit(f"face {fid} is {f.geomType()}, only planar faces can be laid on the bed")
    n = f.normalAt()
    n = np.array([n.x, n.y, n.z])
    # closed form: Rx zeroes the y-component (rx = atan2(ny, nz)); Ry then sends (x', 0, z') to -Z
    rx = 0.0 if n[2] < -0.9999 else math.degrees(math.atan2(n[1], n[2]))
    v = rot_matrix(rx, 0) @ n
    ry = math.degrees(math.atan2(v[0], -v[2]))
    v2 = rot_matrix(rx, ry) @ n
    if v2[2] > -0.9999:  # numerical guard: brute-force fallback
        grid = [(a, b) for a in range(-180, 181, 15) for b in range(-180, 181, 15)]
        rx, ry = min(grid, key=lambda ab: (rot_matrix(*ab) @ n)[2])
        v2 = rot_matrix(rx, ry) @ n
    rx, ry = round(rx, 4), round(ry, 4)
    a = analyze(path, rx, ry)
    return {"face_id": fid, "rx_deg": rx, "ry_deg": ry, "normal_after": [round(x, 4) for x in v2],
            "overhangs_after": a["overhangs"], "summary_after": a["summary"],
            "bed_contact_area_mm2": f.Area(), "height_after_mm": a["part"]["bbox_mm"][2]}


def candidates(path, k=4):
    a0 = analyze(path)
    planar = sorted([r for r in a0["features"] if r["surface_type"] == "Planar"], key=lambda r: -r["area_mm2"])
    out = [{"label": "as-modelled", "rx_deg": 0, "ry_deg": 0, "summary": a0["summary"],
            "height_mm": a0["part"]["bbox_mm"][2], "bed_face": None}]
    seen = set()
    for r in planar:
        key = tuple(np.round(r["normal"], 3))
        if key in seen:
            continue
        seen.add(key)
        L = lay_face(path, r["id"])
        out.append({"label": f"face {r['id']} on bed", "rx_deg": L["rx_deg"], "ry_deg": L["ry_deg"],
                    "summary": L["summary_after"], "height_mm": L["height_after_mm"], "bed_face": r["id"],
                    "bed_area_mm2": round(r["area_mm2"], 1)})
        if len(out) >= k + 1:
            break
    rank = sorted(out, key=lambda c: (c["summary"]["actionable"], c["summary"]["actionable_area_mm2"],
                                      -c.get("bed_area_mm2", 0), c["height_mm"]))
    return {"candidates": out, "recommended": rank[0],
            "rule": "fewest actionable overhangs, then least overhang area, then largest bed contact, then lowest height"}


# ------------------------------------------------------------------ modifications
def teardrop_tool(rec, up_world, ext=1.0):
    C = cq()
    r = rec["radius_mm"]
    a = np.array(rec["axis"]); a /= np.linalg.norm(a)
    p0 = np.array(rec["axis_point"]) + a * (rec["axial_span"][0] - ext)
    L = rec["axial_span"][1] - rec["axial_span"][0] + 2 * ext
    u = up_world - a * np.dot(up_world, a); u /= np.linalg.norm(u)
    xdir = np.cross(u, a)
    plane = C.Plane(origin=C.Vector(*p0), xDir=C.Vector(*xdir), normal=C.Vector(*a))
    if plane.yDir.dot(C.Vector(*u)) < 0:
        plane = C.Plane(origin=C.Vector(*p0), xDir=C.Vector(*(-xdir)), normal=C.Vector(*a))
    t = r * math.sqrt(0.5)  # exact 45 deg tangent points; flanks are tangent to the bore
    pts = [(-t, t), (0, r * math.sqrt(2)), (t, t), (0, 0)]  # kite through the axis overlaps the bore
    return C.Workplane(plane).polyline(pts).close().extrude(L).val()


def modify(path, plan):
    """Apply typed recommendations by face_id (ids refer to the ORIGINAL file). Reorient is applied last."""
    C = cq()
    s = load(path)
    faces = s.Faces()
    recs = {i: face_props(f, i) for i, f in enumerate(faces)}
    ops = plan.get("operations", [])
    reo = next((o for o in ops if o["op"] == "reorient"), None)
    R = rot_matrix(reo["rx_deg"], reo["ry_deg"]) if reo else np.eye(3)
    up_orig = R.T @ np.array([0, 0, 1.0])  # build direction expressed in the original frame
    log = []
    edge_ops = [o for o in ops if o["op"] in ("fillet", "chamfer")]
    for o in ops:
        if o["op"] == "teardrop":
            rec = recs[o["face_id"]]
            if rec["surface_type"] != "Cylinder" or not rec.get("concave_hole"):
                log.append({"op": o, "status": "SKIPPED", "reason": "teardrop needs a concave cylindrical hole"})
                continue
            s = s.cut(teardrop_tool(rec, up_orig))
            log.append({"op": o, "status": "APPLIED"})
    for o in edge_ops:
        try:
            fids = o.get("faces") or [o["face_id"]]
            if len(fids) == 2:
                e1 = {e.hashCode() for e in faces[fids[0]].Edges()}
                edges = [e for e in faces[fids[1]].Edges() if e.hashCode() in e1]
            else:
                edges = faces[fids[0]].Edges()
            # re-find the edges on the current (possibly cut) solid by midpoint proximity
            cur = []
            for e in edges:
                mp = e.Center()
                cur.append(min(s.Edges(), key=lambda x: (x.Center() - mp).Length))
            s = s.fillet(o["radius"], cur) if o["op"] == "fillet" else s.chamfer(o["distance"], None, cur)
            log.append({"op": o, "status": "APPLIED", "edges": len(cur)})
        except Exception as ex:
            log.append({"op": o, "status": "FAILED", "reason": f"{type(ex).__name__}: {ex}"})
    if reo:
        s = rotate_shape(s, reo["rx_deg"], reo["ry_deg"])
        bb = s.BoundingBox()
        s = s.translate(C.Vector(-bb.center.x, -bb.center.y, -bb.zmin))  # sit on the bed at Z=0
        log.append({"op": reo, "status": "APPLIED (last)"})
    return s, log


def render4(path, out):
    """2x2 composite (4 views, edges visible) for the VLM verifier."""
    import pyvista as pv
    from PIL import Image, ImageDraw
    import tempfile
    pv.OFF_SCREEN = True
    C = cq()
    tmp = tempfile.mktemp(suffix=".stl")
    C.exporters.export(C.Workplane().add(load(path)), tmp, tolerance=0.02, angularTolerance=0.1)
    mesh = pv.read(tmp)
    c = np.array(mesh.center)
    r = np.linalg.norm(np.array(mesh.bounds[1::2]) - np.array(mesh.bounds[::2])) * 2.4
    tiles = []
    for title, el, az in [("Iso front", 30, -60), ("Iso back", 30, 120), ("Top", 89, 0), ("Bottom (bed side)", -60, 30)]:
        p = pv.Plotter(off_screen=True, window_size=(1024, 1024))
        p.set_background("white")
        p.add_mesh(mesh, color="#d9a066", show_edges=False, specular=0.3)
        p.add_mesh(mesh.extract_feature_edges(30), color="black", line_width=2)
        e, z = np.radians(el), np.radians(az)
        p.camera.position = tuple(c + r * np.array([np.cos(e) * np.cos(z), np.cos(e) * np.sin(z), np.sin(e)]))
        p.camera.focal_point = tuple(c)
        p.camera.up = (0, 1, 0) if abs(el) > 85 else (0, 0, 1)
        img = Image.fromarray(p.screenshot(return_img=True)); p.close()
        ImageDraw.Draw(img).text((14, 12), title, fill=(0, 0, 0))
        tiles.append(img)
    canvas = Image.new("RGB", (2048, 2048), "white")
    for i, t in enumerate(tiles):
        canvas.paste(t, ((i % 2) * 1024, (i // 2) * 1024))
    canvas.save(out)
    os.remove(tmp)
    return out


def verify(orig, new, plan, out):
    a0, a1 = analyze(orig), analyze(new)
    s1 = load(new)
    dv = (a1["part"]["volume_mm3"] - a0["part"]["volume_mm3"]) / a0["part"]["volume_mm3"] * 100
    qs = []
    for o in plan.get("operations", []):
        if o["op"] == "teardrop":
            qs.append(f"Does the hole that was face_{o['face_id']} now have a pointed (teardrop) top that points up in the build direction?")
        elif o["op"] == "fillet":
            qs.append(f"Do the edges of face_{o.get('face_id', o.get('faces'))} appear smoothly rounded (~R{o['radius']} mm)?")
        elif o["op"] == "chamfer":
            qs.append(f"Do the edges of face_{o.get('face_id', o.get('faces'))} show a ~{o['distance']} mm bevel?")
        elif o["op"] == "reorient":
            qs.append("Is the part resting on a large flat face, stable, with no tall thin footprint?")
    qs += ["Is the part a single closed solid with no missing walls or stray fragments?",
           "Are any large downward-facing surfaces still visible that would need support?"]
    img = render4(new, out + "_4view.png")
    res = {"kernel": {"valid": s1.isValid(), "n_solids": len(s1.Solids()), "volume_delta_pct": round(dv, 3),
                      "faces_before": a0["part"]["n_faces"], "faces_after": a1["part"]["n_faces"]},
           "overhang_recheck": {"before": a0["summary"], "after": a1["summary"], "remaining": a1["overhangs"]},
           "vlm_questions": qs, "render": img,
           "pass_deterministic": s1.isValid() and len(s1.Solids()) == 1 and a1["summary"]["actionable"] == 0}
    json.dump(res, open(out + ".json", "w"), indent=2)
    return res


# ------------------------------------------------------------------ RAG memory
def descriptor(bb):
    p = bb["part"]; b = sorted(p["bbox_mm"])
    types = [f["surface_type"] for f in bb["features"]]
    v = [b[0] / b[2], b[1] / b[2], math.log1p(p["n_faces"]),
         types.count("Planar") / len(types), types.count("Cylinder") / len(types),
         sum(o["kind"] == "horizontal_bore" for o in bb["overhangs"]),
         sum(o["kind"] == "downward_planar" for o in bb["overhangs"]),
         bb["summary"]["actionable_area_mm2"] / max(sum(f["area_mm2"] for f in bb["features"]), 1)]
    v = np.array(v, float)
    return (v / (np.linalg.norm(v) or 1)).tolist()


def memory(cmd, bbp, decision, store, note, k=3):
    bb = json.load(open(bbp))
    d = descriptor(bb)
    if cmd == "add":
        rec = {"part": bb["source"], "descriptor": d, "overhangs": bb["overhangs"],
               "decision": json.load(open(decision)) if decision else None, "lesson": note}
        open(store, "a").write(json.dumps(rec) + "\n")
        return {"stored": True, "store": store}
    rows = [json.loads(l) for l in open(store)] if os.path.exists(store) else []
    sims = sorted(((float(np.dot(d, r["descriptor"])), r) for r in rows), key=lambda x: -x[0])[:k]
    return {"similar_past_parts": [{"similarity": round(s, 3), "part": r["part"], "decision": r["decision"],
                                    "lesson": r.get("lesson")} for s, r in sims]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("analyze"); s.add_argument("step"); s.add_argument("--out"); s.add_argument("--threshold", type=float, default=THRESH)
    s = sub.add_parser("orient"); s.add_argument("step"); s.add_argument("--rx", type=float, default=0); s.add_argument("--ry", type=float, default=0)
    s = sub.add_parser("lay"); s.add_argument("step"); s.add_argument("--face", type=int, required=True)
    s = sub.add_parser("candidates"); s.add_argument("step")
    s = sub.add_parser("modify"); s.add_argument("step"); s.add_argument("--plan", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("verify"); s.add_argument("orig"); s.add_argument("new"); s.add_argument("--plan", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("memory"); s.add_argument("action", choices=["add", "query"]); s.add_argument("--bb", required=True)
    s.add_argument("--decision"); s.add_argument("--store", default="dfam_memory.jsonl"); s.add_argument("--note")
    a = ap.parse_args()
    if a.cmd == "analyze":
        r = analyze(a.step, thresh=a.threshold)
        if a.out:
            json.dump(r, open(a.out, "w"), indent=2)
            r = {"written": a.out, "summary": r["summary"], "overhangs": r["overhangs"], "part": r["part"]}
    elif a.cmd == "orient":
        full = analyze(a.step, a.rx, a.ry)
        r = {"rotation": full["rotation_deg"], "overhangs": full["overhangs"], "summary": full["summary"],
             "height_mm": full["part"]["bbox_mm"][2]}
    elif a.cmd == "lay":
        r = lay_face(a.step, a.face)
    elif a.cmd == "candidates":
        r = candidates(a.step)
    elif a.cmd == "modify":
        shape, log = modify(a.step, json.load(open(a.plan)))
        cq().exporters.export(cq().Workplane().add(shape), a.out)
        r = {"out": a.out, "log": log, "valid": shape.isValid()}
    elif a.cmd == "verify":
        r = verify(a.orig, a.new, json.load(open(a.plan)), a.out)
    else:
        r = memory(a.action, a.bb, a.decision, a.store, a.note)
    print(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()
