# ME Design Skills — Barati Farimani Lab, Carnegie Mellon University

Agent skills for mechanical engineering design, analysis, simulation and manufacturing. They work with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI and other agents that follow the open Agent Skills format.

```bash
npx skills add BaratiLab/me-design-skills --all
```

## Research skills (from lab papers)
[Use cases and pipelines](use-cases.md)

### Design
- [CADSmith: text → validated CadQuery](tutorials/cadsmith-text-to-cad.md)
- [Query2CAD: text → FreeCAD macro](tutorials/query2cad-freecad.md)
- [LinkD: target curve → planar linkage](tutorials/linkage-synthesis.md)
- [LLM Agent as a Mechanical Designer: truss design loop](tutorials/llm-mechanical-designer.md)
- [CFD Forge: physics-constrained CFD](tutorials/cfd-simulation-setup.md)

### Manufacturing
- [AgentsCAD: DFAM for FDM parts](tutorials/agentscad-fdm-dfam.md)
- [Image2Gcode: image → G-code](tutorials/image2gcode.md)
- [AdditiveLLM: L-PBF defect regimes and process maps](tutorials/lpbf-defect-prediction.md)
- [LLM-3D Print: layer-by-layer monitoring and correction](tutorials/llm-3d-print-monitor.md)
- [MeltpoolNet: melt-pool size and mode](tutorials/meltpool-geometry.md)
- [ThermoPore: porosity from thermal images](tutorials/thermal-porosity.md)
- [Diffusion super-resolution of layer images](tutorials/lpbf-superres.md)
- [AMGPT: page-cited answers from your AM library](tutorials/am-literature-rag.md)

## Engineering skills
Machine element sizing, quick FEA, tolerance stack-up, thermal-fluids, DFM review, material selection, design review packages, calculation reports, drawing / GD&T review, parametric CAD, sketch-to-CAD, worked problems, and mechanics visuals. See the [repository README](https://github.com/BaratiLab/me-design-skills#skills-by-category).

## Writing your own skill
See [CONTRIBUTING.md](https://github.com/BaratiLab/me-design-skills/blob/main/CONTRIBUTING.md).
