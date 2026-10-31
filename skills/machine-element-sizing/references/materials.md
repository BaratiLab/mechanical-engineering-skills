# Common materials (typical minimums; confirm against supplier certs)

| Material | Condition | Sut (MPa) | Sy (MPa) | E (GPa) | Notes |
|---|---|---|---|---|---|
| AISI 1018 | cold-drawn | 440 | 370 | 205 | low-carbon, weldable |
| AISI 1020 | hot-rolled | 380 | 210 | 205 | |
| AISI 1045 | cold-drawn | 630 | 530 | 205 | general shafts |
| AISI 1050 | cold-drawn | 690 | 580 | 205 | |
| AISI 4140 | Q&T 425 °C | 1250 | 1140 | 205 | high-strength shafts |
| AISI 4340 | Q&T 425 °C | 1470 | 1360 | 205 | |
| 304 stainless | annealed | 515 | 205 | 193 | |
| 17-4 PH | H1025 | 1070 | 1000 | 197 | |
| 6061-T6 Al | — | 310 | 276 | 69 | no endurance limit; use 5e8-cycle strength ≈ 97 MPa |
| 7075-T6 Al | — | 572 | 503 | 72 | 5e8-cycle ≈ 159 MPa |
| Ti-6Al-4V | annealed | 900 | 830 | 114 | |
| Gray cast iron | ASTM 30 | 214 | — | 100 | brittle; use MNS/Mohr |

Source: Shigley 11e Tables A-20 to A-24, ASM Handbook. Aluminum and titanium have no true endurance limit: the shaft command's `Se' = 0.5 Sut` is for steels only. For non-ferrous alloys, pass the fatigue strength at the design life instead.
