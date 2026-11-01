# RocketSmith: notes for this skill

Pak, Barkley, Loghmani, Baich, Pamal, Barati Farimani. *RocketSmith: Agentic Additive Manufacturing of
High-Powered Rockets.* arXiv:2606.00097 (2026). Code: github.com/ppak10/RocketSmith (a Claude Code plugin).

## System
- **Tools:**
  - OpenRocket (via orhelper) is the source of truth for the component tree, stability and flight
    simulation.
  - build123d produces parametric STEP parts, through CADSmith.
  - PrusaSlicer gives printed mass and G-code.
- **Six subagents:** rocketsmith, cadsmith, gui, manufacturing, openrocket, prusaslicer.
- **Seven skills:** design-for-additive-manufacturing, generate-structures, mass-calibration,
  modify-structures, motor-selection, print-preparation, stability-analysis.
- **Design principle, from RocketBench's finding** that LLMs plateau when they iterate numbers
  themselves: every numeric step (stability, trajectory, slicing, mass) is a tool, and the LLM
  orchestrates.
- **Stability:** (x_CP − x_CG)/d, with CP from Barrowman. The paper wants 1.00–1.25 cal; the flown
  designs had 1.26–1.63 cal at liftoff.

## The four flights (3 May 2026, Tripoli Pittsburgh, RSO-supervised)

| | HP1 | HP2 | HP3 | HP4 |
|---|---|---|---|---|
| Motor | AeroTech H100W | H219T | H219T | J425R (L2) |
| Mass (g) | 2249.8 | 2166.1 | 1857 | 5158.8 |
| Length / diameter (mm) | 850 / 101.6 | 800 / 101.6 | 850 / 101.6 | 1150 / 127.0 |
| Stability, liftoff (cal) | 1.26 | 1.63 | 1.27 | 1.52 |
| OpenRocket apogee | 338.8 m | – | – | 570.1 m |
| Measured apogee | 276 m (80%) | – | – | 479 m (84%) |
| OpenRocket max velocity | 76.4 m/s | – | – | 115.2 m/s |
| Measured max velocity | 63.3 m/s | – | – | 92.4 m/s |
| Outcome | Stable launch; the lower airframe split at the baffle from the ejection charge, eyebolt pulled out | Stable launch; recovery bay didn't separate, so it came down ballistic | Recovered intact (later cracked in tree retrieval) | Recovered, reflyable |

Printing: PETG and ABS (not PLA, which has too low a heat deflection temperature), 15% gyroid infill,
4–5 walls, 0.2 mm layers, on an Ender 3, an Ender 5 Plus and a Voron 2.4 for the tall airframes.

## This skill compared with the paper
- **Same ideas:** deterministic tools for every number, stability-driven fin sizing, mass
  calibration from slicer and scale, DFAM part consolidation (integrated motor mount), and printable
  STEP/STL output.
- **Self-contained substitutes:**
  - Barrowman CP and a 1-D flight model replace OpenRocket.
  - CadQuery replaces build123d; both use the same OpenCASCADE kernel.
  - A wall-plus-infill mass model replaces PrusaSlicer; slice for real and `calibrate` with weighed
    parts.
- **Agreement with the paper's OpenRocket predictions,** using approximate reconstructions of HP1 and
  HP4 (`examples/`). Fins were sized to the paper's stability, mass matched, Cd 0.45, and thrust
  curves were shaped from the certification summaries:

| | Apogee | Max velocity |
|---|---|---|
| HP1, this skill | 326 m | 75.0 m/s |
| HP1, paper's OpenRocket | 338.8 m | 76.4 m/s |
| HP4, this skill | 568 m | 113.7 m/s |
| HP4, paper's OpenRocket | 570.1 m | 115.2 m/s |

  Max acceleration is higher here (54 vs 48 m/s²; 95 vs 79 m/s²) because the summary-shaped curve
  has a sharper peak than the real .eng file.
- **Drag calibration from the altimeter:** the measured apogees imply **Cd ≈ 0.84 (HP1) and 0.76
  (HP4)**, against the 0.45–0.55 typical of smooth airframes. Printed surfaces, rail buttons, open
  slots and weathercocking all cost altitude. `calibrate --apogee` fits Cd so the next prediction
  starts from flight data.

## Deliberately out of scope
Motor, propellant, igniter and ejection-charge design or sizing. The skill uses certified commercial
motors only and leaves recovery charges to the flyer's certification and the Range Safety Officer.
