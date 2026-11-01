#!/usr/bin/env python3
"""Closed LLM <-> FEM design loop (Algorithm 1 of arXiv:2404.17525), with the agent as the LLM.

  init   python design_loop.py init --task t1v1 --run runs/t1v1    [--custom-task task.json]
  eval   python design_loop.py eval --run runs/t1v1 design.json    -> FEM, ranked history, next prompt
  best   python design_loop.py best --run runs/t1v1                -> best feasible design + plot
  plot   python design_loop.py plot --run runs/t1v1 design.json --out truss.png

Loop rules (paper): max 25 iterations; after each FEM evaluation the ranked history R
(feasible sorted by objective, then infeasible sorted by closeness to feasibility) is fed back;
feasible -> OPTIMIZE prompt, infeasible -> CONSTRAINT prompt. The agent may stop on its own
by setting "stop": true in a feasible design when gains have become marginal.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tasks import AREA, TASKS, custom  # noqa: E402
from truss_fem import evaluate  # noqa: E402

MAX_ITERS = 25
PROMPTS = os.path.join(HERE, "..", "references", "prompts.md")


def load_task(run):
    return json.load(open(os.path.join(run, "task.json")))


def history(run):
    p = os.path.join(run, "history.jsonl")
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def infeas_score(h, task):
    """Normalized constraint excess (0 = feasible); invalid designs rank last."""
    r = h["result"]
    if not r.get("valid"):
        return 1e9
    c, s = task["constraints"], 0.0
    if "max_stress" in c: s += max(0, r["max_abs_stress"] / c["max_stress"] - 1)
    if "max_mass" in c: s += max(0, r["total_mass"] / c["max_mass"] - 1)
    if "max_swr" in c: s += max(0, r["swr"] / c["max_swr"] - 1)
    return s


def ranked(hist, task):
    feas = sorted([h for h in hist if h["result"]["feasible"]], key=lambda h: h["result"]["objective"])
    inf = sorted([h for h in hist if not h["result"]["feasible"]], key=lambda h: infeas_score(h, task))
    return feas + inf


def summarize(h):
    r = h["result"]
    if not r.get("valid"):
        return {"iter": h["iter"], "status": "INVALID", "errors": r["errors"]}
    return {"iter": h["iter"], "status": "FEASIBLE" if r["feasible"] else "INFEASIBLE",
            "max_abs_stress": round(r["max_abs_stress"], 4), "total_mass": round(r["total_mass"], 4),
            "swr": round(r["swr"], 4), "violations": r.get("violations", []),
            "critical_members": r["critical_members"],
            "n_nodes": len(h["design"]["node_dict"]), "n_members": len(h["design"]["member_dict"]),
            "design": h["design"]}


def section(name):
    txt = open(PROMPTS).read()
    start = txt.index(f"## {name}")
    end = txt.find("\n## ", start + 3)
    return txt[start: end if end > 0 else None].split("\n", 1)[1].strip()


def render_prompt(mode, task, hist_ranked, current, it):
    t = section(mode)
    fill = {"{nodes}": json.dumps(task["nodes"]), "{load}": json.dumps(task["load"]),
            "{supports}": json.dumps(task["supports"]), "{area_id}": json.dumps(AREA),
            "{constraints}": json.dumps(task["constraints"]), "{objective}": task["objective"],
            "{iteration}": f"{it}/{MAX_ITERS}",
            "{current}": json.dumps(current, indent=1) if current else "none",
            "{history}": json.dumps(hist_ranked[:8], indent=1)}
    for k, v in fill.items():
        t = t.replace(k, v)
    return t


def cmd_init(a):
    os.makedirs(a.run, exist_ok=True)
    task = custom(a.custom_task) if a.custom_task else TASKS[a.task]
    json.dump(task | {"name": a.task or "custom"}, open(os.path.join(a.run, "task.json"), "w"), indent=2)
    open(os.path.join(a.run, "history.jsonl"), "w").close()
    p = render_prompt("INITIAL", task, [], None, 1)
    open(os.path.join(a.run, "prompt_next.md"), "w").write(p)
    print(json.dumps({"run": a.run, "next_prompt": "prompt_next.md", "task": task}, indent=2))


def cmd_eval(a):
    task = load_task(a.run)
    hist = history(a.run)
    if len(hist) >= MAX_ITERS:
        sys.exit(f"iteration budget {MAX_ITERS} exhausted; run `best`")
    design = json.load(open(a.design))
    res = evaluate(design, task)
    h = {"iter": len(hist) + 1, "design": {"node_dict": design["node_dict"], "member_dict": design["member_dict"]},
         "result": res, "stop_requested": bool(design.get("stop"))}
    with open(os.path.join(a.run, "history.jsonl"), "a") as f:
        f.write(json.dumps(h) + "\n")
    hist.append(h)
    R = [summarize(x) for x in ranked(hist, task)]
    stop = (h["stop_requested"] and res["feasible"]) or len(hist) >= MAX_ITERS
    mode = "OPTIMIZE" if res["feasible"] else "CONSTRAINT"
    out = {"iteration": h["iter"], "result": summarize(h), "mode_next": None if stop else mode,
           "stop": stop, "best_so_far": R[0] if R and R[0]["status"] == "FEASIBLE" else None}
    if h["stop_requested"] and not res["feasible"]:
        out["note"] = "stop refused: design is not feasible"
    if not stop:
        open(os.path.join(a.run, "prompt_next.md"), "w").write(render_prompt(mode, task, R, summarize(h), h["iter"] + 1))
        out["next_prompt"] = "prompt_next.md"
    print(json.dumps(out, indent=2))


def plot(design, task, res, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    nd = design["node_dict"]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    st = res.get("member_stress", {})
    smax = max((abs(v) for v in st.values()), default=1) or 1
    cmap = plt.cm.coolwarm
    for m, (a, b, aid) in design["member_dict"].items():
        (x1, y1), (x2, y2) = nd[a][:2], nd[b][:2]
        v = st.get(m, 0)
        ax.plot([x1, x2], [y1, y2], color=cmap(0.5 + 0.5 * v / smax), lw=1 + 0.5 * AREA[str(aid)])
        ax.text((x1 + x2) / 2, (y1 + y2) / 2, f"{v:.1f}", fontsize=7, ha="center",
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.5))
    for n, xy in nd.items():
        ax.plot(*xy[:2], "o", color="#2c3e50", ms=5)
        ax.annotate(n.replace("node_", "n"), xy[:2], xytext=(4, 4), textcoords="offset points", fontsize=8)
    for n, t in task["supports"].items():
        ax.plot(*nd[n][:2], "s" if t == "pinned" else "^", color="#c0392b" if t == "pinned" else "#27ae60", ms=11, alpha=0.8)
    for n, (mag, ang) in task["load"].items():
        fx, fy = mag * np.cos(np.radians(ang)), mag * np.sin(np.radians(ang))
        s = 0.06
        ax.annotate("", xy=(nd[n][0] + fx * s, nd[n][1] + fy * s), xytext=nd[n][:2],
                    arrowprops=dict(arrowstyle="-|>", color="#8e44ad", lw=2))
    ax.set_aspect("equal")
    title = (f"max|σ| = {res['max_abs_stress']:.3f}   mass = {res['total_mass']:.3f}   SWR = {res['swr']:.4f}"
             if res.get("valid") else "INVALID")
    ax.set_title(title, fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=160)


def cmd_best(a):
    task = load_task(a.run)
    R = ranked(history(a.run), task)
    if not R or not R[0]["result"]["feasible"]:
        print(json.dumps({"best": None, "note": "no feasible design yet"}))
        return
    b = R[0]
    out = os.path.join(a.run, "best.png")
    plot(b["design"], task, b["result"], out)
    json.dump(b["design"], open(os.path.join(a.run, "best_design.json"), "w"), indent=2)
    print(json.dumps({"best_iter": b["iter"], "summary": summarize(b), "plot": out,
                      "iterations": len(history(a.run))}, indent=2))


def cmd_plot(a):
    task = load_task(a.run)
    d = json.load(open(a.design))
    plot(d, task, evaluate(d, task), a.out)
    print(a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--task", choices=TASKS); s.add_argument("--custom-task"); s.add_argument("--run", required=True)
    s = sub.add_parser("eval"); s.add_argument("design"); s.add_argument("--run", required=True)
    s = sub.add_parser("best"); s.add_argument("--run", required=True)
    s = sub.add_parser("plot"); s.add_argument("design"); s.add_argument("--run", required=True); s.add_argument("--out", default="truss.png")
    a = ap.parse_args()
    {"init": cmd_init, "eval": cmd_eval, "best": cmd_best, "plot": cmd_plot}[a.cmd](a)


if __name__ == "__main__":
    main()
