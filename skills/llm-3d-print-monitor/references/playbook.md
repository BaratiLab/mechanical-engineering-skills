# Defect → lever playbook (FDM, Klipper), safe step sizes

These values come from the corrections the LLM-3D Print agents made in the paper. They are
capped at the step and range limits in `safety.py`.

| Observation | Likely cause (check first) | First lever | Second lever | Do not |
|---|---|---|---|---|
| Gaps between infill lines, thin or broken perimeters | Low flow, partial clog, too fast, too cold | `M221` +5 to 10% | `M220 S75` to `S85`; `M104` +5 to 10 °C | Push flow past 115%. Past that point it is a hardware problem: tell the user |
| Hairs between islands | Retraction too short or slow, too hot | `SET_RETRACTION RETRACT_LENGTH` +25% (direct drive ≤ 2 mm, Bowden ≤ 6 mm) | `M104` −5 °C | Raise retraction every layer. If two steps don't help, suspect wet filament |
| Blobs, zits, rough top surface | Over-extrusion, pressure advance too low | `M221` −5% | `SET_PRESSURE_ADVANCE ADVANCE=` +0.01 to 0.02 (≤ 0.1 for PLA direct drive) | – |
| Bulging corners | Pressure advance too low, accel too high | `SET_PRESSURE_ADVANCE` +0.01 | `M204 S` −20% | – |
| Lines not fused to the layer below | Too cold, too much cooling, nozzle too high | `M104` +5 °C | `M106` lower; `SET_GCODE_OFFSET Z_ADJUST=-0.02 MOVE=1` | Large Z steps; Z changes are ±0.05 mm per step, ±0.2 mm total |
| Curling or lifting edges | Too little cooling (PLA) or too much (PETG/ABS); bed | `M106` up for PLA, down for PETG | `M140` +5 °C | – |
| TPU or other flexibles: stringing, poor feed | Too hot or too fast | `M220 S50` | `M104 S220` (paper value for TPU) | – |
| Layer shift | Mechanical | **Stop.** Tell the user | – | Try to compensate in G-code |
| Spaghetti, detached part | Adhesion lost | **Stop.** Tell the user to cancel | – | Resume |

Material windows used for the bounds (hotend °C): PLA 190–230, PETG 225–250, ABS/ASA
235–260, TPU 210–235. Pass `--limits` with a JSON file to narrow `hotend_C` for a specific
material.
