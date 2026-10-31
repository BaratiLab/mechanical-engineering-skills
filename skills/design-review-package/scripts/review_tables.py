#!/usr/bin/env python3
"""Build design-review tables from CSVs.

  python review_tables.py bom  bom.csv  --qty 500 --out bom_rollup
      bom.csv columns: level,part_no,description,qty_per,unit_cost,make_buy,lead_time_wk[,cost_breaks]
  python review_tables.py fmea fmea.csv --rpn-threshold 100 --out fmea_ranked
      fmea.csv columns: item,function,failure_mode,effect,S,cause,O,current_controls,D[,action]

Writes <out>.csv, <out>.md (for documents) and prints a JSON summary.
"""
import argparse
import csv
import json


def read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def write(rows, cols, out):
    with open(out + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    with open(out + ".md", "w") as f:
        f.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for r in rows:
            f.write("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n")


def bom(a):
    rows = read(a.csv)
    # Compute extended qty through the level hierarchy
    stack = []
    total = 0.0
    for r in rows:
        lvl = int(r["level"])
        q = float(r["qty_per"])
        while stack and stack[-1][0] >= lvl:
            stack.pop()
        parent_q = stack[-1][1] if stack else 1.0
        ext = parent_q * q
        stack.append((lvl, ext))
        r["ext_qty"] = ext
        uc = float(r.get("unit_cost") or 0)
        r["ext_cost"] = round(ext * uc, 4)
    # Parent rows may carry their own assembly-labour cost
    leaf_total = sum(r["ext_cost"] for r in rows)
    lead = max((float(r.get("lead_time_wk") or 0), r["part_no"]) for r in rows)
    ranked = sorted(rows, key=lambda r: -r["ext_cost"])
    for r in rows:
        r["pct_cost"] = round(100 * r["ext_cost"] / leaf_total, 1) if leaf_total else 0
    cols = ["level", "part_no", "description", "qty_per", "ext_qty", "unit_cost", "ext_cost", "pct_cost", "make_buy", "lead_time_wk"]
    write(rows, cols, a.out)
    pareto, cum = [], 0
    for r in ranked:
        cum += r["pct_cost"]
        pareto.append(r["part_no"])
        if cum >= 80:
            break
    return {"unit_cost": round(leaf_total, 2), "build_qty": a.qty,
            "program_cost": round(leaf_total * a.qty, 2),
            "critical_path_part": lead[1], "critical_lead_time_wk": lead[0],
            "parts_driving_80pct_cost": pareto, "n_line_items": len(rows),
            "files": [a.out + ".csv", a.out + ".md"]}


def fmea(a):
    rows = read(a.csv)
    for r in rows:
        S, O, D = int(r["S"]), int(r["O"]), int(r["D"])
        r["RPN"] = S * O * D
        # AIAG-VDA action priority (simplified)
        if S >= 9 and O >= 4 or S >= 9 and D >= 7:
            ap = "H"
        elif S >= 7 and O >= 4 and D >= 5:
            ap = "H"
        elif r["RPN"] >= a.rpn_threshold or S >= 9:
            ap = "M"
        else:
            ap = "L"
        r["AP"] = ap
        r["flag"] = "ACTION" if ap == "H" or r["RPN"] >= a.rpn_threshold else ""
    rows.sort(key=lambda r: ({"H": 0, "M": 1, "L": 2}[r["AP"]], -r["RPN"]))
    cols = ["item", "function", "failure_mode", "effect", "S", "cause", "O", "current_controls", "D", "RPN", "AP", "flag", "action"]
    write(rows, cols, a.out)
    return {"n_modes": len(rows), "n_high_AP": sum(r["AP"] == "H" for r in rows),
            "n_flagged": sum(bool(r["flag"]) for r in rows),
            "top5": [{k: r[k] for k in ("item", "failure_mode", "RPN", "AP")} for r in rows[:5]],
            "files": [a.out + ".csv", a.out + ".md"]}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bom"); b.add_argument("csv"); b.add_argument("--qty", type=int, default=1); b.add_argument("--out", default="bom_rollup")
    f = sub.add_parser("fmea"); f.add_argument("csv"); f.add_argument("--rpn-threshold", type=int, default=100); f.add_argument("--out", default="fmea_ranked")
    a = p.parse_args()
    print(json.dumps((bom if a.cmd == "bom" else fmea)(a), indent=2))


if __name__ == "__main__":
    main()
