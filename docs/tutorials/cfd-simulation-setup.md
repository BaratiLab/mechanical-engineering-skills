# Tutorial: CFD Forge (physics-constrained CFD setup and acceptance)

**Skill:** [`cfd-simulation-setup`](../../skills/cfd-simulation-setup) · **Paper:** A. S. Oza, R. F. Johnson, A. Barati Farimani, *CFD Forge: A Physics-Constrained Agentic Framework for Autonomous CFD*, [arXiv:2610.14104](https://arxiv.org/abs/2610.14104) · **Code:** [aakashoza31/physics-constrained-cfd-agent](https://github.com/aakashoza31/physics-constrained-cfd-agent)

The agent does the open-ended work: interpreting the request, building the case, diagnosing, proposing one action from a closed list, and writing the report. **Only registered, deterministic contracts decide acceptance.** In the paper, a model judging from the evidence alone accepted 12 of 13 detectable planted faults; with the contracts deciding, it accepted none.

## Use cases
- **Trustworthy automated CFD** in design sweeps and active-learning loops, where an unattended run must not be accepted just because the solver finished.
- **OpenFOAM case setup from a text request**, with provenance for every parameter (stated by the user or a family default).
- **Auditable run reports**: every proposal, ruling, check, and threshold is recorded.
- **Registering your own flow family** (pipe, airfoil, bluff body) with declared tolerances *before* seeing results.
- **Teaching verification**: a settled mean drag isn't a developed flow, a single mesh isn't mesh independence, and unequal inlet and outlet flux isn't a mass error if storage balances it.

## Setup
```bash
npx skills add BaratiLab/me-design-skills --skill cfd-simulation-setup
pip install numpy
# OpenFOAM Foundation v11+ for the solve (the paper used v14); everything else runs without it
python tests/test_paper_cases.py      # 50 checks: replays the paper's recorded decisions and planted faults
```

## Walkthrough: the paper's Mach-3 mesh-sensitivity request
> *"2-D forward-facing step, Mach 3, step height 0.2, step at x = 0.6. Does the result depend on the mesh?"*

**1. Stated values only → resolved spec with provenance**
```bash
echo '{"mach": 3.0, "step_height": 0.2, "step_x": 0.6, "request_criteria": ["transient_health", "grid_sensitivity"]}' > stated.json
python scripts/build_case.py spec --family forward-step-2d --stated stated.json --out spec.json
```
| Parameter | Value | Provenance |
|---|---|---|
| mach | 3.0 | stated_by_user |
| step_height | 0.2 | stated_by_user |
| step_x | 0.6 | stated_by_user |
| end_time | 4.0 | inferred_from_family_defaults |
| max_co | 0.2 | inferred_from_family_defaults |
| dx | 0.0125 | inferred_from_family_defaults |

**2. Scope gate, then build**
```bash
python scripts/validate.py scope --family forward-step-2d --spec spec.json     # in_scope: true
python scripts/build_case.py forward-step --spec spec.json --case case_m3      # 16,128 cells (the paper's mesh)
cd case_m3 && ./Allrun.agent                                                    # blockMesh, checkMesh, foamRun
```

**3. Evidence → blind packet → one proposal.** After `evidence.py` extracts the checks, both the coarse and the refined (×2) grid pass every hard check. The agent proposes:
```json
{"diagnosis": "HEALTHY_COMPLETE", "action": "ACCEPT", "evidence_cited": ["all hard checks on both grids"]}
```

**4. The gates decide**
```bash
python scripts/validate.py action  --evidence evidence.json --proposal proposal.json
python scripts/validate.py verdict --evidence evidence.json
```
```
REFUSED | scientific validator does not return ACCEPT:
          request depends on criteria with no registered tolerance: ['grid_sensitivity']
          → STOPPED_ACTION_REFUSED → INCONCLUSIVE
verdict: INCONCLUSIVE  UNREGISTERED_CRITERION  16/16 checks pass
```
Both solutions are healthy, but nobody declared how much cross-grid change is acceptable, so the sensitivity question **can't be certified**. This matches the paper's recorded refusal. Remove the sensitivity request and the same evidence gives `ACCEPT / PASS_2D_FORWARD_STEP`.

To make such requests answerable, register a cross-grid tolerance in a new contract version **before** running (see [`new_family.md`](../../skills/cfd-simulation-setup/references/new_family.md)).

## More behaviours to try
| Situation | What the gates do |
|---|---|
| Nozzle at t = 1 ms, drift 2% > 0.2% | `CORRECT_AND_RERUN`; `CONTINUE_RUN` approved, an early `ACCEPT` refused |
| Step reached only t = 2 of 4 | `CONTINUE_RUN` refused (requested horizon reached); `EXTEND_END_TIME 2→4` approved; going past 4 refused |
| Front pushed to the inlet (Mach 3, h = 0.3) | `REJECT`; theory shows the flow choked (A*/A 0.719 > 0.70) |
| Cube lateral-force growth 2.10 > 1.25 | `REJECT / STILL_DEVELOPING`, even though mean drag settled |
| OpenFOAM `sigFpe : Enabling floating point exception trapping` | not fatal (this exact false positive stopped a run in the paper) |

## Prompts to try
- *"Set up and run a Mach 2.5 forward step with h = 0.15 and tell me if it passes."*
- *"Register a family for laminar pipe flow (Re 100–2000) with Hagen–Poiseuille as the reference, then run Re = 800."*
