# Design defaults for unspecified features (mm)

## Clearance holes, ISO 273 (fine / medium / coarse)
| Thread | Fine | Medium | Coarse | Tap drill | Counterbore Ø × depth (SHCS) |
|---|---|---|---|---|---|
| M3 | 3.2 | 3.4 | 3.6 | 2.5 | 6.5 × 3.3 |
| M4 | 4.3 | 4.5 | 4.8 | 3.3 | 8.0 × 4.4 |
| M5 | 5.3 | 5.5 | 5.8 | 4.2 | 9.5 × 5.4 |
| M6 | 6.4 | 6.6 | 7.0 | 5.0 | 11.0 × 6.5 |
| M8 | 8.4 | 9.0 | 10.0 | 6.8 | 14.5 × 8.6 |
| M10 | 10.5 | 11.0 | 12.0 | 8.5 | 17.5 × 10.8 |
| M12 | 13.0 | 13.5 | 14.5 | 10.2 | 20.0 × 13.0 |

## Edge distances
- Hole center to edge ≥ 1.5 × hole Ø (machined plate); ≥ 2 × Ø (sheet metal).
- Hole-to-hole spacing ≥ 3 × Ø.

## Minimum wall thickness
| Process | Wall |
|---|---|
| CNC aluminum | 1.0 (0.8 if small) |
| CNC steel | 0.8 |
| FDM print | 1.2 (3 perimeters at 0.4 nozzle) |
| SLA | 0.8 |
| SLS nylon | 1.0 |
| Injection molding | 1.0–3.0, uniform |
| Die casting aluminum | 1.5 |

## Fillets and chamfers
- Internal corners of CNC pockets: radius ≥ tool radius; default R ≥ depth/3, minimum R1.
- Default edge break: 0.5 × 45° chamfer.
- Stress-relief fillet at a load-bearing shoulder: r/d ≥ 0.1.

## Fit tolerances (ISO 286, hole-basis)
Sliding H7/g6 · Locational clearance H7/h6 · Light press H7/p6 · Rolling-bearing seats: shaft k6 (rotating inner ring), housing H7
