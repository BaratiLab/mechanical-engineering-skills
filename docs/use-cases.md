# Use cases: Barati Farimani Lab research skills

Six skills in this library package Barati Farimani Lab papers as agent workflows. Each has a step-by-step tutorial with real outputs.

| Skill | Paper | Best for | Tutorial |
|---|---|---|---|
| `cfd-simulation-setup` | CFD Forge (arXiv:2610.14104) | Trustworthy OpenFOAM setup, diagnosis and acceptance | [tutorial](tutorials/cfd-simulation-setup.md) |
| `cadsmith-text-to-cad` | CADSmith (arXiv:2603.26512) | Dimension-exact CadQuery parts from text, with kernel + vision validation | [tutorial](tutorials/cadsmith-text-to-cad.md) |
| `query2cad-freecad` | Query2CAD (arXiv:2406.00144) | FreeCAD macros from plain language, with a self-refinement loop | [tutorial](tutorials/query2cad-freecad.md) |
| `agentscad-fdm-dfam` | AgentsCAD (arXiv:2607.02448) | Making STEP parts printable: orientation, teardrops, chamfers | [tutorial](tutorials/agentscad-fdm-dfam.md) |
| `image2gcode` | Image2Gcode (Addit. Manuf. Lett. 2026) | Photo or sketch → G-code for 2D/2.5D parts, toolpath datasets | [tutorial](tutorials/image2gcode.md) |
| `llm-mechanical-designer` | LLM Agent as a Mechanical Designer (arXiv:2404.17525) | LLM-in-the-loop truss design against exact FEM | [tutorial](tutorials/llm-mechanical-designer.md) |

## By the job to be done

**"I have an idea in words and need a part."**
- Exact dimensions matter → `cadsmith-text-to-cad`.
- FreeCAD workflow, or the idea is conceptual ("a bookshelf") → `query2cad-freecad`.
- Quick parametric part with no benchmark → `parametric-part-cad`.

**"I have a drawing, sketch, or photo."**
- A flat part to print now → `image2gcode`.
- A 3-D part to model → `sketch-to-cad`, then `cadsmith-text-to-cad`.

**"I have a CAD part and need to make or analyse it."**
- 3D printing → `agentscad-fdm-dfam` (orientation + geometry fixes), then your slicer.
- Machining, molding, sheet metal → `dfm-review`.
- Stress or stiffness → `quick-fea`. Flow → `cfd-simulation-setup`.

**"I need a structure or layout designed."**
- Truss or frame topology with discrete sections → `llm-mechanical-designer`.
- Material choice → `material-selection`; component sizing → `machine-element-sizing`.

**"I need results I can defend."**
- CFD acceptance against declared criteria → `cfd-simulation-setup`.
- A signed-off calculation document → `engineering-calc-report`.

## End-to-end pipelines

1. **Text → printable part.** `cadsmith-text-to-cad` (validated STEP) → `agentscad-fdm-dfam` (orientation + teardrops) → slicer. *Example: "a wall bracket for a 25 mm tube with two M5 screw holes, printed in PETG."*
2. **Text → part → simulation.** `cadsmith-text-to-cad` → `quick-fea` (stiffness, stress) or `cfd-simulation-setup` (flow) → `engineering-calc-report`.
3. **Napkin sketch → physical part in minutes.** `image2gcode` (2.5D) → printer. For 3-D shapes: `sketch-to-cad` → `agentscad-fdm-dfam`.
4. **Structural concept → detailed part.** `llm-mechanical-designer` (truss layout) → `cadsmith-text-to-cad` (members as solids) → `quick-fea` check → `dfm-review`.
5. **Course module on agentic engineering.** Use the tutorials in order (Query2CAD → CADSmith → AgentsCAD → CFD Forge) to show how verification gets stricter: a VLM score, then kernel metrics with an independent judge, then rule-based geometry checks, then registered physics contracts.

## A pattern shared across the papers
The model proposes; something deterministic checks. The check takes a different form in each paper:
- **CFD Forge:** registered contracts decide acceptance.
- **CADSmith:** OpenCASCADE kernel metrics plus an independent judge.
- **AgentsCAD:** rule-based overhang detection and grounded orientation tools.
- **The mechanical designer:** exact FEM scores every design.
- **Query2CAD:** a VQA score and the user's own feedback.
- **Image2Gcode:** build-limit and extrusion validation on the generated G-code.

When you add a skill to this library, keep this pattern: a deterministic check the agent can't talk its way past.
