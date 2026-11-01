#!/usr/bin/env python3
"""Scientific equation discovery with an LLM in the loop, after LLM-SR (Shojaee, Meidani, Gupta, Barati Farimani,
Reddy, ICLR 2025 Oral; code github.com/deep-symbolic-mathematics/LLM-SR, MIT) and LLM-SRBench (ICML 2025).

LLM-SR: the LLM writes equation *skeletons* as Python functions with a `params` vector; the numeric constants are
fitted by an optimiser (BFGS); scores are fed back through an experience buffer of the best programs, which the
LLM sees as in-context examples for its next proposals. Here you are the LLM; this script is the evaluator and memory.

  init     python eqdisc.py init --dir run/ --train train.csv [--test-id id.csv --test-ood ood.csv] --target stress \
               [--inputs strain,temp] --desc "stress in an aluminium rod vs strain and temperature"
  fetch    python eqdisc.py fetch --problem stressstrain|oscillator1|oscillator2|bactgrow --dir run/   LLM-SR benchmark data
  prompt   python eqdisc.py prompt --dir run/ [--k 4]          problem spec + top-k programs from the buffer -> next proposal
  eval     python eqdisc.py eval --dir run/ --file skel.py [--note "why"]   fit params, score, add to the buffer
  top      python eqdisc.py top --dir run/ [--k 10]
  pareto   python eqdisc.py pareto --dir run/ --out front.png     complexity vs error; pick the simplest that generalises
  baseline python eqdisc.py baseline --dir run/                    polynomial / sparse-regression baselines for context

A skeleton file defines `def equation(<inputs...>, params): return ...` using numpy as np; params has MAX_NPARAMS
entries (default 10). Scores: NMSE = mean((y - yhat)^2) / var(y) on train, validation (test-ID) and a final test
(test-OOD, LLM-SR's held-out split) that stays hidden until `final` is run on the chosen equation.
"""
import argparse
import ast
import json
import math
import os
import subprocess
import sys
import textwrap
import time

import numpy as np

MAX_NPARAMS = 10
BENCH = "https://raw.githubusercontent.com/deep-symbolic-mathematics/LLM-SR/main/data/{p}/{s}.csv"
BENCH_DESC = {
    "stressstrain": ("stress", ["strain", "temp"], "Stress in an aluminium rod as a function of strain and temperature, elastic and plastic regions."),
    "oscillator1": ("dv", ["x", "v"], "Acceleration of a nonlinear damped oscillator from position x and velocity v."),
    "oscillator2": ("dv", ["t", "x", "v"], "Acceleration of a driven nonlinear oscillator from time t, position x and velocity v."),
    "bactgrow": ("dB", ["B", "S", "temp", "pH"], "Bacterial growth rate from population density B, substrate S, temperature and pH."),
}
SAFE_NAMES = {"np", "params", "abs", "min", "max", "float", "int", "range", "len", "sum", "pow", "round"}


# ------------------------------------------------------------------ problem setup
def init(d, train, target, inputs=None, test_id=None, test_ood=None, desc=""):
    import pandas as pd
    os.makedirs(d, exist_ok=True)
    tr = pd.read_csv(train)
    inputs = inputs or [c for c in tr.columns if c != target]
    meta = {"target": target, "inputs": inputs, "description": desc, "max_nparams": MAX_NPARAMS, "splits": {}}
    for name, f in (("train", train), ("test_id", test_id), ("test_ood", test_ood)):
        if f:
            df = pd.read_csv(f)[inputs + [target]]
            df.to_csv(os.path.join(d, f"{name}.csv"), index=False)
            meta["splits"][name] = {"rows": len(df), "ranges": {c: [float(df[c].min()), float(df[c].max())] for c in inputs}}
    json.dump(meta, open(os.path.join(d, "problem.json"), "w"), indent=1)
    open(os.path.join(d, "buffer.jsonl"), "a").close()
    return meta


def fetch(problem, d):
    import urllib.request
    os.makedirs(d, exist_ok=True)
    paths = {}
    for s in ("train", "test_id", "test_ood"):
        p = os.path.join(d, f"_{s}.csv")
        urllib.request.urlretrieve(BENCH.format(p=problem, s=s), p)
        paths[s] = p
    t, ins, desc = BENCH_DESC[problem]
    return init(d, paths["train"], t, ins, paths["test_id"], paths["test_ood"], desc)


def load(d, split):
    import pandas as pd
    meta = json.load(open(os.path.join(d, "problem.json")))
    f = os.path.join(d, f"{split}.csv")
    if not os.path.exists(f):
        return None, None, meta
    df = pd.read_csv(f)
    return [df[c].values.astype(float) for c in meta["inputs"]], df[meta["target"]].values.astype(float), meta


# ------------------------------------------------------------------ skeleton checks and evaluation
def check_source(src, meta):
    """Static checks: one function `equation(<inputs>, params)`, numpy only, no imports/IO/dunder, bounded params index."""
    tree = ast.parse(src)
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if not any(f.name == "equation" for f in fns):
        raise ValueError("define `def equation(...)`")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Lambda)) and not isinstance(node, ast.Lambda):
            raise ValueError("no imports/global statements: numpy is available as np")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("dunder/private attributes are not allowed")
        if isinstance(node, ast.Name) and node.id in ("open", "exec", "eval", "compile", "__import__", "globals", "locals", "getattr", "setattr", "input"):
            raise ValueError(f"'{node.id}' is not allowed")
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "params":
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, int) and sl.value >= meta["max_nparams"]:
                raise ValueError(f"params index {sl.value} >= MAX_NPARAMS {meta['max_nparams']}")
    eq = [f for f in fns if f.name == "equation"][0]
    args = [a.arg for a in eq.args.args]
    if args[-1] != "params" or args[:-1] != meta["inputs"]:
        raise ValueError(f"signature must be equation({', '.join(meta['inputs'])}, params)")
    used = sorted({n.slice.value for n in ast.walk(eq) if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                   and n.value.id == "params" and isinstance(n.slice, ast.Constant)})
    complexity = sum(1 for _ in ast.walk(eq.body[-1] if len(eq.body) == 1 else eq))
    return used, complexity


WORKER = r'''
import json, sys, warnings, numpy as np
from scipy.optimize import minimize
warnings.filterwarnings("ignore")
cfg = json.loads(sys.stdin.read())
ns = {"np": np, "__builtins__": {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
      for k in ("abs", "min", "max", "float", "int", "range", "len", "sum", "pow", "round", "True", "False", "None")}}
exec(cfg["src"], ns)
f = ns["equation"]
def arr(split):
    d = cfg["data"].get(split)
    return None if d is None else ([np.asarray(c) for c in d["x"]], np.asarray(d["y"]))
Xtr, ytr = arr("train")
def nmse(X, y, p):
    yh = np.asarray(f(*X, p), float) * np.ones_like(y)
    return float(np.mean((y - yh) ** 2) / (np.var(y) + 1e-30))
def loss(p):
    with np.errstate(all="ignore"):
        try:
            v = nmse(Xtr, ytr, p)
        except Exception:
            return 1e30
    return v if np.isfinite(v) else 1e30
rng = np.random.default_rng(0)
best = None
starts = [np.ones(cfg["n"])] + [rng.normal(0, 1, cfg["n"]) * 10 ** rng.uniform(-1, 1, cfg["n"]) for _ in range(cfg["restarts"])]
for p0 in starts:                       # LLM-SR uses BFGS from ones; extra random starts reduce bad local minima
    r = minimize(loss, p0, method="BFGS", options={"maxiter": 2000})
    if best is None or r.fun < best.fun:
        best = r
out = {"params": best.x.tolist(), "nmse": {}}
for s in ("train", "test_id", "test_ood"):
    d = arr(s)
    if d is not None:
        with np.errstate(all="ignore"):
            try:
                out["nmse"][s] = nmse(d[0], d[1], best.x)
            except Exception as e:
                out["nmse"][s] = None
print(json.dumps(out))
'''


def evaluate(d, src, note="", restarts=4, timeout=120, max_train=4000):
    _, _, meta = load(d, "train")
    used, complexity = check_source(src, meta)
    data = {}
    for s in ("train", "test_id", "test_ood"):
        X, y, _ = load(d, s)
        if X is not None:
            if s == "train" and len(y) > max_train:
                idx = np.random.default_rng(0).choice(len(y), max_train, replace=False)
                X, y = [x[idx] for x in X], y[idx]
            data[s] = {"x": [x.tolist() for x in X], "y": y.tolist()}
    cfg = {"src": src, "data": data, "n": meta["max_nparams"], "restarts": restarts}
    t0 = time.time()
    try:   # separate process: bounded time, no access to this process's state
        r = subprocess.run([sys.executable, "-I", "-c", WORKER], input=json.dumps(cfg), capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "evaluation failed")
        res = json.loads(r.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"evaluation exceeded {timeout} s")
    rec = {"id": sum(1 for _ in open(os.path.join(d, "buffer.jsonl"))) + 1, "src": src, "note": note,
           "nmse": res["nmse"], "params_used": used, "n_params": len(used),
           "params": [round(res["params"][i], 6) for i in used], "complexity": complexity, "seconds": round(time.time() - t0, 1),
           "score": -math.log10(max(res["nmse"].get("train") or 1e30, 1e-30))}
    with open(os.path.join(d, "buffer.jsonl"), "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def buffer(d):
    return [json.loads(l) for l in open(os.path.join(d, "buffer.jsonl")) if l.strip()]


FINAL = "test_ood"   # final hidden test: stored, but not shown until `final` is run on a frozen equation


def hide_final(r):
    r = dict(r); r["nmse"] = {k: v for k, v in r["nmse"].items() if k != FINAL}
    return r


def top(d, k=10, key="train"):
    if key == FINAL:
        raise SystemExit("the final test is hidden during search; select by train or test_id, then run `final --id N`")
    b = [r for r in buffer(d) if r["nmse"].get(key) is not None]
    return [hide_final(r) for r in sorted(b, key=lambda r: (r["nmse"][key], r["complexity"]))[:k]]


def final(d, rid):
    """Reveal the final-test NMSE for one frozen equation, once, and log it."""
    log = os.path.join(d, "final.json")
    if os.path.exists(log):
        prev = json.load(open(log))
        if prev["id"] != rid:
            print(f"warning: the final test was already used for #{prev['id']}; a second look is no longer an untouched test",
                  file=sys.stderr)
    r = next(x for x in buffer(d) if x["id"] == rid)
    out = {"id": rid, "nmse": r["nmse"], "n_params": r["n_params"], "params": r["params"], "src": r["src"].strip()}
    json.dump({"id": rid, "nmse": r["nmse"]}, open(log, "w"))
    return out


def prompt(d, k=4):
    """LLM-SR-style prompt: problem spec + the best k skeletons (with fitted scores), ordered worst -> best, then ask
    for an improved equation_v{k}. Diversity: at most one program per complexity bucket of 5."""
    _, _, meta = load(d, "train")
    b = sorted([r for r in buffer(d) if r["nmse"].get("train") is not None], key=lambda r: r["nmse"]["train"])
    picks, seen = [], set()
    for r in b:
        bucket = r["complexity"] // 5
        if bucket in seen:
            continue
        seen.add(bucket); picks.append(r)
        if len(picks) == k:
            break
    picks = picks[::-1]
    sig = ", ".join(meta["inputs"])
    lines = [f'"""{meta["description"]}"""', f"# Inputs: {sig}. Target: {meta['target']}.",
             f"# Training ranges: {json.dumps(meta['splits']['train']['ranges'])}",
             f"# params: up to {meta['max_nparams']} constants, fitted by BFGS. Lower NMSE is better; prefer simpler forms.", ""]
    for i, r in enumerate(picks):
        body = r["src"].replace("def equation(", f"def equation_v{i}(")
        # feedback uses train and validation (test_id) only; the final test (test_ood) is never shown
        lines += [f"# v{i}: train NMSE {r['nmse']['train']:.3e}" + (f", validation NMSE {r['nmse'].get('test_id'):.3e}" if r["nmse"].get("test_id") is not None else "")
                  + f", {r['n_params']} params, complexity {r['complexity']}", body.strip(), ""]
    lines += [f"def equation_v{len(picks)}({sig}, params):", f'    """Improved version of equation_v{max(len(picks) - 1, 0)}."""']
    return "\n".join(lines)


def pareto(d, out=None):
    b = [r for r in buffer(d) if r["nmse"].get("train") is not None]
    front = []
    for r in sorted(b, key=lambda r: (r["complexity"], r["nmse"]["train"])):
        if not front or r["nmse"]["train"] < front[-1]["nmse"]["train"]:
            front.append(r)
    if out:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6, 4))
        for key, mk, lab in (("train", "o", "train"), ("test_id", "s", "validation")):
            pts = [(r["complexity"], r["nmse"][key]) for r in b if r["nmse"].get(key)]
            if pts:
                ax.scatter(*zip(*pts), marker=mk, alpha=0.6, label=lab)
        ax.plot([r["complexity"] for r in front], [r["nmse"]["train"] for r in front], "k--", lw=1, label="Pareto front (train)")
        for r in front:
            ax.annotate(f"#{r['id']}", (r["complexity"], r["nmse"]["train"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set_yscale("log"); ax.set_xlabel("complexity (AST nodes)"); ax.set_ylabel("NMSE"); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(out, dpi=140)
    return [{"id": r["id"], "complexity": r["complexity"], "nmse": hide_final(r)["nmse"], "n_params": r["n_params"], "note": r["note"]} for r in front]


def baseline(d, degree=3, alpha=1e-6):
    """Reference points: linear regression and polynomial (+ sparse Lasso) in the inputs."""
    from sklearn.linear_model import LinearRegression, Lasso
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    Xtr, ytr, meta = load(d, "train")
    A = np.c_[tuple(Xtr)]
    res = {}
    for name, m in (("linear", LinearRegression()),
                    (f"poly{degree}", make_pipeline(PolynomialFeatures(degree), StandardScaler(), LinearRegression())),
                    (f"poly{degree}_lasso", make_pipeline(PolynomialFeatures(degree), StandardScaler(), Lasso(alpha=1e-4, max_iter=50000)))):
        m.fit(A, ytr)
        res[name] = {}
        for s in ("train", "test_id", "test_ood"):
            X, y, _ = load(d, s)
            if X is not None:
                res[name][s] = float(np.mean((y - m.predict(np.c_[tuple(X)])) ** 2) / np.var(y))
        if "lasso" in name:
            res[name]["nonzero_terms"] = int(np.sum(np.abs(m[-1].coef_) > 1e-8))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--dir", required=True); s.add_argument("--train", required=True)
    s.add_argument("--target", required=True); s.add_argument("--inputs"); s.add_argument("--test-id"); s.add_argument("--test-ood")
    s.add_argument("--desc", default="")
    s = sub.add_parser("fetch"); s.add_argument("--problem", choices=list(BENCH_DESC), required=True); s.add_argument("--dir", required=True)
    s = sub.add_parser("prompt"); s.add_argument("--dir", required=True); s.add_argument("--k", type=int, default=4)
    s = sub.add_parser("eval"); s.add_argument("--dir", required=True); s.add_argument("--file"); s.add_argument("--src")
    s.add_argument("--note", default=""); s.add_argument("--restarts", type=int, default=4)
    s = sub.add_parser("top"); s.add_argument("--dir", required=True); s.add_argument("--k", type=int, default=10)
    s.add_argument("--by", default="train", choices=["train", "test_id"])
    s = sub.add_parser("final", help="reveal the hidden final-test score of one frozen equation")
    s.add_argument("--dir", required=True); s.add_argument("--id", type=int, required=True)
    s = sub.add_parser("pareto"); s.add_argument("--dir", required=True); s.add_argument("--out")
    s = sub.add_parser("baseline"); s.add_argument("--dir", required=True)
    s.add_argument("--final", action="store_true", help="also show baselines on the final test (after selection)")
    a = ap.parse_args()
    if a.cmd == "init":
        r = init(a.dir, a.train, a.target, a.inputs.split(",") if a.inputs else None, a.test_id, a.test_ood, a.desc)
    elif a.cmd == "fetch":
        r = fetch(a.problem, a.dir)
    elif a.cmd == "prompt":
        print(prompt(a.dir, a.k)); return
    elif a.cmd == "eval":
        src = open(a.file).read() if a.file else textwrap.dedent(a.src)
        r = hide_final(evaluate(a.dir, src, a.note, a.restarts)); r.pop("src")
    elif a.cmd == "top":
        r = [{k: v for k, v in x.items() if k != "src"} | {"src": x["src"].strip()} for x in top(a.dir, a.k, a.by)]
    elif a.cmd == "pareto":
        r = pareto(a.dir, a.out)
    elif a.cmd == "final":
        r = final(a.dir, a.id)
    else:
        r = baseline(a.dir)
        if not a.final:
            r = {m: {k: v for k, v in sc.items() if k != FINAL} for m, sc in r.items()}
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
