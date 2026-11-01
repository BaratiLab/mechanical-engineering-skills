import cadquery as cq
D_FL, T_FL, D_HUB, L_HUB = 50, 10, 28, 40
PCD, D_BOLT, N_BOLT = 38, 6.5, 6
D_BORE, KEY_W, KEY_D = 14, 5, 2.5
H = 2 * T_FL + L_HUB

bottom = cq.Workplane("XY").circle(D_FL / 2).extrude(T_FL)
hub = cq.Workplane("XY").workplane(offset=T_FL).circle(D_HUB / 2).extrude(L_HUB)
top = cq.Workplane("XY").workplane(offset=T_FL + L_HUB).circle(D_FL / 2).extrude(T_FL)
part = bottom.union(hub).union(top)

# 6 bolt holes on the PCD through both flanges
bolts = cq.Workplane("XY").polarArray(PCD, 0, 360, N_BOLT).circle(D_BOLT / 2).extrude(H)
part = part.cut(bolts)
# center bore + keyway on +X
part = part.cut(cq.Workplane("XY").circle(D_BORE / 2).extrude(H))
key = cq.Workplane("XY").box(D_BORE / 2 + KEY_D, KEY_W, H, centered=(False, True, False))
part = part.cut(key)
result = part
