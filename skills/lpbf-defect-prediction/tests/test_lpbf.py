"""Run: python tests/test_lpbf.py   (needs network once to fetch MeltpoolNet; full test ~1-2 min)"""
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import lpbf  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    ok += 1


# --- criteria
r = lpbf.criteria(depth=120, width=150, length=420, hatch=100, layer=40)
check("keyhole when W/D<1.5", r["labels"] == ["Keyholing"])
r = lpbf.criteria(depth=50, width=120, length=300, hatch=110, layer=40)
check("LoF when (h/W)^2+(t/D)^2>1", "Lack of Fusion" in r["labels"])
r = lpbf.criteria(depth=60, width=110, length=110 * (math.pi + 0.1), hatch=50, layer=20)
check("balling when L/W>pi", r["labels"] == ["Balling"])
r = lpbf.criteria(depth=60, width=120, length=300, hatch=60, layer=30)
check("none when all pass", r["labels"] == ["None"])
r = lpbf.criteria(depth=60, width=120)
check("unevaluated criteria are reported", r["evaluated"] == ["Keyholing"])
check("baseline text format", lpbf.baseline_text({"material": "SS316L", "power": 200.0, "velocity": 800.0, "beam": 80.0,
                                                  "hatch": float("nan"), "layer": 30.0})
      == "SS316L [SEP] 200 W [SEP] 800 mm/s [SEP] 80 microns [SEP]  [SEP] 30 microns")

# --- dataset + model (end to end)
df = lpbf.build(lpbf.fetch())
check("dataset size", 300_000 < len(df) < 400_000)
aug = df[df.source == "augmented"]
check("augmentation is 20x20 per melt pool", (aug.groupby("group").size() == 400).all())
check("labels are multi-hot and None exclusive", ((df[["Keyholing", "Lack of Fusion", "Balling"]].sum(axis=1) > 0)
                                                  != (df["None"] == 1)).all())
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "data.parquet"); m = os.path.join(d, "m.joblib")
    df.to_parquet(p)
    res = lpbf.train(p, m, split="grouped")
    check(f"grouped exact-match >= 0.80 ({res['exact_match_accuracy']:.3f})", res["exact_match_accuracy"] >= 0.80)
    hot = lpbf.predict(m, "Ti-6Al-4V", 380, 250, 80, 100, 30)
    cold = lpbf.predict(m, "Ti-6Al-4V", 80, 2200, 80, 150, 60)
    check("high energy -> keyholing", "Keyholing" in hot["predicted"])
    check("low energy, coarse hatch -> lack of fusion", "Lack of Fusion" in cold["predicted"])
    check("monotone: more power never lowers P(keyhole)",
          lpbf.predict(m, "Ti-6Al-4V", 300, 800, 80, 100, 30)["probabilities"]["Keyholing"] >=
          lpbf.predict(m, "Ti-6Al-4V", 200, 800, 80, 100, 30)["probabilities"]["Keyholing"])
    mp = lpbf.process_map(m, "Ti-6Al-4V", 100, 30, 80, os.path.join(d, "map.png"))
    check("map written with a window", os.path.exists(mp["map"]) and mp["most_robust_point"] is not None)
print(f"\n{ok} checks passed")
