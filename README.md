# Mechanical Engineering Design Skills

A collection of 22 agent skills for mechanical **design** and **manufacturing**, plus engineering teaching. Nine of them package Barati Farimani Lab research papers. Works with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI, and any agent supported by the open [Agent Skills](https://skills.sh) format.

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


## Skills by category

22 skills in two main groups, **Design** and **Manufacturing**, plus teaching aids. 🔬 marks the
9 skills that package a Barati Farimani Lab paper. Each of those has a tested workflow, a
step-by-step tutorial and use cases. Start with **[docs/use-cases.md](docs/use-cases.md)**.

### Design

| Area | Skill | What it does | Paper · Tutorial |
|---|---|---|---|
| CAD from words, sketches, drawings | 🔬 [`cadsmith-text-to-cad`](skills/cadsmith-text-to-cad) | Text → CadQuery, validated with kernel metrics and a three-view judge; CD / F1 / IoU benchmarking | [CADSmith](https://arxiv.org/abs/2603.26512) · [tutorial](docs/tutorials/cadsmith-text-to-cad.md) |
| | 🔬 [`query2cad-freecad`](skills/query2cad-freecad) | Text → FreeCAD macro with error repair, VQA scoring and caption-driven refinement | [Query2CAD](https://arxiv.org/abs/2406.00144) · [tutorial](docs/tutorials/query2cad-freecad.md) |
| | [`parametric-part-cad`](skills/parametric-part-cad) | Plain-English part spec → CadQuery script → STEP/STL + preview | |
| | [`sketch-to-cad`](skills/sketch-to-cad) | Sketch, photo or video frames → dimensioned CAD reconstruction | |
| | [`drawing-gdt-review`](skills/drawing-gdt-review) | Audits engineering drawings for dimensioning and GD&T errors | |
| Mechanisms & structures | 🔬 [`linkage-synthesis`](skills/linkage-synthesis) | Target curve → four-/six-bar linkage, built node by node with dyadic and kinematic validation | [LinkD](https://arxiv.org/abs/2601.04054) · [tutorial](docs/tutorials/linkage-synthesis.md) |
| | 🔬 [`llm-mechanical-designer`](skills/llm-mechanical-designer) | LLM ↔ FEM truss design loop with ranked history | [LLM Mechanical Designer](https://arxiv.org/abs/2404.17525) · [tutorial](docs/tutorials/llm-mechanical-designer.md) |
| | [`machine-element-sizing`](skills/machine-element-sizing) | Bolts, shafts, bearings, springs, gears, welds, with the work shown and safety factors | |
| Analysis & simulation | 🔬 [`cfd-simulation-setup`](skills/cfd-simulation-setup) | Request → OpenFOAM case → run → diagnosis; acceptance decided only by registered contracts | [CFD Forge](https://arxiv.org/abs/2610.14104) · [tutorial](docs/tutorials/cfd-simulation-setup.md) |
| | [`quick-fea`](skills/quick-fea) | Linear static / modal FEA with a required hand-calc sanity check | |
| | [`tolerance-stackup`](skills/tolerance-stackup) | Worst-case, RSS and Monte Carlo stack-ups with contributor charts | |
| | [`thermal-fluids-calc`](skills/thermal-fluids-calc) | Pipe pressure drop, heat exchangers (LMTD / ε-NTU), fins; CoolProp properties | |
| Decisions & documentation | [`material-selection`](skills/material-selection) | Ashby performance indices → ranked shortlist + charts | |
| | [`design-review-package`](skills/design-review-package) | Requirements, FMEA, BOM cost roll-up and review checklist | |
| | [`engineering-calc-report`](skills/engineering-calc-report) | Turns calculations into a calc report ready for sign-off | |

### Manufacturing

| Area | Skill | What it does | Paper · Tutorial |
|---|---|---|---|
| Design for manufacture | 🔬 [`agentscad-fdm-dfam`](skills/agentscad-fdm-dfam) | STEP → overhang analysis → reorientation, teardrops and chamfers backed by the analysis → verified STEP | [AgentsCAD](https://arxiv.org/abs/2607.02448) · [tutorial](docs/tutorials/agentscad-fdm-dfam.md) |
| | [`dfm-review`](skills/dfm-review) | DFM review for machining, sheet metal, molding and AM | |
| Process planning | 🔬 [`image2gcode`](skills/image2gcode) | Photo or sketch → printer-ready G-code for 2D/2.5D parts; Slice-100K keypoints | [Image2Gcode](https://doi.org/10.1016/j.addlet.2026.100374) · [tutorial](docs/tutorials/image2gcode.md) |
| | 🔬 [`lpbf-defect-prediction`](skills/lpbf-defect-prediction) | Metal L-PBF parameters → keyholing / lack of fusion / balling / none; process maps | [AdditiveLLM](https://doi.org/10.1016/j.addlet.2025.100292) · [tutorial](docs/tutorials/lpbf-defect-prediction.md) |
| In-process monitoring | 🔬 [`llm-3d-print-monitor`](skills/llm-3d-print-monitor) | Layer-by-layer camera inspection and safety-bounded G-code correction through Klipper/Moonraker; mock printer included | [LLM-3D Print](https://arxiv.org/abs/2408.14307) · [tutorial](docs/tutorials/llm-3d-print-monitor.md) |

### Teaching

| Skill | What it does |
|---|---|
| [`worked-problem-generator`](skills/worked-problem-generator) | Textbook-style problems with code-verified solutions |
| [`mechanics-visuals`](skills/mechanics-visuals) | FBDs, Mohr's circle, stress–strain, S–N, beam diagrams |

Install a whole group by naming its skills, for example manufacturing:
```bash
npx skills add BaratiLab/me-design-skills --skill agentscad-fdm-dfam --skill dfm-review --skill image2gcode \
    --skill lpbf-defect-prediction --skill llm-3d-print-monitor
```

Run any skill's tests with `python skills/<skill>/tests/*.py`.

## Dependencies

Skills install Python packages on demand. The full set:

```bash
pip install numpy scipy matplotlib pint CoolProp cadquery pypdf
# research skills
pip install trimesh rtree pyvista opencv-python-headless shapely gmsh scikit-fem
pip install pandas scikit-learn pyarrow joblib pillow   # lpbf-defect-prediction, llm-3d-print-monitor
```

External tools: OpenFOAM v11+ (`cfd-simulation-setup` solves), FreeCAD (`query2cad-freecad`; `micromamba create -p ./fc -c conda-forge freecad`), a Klipper + Moonraker printer with cameras (`llm-3d-print-monitor` live mode; its mock printer needs nothing). `lpbf-defect-prediction` downloads the MeltpoolNet data from GitHub on first use.

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
