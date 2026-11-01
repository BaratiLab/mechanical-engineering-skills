# Mechanical Engineering Design Skills

A collection of 19 agent skills for mechanical design, analysis, simulation, manufacturing, and engineering teaching, including six skills that package Barati Farimani Lab research papers. Works with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI, and any agent supported by the open [Agent Skills](https://skills.sh) format.

Maintained by the Barati Farimani Lab, Carnegie Mellon University.

## Install

```bash
# Install every skill in this repo
npx skills add BaratiLab/me-design-skills --all

# Pick skills interactively
npx skills add BaratiLab/me-design-skills

# Install one skill
npx skills add BaratiLab/me-design-skills --skill machine-element-sizing

# Install globally for Claude Code only
npx skills add BaratiLab/me-design-skills --all -g -a claude-code

# See what's inside without installing
npx skills add BaratiLab/me-design-skills --list
```


## Research skills from the lab

Each one turns a published method into an agent workflow, with tested scripts, a step-by-step tutorial, and use cases. Start with **[docs/use-cases.md](docs/use-cases.md)**.

| Skill | Paper | What it does | Tutorial |
|---|---|---|---|
| [`cfd-simulation-setup`](skills/cfd-simulation-setup) | CFD Forge, [arXiv:2610.14104](https://arxiv.org/abs/2610.14104) | OpenFOAM request → case → diagnosis; registered contracts alone decide acceptance | [→](docs/tutorials/cfd-simulation-setup.md) |
| [`cadsmith-text-to-cad`](skills/cadsmith-text-to-cad) | CADSmith, [arXiv:2603.26512](https://arxiv.org/abs/2603.26512) | Text → CadQuery with kernel-metric + three-view judge validation; CD / F1 / IoU benchmarking | [→](docs/tutorials/cadsmith-text-to-cad.md) |
| [`query2cad-freecad`](skills/query2cad-freecad) | Query2CAD, [arXiv:2406.00144](https://arxiv.org/abs/2406.00144) | Text → FreeCAD macro with error repair, VQA scoring and caption-driven refinement | [→](docs/tutorials/query2cad-freecad.md) |
| [`agentscad-fdm-dfam`](skills/agentscad-fdm-dfam) | AgentsCAD, [arXiv:2607.02448](https://arxiv.org/abs/2607.02448) | STEP → overhang analysis → grounded reorientation, teardrops, chamfers → verified STEP | [→](docs/tutorials/agentscad-fdm-dfam.md) |
| [`image2gcode`](skills/image2gcode) | Image2Gcode, [Addit. Manuf. Lett. 2026](https://doi.org/10.1016/j.addlet.2026.100374) | Photo or sketch → printer-ready G-code for 2D/2.5D parts; Slice-100K keypoints | [→](docs/tutorials/image2gcode.md) |
| [`llm-mechanical-designer`](skills/llm-mechanical-designer) | LLM Agent as a Mechanical Designer, [arXiv:2404.17525](https://arxiv.org/abs/2404.17525) | LLM ↔ FEM truss design loop with ranked history and optimize/constraint prompts | [→](docs/tutorials/llm-mechanical-designer.md) |

Run any skill's tests with `python skills/<skill>/tests/*.py`.

## General engineering skills

| Category | Skill | What it does |
|---|---|---|
| Design & CAD | [`parametric-part-cad`](skills/parametric-part-cad) | Plain-English part spec → CadQuery script → STEP/STL + preview |
| | [`sketch-to-cad`](skills/sketch-to-cad) | Sketch, photo, or video frames → dimensioned CAD reconstruction |
| | [`drawing-gdt-review`](skills/drawing-gdt-review) | Audits engineering drawings for dimensioning and GD&T errors |
| Analysis & sizing | [`machine-element-sizing`](skills/machine-element-sizing) | Bolts, shafts, bearings, springs, gears, welds — with shown work and safety factors |
| | [`quick-fea`](skills/quick-fea) | Linear static / modal FEA with a mandatory hand-calc sanity check |
| | [`tolerance-stackup`](skills/tolerance-stackup) | Worst-case, RSS, and Monte Carlo stack-ups with contributor charts |
| | [`cfd-simulation-setup`](skills/cfd-simulation-setup) | Request → OpenFOAM case → run → diagnosis, with deterministic acceptance contracts ([CFD Forge](https://arxiv.org/abs/2610.14104)) |
| | [`thermal-fluids-calc`](skills/thermal-fluids-calc) | Pipe pressure drop, heat exchangers (LMTD / ε-NTU), fins — CoolProp properties |
| Process & docs | [`dfm-review`](skills/dfm-review) | Design-for-manufacture review for machining, sheet metal, molding, AM |
| | [`material-selection`](skills/material-selection) | Ashby performance indices → ranked shortlist + charts |
| | [`design-review-package`](skills/design-review-package) | Requirements, FMEA, BOM cost roll-up, and review checklist |
| | [`engineering-calc-report`](skills/engineering-calc-report) | Turns calculations into a signed-off-ready calc report |
| Teaching | [`worked-problem-generator`](skills/worked-problem-generator) | Textbook-style problems with code-verified solutions |
| | [`mechanics-visuals`](skills/mechanics-visuals) | FBDs, Mohr's circle, stress–strain, S–N, beam diagrams |

## Dependencies

Skills install Python packages on demand. The full set:

```bash
pip install numpy scipy matplotlib pint CoolProp cadquery pypdf
# research skills
pip install trimesh rtree pyvista opencv-python-headless shapely gmsh scikit-fem
```

External tools: OpenFOAM v11+ (`cfd-simulation-setup` solves), FreeCAD (`query2cad-freecad`; `micromamba create -p ./fc -c conda-forge freecad`).

`quick-fea` uses `gmsh` and `scikit-fem`. `cfd-simulation-setup` needs OpenFOAM Foundation v11+ (v14 tested in the paper) for the solve; its validators, evidence extraction and builders run without it (`python skills/cfd-simulation-setup/tests/test_paper_cases.py`).

## Repo layout

```
skills/<skill-name>/
├── SKILL.md          # frontmatter (name, description) + instructions
├── scripts/          # deterministic code the agent runs
└── references/       # tables, rules, formulas loaded on demand
_template/            # starter skill (ignored by the installer)
docs/                 # use cases + tutorials for the research skills (GitHub Pages-ready)
```

## Contributing a new skill

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
