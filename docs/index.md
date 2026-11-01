<p align="center"><img src="img/banner.svg" alt="Mechanical Engineering Skills" width="100%"></p>

# Mechanical Engineering Skills — Barati Farimani Lab, Carnegie Mellon University

Agent skills for mechanical engineering design, analysis, simulation and manufacturing. Each skill
packages instructions and tested scripts. The agent orchestrates and the tools compute. They work
with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI and other agents that follow the open Agent
Skills format.

```bash
npx skills add BaratiLab/mechanical-engineering-skills --all
```

Click an icon: 🔬 skills open their tutorial, the others open their folder on GitHub.

<h3>Design & CAD</h3>
<table>
<tr>
<td align="center" width="25%"><a href="tutorials/cadsmith-text-to-cad.html"><img src="icons/cadsmith-text-to-cad.svg" width="64" alt="cadsmith-text-to-cad icon"></a><br><b><a href="tutorials/cadsmith-text-to-cad.html"><code>cadsmith-text-to-cad</code></a></b> 🔬<br><sub>Text → validated CAD</sub></td>
<td align="center" width="25%"><a href="tutorials/query2cad-freecad.html"><img src="icons/query2cad-freecad.svg" width="64" alt="query2cad-freecad icon"></a><br><b><a href="tutorials/query2cad-freecad.html"><code>query2cad-freecad</code></a></b> 🔬<br><sub>Text → FreeCAD macro</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/parametric-part-cad"><img src="icons/parametric-part-cad.svg" width="64" alt="parametric-part-cad icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/parametric-part-cad"><code>parametric-part-cad</code></a></b><br><sub>Spec → parametric part</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/sketch-to-cad"><img src="icons/sketch-to-cad.svg" width="64" alt="sketch-to-cad icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/sketch-to-cad"><code>sketch-to-cad</code></a></b><br><sub>Sketch / photo → CAD</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/drawing-gdt-review"><img src="icons/drawing-gdt-review.svg" width="64" alt="drawing-gdt-review icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/drawing-gdt-review"><code>drawing-gdt-review</code></a></b><br><sub>Drawing & GD&T audit</sub></td>
<td align="center" width="25%"><a href="tutorials/linkage-synthesis.html"><img src="icons/linkage-synthesis.svg" width="64" alt="linkage-synthesis icon"></a><br><b><a href="tutorials/linkage-synthesis.html"><code>linkage-synthesis</code></a></b> 🔬<br><sub>Target path → linkage</sub></td>
<td align="center" width="25%"><a href="tutorials/rocketsmith.html"><img src="icons/rocketsmith.svg" width="64" alt="rocketsmith icon"></a><br><b><a href="tutorials/rocketsmith.html"><code>rocketsmith</code></a></b> 🔬<br><sub>Printed rockets: stability & flight</sub></td>
<td align="center" width="25%"><a href="tutorials/llm-mechanical-designer.html"><img src="icons/llm-mechanical-designer.svg" width="64" alt="llm-mechanical-designer icon"></a><br><b><a href="tutorials/llm-mechanical-designer.html"><code>llm-mechanical-designer</code></a></b> 🔬<br><sub>LLM ↔ FEM truss design</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/machine-element-sizing"><img src="icons/machine-element-sizing.svg" width="64" alt="machine-element-sizing icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/machine-element-sizing"><code>machine-element-sizing</code></a></b><br><sub>Bolts, shafts, gears, springs</sub></td>
</tr>
</table>

<h3>Analysis & simulation</h3>
<table>
<tr>
<td align="center" width="25%"><a href="tutorials/cfd-simulation-setup.html"><img src="icons/cfd-simulation-setup.svg" width="64" alt="cfd-simulation-setup icon"></a><br><b><a href="tutorials/cfd-simulation-setup.html"><code>cfd-simulation-setup</code></a></b> 🔬<br><sub>OpenFOAM setup & diagnosis</sub></td>
<td align="center" width="25%"><a href="tutorials/stress-field-surrogate.html"><img src="icons/stress-field-surrogate.svg" width="64" alt="stress-field-surrogate icon"></a><br><b><a href="tutorials/stress-field-surrogate.html"><code>stress-field-surrogate</code></a></b> 🔬<br><sub>Instant stress fields</sub></td>
<td align="center" width="25%"><a href="tutorials/lattice-inverse-design.html"><img src="icons/lattice-inverse-design.svg" width="64" alt="lattice-inverse-design icon"></a><br><b><a href="tutorials/lattice-inverse-design.html"><code>lattice-inverse-design</code></a></b> 🔬<br><sub>Target stiffness → lattice</sub></td>
<td align="center" width="25%"><a href="tutorials/equation-discovery.html"><img src="icons/equation-discovery.svg" width="64" alt="equation-discovery icon"></a><br><b><a href="tutorials/equation-discovery.html"><code>equation-discovery</code></a></b> 🔬<br><sub>Data → interpretable equations</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/quick-fea"><img src="icons/quick-fea.svg" width="64" alt="quick-fea icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/quick-fea"><code>quick-fea</code></a></b><br><sub>Quick FEA + hand check</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/tolerance-stackup"><img src="icons/tolerance-stackup.svg" width="64" alt="tolerance-stackup icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/tolerance-stackup"><code>tolerance-stackup</code></a></b><br><sub>Tolerance stack-ups</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/thermal-fluids-calc"><img src="icons/thermal-fluids-calc.svg" width="64" alt="thermal-fluids-calc icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/thermal-fluids-calc"><code>thermal-fluids-calc</code></a></b><br><sub>Pipes, heat exchangers, fins</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/material-selection"><img src="icons/material-selection.svg" width="64" alt="material-selection icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/material-selection"><code>material-selection</code></a></b><br><sub>Ashby charts & indices</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/design-review-package"><img src="icons/design-review-package.svg" width="64" alt="design-review-package icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/design-review-package"><code>design-review-package</code></a></b><br><sub>Requirements, FMEA, BOM</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/engineering-calc-report"><img src="icons/engineering-calc-report.svg" width="64" alt="engineering-calc-report icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/engineering-calc-report"><code>engineering-calc-report</code></a></b><br><sub>Calc reports for sign-off</sub></td>
</tr>
</table>

<h3>Manufacturing</h3>
<table>
<tr>
<td align="center" width="25%"><a href="tutorials/agentscad-fdm-dfam.html"><img src="icons/agentscad-fdm-dfam.svg" width="64" alt="agentscad-fdm-dfam icon"></a><br><b><a href="tutorials/agentscad-fdm-dfam.html"><code>agentscad-fdm-dfam</code></a></b> 🔬<br><sub>Make STEP parts printable</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/dfm-review"><img src="icons/dfm-review.svg" width="64" alt="dfm-review icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/dfm-review"><code>dfm-review</code></a></b><br><sub>DFM review</sub></td>
<td align="center" width="25%"><a href="tutorials/image2gcode.html"><img src="icons/image2gcode.svg" width="64" alt="image2gcode icon"></a><br><b><a href="tutorials/image2gcode.html"><code>image2gcode</code></a></b> 🔬<br><sub>Image → G-code</sub></td>
<td align="center" width="25%"><a href="tutorials/lpbf-defect-prediction.html"><img src="icons/lpbf-defect-prediction.svg" width="64" alt="lpbf-defect-prediction icon"></a><br><b><a href="tutorials/lpbf-defect-prediction.html"><code>lpbf-defect-prediction</code></a></b> 🔬<br><sub>L-PBF defect regimes</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="tutorials/am-alloy-screening.html"><img src="icons/am-alloy-screening.svg" width="64" alt="am-alloy-screening icon"></a><br><b><a href="tutorials/am-alloy-screening.html"><code>am-alloy-screening</code></a></b> 🔬<br><sub>Which alloy prints</sub></td>
<td align="center" width="25%"><a href="tutorials/sls-process-optimization.html"><img src="icons/sls-process-optimization.svg" width="64" alt="sls-process-optimization icon"></a><br><b><a href="tutorials/sls-process-optimization.html"><code>sls-process-optimization</code></a></b> 🔬<br><sub>SLS settings batch by batch</sub></td>
<td align="center" width="25%"><a href="tutorials/meltpool-geometry.html"><img src="icons/meltpool-geometry.svg" width="64" alt="meltpool-geometry icon"></a><br><b><a href="tutorials/meltpool-geometry.html"><code>meltpool-geometry</code></a></b> 🔬<br><sub>Melt-pool size & mode</sub></td>
<td align="center" width="25%"><a href="tutorials/llm-3d-print-monitor.html"><img src="icons/llm-3d-print-monitor.svg" width="64" alt="llm-3d-print-monitor icon"></a><br><b><a href="tutorials/llm-3d-print-monitor.html"><code>llm-3d-print-monitor</code></a></b> 🔬<br><sub>Watch & fix prints layer by layer</sub></td>
</tr>
<tr>
<td align="center" width="25%"><a href="tutorials/thermal-porosity.html"><img src="icons/thermal-porosity.svg" width="64" alt="thermal-porosity icon"></a><br><b><a href="tutorials/thermal-porosity.html"><code>thermal-porosity</code></a></b> 🔬<br><sub>Pores from thermal images</sub></td>
<td align="center" width="25%"><a href="tutorials/lpbf-superres.html"><img src="icons/lpbf-superres.svg" width="64" alt="lpbf-superres icon"></a><br><b><a href="tutorials/lpbf-superres.html"><code>lpbf-superres</code></a></b> 🔬<br><sub>Webcam → high-res layers</sub></td>
<td align="center" width="25%"><a href="tutorials/am-literature-rag.html"><img src="icons/am-literature-rag.svg" width="64" alt="am-literature-rag icon"></a><br><b><a href="tutorials/am-literature-rag.html"><code>am-literature-rag</code></a></b> 🔬<br><sub>Page-cited answers from papers</sub></td>
</tr>
</table>

<h3>Teaching</h3>
<table>
<tr>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/worked-problem-generator"><img src="icons/worked-problem-generator.svg" width="64" alt="worked-problem-generator icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/worked-problem-generator"><code>worked-problem-generator</code></a></b><br><sub>Problems with verified solutions</sub></td>
<td align="center" width="25%"><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/mechanics-visuals"><img src="icons/mechanics-visuals.svg" width="64" alt="mechanics-visuals icon"></a><br><b><a href="https://github.com/BaratiLab/mechanical-engineering-skills/tree/main/skills/mechanics-visuals"><code>mechanics-visuals</code></a></b><br><sub>FBDs, Mohr's circle, diagrams</sub></td>
</tr>
</table>

## Research skills (from lab papers)
[Use cases and pipelines](use-cases.md)

### Design
- [CADSmith: text → validated CadQuery](tutorials/cadsmith-text-to-cad.md)
- [Query2CAD: text → FreeCAD macro](tutorials/query2cad-freecad.md)
- [LinkD: target curve → planar linkage](tutorials/linkage-synthesis.md)
- [LLM Agent as a Mechanical Designer: truss design loop](tutorials/llm-mechanical-designer.md)
- [CFD Forge: physics-constrained CFD](tutorials/cfd-simulation-setup.md)
- [StressD: instant stress fields](tutorials/stress-field-surrogate.md)
- [GLU3D: lattice cells for a target stiffness](tutorials/lattice-inverse-design.md)
- [LLM-SR: equation discovery](tutorials/equation-discovery.md)
- [RocketSmith: printed high-power rockets](tutorials/rocketsmith.md)

### Manufacturing
- [AgentsCAD: DFAM for FDM parts](tutorials/agentscad-fdm-dfam.md)
- [Image2Gcode: image → G-code](tutorials/image2gcode.md)
- [AdditiveLLM: L-PBF defect regimes and process maps](tutorials/lpbf-defect-prediction.md)
- [LLM-3D Print: layer-by-layer monitoring and correction](tutorials/llm-3d-print-monitor.md)
- [Agentic alloy evaluation: which alloy prints](tutorials/am-alloy-screening.md)
- [Agentic SLS process optimization](tutorials/sls-process-optimization.md)
- [MeltpoolNet: melt-pool size and mode](tutorials/meltpool-geometry.md)
- [ThermoPore: porosity from thermal images](tutorials/thermal-porosity.md)
- [Diffusion super-resolution of layer images](tutorials/lpbf-superres.md)
- [AMGPT: page-cited answers from your AM library](tutorials/am-literature-rag.md)

## Engineering skills
Machine element sizing, quick FEA, tolerance stack-up, thermal-fluids, DFM review, material selection, design review packages, calculation reports, drawing / GD&T review, parametric CAD, sketch-to-CAD, worked problems, and mechanics visuals. See the [repository README](https://github.com/BaratiLab/mechanical-engineering-skills#skills-by-category).

## Writing your own skill
See [CONTRIBUTING.md](https://github.com/BaratiLab/mechanical-engineering-skills/blob/main/CONTRIBUTING.md).
