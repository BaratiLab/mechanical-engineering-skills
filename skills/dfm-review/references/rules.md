# DFM rules by process (typical; confirm with your supplier)

## CNC milling / turning
| Rule | Guideline |
|---|---|
| Internal corner radius | ≥ 1/3 cavity depth; ≥ R1; ideally slightly larger than the tool radius (R3.2 for a Ø6 tool) |
| Pocket depth | ≤ 4× tool Ø (economical), ≤ 6× (possible) |
| Wall thickness | Al ≥ 0.8, steel ≥ 0.5, plastic ≥ 1.5 mm |
| Hole depth | ≤ 4× Ø standard drill; ≤ 10× with peck drilling; standard drill sizes |
| Thread depth | 1.5× Ø is enough; avoid > 3× Ø |
| Tolerances | ±0.1 standard, ±0.025 achievable, < ±0.01 = grinding/costly |
| Surface finish | Ra 3.2 as-machined; Ra 1.6 one extra pass; Ra 0.8 or better is costly |
| Setups | minimize; design features accessible from 1–2 directions |
| Text/engraving | ≥ 0.5 mm stroke, engraved not embossed |
| Sharp external edges | specify an edge break |

## Sheet metal
| Rule | Guideline |
|---|---|
| Inside bend radius | ≥ material thickness t |
| Flange length | ≥ 4t (≥ 3t + R) |
| Hole to bend | ≥ 2.5t + R |
| Hole to edge | ≥ 2t; hole Ø ≥ t |
| Bend relief | width ≥ t, depth ≥ R + t |
| Slot width | ≥ 1.5t |
| Tolerance | ±0.1 punched, ±0.25 across bends |
| Constant thickness | one gauge per part |

## Injection molding
| Rule | Guideline |
|---|---|
| Wall | uniform; ABS/PC 1.2–3.5, PP 0.8–3.8, PA 0.8–3.0 mm; transitions ≤ 15% per step, tapered 3:1 |
| Draft | ≥ 0.5° (1–2° typical); +1° per 0.025 mm texture depth |
| Ribs | thickness 0.5–0.6× wall, height ≤ 3× wall, spacing ≥ 2× wall |
| Bosses | OD ≈ 2× screw Ø, wall 0.6× nominal, cored, gusseted |
| Corners | inside R ≥ 0.5 wall, outside R = inside + wall |
| Undercuts | avoid, or use bump-offs, pass-through cores, side actions (+$$) |
| Holes | depth ≤ 3× Ø blind |
| Gate / weld lines | keep away from load-bearing and cosmetic faces |

## Die / sand casting
Wall ≥ 1.5 mm (die), ≥ 3–5 mm (sand); draft 1–3°; uniform sections; fillets everywhere; machining allowance 1–3 mm on machined faces.

## Additive manufacturing
| Process | Min wall | Min hole | Overhang | Notes |
|---|---|---|---|---|
| FDM | 1.2 | 2 | ≤ 45° unsupported | anisotropic in Z, orient load in XY |
| SLA | 0.6 | 0.5 | supports needed | drain holes Ø ≥ 3.5 for hollow parts |
| SLS / MJF | 0.8 | 1.5 | no supports | escape holes for powder |
| Metal LPBF | 0.4 | 1.0 | ≤ 45°, supports removed by machining | stress relief, HIP for fatigue |
