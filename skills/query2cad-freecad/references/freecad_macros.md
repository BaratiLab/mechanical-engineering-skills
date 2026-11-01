# FreeCAD macro guide for Query2CAD (headless)

Macros run in `freecadcmd` with no GUI. Don't import FreeCADGui and don't call `Gui.*`. The runner creates an active document; your macro adds objects to `App.ActiveDocument`. Final top-level solids are exported automatically, and intermediate objects consumed by booleans are skipped.

## Skeleton
```python
import FreeCAD as App, Part
doc = App.ActiveDocument
V = App.Vector

base = doc.addObject("Part::Box", "Base")
base.Length, base.Width, base.Height = 40, 20, 10            # mm

hole = doc.addObject("Part::Cylinder", "Hole")
hole.Radius, hole.Height = 3, 12
hole.Placement = App.Placement(V(20, 10, -1), App.Rotation(0, 0, 0))

cut = doc.addObject("Part::Cut", "Plate")
cut.Base, cut.Tool = base, hole
doc.recompute()
```

## Primitives (Part workbench)
`Part::Box` (Length, Width, Height) · `Part::Cylinder` (Radius, Height, Angle) · `Part::Sphere` (Radius) · `Part::Cone` (Radius1, Radius2, Height) · `Part::Torus` (Radius1 major, Radius2 minor) · `Part::Prism` (Polygon, Circumradius, Height) · `Part::Wedge`.
Primitives sit with their corner (box) or base centre (cylinder, cone) at the placement origin and extend +Z.

## Booleans
`Part::Fuse` (Base, Tool), `Part::Cut`, `Part::Common`; `Part::MultiFuse` (Shapes = [...]).
To overlap, extend tool bodies 1 mm beyond the faces they cut, or results can be empty.

## Placement and rotation
`App.Placement(App.Vector(x, y, z), App.Rotation(App.Vector(ax, ay, az), angle_deg))`.
For a cylinder lying along X: `App.Rotation(App.Vector(0, 1, 0), 90)`.

## Shape-level API (for patterns and complex profiles)
```python
pts = [V(0,0,0), V(30,0,0), V(30,10,0), V(0,10,0), V(0,0,0)]
face = Part.Face(Part.makePolygon(pts))
solid = face.extrude(V(0, 0, 5))
for k in range(6):                                  # bolt circle
    c = Part.makeCylinder(3.25, 20, V(19*math.cos(k*math.pi/3), 19*math.sin(k*math.pi/3), -5))
    solid = solid.cut(c)
Part.show(solid, "Result")                           # adds a Part::Feature to the doc
```
Also available: `Part.makeBox`, `makeCylinder(r, h, pnt, dir)`, `makeSphere`, `makeCone`, `makeTorus`, `shape.fillet(r, edges)`, `shape.makeChamfer(d, edges)`, `Part.makeHelix`, `Wire.makePipeShell([profile], True, True)` (sweep), `Part.makeLoft([w1, w2], True)`, `face.revolve(V(0,0,0), V(0,0,1), 360)`.

## Common errors → fixes
| Error | Fix |
|---|---|
| `No module named 'FreeCADGui'` / `Gui` undefined | Remove GUI calls; headless only |
| `Shape is null` / `BRep_API: command not done` | Boolean bodies don't overlap or are coplanar; extend the tool by 1 mm |
| `Both shapes must be valid` | An earlier op failed; check `shape.isValid()` step by step |
| fillet fails | Radius too large; fillet fewer edges; fillet before cutting small holes |
| `Wire is not closed` | The last point must equal the first in `makePolygon` |
| Placement wrong | Primitive origins are corners or base centres, not centroids |
| Object exported twice / extra solids | Booleans hide their inputs automatically; avoid leaving stray `Part.show` copies |
