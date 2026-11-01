# Stage formats and how to reason at each stage

This loop follows LLM-3D Print (Jadhav, Pak & Barati Farimani, *Additive Manufacturing* 114
(2025) 105027). In the paper, separate agents handled each stage. Here the stages are done by
you, in order, and `printer.py` refuses to run them out of order.

| Paper agent | You do | Command |
|---|---|---|
| Image capture after the layer finishes (printer parked) | – | `wait`, `snapshot` |
| VLM failure detection | Look at `top.jpg` and `front.jpg`; write detect.json | `record detect` |
| Supervisor and state dictionary | Handled by the session file | – |
| Information-gathering planner + executor (ReAct) | Decide what you need to know and query it | `query <objects>` |
| Solution planner | Write plan.json: the smallest change that addresses the main failure | `record plan` |
| Solution executor | Safety-checked, all-or-nothing | `apply --live` |
| Handoff / resume | – | `resume --live` |

## detect.json

```json
{"problems": "Problems found" | "No problems found",
 "observations": ["concrete, located, visual facts — what and where"],
 "failures": ["named failure modes, most prominent first"],
 "previous_solution": "did last layer's change work? cite the occupancy change",
 "rating": 1-10}
```

How to look:
- Judge **only the layer just printed**. Earlier layers are context. The paper's prompt told
  the VLM to ignore the previous layer and to say whether the last fix worked.
- Tell the agent what the part is ("letters ME, 0.2 mm layers, PLA"). The paper found that
  knowing the object stops intended features from being flagged as defects.
- Name the location: "left stroke of M", "outer perimeter on the front face".
- Rule out what cannot happen. If the bed is known to be level, do not blame levelling. If the
  front camera shows no shift, write "no layer shift".
- Occupancy is a supporting number. Under-extrusion lowers it and blobs raise it. It never
  overrides what you see.

## Information gathering

When problems were found, query before you plan. Choose the objects that separate the
candidate causes:

| Failure | Query | What separates causes |
|---|---|---|
| Under-extrusion | `extruder gcode_move` | Is temperature at target? What are extrude_factor and speed_factor? Has the extruder ever reported `can_extrude` false? |
| Stringing / oozing | `firmware_retraction extruder` | Retraction length and speed; temperature |
| Over-extrusion / blobs | `gcode_move extruder` | extrude_factor, pressure_advance |
| Poor adhesion / warping | `heater_bed fan extruder` | Bed target and actual; part-cooling fan |
| Inconsistent first layers | `gcode_move` (homing_origin z) | Current Z offset |

Some causes need a person: wet filament, a worn nozzle, a loose belt, a partial clog that
needs a cold pull. Put these in `observations` and tell the user. Do not try to fix them with
G-code.

## plan.json

```json
[{"gcode": "M221 S110", "why": "failure -> lever -> expected effect"}]
```

- Change **one or two levers** per layer, so the next image tells you which one worked.
  The paper's runs changed four or five at once and then ratcheted (speed down to 30%), which
  is the drift `safety.py` now prevents.
- An empty list `[]` means "no change". Record it when you want to resume without touching
  anything.
- Every line must pass `printer.py check "<gcode>"`. See `safety.md`.
