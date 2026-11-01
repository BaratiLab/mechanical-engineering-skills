G90
M82            ; absolute extrusion
G92 E0
G1 Z0.2 F3000
G1 X10 Y10 F6000
G1 X20 Y10 E1.0 F1200   ; 10 mm, E +1.0
G1 X20 Y20 E2.0         ; 10 mm, E +1.0
G92 E0                  ; reset mid-layer
G1 X10 Y20 E1.0         ; 10 mm, E +1.0 (after reset)
G91                     ; relative positioning
G1 X0 Y-10 E1.0         ; 10 mm, E abs 1.0 -> +0.0? (M82 absolute: E1.0 again = no extrusion)
G1 X-5 Y0 E1.5          ; relative move, E +0.5
G90
M83                     ; relative extrusion
G1 Z0.4
G1 X0 Y0 E0.3
