"""Nine-face birdhouse like the AgentsCAD test case: pentagonal house prism (7 planar faces),
Ø25 entrance bore along Y and Ø8 perch hole along X (2 horizontal cylinders).
python make_birdhouse.py birdhouse.step"""
import sys
import cadquery as cq
prof = [(-30, 0), (30, 0), (30, 40), (0, 60), (-30, 40)]
house = cq.Workplane("XZ").polyline(prof).close().extrude(-50)
house = house.cut(cq.Workplane("XZ").center(0, 32).circle(12.5).extrude(-50))
house = house.cut(cq.Workplane("YZ").workplane(offset=-30).center(25, 12).circle(4).extrude(60))
cq.exporters.export(house, sys.argv[1] if len(sys.argv) > 1 else "birdhouse.step")
