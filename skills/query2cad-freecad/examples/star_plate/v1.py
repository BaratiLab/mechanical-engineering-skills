# v1 (error refinement): close the outline, make a face, extrude
import FreeCAD as App, Part, math
V = App.Vector
pts = [V(30*math.cos(math.pi/2 + k*2*math.pi/5), 30*math.sin(math.pi/2 + k*2*math.pi/5), 0) for k in range(5)]
pts.append(pts[0])
Part.show(Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, 4)), "Star")
