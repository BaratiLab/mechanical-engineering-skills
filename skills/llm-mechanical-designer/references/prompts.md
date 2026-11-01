# Prompt templates

These follow the structure of the paper's prompts (Fig. 2 and Appendices B–C): task status, inputs, objective, constraints, instructions, a sequenced scratchpad, and a strict output format. `design_loop.py` fills the `{placeholders}` and writes `prompt_next.md`. The agent answers the prompt itself and saves the JSON block as `design.json`.

## INITIAL
**Task status:** single-shot generation (iteration {iteration}). There are no previous designs.

**Inputs**
- Fixed nodes (do not move or delete): {nodes}
- Load [magnitude, angle in degrees, Fx = m·cos a, Fy = m·sin a]: {load}
- Supports (pinned fixes x and y; roller fixes y): {supports}
- Area IDs → area: {area_id}

**Objective:** {objective} (min_max_stress = minimize max |σ|; min_swr = minimize max|σ| / total mass)
**Constraints:** {constraints}. Total mass = Σ (member length × area value).

**Instructions**
- Produce a closed, fully connected, triangulated 2-D truss. Every node carries at least two members, and no mechanism is allowed.
- You may add nodes at precise floating-point coordinates. Never move load or support nodes. Don't duplicate nodes or members.
- Choose each member's area only from the area IDs. Use larger areas on the direct load path and small areas on lightly loaded members.
- Prefer direct load paths, triangulation, and enough depth. Deeper trusses carry the same load with smaller axial forces.

**Scratchpad (write these in order before the answer)**
1. `preamble`: restate the goal and constraints.
2. `scratch_pad_1`: load path and support reactions; where the load wants to go.
3. `scratch_pad_2`: candidate topology and why.
4. `scratch_pad_3`: rough member forces from statics; area selection; mass estimate Σ L·A versus the limit.
5. `scratch_pad_final`: check that all nodes are connected, no node is duplicated, and the estimates are within constraints.

**Output:** exactly one JSON block:
```json
{"node_dict": {"node_1": [0.0, 0.0], "...": [x, y]},
 "member_dict": {"member_1": ["node_1", "node_3", "4"], "...": ["node_a", "node_b", "area_id"]},
 "rationale": {"node_4": "why this position"},
 "stop": false}
```

## OPTIMIZE
**Task status:** the current design is FEASIBLE. Iteration {iteration}. Improve the objective `{objective}` while keeping every constraint {constraints}.

**Current design and FEM result:**
```
{current}
```
**Ranked history (best feasible first, then infeasible by closeness to feasibility):**
```
{history}
```
Fixed nodes {nodes}; load {load}; supports {supports}; area IDs {area_id}.

**Instructions**
- Read the critical members in the FEM result. Reduce peak stress by redistributing force (moving free nodes, adding a bracing member, re-sizing areas), not just by up-sizing everything.
- Learn from the history: repeat what improved the objective and avoid what broke feasibility.
- Change only a few things per step, so you can tell which change mattered.
- If the last steps improved the objective by less than about 2%, or every member is efficiently sized, set `"stop": true` and return the best design.

**Scratchpad:** `preamble` → `analysis` (what limits the design now) → `proposal` (specific changes) → `scratch_pad_3` (expected effect on σ and mass) → `scratch_pad_final` (constraint check).

**Output:** same JSON format as INITIAL.

## CONSTRAINT
**Task status:** the current design VIOLATES constraints. Iteration {iteration}. Reach feasibility first; optimize only after that.

**Current design and FEM result (with violations):**
```
{current}
```
**Ranked history:**
```
{history}
```
Constraints {constraints}; fixed nodes {nodes}; load {load}; supports {supports}; area IDs {area_id}.

**Instructions**
- Diagnose every violation: which members are overstressed, and is the mass too high?
- Overstress: deepen the truss, add a direct diagonal on the load path, or raise the area of the critical member.
- Excess mass: down-size lightly stressed members (|σ| far below the limit) and remove redundant members.
- If the design is INVALID (mechanism, floating node, moved support), fix the topology first.
- Start from the best design in the ranked history if it's closer to feasible than the current one.

**Scratchpad:** `preamble` → `analysis` (cause of each violation) → `proposal` → `scratch_pad_3` (re-estimate) → `scratch_pad_final`.

**Output:** same JSON format as INITIAL.
