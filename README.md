# Mechanical Engineering Design Skills

A collection of 14 agent skills for mechanical design, analysis, manufacturing review, and engineering teaching. Works with Claude Code, Claude.ai, Cursor, Codex, Gemini CLI, and any agent supported by the open [Agent Skills](https://skills.sh) format.

Maintained by the Barati Farimani Lab, Carnegie Mellon University.

## Install

```bash
# Install every skill in this repo
npx skills add <owner>/me-design-skills --all

# Pick skills interactively
npx skills add <owner>/me-design-skills

# Install one skill
npx skills add <owner>/me-design-skills --skill machine-element-sizing

# Install globally for Claude Code only
npx skills add <owner>/me-design-skills --all -g -a claude-code

# See what's inside without installing
npx skills add <owner>/me-design-skills --list
```

Replace `<owner>` with the GitHub account hosting this repo.

## The skills

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
```

`quick-fea` uses `gmsh` and `scikit-fem`. `cfd-simulation-setup` needs OpenFOAM Foundation v11+ (v14 tested in the paper) for the solve; its validators, evidence extraction and builders run without it (`python skills/cfd-simulation-setup/tests/test_paper_cases.py`).

## Repo layout

```
skills/<skill-name>/
├── SKILL.md          # frontmatter (name, description) + instructions
├── scripts/          # deterministic code the agent runs
└── references/       # tables, rules, formulas loaded on demand
_template/            # starter skill (ignored by the installer)
```

## Contributing a new skill

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
