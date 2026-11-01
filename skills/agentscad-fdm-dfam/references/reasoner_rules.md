# Design Reasoner rules (DFAM for FDM)

These condense the manufacturing system prompt described in AgentsCAD §4.4. The deterministic analysis (overhang flags, adjacency) is the ground truth. Never re-derive it, and never contradict it.

## Angle conventions
- Build direction is +Z; the bed is at the part's minimum Z.
- `overhang_deg` for a planar face is the downward tilt from vertical: 90 = flat ceiling, 0 = vertical wall. Actionable when > 45 (+0.5° tolerance) and the face is not on the bed.
- For bores, `overhang_deg = −tilt` of the axis from vertical; −90 = horizontal. The crown of a horizontal hole is an unsupported arch. Holes under Ø5 mm usually bridge acceptably.

## Mandatory decision order
1. **Reorientation (global).** Run `dfam.py candidates` (at most 4 candidates). Ground any rotation you consider with `dfam.py orient --rx --ry` and `dfam.py lay --face N`. Never state rotation angles you didn't get from a tool; without these tools the paper's agent hallucinated rotations confidently. Prefer: fewest actionable overhangs, then the least overhang area, then the largest bed contact, then the lowest height (stability, print time). A tall, thin footprint (bed contact area much smaller than the projected area) is a stability risk; say so.
2. **Local modifications, after orientation is fixed.** Face IDs refer to the ORIGINAL file.
   - Horizontal bore Ø ≥ 5 mm → `teardrop` (45° apex in the final build direction).
   - Downward ledge / ceiling edge → `chamfer` of the edge between the ledge and its wall (`"faces": [a, b]`) at 45°, so the ledge becomes self-supporting.
   - Sharp re-entrant corner under load → `fillet` (stress relief). Don't fillet bed edges (it causes elephant-foot and lifting).
   - Never chamfer or fillet the bed face itself, and don't modify vertical walls to "fix" overhangs.
3. **Supports.** Flag them only when no geometric fix keeps function (internal channels, functional undercuts).
4. **Split the part.** Last resort; it overrides everything else. Name the split plane and the joining method (pins, dovetail, adhesive).

## Function first
Don't change mating features, bore diameters, or sealing faces without saying so. A teardrop changes a bore's top profile: flag it if a shaft must be located by the full circle (ream after printing, or use a sacrificial bridge layer instead).

## Output (typed JSON consumed by `dfam.py modify`)
```json
{"part": "x.step",
 "reasoning": "short chain of thought, tied to face ids and tool outputs",
 "operations": [
   {"op": "teardrop", "face_id": 6},
   {"op": "chamfer", "faces": [3, 7], "distance": 2.0},
   {"op": "fillet", "face_id": 5, "radius": 1.0},
   {"op": "reorient", "rx_deg": -90, "ry_deg": 180, "bed_face": 3}
 ],
 "supports": [],
 "split": null}
```
`reorient` is always applied last, because rotation re-indexes faces.
