<p align="center"><img src="docs/img/banner.svg" alt="Mechanical Engineering Skills: 32 agent skills for design, analysis and manufacturing" width="100%"></p>

<p align="center">
<a href="https://baratilab.github.io/mechanical-engineering-skills/"><b>Tutorials & use cases</b></a> ·
<a href="#install">Install</a> ·
<a href="#skills-by-category">Full skill list</a> ·
<a href="docs/use-cases.md">Which skill do I need?</a>
</p>

**Mechanical Engineering Skills** gives an AI agent the working habits of a mechanical engineer. It
covers design, analysis and manufacturing:
- sizing a shaft;
- setting up a CFD case;
- finding a lattice for a target stiffness;
- choosing laser settings for a new alloy;
- watching a 3D print layer by layer.

Each skill is a folder with instructions the agent follows and **tested scripts that do the
numbers**. The agent orchestrates, the tools compute, and every result comes with the check that
backs it.

**19 of the 32 skills (🔬)** package peer-reviewed or preprint research from the
[Barati Farimani Lab](https://github.com/BaratiLab)
at Carnegie Mellon University. Each comes with a step-by-step tutorial that reproduces the paper's
key results. The skills work with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI and any agent
that reads the open [Agent Skills](https://skills.sh) format.

### How it works
| ① Install | ② Ask in plain English | ③ Get checked results |
|---|---|---|
| `npx skills add BaratiLab/mechanical-engineering-skills --all` | *"Find a printable lattice with E₃ = 2.5 E₁ at under 30% density"* | The agent runs the skill's scripts, checks the answer (hand calc, exact case, re-simulation) and hands you files: STEP/STL, G-code, reports, plots |

## What's inside

<h3>Design & CAD</h3>
<table>
<tr>
<td align="center" width="25%"><a href="skills/cadsmith-text-to-cad"><img src="docs/icons/cadsmith-text-to-cad.svg" width="64" alt="cadsmith-text-to-cad icon"></a><br><b><a href="skills/cadsmith-text-to-cad"><code>cadsmith-text-to-cad</code></a></b> 🔬<br><sub>Text → validated CAD</sub></td>
<td align="center" width="25%"><a href="skills/query2cad-freecad"><img src="docs/icons/query2cad-freecad.svg" width="64" alt="query2cad-freecad icon"></a><br><b><a href="skills/query2cad-freecad"><code>query2cad-freecad</code></a></b> 🔬<br><sub>Text → FreeCAD macro</sub></td>
<td align="center" width="25%"><a href="skills/parametric-part-cad"><img src="docs/icons/parametric-part-cad.svg" width="64" alt="parametric-part-cad icon"></a><br><b><a href="skills/parametric-part-cad"><code>parametric-part-cad</code></a></b><br><sub>Spec → parametric part</sub></td>
<td align="center" width="25%"><a href="skills/sketch-to-cad"><img src="docs/icons/sketch-to-cad.svg" width="64" alt="sketch-to-cad icon"></a><br><b><a href="skills/sketch-to-cad"><code>sketch-to-cad</code></a></b><br><sub>Sketch / photo → CAD</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/drawing-gdt-review"><img src="docs/icons/drawing-gdt-review.svg" width="64" alt="drawing-gdt-review icon"></a><br><b><a href="skills/drawing-gdt-review"><code>drawing-gdt-review</code></a></b><br><sub>Drawing & GD&T audit</sub></td>
<td align="center" width="25%"><a href="skills/linkage-synthesis"><img src="docs/icons/linkage-synthesis.svg" width="64" alt="linkage-synthesis icon"></a><br><b><a href="skills/linkage-synthesis"><code>linkage-synthesis</code></a></b> 🔬<br><sub>Target path → linkage</sub></td>
<td align="center" width="25%"><a href="skills/rocketsmith"><img src="docs/icons/rocketsmith.svg" width="64" alt="rocketsmith icon"></a><br><b><a href="skills/rocketsmith"><code>rocketsmith</code></a></b> 🔬<br><sub>Printed rockets: stability & flight</sub></td>
<td align="center" width="25%"><a href="skills/llm-mechanical-designer"><img src="docs/icons/llm-mechanical-designer.svg" width="64" alt="llm-mechanical-designer icon"></a><br><b><a href="skills/llm-mechanical-designer"><code>llm-mechanical-designer</code></a></b> 🔬<br><sub>LLM ↔ FEM truss design</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/machine-element-sizing"><img src="docs/icons/machine-element-sizing.svg" width="64" alt="machine-element-sizing icon"></a><br><b><a href="skills/machine-element-sizing"><code>machine-element-sizing</code></a></b><br><sub>Bolts, shafts, gears, springs</sub></td>
</tr>
</table>

<h3>Analysis & simulation</h3>
<table>
<tr>
<td align="center" width="25%"><a href="skills/cfd-simulation-setup"><img src="docs/icons/cfd-simulation-setup.svg" width="64" alt="cfd-simulation-setup icon"></a><br><b><a href="skills/cfd-simulation-setup"><code>cfd-simulation-setup</code></a></b> 🔬<br><sub>OpenFOAM setup & diagnosis</sub></td>
<td align="center" width="25%"><a href="skills/stress-field-surrogate"><img src="docs/icons/stress-field-surrogate.svg" width="64" alt="stress-field-surrogate icon"></a><br><b><a href="skills/stress-field-surrogate"><code>stress-field-surrogate</code></a></b> 🔬<br><sub>Instant stress fields</sub></td>
<td align="center" width="25%"><a href="skills/lattice-inverse-design"><img src="docs/icons/lattice-inverse-design.svg" width="64" alt="lattice-inverse-design icon"></a><br><b><a href="skills/lattice-inverse-design"><code>lattice-inverse-design</code></a></b> 🔬<br><sub>Target stiffness → lattice</sub></td>
<td align="center" width="25%"><a href="skills/equation-discovery"><img src="docs/icons/equation-discovery.svg" width="64" alt="equation-discovery icon"></a><br><b><a href="skills/equation-discovery"><code>equation-discovery</code></a></b> 🔬<br><sub>Data → interpretable equations</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/quick-fea"><img src="docs/icons/quick-fea.svg" width="64" alt="quick-fea icon"></a><br><b><a href="skills/quick-fea"><code>quick-fea</code></a></b><br><sub>Quick FEA + hand check</sub></td>
<td align="center" width="25%"><a href="skills/tolerance-stackup"><img src="docs/icons/tolerance-stackup.svg" width="64" alt="tolerance-stackup icon"></a><br><b><a href="skills/tolerance-stackup"><code>tolerance-stackup</code></a></b><br><sub>Tolerance stack-ups</sub></td>
<td align="center" width="25%"><a href="skills/thermal-fluids-calc"><img src="docs/icons/thermal-fluids-calc.svg" width="64" alt="thermal-fluids-calc icon"></a><br><b><a href="skills/thermal-fluids-calc"><code>thermal-fluids-calc</code></a></b><br><sub>Pipes, heat exchangers, fins</sub></td>
<td align="center" width="25%"><a href="skills/material-selection"><img src="docs/icons/material-selection.svg" width="64" alt="material-selection icon"></a><br><b><a href="skills/material-selection"><code>material-selection</code></a></b><br><sub>Ashby charts & indices</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/design-review-package"><img src="docs/icons/design-review-package.svg" width="64" alt="design-review-package icon"></a><br><b><a href="skills/design-review-package"><code>design-review-package</code></a></b><br><sub>Requirements, FMEA, BOM</sub></td>
<td align="center" width="25%"><a href="skills/engineering-calc-report"><img src="docs/icons/engineering-calc-report.svg" width="64" alt="engineering-calc-report icon"></a><br><b><a href="skills/engineering-calc-report"><code>engineering-calc-report</code></a></b><br><sub>Calc reports for sign-off</sub></td>
</tr>
</table>

<h3>Manufacturing</h3>
<table>
<tr>
<td align="center" width="25%"><a href="skills/agentscad-fdm-dfam"><img src="docs/icons/agentscad-fdm-dfam.svg" width="64" alt="agentscad-fdm-dfam icon"></a><br><b><a href="skills/agentscad-fdm-dfam"><code>agentscad-fdm-dfam</code></a></b> 🔬<br><sub>Make STEP parts printable</sub></td>
<td align="center" width="25%"><a href="skills/dfm-review"><img src="docs/icons/dfm-review.svg" width="64" alt="dfm-review icon"></a><br><b><a href="skills/dfm-review"><code>dfm-review</code></a></b><br><sub>DFM review</sub></td>
<td align="center" width="25%"><a href="skills/image2gcode"><img src="docs/icons/image2gcode.svg" width="64" alt="image2gcode icon"></a><br><b><a href="skills/image2gcode"><code>image2gcode</code></a></b> 🔬<br><sub>Image → G-code</sub></td>
<td align="center" width="25%"><a href="skills/lpbf-defect-prediction"><img src="docs/icons/lpbf-defect-prediction.svg" width="64" alt="lpbf-defect-prediction icon"></a><br><b><a href="skills/lpbf-defect-prediction"><code>lpbf-defect-prediction</code></a></b> 🔬<br><sub>L-PBF defect regimes</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/am-alloy-screening"><img src="docs/icons/am-alloy-screening.svg" width="64" alt="am-alloy-screening icon"></a><br><b><a href="skills/am-alloy-screening"><code>am-alloy-screening</code></a></b> 🔬<br><sub>Which alloy prints</sub></td>
<td align="center" width="25%"><a href="skills/sls-process-optimization"><img src="docs/icons/sls-process-optimization.svg" width="64" alt="sls-process-optimization icon"></a><br><b><a href="skills/sls-process-optimization"><code>sls-process-optimization</code></a></b> 🔬<br><sub>SLS settings batch by batch</sub></td>
<td align="center" width="25%"><a href="skills/meltpool-geometry"><img src="docs/icons/meltpool-geometry.svg" width="64" alt="meltpool-geometry icon"></a><br><b><a href="skills/meltpool-geometry"><code>meltpool-geometry</code></a></b> 🔬<br><sub>Melt-pool size & mode</sub></td>
<td align="center" width="25%"><a href="skills/llm-3d-print-monitor"><img src="docs/icons/llm-3d-print-monitor.svg" width="64" alt="llm-3d-print-monitor icon"></a><br><b><a href="skills/llm-3d-print-monitor"><code>llm-3d-print-monitor</code></a></b> 🔬<br><sub>Watch & fix prints layer by layer</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="skills/thermal-porosity"><img src="docs/icons/thermal-porosity.svg" width="64" alt="thermal-porosity icon"></a><br><b><a href="skills/thermal-porosity"><code>thermal-porosity</code></a></b> 🔬<br><sub>Pores from thermal images</sub></td>
<td align="center" width="25%"><a href="skills/lpbf-superres"><img src="docs/icons/lpbf-superres.svg" width="64" alt="lpbf-superres icon"></a><br><b><a href="skills/lpbf-superres"><code>lpbf-superres</code></a></b> 🔬<br><sub>Webcam → high-res layers</sub></td>
<td align="center" width="25%"><a href="skills/am-literature-rag"><img src="docs/icons/am-literature-rag.svg" width="64" alt="am-literature-rag icon"></a><br><b><a href="skills/am-literature-rag"><code>am-literature-rag</code></a></b> 🔬<br><sub>Page-cited answers from papers</sub></td>
</tr>
</table>

<h3>Teaching</h3>
<table>
<tr>
<td align="center" width="25%"><a href="skills/worked-problem-generator"><img src="docs/icons/worked-problem-generator.svg" width="64" alt="worked-problem-generator icon"></a><br><b><a href="skills/worked-problem-generator"><code>worked-problem-generator</code></a></b><br><sub>Problems with verified solutions</sub></td>
<td align="center" width="25%"><a href="skills/mechanics-visuals"><img src="docs/icons/mechanics-visuals.svg" width="64" alt="mechanics-visuals icon"></a><br><b><a href="skills/mechanics-visuals"><code>mechanics-visuals</code></a></b><br><sub>FBDs, Mohr's circle, diagrams</sub></td>
</tr>
</table>

## Install

```bash
# Install every skill in this repo
npx skills add BaratiLab/mechanical-engineering-skills --all

# Pick skills interactively
npx skills add BaratiLab/mechanical-engineering-skills

# Install one skill
npx skills add BaratiLab/mechanical-engineering-skills --skill machine-element-sizing

# Install globally for Claude Code only
npx skills add BaratiLab/mechanical-engineering-skills --all -g -a claude-code

# See what's inside without installing
npx skills add BaratiLab/mechanical-engineering-skills --list
```


## Skills by category

32 skills in two main groups, **Design** and **Manufacturing**, plus teaching aids. 🔬 marks the
19 skills that package a Barati Farimani Lab paper. Each of those has a tested workflow, a
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
| | 🔬 [`rocketsmith`](skills/rocketsmith) | 3D-printed hobby high-power rockets: Barrowman stability, fin sizing, flight simulation, printable nose cone and fin can, flight-data calibration | [RocketSmith](https://arxiv.org/abs/2606.00097) · [tutorial](docs/tutorials/rocketsmith.md) |
| | 🔬 [`llm-mechanical-designer`](skills/llm-mechanical-designer) | LLM ↔ FEM truss design loop with ranked history | [LLM Mechanical Designer](https://arxiv.org/abs/2404.17525) · [tutorial](docs/tutorials/llm-mechanical-designer.md) |
| | [`machine-element-sizing`](skills/machine-element-sizing) | Bolts, shafts, bearings, springs, gears, welds, with the work shown and safety factors | |
| Analysis & simulation | 🔬 [`cfd-simulation-setup`](skills/cfd-simulation-setup) | Request → OpenFOAM case → run → diagnosis; acceptance decided only by registered contracts | [CFD Forge](https://arxiv.org/abs/2610.14104) · [tutorial](docs/tutorials/cfd-simulation-setup.md) |
| | 🔬 [`stress-field-surrogate`](skills/stress-field-surrogate) | Geometry + supports + loads → von Mises field in milliseconds (diffusion + scale network); built-in Q4 FEM data generator; unseen-geometry validation | [StressD](https://doi.org/10.1016/j.cma.2023.116343) · [tutorial](docs/tutorials/stress-field-surrogate.md) |
| | 🔬 [`lattice-inverse-design`](skills/lattice-inverse-design) | Target stiffness → printable TPMS / hybrid lattice cell: periodic homogenisation (6×6 C), parametric search, stiffness-conditioned 3D diffusion, watertight tiled STL | [GLU3D](https://doi.org/10.1002/adfm.202404165) · [tutorial](docs/tutorials/lattice-inverse-design.md) |
| | 🔬 [`equation-discovery`](skills/equation-discovery) | LLM-SR loop: propose equation skeletons, fit constants, score in- and out-of-domain, Pareto choice | [LLM-SR](https://arxiv.org/abs/2404.18400) · [tutorial](docs/tutorials/equation-discovery.md) |
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
| | 🔬 [`am-alloy-screening`](skills/am-alloy-screening) | Known or new alloy → properties (Thermo-Calc or flagged estimates) → lack-of-fusion process map → ranked recommendation, unit-checked | [Agentic alloy evaluation](https://doi.org/10.1016/j.addlet.2026.100355) · [tutorial](docs/tutorials/am-alloy-screening.md) |
| | 🔬 [`sls-process-optimization`](skills/sls-process-optimization) | Polymer SLS batch-to-batch optimization: build memory, ASTM D638/D790 reduction, bounded Bayesian next-batch suggestions | [Agentic SLS](https://arxiv.org/abs/2608.25928) · [tutorial](docs/tutorials/sls-process-optimization.md) |
| | 🔬 [`meltpool-geometry`](skills/meltpool-geometry) | Melt-pool depth / width / length and mode from power, speed and alloy; Rosenthal, dimensionally consistent power laws, cross-study validation, own-track calibration | [MeltpoolNet](https://doi.org/10.1016/j.addma.2022.102817) · [tutorial](docs/tutorials/meltpool-geometry.md) |
| In-process monitoring | 🔬 [`llm-3d-print-monitor`](skills/llm-3d-print-monitor) | Layer-by-layer camera inspection and safety-bounded G-code correction through Klipper/Moonraker; mock printer included | [LLM-3D Print](https://doi.org/10.1016/j.addma.2025.105027) · [tutorial](docs/tutorials/llm-3d-print-monitor.md) |
| | 🔬 [`thermal-porosity`](skills/thermal-porosity) | L-PBF pyrometry sequences → layer pore count and 16×16 porosity map; CT alignment, ESD thresholds, baseline + CNN / ViViT | [ThermoPore](https://doi.org/10.1016/j.addma.2024.104503) · [tutorial](docs/tutorials/thermal-porosity.md) |
| | 🔬 [`lpbf-superres`](skills/lpbf-superres) | Webcam → high-resolution layer images with conditional diffusion; registration, PSNR / SSIM / texture metrics, part IoU and edge roughness | [LPBF super-resolution](https://doi.org/10.1016/j.addma.2025.104790) · [tutorial](docs/tutorials/lpbf-superres.md) |
| Knowledge | 🔬 [`am-literature-rag`](skills/am-literature-rag) | Page-cited answers from your own AM paper library (BM25 + all-mpnet-base-v2 retrieval); retrieval evaluation | [AMGPT](https://doi.org/10.1016/j.addlet.2024.100232) · [tutorial](docs/tutorials/am-literature-rag.md) |

### Teaching

| Skill | What it does |
|---|---|
| [`worked-problem-generator`](skills/worked-problem-generator) | Textbook-style problems with code-verified solutions |
| [`mechanics-visuals`](skills/mechanics-visuals) | FBDs, Mohr's circle, stress–strain, S–N, beam diagrams |

Install a whole group by naming its skills, for example manufacturing:
```bash
npx skills add BaratiLab/mechanical-engineering-skills --skill agentscad-fdm-dfam --skill dfm-review --skill image2gcode \
    --skill lpbf-defect-prediction --skill meltpool-geometry --skill am-alloy-screening --skill sls-process-optimization \
    --skill llm-3d-print-monitor --skill thermal-porosity --skill lpbf-superres --skill am-literature-rag
```

Run any skill's tests with `python skills/<skill>/tests/*.py`.

## Dependencies

Skills install Python packages on demand. The full set:

```bash
pip install numpy scipy matplotlib pint CoolProp cadquery pypdf
# research skills
pip install trimesh rtree pyvista opencv-python-headless shapely gmsh scikit-fem
pip install pandas scikit-learn pyarrow joblib pillow PyWavelets scikit-image pypdf rank_bm25   # AM skills
pip install pyamg   # optional: faster lattice homogenisation
pip install torch sentence-transformers   # optional: deep models (thermal-porosity, lpbf-superres), dense retrieval
```

External tools: OpenFOAM v11+ (`cfd-simulation-setup` solves), FreeCAD (`query2cad-freecad`; `micromamba create -p ./fc -c conda-forge freecad`), a Klipper + Moonraker printer with cameras (`llm-3d-print-monitor` live mode; its mock printer needs nothing). `lpbf-defect-prediction` and `meltpool-geometry` download the MeltpoolNet data from GitHub on first use. `thermal-porosity` and `lpbf-superres` ship synthetic rehearsal data because the papers' datasets are not public; bring your own builds for real numbers.

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
