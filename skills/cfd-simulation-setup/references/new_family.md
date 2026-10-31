# Registering a new flow family

A family = (envelope, defaults, recipe, builder, checks with thresholds, action vocabulary). Register it in `scripts/contracts.py` **before** the first result exists, and date the commit. Thresholds are declared engineering tolerances: never relax one to pass a run. To change one, bump `version` and record why.

## 1. Pin the physics with the user
| Item | Example (laminar pipe) |
|---|---|
| Physical model | incompressible, laminar, Newtonian |
| Solver / module | `foamRun -solver incompressibleFluid` |
| Envelope | Re 100–2000, L/D 20–200 |
| BC formulation (fixed) | inlet fixedValue U (parabolic/uniform), outlet fixedValue p=0, wall noSlip |
| Numerics (fixed recipe) | copy from a tutorial; hash `system/fvSchemes`, `fvSolution`, `constant/*` |
| Reference | Hagen–Poiseuille Δp = 128 μ L Q / (π D⁴); entrance length ≈ 0.05 Re D |

## 2. Choose checks by category
- **hard**: a violation means the solution is wrong, not unfinished. Covers mesh validity, solver completion with no fatal signature, positive/finite fields, boundary conservation (wall flux ≈ 0), a realized inlet condition, BC audit, and y⁺ in the wall model's range.
- **development**: healthy but unfinished. Covers horizon reached, monitor drift, field change between writes, mass balance, residual floor, lateral-force growth, and cross-grid change (only when the request asks for grid sensitivity).
- **reference**: comparison with theory or experiment. Hidden from diagnosis; computed by code afterwards.

Starting thresholds (edit with the user):

| Check | Steady | Transient / statistically stationary |
|---|---|---|
| Monitor drift over final window | < 0.2–0.5 % | least-squares drift < 2 % of mean |
| Mass balance | < 0.1 % | storage-aware closure < 1e-6 (explicit FV) |
| Residuals (initial) | < 1e-4 to 1e-5 | per-step convergence within outer loops |
| Fluctuation growth | — | 2nd-half / 1st-half mean abs < 1.25 |
| Window length | ≥ 3 flow-throughs | ≥ 10 shedding periods (≥ 20 convective units) |
| Cross-grid change (if requested) | < 1–2 % last pair; GCI with 3 grids | same, on time-averaged quantities |
| Mesh quality | non-ortho < 70°, skewness < 4 | same |

## 3. Choose the action vocabulary
Pick from: ACCEPT, CONTINUE_RUN, EXTEND_END_TIME, REFINE_MESH (or REFINE_<region>), REPAIR_MESH, REDUCE_MAX_CO, REDUCE_RELAXATION, RESTART_CLEAN, REBUILD_FROM_VALIDATED_SPEC, REQUEST_DIAGNOSTIC, REQUEST_CLARIFICATION, REJECT_UNSUPPORTED, FAIL_SAFELY. Only list actions that have an executable, bounded implementation. Then add rules for any new action in `validate.py::validate_action`.

## 4. Write the builder
Add a function in `scripts/build_case.py` that turns the resolved spec into a case. Copy the recipe from a template, write the mesh (blockMeshDict via the `BlockMesh` helper, or snappyHexMesh/gmsh for CAD), and set values with `foamDictionary`. Store `case_record.json`.

## 5. Freeze with an LLM-free reference campaign
Run the family once by hand on 3–4 grids and 2–3 numerical controls (halved Courant number, a perturbed start). Record the last-pair changes. This shows the recipe is sound before the agent uses it. The paper's nozzle campaign: last-pair change < 0.5 %, controls < 0.2 %.

## 6. Test with planted faults
Copy an accepted evidence.json, alter one diagnostic at a time (solver_completed=false, negative minimum, wall flux, horizon not reached, missing patch), and confirm `validate.py verdict` never returns ACCEPT. Add these as regression tests.
