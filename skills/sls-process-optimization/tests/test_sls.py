"""Run: python tests/test_sls.py   (no network, ~20 s)"""
import os, sys, json, sqlite3, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import sls  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

ex = os.path.join(HERE, "..", "examples")
t = sls.astm("d638", os.path.join(ex, "d638_type4_example.csv"), 4)
check(f"D638 modulus recovered ({t['Et_MPa']} vs 1500)", abs(t["Et_MPa"] - 1500) < 30)
check(f"D638 UTS ({t['UTS_MPa']} vs ~35.8)", 35 < t["UTS_MPa"] < 36.5)
f = sls.astm("d790", os.path.join(ex, "d790_example.csv"))
check(f"D790 flexural modulus recovered ({f['Ef_MPa']} vs 1100)", abs(f["Ef_MPa"] - 1100) < 25)
s = sls.summarize([{"Et_MPa": 1000}, {"Et_MPa": 1200}, {"Et_MPa": 1100}])
check("summary has best, mean, sd", s["Et_MPa"]["best"] == 1200 and s["Et_MPa"]["mean"] == 1100 and s["Et_MPa"]["sd"] == 100)

with tempfile.TemporaryDirectory() as d:
    db = os.path.join(d, "b.sqlite")
    r = sls.init(db, seed=True)
    check("paper history seeded (21 batches, 3 materials)", r["batches"] == 21 and len(r["materials"]) == 3)
    h = sls.history(db, "PA11 Onyx")
    check("PA11 Onyx improves O->R", h["batches"][-1]["Et"] > h["batches"][0]["Et"] and h["batches"][-1]["score"] > 0.75)
    check("non-reproducible batch H excluded", [b for b in sls.history(db, "PA12 GF")["batches"] if b["batch"] == "H"][0]["excluded"])
    # replay: after A-C the suggester should move overlap to 50 (the real improvement in batch D)
    rp = os.path.join(d, "r.sqlite"); shutil.copy(db, rp)
    con = sqlite3.connect(rp); con.execute("delete from batches where material='PA12 GF' and id>'C'"); con.commit()
    sg = sls.suggest(rp, "PA12 GF", "UTS", 3)
    check("replay after A-C proposes overlap 50 %", all(c["overlap_pct"] == 50 for c in sg["candidates"]))
    sg = sls.suggest(db, "PA11 Onyx", "score", 3)
    tm = sg["tds_target"] and sls.history(db, "PA11 Onyx")["tmelt_C"]
    check("suggestions stay below the melt peak", all(c["tsurf_C"] <= tm - 3 for c in sg["candidates"]))
    check("suggestions within one fill step of the best batch", all(abs(c["fill_mJ_mm"] - sg["best_so_far"]["fill_mJ_mm"]) <= 8 for c in sg["candidates"]))
    check("warnings carried into the suggestion", any("warping" in w for w in sg["warnings"]))
    con = sls.connect(db); con.execute("insert into materials values ('NewPA', ?, 180, '')", (json.dumps({"Et": 1500}),)); con.commit()
    check("empty material gives a conservative start", "start" in sls.suggest(db, "NewPA"))
print(f"\n{ok} checks passed")
