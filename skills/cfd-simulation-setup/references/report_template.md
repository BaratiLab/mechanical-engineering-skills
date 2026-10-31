# CFD run report — <case name>

**Verdict:** ACCEPT / CORRECT_AND_RERUN / REJECT / INCONCLUSIVE  (`<status>`, contract `<family> v<version>`)
**One-line answer to the request:** …

## 1. Request and specification
Request (verbatim): "…"

| Parameter | Value | Provenance |
|---|---|---|
| mach | 2.0 | stated_by_user |
| end_time | 4.0 | inferred_from_family_defaults |

Scope gate: N/N checks pass.

## 2. Case
Solver / module, physical model, BC formulation (from contract), mesh (cells, Δx, checkMesh summary), recipe SHA-256.

## 3. Evidence (copied from evidence.json, never retyped)
| Check | Category | Value | Threshold | Status |
|---|---|---|---|---|

## 4. Decision trail
| Iter | Diagnosis | Proposed action | Ruling | Reason |
|---|---|---|---|---|

## 5. Reference comparison (computed by code after diagnosis)
| Quantity | CFD | Theory/reference | Diff | Tolerance |
|---|---|---|---|---|

## 6. Physical interpretation
2–4 sentences on what the flow does. Use normalized units if the family is normalized.

## 7. Limitations
What acceptance does **not** certify: single-mesh acceptance is not grid independence; inviscid families ignore boundary layers; stationarity window length; any extractor fixes applied with re-analysis.

## 8. Artifacts
Case directory, logs, evidence.json, proposals, validator outputs, field images.
