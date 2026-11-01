#!/usr/bin/env python3
"""Image -> printer-ready G-code for 2D / 2.5D parts (after Image2Gcode, Wang, Jadhav, Pak,
Barati Farimani, Additive Manufacturing Letters 17 (2026) 100374).

  preprocess  python i2g.py preprocess photo.jpg --out sil.png [--mode sketch|photo|slice]   edges -> contours -> binary 224x224
  generate    python i2g.py generate sil.png --size-mm 40 --layers 15 --out part.gcode      baseline toolpath generator
  keypoints   python i2g.py keypoints part.gcode --out kp.npz [--nmax 2048]                 Slice-100K style (X,Y,E) per layer
  emit        python i2g.py emit kp.npz --layer 0 --out layer.gcode [--size-mm 40]          denormalize keypoints -> G-code
  validate    python i2g.py validate part.gcode [--bed 220 220 250]                          bounds, extrusion, travel distance
  plot        python i2g.py plot part.gcode --out paths.png [--layers 0,7]

The paper's generator is a DDPM (DinoV2-S encoder + 1-D U-Net, x0-prediction, cosine schedule,
T=500) trained on Slice-100K; weights are available from the authors on request. `generate`
is a deterministic perimeter + infill stand-in that produces the SAME keypoint representation,
so `emit` / `validate` / `plot` work identically on DDPM samples (see references/ddpm_hook.md).
"""
import argparse
import json
import math
import re
import sys

import numpy as np

FIL_D = 1.75


# ------------------------------------------------------------------ preprocessing (paper §3.2)
def preprocess(path, out, mode="sketch", size=224, invert=None):
    import cv2
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        sys.exit(f"cannot read {path}")
    img = cv2.GaussianBlur(img, (5, 5), 0)
    if mode == "slice":  # already a clean slice render
        _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if invert is None:
            invert = bw.mean() > 127
        if invert:
            bw = 255 - bw
    else:
        edges = cv2.Canny(img, 40, 120)
        k = 5 if mode == "photo" else 3
        edges = cv2.dilate(edges, np.ones((k, k), np.uint8), iterations=2)  # close gaps in pen strokes
        cnts, hier = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            sys.exit("no contours found; try --mode slice or a cleaner image")
        # A drawn outline is a closed stroke band, so contours nest: d0 = outer edge of the outline stroke,
        # d1 = its inner edge, d2 = outer edge of a hole stroke, d3 = inner edge of the hole stroke, ...
        # Material = fill d0 (mod 4), clear d3 (mod 4); then erode half a stroke so both edges land on the pen line.
        depth = []
        for i in range(len(cnts)):
            d, j = 0, hier[0][i][3]
            while j != -1:
                d, j = d + 1, hier[0][j][3]
            depth.append(d)
        areas = [cv2.contourArea(c) for c in cnts]
        amax = max(areas)
        bw = np.zeros_like(img)
        for d_target, val in ((0, 255), (3, 0), (4, 255), (7, 0)):
            for i, c in enumerate(cnts):
                if depth[i] == d_target and areas[i] > 0.002 * amax:
                    cv2.drawContours(bw, cnts, i, val, -1)
        bw = cv2.erode(bw, np.ones((k, k), np.uint8), iterations=2)  # undo the stroke dilation
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(bw)
    if not len(xs):
        sys.exit("empty silhouette")
    crop = bw[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
    h, w = crop.shape
    s = (size * 0.86) / max(h, w)
    crop = cv2.resize(crop, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((size, size), np.uint8)
    y0, x0 = (size - crop.shape[0]) // 2, (size - crop.shape[1]) // 2
    canvas[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    cv2.imwrite(out, canvas)
    return {"silhouette": out, "fill_fraction": float((canvas > 0).mean()), "size": size}


# ------------------------------------------------------------------ silhouette -> polygons (mm)
def silhouette_polygons(sil, size_mm):
    import cv2
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    bw = cv2.imread(sil, cv2.IMREAD_GRAYSCALE) > 127
    ys, xs = np.nonzero(bw)
    px_extent = max(np.ptp(xs), np.ptp(ys)) + 1
    mm_per_px = size_mm / px_extent
    cnts, hier = cv2.findContours(bw.astype(np.uint8) * 255, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    to_mm = lambda c: [((p[0][0] - cx) * mm_per_px, (cy - p[0][1]) * mm_per_px) for p in c]  # image y down -> +Y up
    polys = []
    for i, c in enumerate(cnts):
        if hier[0][i][3] == -1 and len(c) >= 3:
            holes = [to_mm(cnts[j]) for j in range(len(cnts)) if hier[0][j][3] == i and len(cnts[j]) >= 3]
            P = Polygon(to_mm(c), holes).buffer(0)
            if P.area > 1e-3:
                polys.append(P)
    g = unary_union(polys)
    r = mm_per_px * 1.5  # close/open smoothing removes pixel stair-steps, then simplify
    g = g.buffer(r, join_style=1).buffer(-2 * r, join_style=1).buffer(r, join_style=1)
    return g.simplify(mm_per_px * 0.3), mm_per_px


def lines_in(poly, spacing, angle_deg):
    from shapely import affinity
    from shapely.geometry import LineString, MultiLineString
    c = poly.centroid
    rot = affinity.rotate(poly, -angle_deg, origin=c)
    x0, y0, x1, y1 = rot.bounds
    segs = []
    for k, y in enumerate(np.arange(y0 + spacing / 2, y1, spacing)):
        inter = rot.intersection(LineString([(x0 - 1, y), (x1 + 1, y)]))
        parts = [inter] if inter.geom_type == "LineString" else list(getattr(inter, "geoms", []))
        parts = [p for p in parts if p.geom_type == "LineString" and p.length > 1e-6]
        parts.sort(key=lambda p: p.coords[0][0])
        if k % 2:  # serpentine ordering reduces travel
            parts = [LineString(list(p.coords)[::-1]) for p in parts[::-1]]
        segs += [affinity.rotate(p, angle_deg, origin=c) for p in parts]
    return segs


def rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for p in polys:
        if p.is_empty:
            continue
        out.append(list(p.exterior.coords))
        out += [list(h.coords) for h in p.interiors]
    return out


def layer_paths(poly, line_w, perims, infill, density, layer_idx):
    """Return list of (polyline_points, extrude_bool) in print order for one layer."""
    paths = []
    cur = poly
    for k in range(perims):
        off = cur.buffer(-line_w / 2 if k == 0 else -line_w, join_style=2)
        if off.is_empty:
            break
        paths += [(r, True) for r in rings(off)]
        cur = off
    inner = cur.buffer(-line_w / 2, join_style=2) if perims else poly
    if not inner.is_empty and density > 0:
        spacing = line_w / max(min(density, 1.0), 1e-3)
        if infill == "concentric":
            g = inner
            while not g.is_empty:
                paths += [(r, True) for r in rings(g)]
                g = g.buffer(-spacing, join_style=2)
        else:
            ang = 45 if layer_idx % 2 == 0 else -45
            paths += [(list(s.coords), True) for s in lines_in(inner, spacing, ang)]
    return paths


# ------------------------------------------------------------------ G-code writing (paper §2.4 post-processing)
def header(p):
    return [f"; Image2Gcode-style output (baseline generator)", "G90 ; absolute positioning", "M83 ; relative extrusion",
            f"M140 S{p['bed_temp']}", f"M104 S{p['nozzle_temp']}", "G28 ; home", f"M190 S{p['bed_temp']}",
            f"M109 S{p['nozzle_temp']}", "G92 E0", "G1 Z5 F3000"]


def footer(p):
    return ["G1 E-2 F2400 ; retract", f"G91", "G1 Z10 F3000", "G90", "M104 S0", "M140 S0", "M84 ; motors off"]


def e_per_mm(p):
    return p["layer_h"] * p["line_w"] * p["flow"] / (math.pi * (FIL_D / 2) ** 2)


def generate(sil, out, size_mm=40.0, layers=10, layer_h=0.2, line_w=0.45, perims=2, infill="rectilinear",
             density=0.25, center=(110.0, 110.0), feed=1800, travel=6000, nozzle_temp=210, bed_temp=60, flow=1.0):
    p = dict(layer_h=layer_h, line_w=line_w, flow=flow, nozzle_temp=nozzle_temp, bed_temp=bed_temp)
    poly, mmpx = silhouette_polygons(sil, size_mm)
    epm = e_per_mm(p)
    g = header(p)
    pos = None
    for L in range(layers):
        z = layer_h * (L + 1)
        g.append(f";LAYER:{L}")
        g.append(f"G1 Z{z:.3f} F3000")
        for pts, ext in layer_paths(poly, line_w, perims, infill, density, L):
            x, y = pts[0]
            X, Y = x + center[0], y + center[1]
            g.append(f"G0 X{X:.3f} Y{Y:.3f} F{travel}")
            pos = (X, Y)
            for x, y in pts[1:]:
                X, Y = x + center[0], y + center[1]
                d = math.hypot(X - pos[0], Y - pos[1])
                if d < 1e-4:
                    continue
                g.append(f"G1 X{X:.3f} Y{Y:.3f} E{d * epm:.5f} F{feed}")
                pos = (X, Y)
    g += footer(p)
    open(out, "w").write("\n".join(g) + "\n")
    return {"gcode": out, "layers": layers, "area_mm2": round(poly.area, 2), "mm_per_px": mmpx,
            "bbox_mm": [round(v, 2) for v in poly.bounds], "e_per_mm": epm}


# ------------------------------------------------------------------ parsing -> keypoints (paper §2.1)
def parse_gcode(path):
    """Layers of (X, Y, E_abs) for extruding G1 moves. Handles G90/G91, M82/M83, G92 E resets, comments."""
    absxy, abse = True, True
    x = y = z = 0.0
    e_reader = 0.0   # extruder position as the firmware sees it (after G92)
    e_abs = 0.0      # true cumulative extrusion
    layers, cur, curz = [], [], None
    last_ext = False
    travel = 0.0
    for raw in open(path):
        line = raw.split(";")[0].strip().upper()
        if not line:
            continue
        cmd = line.split()[0]
        args = {m[0]: float(m[1]) for m in re.findall(r"([XYZEF])(-?\d*\.?\d+)", line)}
        if cmd == "G90": absxy = True; continue
        if cmd == "G91": absxy = False; continue
        if cmd == "M82": abse = True; continue
        if cmd == "M83": abse = False; continue
        if cmd == "G92":
            if "E" in args:
                e_reader = args["E"]
            continue
        if cmd not in ("G0", "G1"):
            continue
        nx = (args.get("X", x) if absxy else x + args.get("X", 0.0))
        ny = (args.get("Y", y) if absxy else y + args.get("Y", 0.0))
        nz = (args.get("Z", z) if absxy else z + args.get("Z", 0.0))
        de = 0.0
        if "E" in args:
            de = (args["E"] - e_reader) if abse else args["E"]
            e_reader = args["E"] if abse else e_reader + args["E"]
        if nz != z:
            if cur:
                layers.append({"z": curz, "kp": np.array(cur)})
            cur, curz = [], nz
        dist = math.hypot(nx - x, ny - y)
        travel += dist
        if de > 0 and dist > 0:
            if not cur or not last_ext:  # keep the travel end as a keypoint: constant E marks a travel move
                cur.append((x, y, e_abs))
            e_abs += de
            cur.append((nx, ny, e_abs))
            last_ext = True
        else:
            last_ext = False
        x, y, z = nx, ny, nz
    if cur:
        layers.append({"z": curz, "kp": np.array(cur)})
    return layers, travel


def normalize(kp):
    """Paper normalization: XY centred on bbox midpoint, scaled by the larger extent to [-1,1]
    (aspect preserved); E min-max to [-1,1] per layer. Returns normalized array + params."""
    xy = kp[:, :2]
    lo, hi = xy.min(0), xy.max(0)
    mid, half = (lo + hi) / 2, max((hi - lo).max() / 2, 1e-9)
    e = kp[:, 2]
    emin, emax = e.min(), e.max()
    en = 2 * (e - emin) / max(emax - emin, 1e-12) - 1
    return np.c_[(xy - mid) / half, en], {"mid": mid.tolist(), "half": float(half), "emin": float(emin), "emax": float(emax)}


def to_keypoints(gcode, out, nmax=2048):
    layers, _ = parse_gcode(gcode)
    X = np.zeros((len(layers), nmax, 3), np.float32)
    M = np.zeros((len(layers), nmax), np.uint8)
    params, trunc = [], 0
    for i, L in enumerate(layers):
        kn, pr = normalize(L["kp"])
        n = min(len(kn), nmax)
        trunc += len(kn) > nmax
        X[i, :n], M[i, :n] = kn[:n], 1
        params.append(pr | {"z": L["z"], "n": int(len(kn))})
    np.savez_compressed(out, keypoints=X, mask=M, params=json.dumps(params))
    return {"npz": out, "layers": len(layers), "nmax": nmax, "truncated_layers": int(trunc),
            "points_per_layer": [p["n"] for p in params][:10]}


def emit(npz, layer, out, size_mm=None, center=(110.0, 110.0), feed=1800, layer_h=0.2, flow_mult=1.0,
         nozzle_temp=210, bed_temp=60):
    """Denormalize one layer of (possibly model-generated) keypoints and write a single-layer G-code."""
    d = np.load(npz)
    kp, m = d["keypoints"][layer], d["mask"][layer].astype(bool)
    pr = json.loads(str(d["params"]))[layer]
    kp = kp[m]
    half = (size_mm / 2) if size_mm else pr["half"]
    xy = kp[:, :2] * half + (np.array(center) if size_mm else np.array(pr["mid"]))
    e = (kp[:, 2] + 1) / 2 * (pr["emax"] - pr["emin"]) + pr["emin"]
    if size_mm:  # rescaling geometry rescales deposited volume per mm^2 by the area ratio
        e = e * (half / pr["half"]) ** 1 * flow_mult
    else:
        e = e * flow_mult
    p = dict(nozzle_temp=nozzle_temp, bed_temp=bed_temp)
    g = header(p) + [f"G1 Z{layer_h:.3f} F3000", f"G0 X{xy[0, 0]:.3f} Y{xy[0, 1]:.3f} F6000"]
    for i in range(1, len(xy)):
        de = e[i] - e[i - 1]
        if de <= 0:
            g.append(f"G0 X{xy[i, 0]:.3f} Y{xy[i, 1]:.3f} F6000")
        else:
            g.append(f"G1 X{xy[i, 0]:.3f} Y{xy[i, 1]:.3f} E{de:.5f} F{feed}")
    g += footer(p)
    open(out, "w").write("\n".join(g) + "\n")
    return {"gcode": out, "points": int(len(xy))}


# ------------------------------------------------------------------ validation (paper §2.4, §3.4)
def validate(gcode, bed=(220, 220, 250)):
    layers, travel = parse_gcode(gcode)
    issues = []
    allxy = np.vstack([L["kp"][:, :2] for L in layers]) if layers else np.zeros((0, 2))
    zs = [L["z"] for L in layers]
    if len(allxy):
        if allxy.min() < 0 or allxy[:, 0].max() > bed[0] or allxy[:, 1].max() > bed[1]:
            issues.append("toolpath leaves the build plate")
    if zs and (max(zs) > bed[2] or min(zs) <= 0):
        issues.append("Z outside build volume")
    nonmono = sum(int(np.any(np.diff(L["kp"][:, 2]) < -1e-9)) for L in layers)
    if nonmono:
        issues.append(f"{nonmono} layers with non-monotonic cumulative extrusion")
    if any(b <= a for a, b in zip(zs, zs[1:])):
        issues.append("layer Z not strictly increasing")
    ext_len = sum(float(np.sum(np.hypot(*np.diff(L["kp"][:, :2], axis=0).T))) for L in layers)
    e_total = sum(float(L["kp"][-1, 2] - L["kp"][0, 2]) for L in layers)
    return {"ok": not issues, "issues": issues, "layers": len(layers),
            "z_range": [min(zs), max(zs)] if zs else None,
            "xy_bounds": [allxy.min(0).round(3).tolist(), allxy.max(0).round(3).tolist()] if len(allxy) else None,
            "total_travel_distance_mm": round(travel, 2), "extrusion_path_mm": round(ext_len, 2),
            "filament_mm": round(e_total, 2),
            "per_layer_travel_mm": round(travel / max(len(layers), 1), 2)}


def plot(gcode, out, which=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    layers, _ = parse_gcode(gcode)
    idx = which if which else ([0, len(layers) // 2] if len(layers) > 1 else [0])
    fig, axs = plt.subplots(1, len(idx), figsize=(5 * len(idx), 5))
    axs = np.atleast_1d(axs)
    for ax, i in zip(axs, idx):
        kp = layers[i]["kp"]
        de = np.r_[0, np.diff(kp[:, 2])]
        for j in range(1, len(kp)):
            if de[j] > 0:
                ax.plot(kp[j - 1:j + 1, 0], kp[j - 1:j + 1, 1], color=plt.cm.viridis(min(de[j] / (de.max() or 1), 1)), lw=1)
        ax.set_aspect("equal"); ax.set_title(f"layer {i}  z={layers[i]['z']:.2f} mm  ({len(kp)} keypoints)", fontsize=9)
        ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
    fig.tight_layout(); fig.savefig(out, dpi=140)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("preprocess"); s.add_argument("image"); s.add_argument("--out", required=True)
    s.add_argument("--mode", choices=["sketch", "photo", "slice"], default="sketch"); s.add_argument("--invert", action="store_true", default=None)
    s = sub.add_parser("generate"); s.add_argument("sil"); s.add_argument("--out", required=True)
    s.add_argument("--size-mm", type=float, default=40); s.add_argument("--layers", type=int, default=10)
    s.add_argument("--layer-h", type=float, default=0.2); s.add_argument("--line-w", type=float, default=0.45)
    s.add_argument("--perims", type=int, default=2); s.add_argument("--infill", choices=["rectilinear", "concentric"], default="rectilinear")
    s.add_argument("--density", type=float, default=0.25); s.add_argument("--nozzle-temp", type=int, default=210); s.add_argument("--bed-temp", type=int, default=60)
    s = sub.add_parser("keypoints"); s.add_argument("gcode"); s.add_argument("--out", required=True); s.add_argument("--nmax", type=int, default=2048)
    s = sub.add_parser("emit"); s.add_argument("npz"); s.add_argument("--layer", type=int, default=0); s.add_argument("--out", required=True)
    s.add_argument("--size-mm", type=float); s.add_argument("--flow-mult", type=float, default=1.0)
    s = sub.add_parser("validate"); s.add_argument("gcode"); s.add_argument("--bed", type=float, nargs=3, default=[220, 220, 250])
    s = sub.add_parser("plot"); s.add_argument("gcode"); s.add_argument("--out", required=True); s.add_argument("--layers")
    a = ap.parse_args()
    if a.cmd == "preprocess": r = preprocess(a.image, a.out, a.mode, invert=a.invert)
    elif a.cmd == "generate":
        r = generate(a.sil, a.out, a.size_mm, a.layers, a.layer_h, a.line_w, a.perims, a.infill, a.density,
                     nozzle_temp=a.nozzle_temp, bed_temp=a.bed_temp)
    elif a.cmd == "keypoints": r = to_keypoints(a.gcode, a.out, a.nmax)
    elif a.cmd == "emit": r = emit(a.npz, a.layer, a.out, a.size_mm, flow_mult=a.flow_mult)
    elif a.cmd == "validate": r = validate(a.gcode, a.bed)
    else: r = {"plot": plot(a.gcode, a.out, [int(x) for x in a.layers.split(",")] if a.layers else None)}
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
