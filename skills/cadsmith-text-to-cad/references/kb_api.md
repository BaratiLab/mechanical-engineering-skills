# KB1 — CadQuery API reference (curated for code generation)

Each entry: signature · what it does · example · pitfalls. Retrieved by keyword with `cadsmith.py kb "<keywords>"`. Conventions: mm, XY base plane, Z up, origin-centred unless the prompt says otherwise.

### box primitive cuboid rectangle block
`Workplane.box(length, width, height, centered=True)` creates a cuboid centred on the workplane origin.
`cq.Workplane("XY").box(40, 20, 10)` spans x∈[−20,20], y∈[−10,10], z∈[−5,5].
Pitfall: for a part sitting on Z=0 use `centered=(True, True, False)`.

### cylinder circle extrude disc rod
`Workplane.circle(r).extrude(h)` or `Workplane.cylinder(height, radius, centered=...)`.
`cq.Workplane("XY").circle(25).extrude(10)` is a Ø50 disc from z=0 to 10.
Pitfall: `circle` takes the RADIUS. Prompts give diameters, so divide by 2.

### sphere dome hemisphere ball
`Workplane.sphere(r)`; for a dome: `cq.Workplane("XY").sphere(r).split(keepTop=True)`.
Pitfall: `split` needs a workplane through the cut plane; check volume ≈ (2/3)πr³.

### cone frustum taper revolve
`cq.Solid.makeCone(r1, r2, h, pnt=cq.Vector(0,0,0), dir=cq.Vector(0,0,1))`, then `cq.Workplane().add(solid)`.
Or revolve a trapezoid profile on the XZ plane about Z.

### torus ring donut
`cq.Solid.makeTorus(R_major, r_minor)` → `cq.Workplane().add(...)`.
Pitfall: bbox = 2(R + r) wide, 2r tall.

### polygon hexagon prism regular
`Workplane.polygon(nSides, diameter).extrude(h)`, where the diameter is the CIRCUMSCRIBED circle.
Hex across-flats s → circumscribed diameter = s / cos(30°).

### polyline closed profile sketch wire
`Workplane("XY").polyline(pts).close().extrude(h)`.
Pitfall: an unclosed wire gives "BRep_API: command not done" on extrude. Always call `.close()`.

### workplane offset plane faces selector
`.faces(">Z").workplane()` starts a new sketch on the top face; `.workplane(offset=d)` shifts along the normal.
`cq.Workplane("XZ")` normal is −Y in CadQuery (right-handed X, Z) — check feature direction.
Pitfall: `centerOption="CenterOfBoundBox"` keeps origins predictable on non-symmetric faces.

### hole cboreHole cskHole through counterbore countersink
`.hole(d, depth=None)`, `.cboreHole(d, cboreD, cboreDepth)`, `.cskHole(d, cskD, cskAngle)` act on the current workplane's points.
`.faces(">Z").workplane().pushPoints([(x,y),...]).hole(6.5)`.
Pitfall: `hole` cuts in −normal from the workplane; on `faces("<Z")` the workplane faces down.

### pushPoints rarray polarArray pattern bolt circle pitch
`.pushPoints(list)`, `.rarray(xs, ys, nx, ny)`, `.polarArray(radius, startAngle, angle, count)`.
Bolt holes on a 38 mm PCD: `.polarArray(19, 0, 360, 6).hole(6.5)` (radius = PCD/2).
Pitfall: polarArray rotates the local frame per point; use `rotate=False` for non-symmetric features.

### extrude cutBlind cutThruAll pocket slot
`.extrude(d)`, `.cutBlind(-d)`, `.cutThruAll()`; slots: `.slot2D(length, width, angle)`.
Pitfall: `cutBlind` depth is signed along the workplane normal; negative cuts into the part.

### union cut intersect boolean combine
`a.union(b)`, `a.cut(b)`, `a.intersect(b)`.
Pitfall: bodies that only touch along a face can merge into a single solid or not, depending on tolerance. Overlap them by 0.01 mm. Check `n_solids == 1`.

### fillet chamfer edges round bevel
`.edges("|Z").fillet(r)`, `.edges(">Z").chamfer(c)`.
Pitfall: the radius must be smaller than the adjacent face widths. Fillet last; select narrowly (`.edges(cq.selectors.BoxSelector(...))`).

### shell hollow thickness enclosure
`.faces(">Z").shell(-t)` removes the top face and hollows inward by t.
Pitfall: shell fails on complex fillets. Shell before filleting; negative t means inward.

### revolve axisymmetric lathe profile
`cq.Workplane("XZ").polyline(pts).close().revolve(360, (0,0,0), (0,1,0))`.
Pitfall: the axis is given in LOCAL workplane coordinates; on "XZ", the local y is global Z.

### loft transition sections
`cq.Workplane("XY").rect(a,b).workplane(offset=h).circle(r).loft(combine=True)`.
Pitfall: the sections need compatible orientation; use `ruled=True` for straight sides.

### sweep path pipe tube handle
`profile.sweep(path, isFrenet=True)`, where path = `cq.Workplane("XZ").spline(...)` or a `polyline` wire.
Pitfall: the profile plane must be perpendicular to the path start tangent.

### mirror symmetric half
`.mirror("YZ")` or `part.mirror(mirrorPlane="XZ", basePointVector=(0,0,0), union=True)`.

### translate rotate transform move position
`.translate((x,y,z))`, `.rotate((0,0,0), (0,0,1), angle_deg)`.
Pitfall: rotation is about an axis through the two given points.

### text engrave emboss
`.text("TXT", fontsize, distance, cut=True)`.

### keyway slot bore spline shaft
Keyway on a bore wall (+X side, width w, depth d measured from the bore wall, length L along Z):
`key = cq.Workplane("XY").box(r_bore + d, w, L, centered=(False, True, False))` spans x∈[0, r_bore+d], so cut it: `part = part.cut(key)`.
Pitfall: the box must start inside the bore (x=0 is fine) and end at r_bore + d. Check that the bbox is unchanged and the volume drops by ≈ w·d·L.

### gear involute teeth spur
Approximate with polarArray tooth profiles, or use `cq_gears` if installed. For benchmarks, a polygonal tooth profile around the root circle is acceptable if bbox and tooth count match.

### selectors string syntax
`">Z"` max Z face, `"<Z"` min, `"|Z"` parallel to Z, `"#Z"` perpendicular, `"%CIRCLE"` circular edges, combine with `and`/`or`/`not`: `.edges("|Z and >X")`.

### assembly multi-body unions
Build each body, `union` them in sequence, then verify `n_solids == 1`. Gaps of 0.01 mm leave separate solids (the CADSmith T3_019 near-miss).
