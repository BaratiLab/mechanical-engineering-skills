# Performance indices (maximize)

| Component & objective | Constraint | Free variable | Index | `--index` |
|---|---|---|---|---|
| Tie, min mass | stiffness | area | E/ρ | stiff-tie |
| Tie, min mass | strength | area | σy/ρ | strong-tie |
| Beam, min mass | stiffness | section size | E^½/ρ | stiff-beam |
| Beam, min mass | strength | section size | σy^⅔/ρ | strong-beam |
| Panel/plate, min mass | stiffness | thickness | E^⅓/ρ | stiff-panel |
| Panel/plate, min mass | strength | thickness | σy^½/ρ | strong-panel |
| Column, min mass | buckling | section size | E^½/ρ | stiff-beam |
| Spring, min volume | no yield | — | σy²/E | spring |
| Spring, min mass | no yield | — | σy²/(Eρ) | light-spring |
| Elastic hinge / snap fit | no yield | — | σy/E | flexure-hinge |
| Pressure vessel, leak before break | — | — | K_IC/σy | damage-tolerant |
| Precision structure | thermal distortion | — | k/α | thermal-stability |

For minimum **cost**, replace ρ with ρ·Cm (`--minimize-cost`).

Derivation pattern (stiff beam, square section b×b, length L fixed):
m = ρ b² L; stiffness S = C E b⁴/(12 L³) → b² = (12 S L³ / C E)^½ → m = (12 S/C)^½ L^{5/2} · ρ/E^½, so maximize E^½/ρ.
