"""Flanged bushing — template showing the required part-script structure.

Units: mm. Origin: center of flange bottom face. +Z along bushing axis.
"""
import cadquery as cq

PARAMS = {
    "bore": 20.0,          # through-bore diameter
    "hub_od": 32.0,        # hub outer diameter
    "hub_len": 25.0,       # hub length above flange
    "flange_od": 60.0,
    "flange_t": 6.0,
    "n_bolts": 4,
    "bolt_circle": 46.0,
    "bolt_hole": 5.5,      # M5 clearance (ISO 273 medium)
    "chamfer": 0.8,
    "fillet": 1.5,         # hub-to-flange fillet
}
PARAMS.update(globals().get("OVERRIDES", {}))
P = PARAMS
DENSITY_KG_M3 = 7850  # steel

# Geometry sanity checks — fail early with a clear message
assert P["bore"] < P["hub_od"] - 4, "hub wall < 2 mm"
assert P["bolt_circle"] - P["bolt_hole"] > P["hub_od"] + 2, "bolt holes cut into hub"
assert P["bolt_circle"] + P["bolt_hole"] < P["flange_od"] - 3, "bolt holes too close to flange edge"

flange = cq.Workplane("XY").circle(P["flange_od"] / 2).extrude(P["flange_t"])
hub = (cq.Workplane("XY").workplane(offset=P["flange_t"])
       .circle(P["hub_od"] / 2).extrude(P["hub_len"]))
body = flange.union(hub)
r, t = P["hub_od"] / 2 + 0.1, P["flange_t"]
# select only the hub/flange junction circle: its bounding box fits in this thin box
body = body.edges(cq.selectors.BoxSelector((-r, -r, t - 0.01), (r, r, t + 0.01), boundingbox=True)).fillet(P["fillet"])
body = body.faces(">Z").workplane().hole(P["bore"])
body = (body.faces("<Z").workplane()
        .polarArray(P["bolt_circle"] / 2, 0, 360, int(P["n_bolts"]))
        .hole(P["bolt_hole"]))
body = body.faces(">Z").edges().chamfer(P["chamfer"])

result = body
