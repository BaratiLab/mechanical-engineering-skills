"""Run: python tests/test_eqdisc.py   (synthetic data, no network, ~30 s)"""
import json, os, sys, tempfile
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import eqdisc as E  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

with tempfile.TemporaryDirectory() as d:
    rng = np.random.default_rng(0)
    def make(n, tmin, tmax):   # damped saturation law: y = a (1 - exp(-b x)) exp(-c T)
        x, T = rng.uniform(0, 3, n), rng.uniform(tmin, tmax, n)
        return pd.DataFrame({"x": x, "T": T, "y": 2.0 * (1 - np.exp(-1.5 * x)) * np.exp(-0.8 * T) + rng.normal(0, 0.005, n)})
    for name, (lo, hi) in {"train": (0, 1), "id": (0, 1), "ood": (1.2, 1.6)}.items():
        make(400, lo, hi).to_csv(os.path.join(d, f"{name}.csv"), index=False)
    run = os.path.join(d, "run")
    E.init(run, os.path.join(d, "train.csv"), "y", ["x", "T"], os.path.join(d, "id.csv"), os.path.join(d, "ood.csv"), "test law")
    good = "def equation(x, T, params):\n    return params[0] * (1 - np.exp(-params[1] * x)) * np.exp(-params[2] * T)\n"
    poly = "def equation(x, T, params):\n    return params[0] + params[1] * x + params[2] * T + params[3] * x * T + params[4] * x ** 2\n"
    r1 = E.evaluate(run, poly, "polynomial"); r2 = E.evaluate(run, good, "true form")
    check(f"true form fits to noise level (NMSE {r2['nmse']['train']:.1e})", r2["nmse"]["train"] < 1e-3)
    check("fitted constants recovered", np.allclose(sorted(r2["params"]), sorted([2.0, 1.5, 0.8]), atol=0.05))
    check("true form extrapolates far better than the polynomial", r2["nmse"]["test_ood"] < 0.1 * r1["nmse"]["test_ood"])
    check("params used counted", r2["n_params"] == 3 and r1["n_params"] == 5)
    for bad, why in [("import os\ndef equation(x, T, params):\n    return x\n", "imports"),
                     ("def equation(x, T, params):\n    return open('f').read()\n", "open"),
                     ("def equation(x, T, params):\n    return x.__class__\n", "dunder"),
                     ("def equation(T, x, params):\n    return x\n", "signature"),
                     ("def equation(x, T, params):\n    return params[12] * x\n", "params bound")]:
        try:
            E.evaluate(run, bad); passed = False
        except (ValueError, RuntimeError):
            passed = True
        check(f"rejects {why}", passed)
    p = E.prompt(run, 3)
    check("prompt lists programs worst->best and asks for the next version",
          p.index("equation_v0") < p.index("equation_v1") and "def equation_v2(x, T, params):" in p)
    fr = E.pareto(run)
    check("pareto front ends at the best program", fr[-1]["nmse"]["train"] == min(r["nmse"]["train"] for r in E.buffer(run)))
    b = E.baseline(run)
    check("baselines computed", "poly3" in b and b["poly3"]["train"] < b["linear"]["train"])
    check("final test never appears in the proposal prompt", "OOD" not in p and f"{r2['nmse']['test_ood']:.3e}" not in p)
    check("final test hidden from pareto and top during search",
          all("test_ood" not in r["nmse"] for r in fr) and all("test_ood" not in r["nmse"] for r in E.top(run, 5)))
    try:
        E.top(run, 5, "test_ood"); refused = False
    except SystemExit:
        refused = True
    check("selecting by the final test is refused", refused)
    f = E.final(run, r2["id"])
    check("final reveals the held-out score once and logs it",
          abs(f["nmse"]["test_ood"] - r2["nmse"]["test_ood"]) < 1e-12 and os.path.exists(os.path.join(run, "final.json")))
print(f"\n{ok} checks passed")
