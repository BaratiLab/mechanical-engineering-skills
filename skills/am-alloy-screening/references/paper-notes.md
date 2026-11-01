# Agentic AM alloy evaluation: notes for this skill

Pak, Chandrasekhar, Barati Farimani. *Agentic additive manufacturing alloy evaluation.* Additive Manufacturing
Letters 17 (2026) 100355. doi:10.1016/j.addlet.2026.100355.
Code: github.com/BaratiLab/Agentic-Additive-Manufacturing-Alloy-Evaluation (MIT). PyPI packages used:
`additive-manufacturing`, `thermo-calc`, `workspace-agent`.

## The paper's pipeline
1. **Composition.** Mass fractions come from a lookup table of known alloys, or are parsed by the
   LLM from the user's text.
2. **Thermo-Calc property diagram** (TC-Python, 500–3500 K):
   - Solidus and liquidus come from the liquid volume fraction sweep; "melting" is their mean.
   - Density is B/V, Cp is HM.T, and k and electrical resistivity are built-in quantities.
   - The database is chosen by the top element (Appendix C):

| Condition | Database |
|---|---|
| Ti | TCTI6 |
| Ni, or Ni ≥ 0.30 | TCNI12 |
| Fe | TCFE14 |
| Al | TCAL9 |
| Pure element | PURE5 |
| Otherwise (e.g. multi-principal-element alloys) | TCHEA7 |

3. **Absorptivity** from resistivity at 1070 nm with the Drude/Hagen–Rubens series (Eq. 2), checked
   against experimental data in Appendix D.
4. **Melt pool** from the Rosenthal point source (Eq. 5). The boundary is swept in 1 µm steps of R
   using Eq. 4, with the tail length R = εP/(2πkΔT) (Eq. 15). This is conduction mode only.
5. **Lack of fusion** when (hatch/W)² + (layer/D)² > 1 (Eq. 3). Maps cover P × V from 100 to 1000
   (W, mm/s) in steps of 100, at the prescribed layer and ±25 µm.
6. **LLM (Claude Sonnet 4 through MCP subagents)** orchestrates, then ranks candidates by the size of
   their LoF regime.

## Results reported
- 11 of 12 known alloys produced a suitable LoF map.
- SS316L matched literature high-density points (150 W/500 mm/s, 200/700, 250/900, 300/1100). This
  skill also predicts all four as outside LoF at 50 µm hatch and 30 µm layer.
- In a corrosion-resistant comparison the LLM chose IN625 over SS316L for its smaller LoF region.
  This skill's `rank` gives the same order.
- **Error case:** the LLM recommended Enhanced Maraging Steel despite its *largest* LoF region. The
  authors trace this to tool output that was a bare list of (P, V) tuples. This skill returns
  explicitly keyed results (`lack_of_fusion_points`, `process_window_fraction`, `rank`) for that
  reason.

## Found while building this skill: unit slips in the repository's Thermo-Calc outputs
Several `materials/*.json` files under `results/known_alloys` (Ti-6Al-4V, Monel K500, H13, Al 7050)
hold the following, while the hand-entered files (SS316L, AlSi10Mg) are in proper units:
- density about **1000× too high**, e.g. 4.40e6 for Ti-6Al-4V. This is consistent with B/V in g/m³.
- Cp of about **30**. That is J/mol·K, the Dulong–Petit value, not J/kg·K.

Diffusivity k/(ρCp) for those alloys is therefore off by roughly 50–100×, and so are their Rosenthal
melt pools and LoF maps. `alloy.py check` (also applied whenever a material file is loaded) detects
both slips and converts them, using the alloy's molar mass for Cp. Re-check any Thermo-Calc-derived
map made before the fix.

## Limits to state in every report
- Rosenthal has a point source, constant properties and no fluid flow. It under-predicts melt pools
  at high energy, so the LoF boundary is conservative. It cannot show keyholing (W/D is always 2) or
  balling; use `lpbf-defect-prediction` for those.
- Property fidelity sets map fidelity. Built-in values are nominal room-temperature handbook values.
  The no-CALPHAD fallback (rule of mixtures plus nearest known alloy) is labelled low-confidence when
  the composition is far from any known alloy.
