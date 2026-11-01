"""Run: python tests/test_rocket.py   (~30 s; CAD step needs CadQuery)"""
import json, math, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import rocket as R  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

m = R.motor_from_summary("H100W")
check("summary-shaped curve keeps certified impulse", abs(m.I - 226.8) < 0.5)
check("H100W is an H (L1) motor", m.letter() == "H" and R.CERT["H"] == "L1")
check("propellant burns off", math.isclose(m.mass(0), 0.261) and math.isclose(m.mass(99), 0.140, abs_tol=1e-9))
with tempfile.TemporaryDirectory() as d:
    eng = os.path.join(d, "t.eng")
    open(eng, "w").write("; test\nT100 38 150 0 0.1 0.25 X\n0.1 100\n1.0 100\n1.1 0\n")
    me = R.motor_from_eng(eng)
    check("RASP .eng parsed", me.d == 38 and abs(me.I - (0.5 * 0.1 * 100 + 0.9 * 100 + 0.5 * 0.1 * 100)) < 1e-6)

des = json.load(open(os.path.join(HERE, "..", "examples", "hp1_v38.json")))
rep, hist = R.report(des, m, 0.45)
ref = des["paper_reference"]
check(f"HP1 liftoff mass ~ paper ({rep['mass_g']['liftoff']} vs {ref['liftoff_mass_g']} g)", abs(rep["mass_g"]["liftoff"] - ref["liftoff_mass_g"]) < 60)
check(f"HP1 stability ~ paper ({rep['stability_cal']['liftoff']} vs {ref['stability_cal']})", abs(rep["stability_cal"]["liftoff"] - ref["stability_cal"]) < 0.05)
check("stability rises at burnout", rep["stability_cal"]["burnout"] > rep["stability_cal"]["liftoff"])
check(f"HP1 apogee within 10% of OpenRocket ({rep['flight']['apogee_m']} vs {ref['openrocket_apogee_m']} m)",
      abs(rep["flight"]["apogee_m"] / ref["openrocket_apogee_m"] - 1) < 0.10)
d4 = json.load(open(os.path.join(HERE, "..", "examples", "hp4_big_heavy_2.json")))
r4, _ = R.report(d4, R.motor_from_summary("J425R"), 0.45)
check(f"HP4 apogee within 10% of OpenRocket ({r4['flight']['apogee_m']} vs 570.1 m)", abs(r4["flight"]["apogee_m"] / 570.1 - 1) < 0.10)
cd = R.fit_cd(des, m, ref["measured_apogee_m"])
check(f"altimeter apogee implies higher drag (Cd {cd})", 0.6 < cd < 1.1)

# stability physics: bigger fins -> more stable; nose weight -> more stable
big = json.loads(json.dumps(des)); big["fins"]["span_mm"] *= 1.3
check("bigger fins increase stability", R.report(big, m)[0]["stability_cal"]["liftoff"] > rep["stability_cal"]["liftoff"])
nw = json.loads(json.dumps(des)); nw["masses"].append({"name": "nose weight", "mass_g": 100, "x_mm": 150})
check("nose weight increases stability", R.report(nw, m)[0]["stability_cal"]["liftoff"] > rep["stability_cal"]["liftoff"])
small = json.loads(json.dumps(des)); small["fins"]["span_mm"] = 40
rs = R.report(small, m)[0]
check("unstable design is flagged as an error", any(c["check"].startswith("stability") and not c["ok"] and c["severity"] == "error" for c in rs["checks"]) and not rs["go_for_review"])
sz = R.size_fins(small, m, 1.25)
check("fin sizing reaches the target", sz["ok"] and abs(sz["stability_cal"] - 1.25) < 0.02)
heavy = json.loads(json.dumps(des)); heavy["masses"].append({"name": "lead", "mass_g": 2500, "x_mm": 400})
hr = R.report(heavy, m)[0]
check("heavy rocket fails rail-exit / thrust-to-weight", any(c["check"].startswith(("rail", "average thrust")) and not c["ok"] for c in hr["checks"]))
try:
    import cadquery  # noqa: F401
    with tempfile.TemporaryDirectory() as d:
        c = R.cad(des, d, m)
        check("nose and fin can exported", all(os.path.getsize(p) > 1000 for p in c["files"].values()) and c["solid_volume_cm3"]["fincan"] > c["solid_volume_cm3"]["nose"])
except ImportError:
    print("SKIP cad (no cadquery)")
print(f"\n{ok} checks passed")
