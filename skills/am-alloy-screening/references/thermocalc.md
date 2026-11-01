# Thermo-Calc setup (optional, licensed)

1. Install Thermo-Calc (2025b or later) and TC-Python from the Thermo-Calc installer. Set
   `TC25B_HOME` (or your version's variable), `LSHOST` (licence server) and `JAVA_HOME`.
   The lab's `pip install thermo-calc` package (ppak10/thermo-calc) automates the install.
2. Check it works: `python -c "import tc_python"`.
3. Run `python scripts/alloy.py properties --comp "Fe-10Ni-10Ti" --thermocalc --out FeNiTi.json`.
   - The database is picked automatically (Appendix C rules).
   - Solidus and liquidus come from the liquid volume fraction over 500–3500 K.
   - Density, Cp, k and resistivity are evaluated at the melting point; absorptivity is computed
     from the resistivity.
   - `meta.raw` keeps the raw Thermo-Calc numbers and `meta.unit_fixes` lists any conversion applied.
4. Database coverage limits accuracy. Multi-principal-element and exotic compositions extrapolate.
   Always run `check` and compare with the nearest known alloy.

The Thermo-Calc code path can't be tested without a licence. The unit sanitizer and everything
downstream is covered by `tests/test_alloy.py`.
