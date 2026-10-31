# First-iteration defaults (always flag as assumptions)

## Shaft stress concentrations (Shigley Table 7-1, steel)
| Feature | Kt (bending) | Kts (torsion) |
|---|---|---|
| Shoulder fillet, sharp (r/d = 0.02) | 2.7 | 2.2 |
| Shoulder fillet, well rounded (r/d = 0.1) | 1.7 | 1.5 |
| End-mill keyseat (r/d = 0.02) | 2.14 | 3.0 |
| Sled-runner keyseat | 1.7 | — |
| Retaining ring groove | 5.0 | 3.0 |

Use Kf ≈ Kt and Kfs ≈ Kts (conservative) on the first pass, then refine with notch sensitivity q.

## Bolted joint stiffness constant C
| Joint | C |
|---|---|
| Steel bolt, steel members, no gasket | 0.15–0.25 |
| Steel bolt, aluminum members | 0.25–0.35 |
| Soft gasket | 0.5–0.9 (prefer confined gasket) |

## Bearing application factor af
| Service | af |
|---|---|
| Precision gearing | 1.0–1.1 |
| Commercial gearing | 1.1–1.3 |
| Light impact | 1.2–1.5 |
| Heavy impact (crushers) | 1.5–3.0 |

## Design-life hours (bearings)
Household appliances 1–2k; intermittent machinery 4–8k; 8-h/day machinery 15–30k; 24-h continuous 50–100k.
