# v2 (model refinement): 10 vertices alternating outer radius 30 mm (tips) and inner radius 12 mm (notches)
import FreeCAD as App, Part, math
V = App.Vector
R_TIP, R_NOTCH, T = 30.0, 12.0, 4.0
pts = []
for k in range(10):
    r = R_TIP if k % 2 == 0 else R_NOTCH
    a = math.pi / 2 + k * math.pi / 5
    pts.append(V(r * math.cos(a), r * math.sin(a), 0))
pts.append(pts[0])
Part.show(Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, T)), "StarPlate")
