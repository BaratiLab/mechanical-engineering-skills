import cadquery as cq, math
# independent reference: revolve the half-profile, then cut features
prof = [(7,0),(25,0),(25,10),(14,10),(14,50),(25,50),(25,60),(7,60)]
body = cq.Workplane("XZ").polyline(prof).close().revolve(360,(0,0,0),(0,1,0))
for k in range(6):
    a = math.radians(60*k)
    body = body.cut(cq.Workplane("XY").center(19*math.cos(a), 19*math.sin(a)).circle(3.25).extrude(60))
body = body.cut(cq.Workplane("XY").box(9.5, 5, 60, centered=(False, True, False)))
result = body
