# Agent roles and prompts (condensed from the CADSmith paper)

## Planner (no code)
Input: the user prompt. Output `plan.json`:
```json
{"components": [{"name": "bottom flange", "shape": "disc", "dims_mm": {"d": 50, "t": 10}, "z_range": [0, 10]}],
 "target_bbox": [50, 50, 60],
 "holes": [{"diameter": 6.5, "count": 6, "pattern": "PCD 38"}, {"diameter": 14, "count": 1}],
 "n_solids": 1,
 "constraints": ["coaxial about Z", "keyway 5x2.5 on +X bore wall"],
 "notes_for_coder": "build as one revolve or 3 stacked cylinders; cut bore last"}
```
Use `null` for a bbox axis that can't be stated exactly. `volume_range` is optional.

## Coder
Input: plan + KB1 entries retrieved with `cadsmith.py kb "<keywords from plan>"`. Output: a CadQuery script ending with `result = ...`. Use named dimensions at the top. Comment each feature with the plan component it implements.

## Error Refiner (inner loop, ≤3)
Input: failing code + traceback + KB1 + KB2 (`cadsmith.py kb "<keywords>" --errors traceback.txt`). Fix only what the traceback implicates.

## Validator / Judge (outer loop): use an INDEPENDENT judge
CADSmith used a stronger, separate model as the judge to avoid self-confirmation bias. Here, spawn a separate subagent with a fresh context when the harness allows it. Otherwise judge yourself strictly against this rubric and say that the judge wasn't independent.

Judge inputs: (1) the original prompt, (2) the code, (3) kernel metrics plus the `check` result, (4) the three-view image.
Rules:
- Cross-reference ALL evidence: code logic, kernel measurements, rendered views.
- Count holes, bolts and mounting points visible in the renders and compare against the prompt.
- Check bbox dimensions against the prompt.
- Catch false convergence: metrics can look right while the shape is wrong (feature on the wrong side, missing keyway, flipped direction).
- Look closely at joints: gaps between arms and a hub can pass both the metrics and a coarse render. Require `n_solids == 1` for parts meant to be one piece.
- Escalation: if you gave the same feedback before, recommend a fundamentally different construction approach instead.
- Output: `{"passed": bool, "feedback": "specific numeric discrepancies and the fix"}`.
- A hard kernel failure (invalid / not watertight) is a FAIL regardless of appearance.

## Refiner (outer loop, ≤5)
Input: current code, judge feedback, plan, prompt, and the ledger history. Make targeted changes. From outer iteration 3 on (the ledger sets `escalate: true`), change the construction strategy instead of tweaking parameters.
