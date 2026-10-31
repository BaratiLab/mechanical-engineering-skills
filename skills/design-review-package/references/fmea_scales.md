# DFMEA rating scales (condensed AIAG-VDA)

| Rating | Severity (effect) | Occurrence (design cause likelihood) | Detection (design control finds it before release) |
|---|---|---|---|
| 10 | Safety / regulatory, no warning | New tech, no history | No control / cannot detect |
| 9 | Safety / regulatory, with warning | — | Not likely to detect |
| 8 | Loss of primary function | Very high: new design, little experience | Unproven analysis |
| 7 | Degraded primary function | High | Simulation not correlated |
| 6 | Loss of secondary function | Moderate-high | Test after design freeze |
| 5 | Degraded secondary function | Moderate: similar designs had issues | Test during development, pass/fail |
| 4 | Annoyance, most customers notice | Low-moderate | Test-to-failure during development |
| 3 | Annoyance, some notice | Low: few failures on similar designs | Degradation testing |
| 2 | Annoyance, discriminating customers | Very low | Proven analysis, correlated |
| 1 | No discernible effect | Prevented by design / standard | Failure mode designed out |

RPN = S × O × D (legacy). Prefer action priority: H if S ≥ 9 with O ≥ 4 or D ≥ 7, or S ≥ 7 with O ≥ 4 and D ≥ 5.
