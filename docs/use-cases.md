# Use cases: Barati Farimani Lab research skills

Eighteen skills in this library package Barati Farimani Lab papers as agent workflows: eight for **design** and ten for **manufacturing**. Each has a step-by-step tutorial with real outputs.

### Design
| Skill | Paper | Best for | Tutorial |
|---|---|---|---|
| `cadsmith-text-to-cad` | CADSmith (arXiv:2603.26512) | Dimension-exact CadQuery parts from text, with kernel + vision validation | [tutorial](tutorials/cadsmith-text-to-cad.md) |
| `query2cad-freecad` | Query2CAD (arXiv:2406.00144) | FreeCAD macros from plain language, with a self-refinement loop | [tutorial](tutorials/query2cad-freecad.md) |
| `linkage-synthesis` | LinkD (arXiv:2601.04054) | Four-bar and six-bar linkages that trace a target path | [tutorial](tutorials/linkage-synthesis.md) |
| `llm-mechanical-designer` | LLM Agent as a Mechanical Designer (arXiv:2404.17525) | LLM-in-the-loop truss design against exact FEM | [tutorial](tutorials/llm-mechanical-designer.md) |
| `cfd-simulation-setup` | CFD Forge (arXiv:2610.14104) | Trustworthy OpenFOAM setup, diagnosis and acceptance | [tutorial](tutorials/cfd-simulation-setup.md) |
| `stress-field-surrogate` | StressD (CMAME 2023) | Instant von Mises fields for design iteration, validated on unseen geometries | [tutorial](tutorials/stress-field-surrogate.md) |
| `equation-discovery` | LLM-SR (ICLR 2025) | Interpretable laws from test data that extrapolate | [tutorial](tutorials/equation-discovery.md) |
| `rocketsmith` | RocketSmith (arXiv:2606.00097) | Printed hobby rockets: stability, flight prediction, printable parts | [tutorial](tutorials/rocketsmith.md) |

### Manufacturing
| Skill | Paper | Best for | Tutorial |
|---|---|---|---|
| `agentscad-fdm-dfam` | AgentsCAD (arXiv:2607.02448) | Making STEP parts printable: orientation, teardrops, chamfers | [tutorial](tutorials/agentscad-fdm-dfam.md) |
| `image2gcode` | Image2Gcode (Addit. Manuf. Lett. 2026) | Photo or sketch → G-code for 2D/2.5D parts, toolpath datasets | [tutorial](tutorials/image2gcode.md) |
| `lpbf-defect-prediction` | AdditiveLLM (Addit. Manuf. Lett. 2025) | Metal L-PBF parameter screening and process windows | [tutorial](tutorials/lpbf-defect-prediction.md) |
| `llm-3d-print-monitor` | LLM-3D Print (Addit. Manuf. 2025) | Layer-by-layer camera monitoring and safe in-process correction of FDM prints | [tutorial](tutorials/llm-3d-print-monitor.md) |
| `am-alloy-screening` | Agentic alloy evaluation (Addit. Manuf. Lett. 2026) | Which alloy (known or new) prints, and where its LoF boundary is | [tutorial](tutorials/am-alloy-screening.md) |
| `sls-process-optimization` | Agentic SLS (arXiv:2608.25928) | Polymer SLS parameters from ASTM results, batch by batch | [tutorial](tutorials/sls-process-optimization.md) |
| `meltpool-geometry` | MeltpoolNet (Addit. Manuf. 2022) | Melt-pool size and mode estimates with Rosenthal, power laws and calibrated ML | [tutorial](tutorials/meltpool-geometry.md) |
| `thermal-porosity` | ThermoPore (Addit. Manuf. 2024) | Pore count and location per layer from in-situ pyrometry | [tutorial](tutorials/thermal-porosity.md) |
| `lpbf-superres` | Diffusion super-resolution (Addit. Manuf. 2025) | High-resolution layer images and edge roughness from a webcam | [tutorial](tutorials/lpbf-superres.md) |
| `am-literature-rag` | AMGPT (Addit. Manuf. Lett. 2024) | Page-cited answers from your own AM literature | [tutorial](tutorials/am-literature-rag.md) |

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

**"I need a mechanism that moves along a path."**
- A gripper, foot, claw or any coupler-curve problem → `linkage-synthesis`, then `machine-element-sizing` for the pins.

**"I'm printing it in metal."**
- Is this parameter set safe? Where is the window? → `lpbf-defect-prediction`.
- How big will the melt pool be? → `meltpool-geometry` (calibrate with a few of your own single tracks).
- Where are the pores in this build? → `thermal-porosity` (pyrometry) and `lpbf-superres` (layer images from a cheap camera).
- What does the literature say? → `am-literature-rag` over your own papers.

**"My print is going wrong as it prints."**
- Klipper printer with cameras → `llm-3d-print-monitor`. Rehearse on its mock printer first.

**"I need an equation, not a black box."**
- Test data → interpretable law that extrapolates → `equation-discovery`.

**"I'm iterating a 2D shape and FEA is too slow."**
- `stress-field-surrogate` for instant fields on new shapes, `quick-fea` to confirm the final one.

**"Which alloy, or which polymer settings?"**
- Metal powder bed: `am-alloy-screening` (alloy choice) → `lpbf-defect-prediction` (window).
- Polymer SLS: `sls-process-optimization`.

**"I'm building a rocket."**
- `rocketsmith` (certified commercial motors; design check, not launch approval).

**"I need results I can defend."**
- CFD acceptance against declared criteria → `cfd-simulation-setup`.
- A signed-off calculation document → `engineering-calc-report`.

## End-to-end pipelines

1. **Text → printable part.** `cadsmith-text-to-cad` (validated STEP) → `agentscad-fdm-dfam` (orientation + teardrops) → slicer. *Example: "a wall bracket for a 25 mm tube with two M5 screw holes, printed in PETG."*
2. **Text → part → simulation.** `cadsmith-text-to-cad` → `quick-fea` (stiffness, stress) or `cfd-simulation-setup` (flow) → `engineering-calc-report`.
3. **Napkin sketch → physical part in minutes.** `image2gcode` (2.5D) → printer. For 3-D shapes: `sketch-to-cad` → `agentscad-fdm-dfam`.
4. **Structural concept → detailed part.** `llm-mechanical-designer` (truss layout) → `cadsmith-text-to-cad` (members as solids) → `quick-fea` check → `dfm-review`.
5. **Path → mechanism → hardware.** `linkage-synthesis` (six-bar) → `parametric-part-cad` (links and pins) → `machine-element-sizing` → `agentscad-fdm-dfam` to print a prototype.
6. **Print with a watcher.** `agentscad-fdm-dfam` → slice → `add_layer_pauses.py` → `llm-3d-print-monitor` corrects the print layer by layer and leaves an audit log.
7. **Metal part qualification plan.** `lpbf-defect-prediction` map → choose the robust point → design a density-cube DOE around it → `engineering-calc-report`.
8. **Metal AM process development loop.** `am-literature-rag` (what has been tried for this alloy) → `meltpool-geometry` + `lpbf-defect-prediction` (window) → single tracks to calibrate (`--extra`) → build with pyrometry and a webcam → `thermal-porosity` + `lpbf-superres` flag layers → targeted CT.
9. **Course module on agentic engineering.** Use the tutorials in order (Query2CAD → CADSmith → AgentsCAD → CFD Forge) to show how verification gets stricter: a VLM score, then kernel metrics with an independent judge, then rule-based geometry checks, then registered physics contracts.

## A pattern shared across the papers
The model proposes; something deterministic checks. The check takes a different form in each paper:
- **CFD Forge:** registered contracts decide acceptance.
- **CADSmith:** OpenCASCADE kernel metrics plus an independent judge.
- **AgentsCAD:** rule-based overhang detection and grounded orientation tools.
- **The mechanical designer:** exact FEM scores every design.
- **Query2CAD:** a VQA score and the user's own feedback.
- **Image2Gcode:** build-limit and extrusion validation on the generated G-code.
- **LinkD:** dyadic topology and full-rotation kinematics checks on every node, with bounded retries.
- **AdditiveLLM:** closed-form melt-pool criteria label the data; monotonic physics constraints shape the model.
- **LLM-3D Print:** a supervisor enforces stage order, and an allowlist with step limits decides what reaches the printer.
- **MeltpoolNet:** dimensional analysis constrains the fitted equations; leave-paper-out validation decides how much to trust the ML.
- **ThermoPore:** an interpretable thermal-history baseline every deep model must beat.
- **Super-resolution:** texture and roughness metrics alongside PSNR, so a smooth average can't pass for detail.
- **AMGPT:** every sentence of an answer carries a page citation; no passage, no claim.
- **Alloy evaluation:** unit sanity checks on every material file; keyed outputs so a ranking can't be misread.
- **SLS:** a human approves each batch; bounded step sizes; datasheet targets and scatter both reported.
- **RocketSmith:** tools compute every number; stability, rail exit and Class limits are hard checks.
- **StressD:** validated on unseen geometries, against a FEM that is itself checked against beam theory.
- **LLM-SR:** constants fitted by an optimizer, never guessed; out-of-domain error picks the law.

When you add a skill to this library, keep this pattern: a deterministic check the agent can't talk its way past.
