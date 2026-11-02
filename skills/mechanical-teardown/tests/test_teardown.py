"""Run: python tests/test_teardown.py   (a few seconds, standard library only)"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import teardown as T  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

def spec(parts, **prod):
    return {"product": dict({"name": "t", "annual_volume": 1000, "lifetime_years": 1, "labor_usd_h": 36.0}, **prod),
            "parts": parts}

# --- DFA index against a hand calculation ----------------------------------------------------------
s = spec([
    {"id": "A", "name": "base", "kind": "part", "handling": "easy", "insertion": "drop_in", "separate_for_service": True, "cost_usd": 1},
    {"id": "B", "name": "rotor", "kind": "part", "handling": "orient", "insertion": "align", "moves": True, "cost_usd": 1},
    {"id": "C", "name": "cover", "kind": "part", "handling": "easy", "insertion": "snap", "cost_usd": 1},
    {"id": "F", "name": "screw", "kind": "fastener", "qty": 4, "handling": "small", "insertion": "screw", "cost_usd": 0.1},
])
a = T.analyze(s)
t_hand = (1.5 + 1.5) + (2.2 + 3.0) + (1.5 + 2.5) + 4 * (3.0 + 6.0)
check("assembly time is the sum of handling + insertion per item", abs(a["assembly_time_s"] - t_hand) < 1e-9)
check("N_min counts only parts passing the Boothroyd test (base, rotor)", a["n_min"] == 2)
check("DFA index = 3 N_min / T", abs(a["dfa_index"] - 3 * 2 / t_hand) < 1e-12)
check("fasteners counted by quantity", a["fasteners"] == 4 and a["n_parts"] == 7)
check("labour = time x rate", abs(a["labor_usd"] - t_hand / 3600 * 36.0) < 1e-12)
check("elimination candidates are ranked by time (screws first)",
      [c["id"] for c in a["elimination_candidates"]] == ["F", "C"])

a2 = T.analyze(spec([{"id": "R", "name": "regulate", "kind": "process", "qty": 2, "time_s": 40, "cost_usd": 0}]))
check("time_s overrides the table time, and process steps are never necessary",
      a2["assembly_time_s"] == 80 and a2["n_min"] == 0)

# --- necessity rules -------------------------------------------------------------------------------
check("fasteners are never necessary", not T.is_necessary({"kind": "fastener", "moves": True}))
check("different material makes a part necessary", T.is_necessary({"kind": "part", "different_material": True}))
check("explicit override wins", not T.is_necessary({"kind": "part", "moves": True, "necessary": False}))

# --- should-cost model -----------------------------------------------------------------------------
p = {"id": "M", "qty": 2, "material": "ABS", "process": "injection_molding", "mass_g": 100,
     "cycle_s": 36, "cavities": 2, "tooling_usd": 20000}
notes = []
c, br = T.part_cost(p, {"annual_volume": 10000, "lifetime_years": 2}, notes)
rate, _, _, scrap = T.PROCESS["injection_molding"]
unit = 0.1 * 2.5 / (1 - scrap) + 36 / 3600 * rate / 2 + 20000 / 20000
check("modelled cost = material + conversion + amortised tooling, times qty", abs(c - 2 * unit) < 1e-12)
check("given cost overrides the model", T.part_cost({"id": "x", "qty": 3, "cost_usd": 0.5}, {}, [])[0] == 1.5)
notes = []
T.part_cost({"id": "y", "material": "unobtainium", "process": "cnc_milling", "mass_g": 10}, {}, notes)
check("unknown material and defaulted cycle are reported as assumptions",
      any("unobtainium" in n for n in notes) and any("default cycle" in n for n in notes))
z = {"id": "z", "material": "ABS", "process": "injection_molding", "mass_g": 100, "cycle_s": 0, "tooling_usd": 0}
c_tab = T.part_cost(z, {}, [])[0]; c_own = T.part_cost(z, {"material_usd_kg": {"abs": 10.0}}, [])[0]
check("spec material price overrides the table", abs(c_own / c_tab - 4.0) < 1e-9)

# --- repairability ---------------------------------------------------------------------------------
def rep(joint, depth=0):
    return T.analyze(spec([
        {"id": "H", "name": "housing", "subassembly": "S", "insertion": "screw", "separate_for_service": True, "cost_usd": 1},
        {"id": "W", "name": "wear", "subassembly": "S", "insertion": joint, "wear_part": True, "depth": depth, "cost_usd": 1},
    ], repair={"standard_tools": True, "spares_available": False, "manual_available": False}))["repairability"]
check("screwed wear part scores higher than a glued one", rep("screw") > rep("adhesive") + 2)
check("a buried wear part scores lower than an exposed one", rep("screw", 0) > rep("screw", 6))
check("score stays within 0-10", 0 <= rep("weld", 20) <= 10 and rep("screw") <= 10)

# --- FMEA ------------------------------------------------------------------------------------------
s2 = spec([{"id": "A", "cost_usd": 1}])
s2["fmea"] = [{"mode": "a", "S": 4, "O": 8, "D": 8}, {"mode": "b", "S": 9, "O": 1, "D": 2},
              {"mode": "c", "S": 7, "O": 5, "D": 2}]
f = T.analyze(s2)["fmea"]
check("RPN = S x O x D", f[-1]["RPN"] == 256)
check("action priority ranks High severity above raw RPN", [x["mode"] for x in f] == ["c", "b", "a"])
s2["fmea"] = [{"mode": "bad", "S": 11, "O": 1, "D": 1}]
try:
    T.analyze(s2); bad = False
except ValueError:
    bad = True
check("ratings outside 1-10 are rejected", bad)
try:
    T.analyze(spec([{"id": "A"}, {"id": "A"}])); dup = False
except ValueError:
    dup = True
check("duplicate part ids are rejected", dup)

# --- worked example and report ---------------------------------------------------------------------
for exf in sorted(f for f in os.listdir(os.path.join(HERE, "..", "examples")) if f.endswith(".json")):
    ea = T.analyze(json.load(open(os.path.join(HERE, "..", "examples", exf))))
    check(f"example {exf}: analyses without error, 0 < DFA < 1", 0 < ea["dfa_index"] < 1)
ex = os.path.join(HERE, "..", "examples", "cordless_drill.json")
E = json.load(open(ex))
a = T.analyze(E)
check("example: parts cost equals the sum of line items", abs(a["parts_cost_usd"] - sum(r["cost_usd"] for r in a["parts"])) < 1e-9)
check("example: N_min <= N and DFA index in (0, 1)", a["n_min"] <= a["n_parts"] and 0 < a["dfa_index"] < 1)
check("example: should-cost below retail price", a["cost_to_price"] < 1)
html = T.render_html(E, a)
for sec_name in ["Bill of materials", "Design for assembly", "Should-cost", "Repairability", "Failure modes", "Engineering verdict"]:
    check(f"report has section '{sec_name}'", sec_name in html)
E2 = json.loads(json.dumps(E)); E2["product"]["name"] = "<script>x</script>"
check("report escapes HTML in user text", "<script>x" not in T.render_html(E2, T.analyze(E2)))
with tempfile.TemporaryDirectory() as d:
    tp = os.path.join(d, "t.json")
    out = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "teardown.py"), "template"],
                         capture_output=True, text=True, check=True).stdout
    open(tp, "w").write(out)
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "teardown.py"), "report", tp,
                        "-o", os.path.join(d, "r.html")], capture_output=True, text=True)
    check("CLI: template -> report runs end to end", r.returncode == 0 and os.path.getsize(os.path.join(d, "r.html")) > 2000)

print(f"\n{ok} checks passed")
