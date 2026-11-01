# v0 (direct generation): steps = 1) five outline points  2) draw polygon  3) extrude 4 mm
import FreeCAD as App, Part, math
V = App.Vector
pts = [V(30*math.cos(math.pi/2 + k*2*math.pi/5), 30*math.sin(math.pi/2 + k*2*math.pi/5), 0) for k in range(5)]
outline = Part.makePolygon(pts)            # not closed: last point != first
Part.show(outline.extrude(V(0, 0, 4)), "Star")
