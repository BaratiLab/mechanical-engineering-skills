# AI agentic SLS process optimization: notes for this skill

Pak, Alvarado, Barati Farimani. *AI Agentic Selective Laser Sintering Process Optimization.* arXiv:2608.25928 (2026).

## Setup
- **Machine:** SLS4All Inova Mk1, an open-source kit. It has a 10 W, 450 nm blue diode laser,
  150 × 150 × 185 mm build volume, halogen surface heating and a 32 × 24 px thermal camera. Average
  scan speed is about 1650 mm/s at 5 W and 2800 mm/s at 10 W. Polymers up to about 200 °C melt.
- **Agent:** Claude Fable with MCP tools in several harnesses, plus PostgreSQL memory of previous
  builds. Tool groups cover:
  - material info (technical data sheets)
  - initial testing (a 5 × 5 grid of parameter patches)
  - print profile and build history
  - recorded ASTM data
  - runtime overrides (surface temperature, recoating, energy)

  A GUI shows the proposed parameters and the reasoning before each build; a human approves it.
- **Fixed for every build:** 145 °C chamber, 100 µm layers, 100% recoater speed, overnight cooling.
- **Tests:** ASTM D638 Type 1 and Type 4 (tensile) and D790 (flexural) on an Instron 4469 with a
  50 kN cell, at least 5 specimens per batch. **Tables report the best specimen.**

## Results (best specimen; fill line energy in mJ/mm, overlap %, surface temperature °C)

**PA12 GF, manual tuning** (TDS: Et 2800 MPa, UTS 38 MPa; Formlabs reference parts measured Et 2599 MPa)
- Fourteen batches, A–N, moved fill from 14 to 40, overlap from 25 to 50 and surface temperature
  from 172 to 178.
- Batch H (24, 50, 173) reached Et 2817 MPa, but the result **wasn't reproducible** and was excluded.
- Batch J (32, 50, 178) was the best reproducible batch: Et 2482 MPa, UTS 23.0 MPa.

**PA11 Onyx, agentic** (TDS: Et 1680, UTS 55, Ef 1290, σf 54.2 MPa; Sinterit specifies a
nitrogen atmosphere, which the Inova Mk1 doesn't have)

| Batch | Fill / overlap / surface | Et (MPa) | UTS (MPa) | Note |
|---|---|---|---|---|
| O | 36 / 50 / 186 | 934 | – | Heavy warping, only 3 samples survived |
| P | 32 / 33 / 186 | 827 | – | |
| Q | 32 / 50 / 186 | 1323 | – | |
| R | 34 / 50 / 188 | **1571** | **36.3** | |

**PA12 Blend, agentic** (25% PA12 GF + 75% PA12 White, so the glass-filled powder raises
absorptivity for the blue laser)

| Batch | Fill / overlap / surface | Et (MPa) | UTS (MPa) | σf (MPa) |
|---|---|---|---|---|
| S | 48 / 50 / 168 | 1092 | 14.4 | – |
| T | 56 / 50 / 168 | 1675 | 35.2 | 47.3 |
| U | 56 / 50 / 172 | 1678 | **44.4** | **60.6** |

U's UTS is above the PA12 GF TDS (38) and close to PA12 White (47).

## How this skill differs
- SQLite stands in for PostgreSQL as the memory. `init --seed-paper` loads all 21 batches above, so
  a new user starts with the lab's evidence.
- A **bounded Gaussian-process expected-improvement** suggester gives the agent ranked, explainable
  options:
  - fill within ±8 mJ/mm of the best batch;
  - overlap chosen from {25, 33, 50};
  - surface temperature between 25 °C and 3 °C below the melt peak.

  The agent still decides, and states why.
- Replaying PA12 GF history, the suggester points the same way the manual tuning eventually went:
  - after batches A–C it changes overlap 25 → 50, which was batch D's real improvement;
  - after A–E it raises fill to 28 (batch I);
  - after A–G it suggests fill 30 (between I and J).
- An ASTM reducer computes Et, UTS, Ef and σf from raw load–displacement CSVs. It reports **mean ± sd
  as well as the best specimen**, because best-specimen values hide scatter. Batch H shows why that
  matters.
- Printer communication (Inova Mk1 firmware plugins or other machines) is out of scope. The skill
  outputs the parameters and the reasoning, and the operator loads the profile.
