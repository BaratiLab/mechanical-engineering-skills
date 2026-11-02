#!/usr/bin/env python3
"""Mechanical product teardown: turn a teardown spec (JSON) into numbers and a report.

    python teardown.py template  > my_product.json         # empty spec to fill in
    python teardown.py analyze   my_product.json           # DFA, cost, mass, repairability, FMEA as text
    python teardown.py analyze   my_product.json --json    # same, machine-readable
    python teardown.py report    my_product.json -o teardown_report.html

The spec holds what was observed (parts, materials, processes, joints, masses) and what was
judged (functions, failure modes, design signals, opportunities). This script only computes:
it never invents parts. Every default it applies is listed in the "assumptions" output.

Methods (see ../references/):
  * DFA index (Boothroyd-Dewhurst, manual assembly): E = 3 * N_min / total assembly time.
    A part is theoretically necessary if it moves relative to parts already assembled, must be a
    different material, or must be separate for assembly or service. Fasteners never are.
  * Should-cost per part: material (mass, scrap, $/kg) + conversion (cycle time x machine rate /
    cavities) + tooling amortised over lifetime volume; or a cost the user measured or quoted.
    Assembly labour = total DFA time x labour rate.
  * Repairability (0-10) over the parts marked as wear/failure parts: reversibility of the joint
    holding each part, how many parts must come off first, and tool / spare / manual availability.
  * FMEA: RPN = S x O x D (1-10 each), ranked; action priority High when S >= 9, or S >= 7 and O >= 4.
"""
import argparse, base64, html, json, math, os, sys

# ----------------------------------------------------------------------------- data tables
# Manual handling and insertion times in seconds, condensed from the Boothroyd-Dewhurst
# manual-assembly tables (typical mid-range values; see references/dfa_times.md).
HANDLING_S = {
    "easy": 1.5,        # one hand, no tools, symmetric or easy to orient
    "orient": 2.2,      # must be oriented about one axis
    "small": 3.0,       # small/slippery, needs tweezers or care (< 6 mm)
    "flexible": 4.5,    # wires, springs that tangle, gaskets, flex cables
    "heavy": 4.0,       # two hands or a lift aid
}
INSERTION_S = {
    "drop_in": 1.5,     # placed, self-locating, not secured
    "align": 3.0,       # needs alignment, held by the next part
    "snap": 2.5,        # snap fit / clip, secured on insertion
    "hold_down": 5.5,   # must be held while the next part goes on
    "press": 4.5,       # press fit, bearing pressed onto shaft
    "screw": 6.0,       # per screw: place and drive with a power driver
    "rivet": 5.0,
    "connector": 4.0,   # plug a wire connector
    "solder": 9.0,      # hand solder a joint
    "adhesive": 10.0,   # dispense glue, place, hold
    "weld": 12.0,       # spot/ultrasonic weld per joint
    "wire_route": 8.0,  # route and dress a wire or harness
}
# Joint reversibility for repair (1 = comes apart and goes back without damage).
REVERSIBILITY = {
    "screw": 1.0, "rivet": 0.3, "snap": 0.8, "drop_in": 1.0, "align": 1.0, "hold_down": 1.0,
    "connector": 1.0, "press": 0.5, "solder": 0.4, "adhesive": 0.1, "weld": 0.0, "wire_route": 0.9,
}
# Indicative raw-material prices in USD/kg (2025-26 order of magnitude; override in the spec).
MATERIAL_USD_KG = {
    "abs": 2.5, "pc": 3.5, "pc/abs": 3.0, "pa6": 3.2, "pa66": 3.5, "pa66-gf30": 4.0, "pa6-gf30": 3.8,
    "pom": 3.0, "pp": 1.6, "pe": 1.6, "pbt": 3.2, "tpe": 4.0, "silicone": 8.0, "pmma": 3.0,
    "steel": 1.2, "carbon steel": 1.2, "alloy steel": 2.0, "stainless steel": 4.0, "spring steel": 2.5,
    "sintered steel": 3.0, "cast iron": 1.0, "aluminum": 3.5, "aluminium": 3.5, "die-cast aluminum": 3.0,
    "zinc": 3.5, "die-cast zinc": 3.2, "brass": 8.0, "copper": 10.0, "magnesium": 5.0, "titanium": 25.0,
    "rubber": 3.0, "tin": 30.0, "glass": 1.5, "cardboard": 1.0,
}
# Process: (machine rate USD/h, default cycle s, default tooling USD, default scrap fraction)
PROCESS = {
    "injection_molding": (45.0, 30.0, 25000.0, 0.03),
    "overmolding": (55.0, 45.0, 40000.0, 0.04),
    "die_casting": (90.0, 45.0, 60000.0, 0.05),
    "sand_casting": (60.0, 300.0, 5000.0, 0.08),
    "investment_casting": (70.0, 600.0, 15000.0, 0.06),
    "stamping": (80.0, 2.0, 15000.0, 0.10),
    "progressive_die": (110.0, 0.8, 40000.0, 0.10),
    "cnc_turning": (70.0, 90.0, 0.0, 0.02),
    "cnc_milling": (85.0, 300.0, 0.0, 0.02),
    "screw_machining": (60.0, 20.0, 0.0, 0.03),
    "powder_metallurgy": (70.0, 10.0, 20000.0, 0.02),
    "forging": (100.0, 20.0, 30000.0, 0.05),
    "extrusion": (60.0, 10.0, 3000.0, 0.05),
    "sheet_metal": (70.0, 60.0, 500.0, 0.05),
    "fdm": (5.0, 3600.0, 0.0, 0.05),
    "sls": (40.0, 900.0, 0.0, 0.05),
    "wire_forming": (40.0, 3.0, 2000.0, 0.02),
    "purchased": (0.0, 0.0, 0.0, 0.0),   # bought-in: cost_usd must be given
}
DEFAULTS = {"labor_usd_h": 30.0, "annual_volume": 100000, "lifetime_years": 3}

PART_FIELDS = ["id", "name", "qty", "subassembly", "kind", "material", "process", "mass_g", "cost_usd",
               "cycle_s", "cavities", "tooling_usd", "handling", "insertion", "time_s", "moves",
               "different_material", "separate_for_service", "necessary", "wear_part", "depth", "notes"]


def template():
    return {
        "product": {"name": "", "category": "", "maker": "", "model": "", "price_usd": None,
                    "annual_volume": DEFAULTS["annual_volume"], "lifetime_years": DEFAULTS["lifetime_years"],
                    "labor_usd_h": DEFAULTS["labor_usd_h"], "pitch": "",
                    "evidence": ["what was seen: own teardown / photos / exploded view / manual / patents"],
                    "repair": {"standard_tools": True, "spares_available": False, "manual_available": False}},
        "requirements": [{"need": "", "metric": "", "how_met": ""}],
        "functions": [{"function": "", "parts": [], "subfunctions": []}],
        "parts": [{"id": "P1", "name": "", "qty": 1, "subassembly": "", "kind": "part",
                   "material": "", "process": "injection_molding", "mass_g": 0.0,
                   "handling": "easy", "insertion": "snap", "moves": False, "different_material": False,
                   "separate_for_service": False, "wear_part": False, "depth": 0, "notes": ""}],
        "fmea": [{"item": "", "mode": "", "effect": "", "cause": "", "S": 5, "O": 3, "D": 5, "action": ""}],
        "design_signals": [{"title": "", "evidence": "", "why": ""}],
        "benchmark": {"dimensions": [], "products": [{"name": "", "values": []}]},
        "opportunities": [{"title": "", "change": "", "impact": "", "effort": "low|med|high", "savings_usd": 0.0}],
        "verdict": "",
        "images": [{"path": "", "caption": ""}],
    }


# ----------------------------------------------------------------------------- analysis
def _num(x, default=0.0):
    try:
        return float(x) if x is not None else default
    except (TypeError, ValueError):
        return default


def is_necessary(p):
    """Boothroyd minimum-part-count test for one part (per unit)."""
    if "necessary" in p and p["necessary"] is not None:
        return bool(p["necessary"])
    if p.get("kind") in ("fastener", "label", "packaging", "process"):
        return False
    return bool(p.get("moves") or p.get("different_material") or p.get("separate_for_service"))


def part_cost(p, prod, notes):
    """Return (unit cost USD, breakdown dict). A given cost_usd wins over the model."""
    qty = max(1, int(_num(p.get("qty"), 1)))
    if p.get("cost_usd") is not None:
        c = _num(p["cost_usd"])
        return c * qty, {"material": None, "conversion": None, "tooling": None, "given": c * qty}
    proc = (p.get("process") or "purchased").lower()
    if proc not in PROCESS:
        notes.append(f"{p['id']}: unknown process '{proc}', costed as material only")
        rate, cyc, tool, scrap = 0.0, 0.0, 0.0, 0.03
    else:
        rate, cyc, tool, scrap = PROCESS[proc]
    if proc == "purchased":
        notes.append(f"{p['id']}: purchased part with no cost_usd, counted as $0, add a quote")
        return 0.0, {"material": 0.0, "conversion": 0.0, "tooling": 0.0, "given": None}
    mat = (p.get("material") or "").lower()
    usd_kg = prod.get("material_usd_kg", {}).get(mat, MATERIAL_USD_KG.get(mat))
    if usd_kg is None:
        notes.append(f"{p['id']}: no price for material '{mat}', material cost set to 0")
        usd_kg = 0.0
    m_kg = _num(p.get("mass_g")) / 1000.0
    material = m_kg * usd_kg / (1.0 - scrap)
    cycle = _num(p.get("cycle_s"), cyc)
    if p.get("cycle_s") is None and cyc:
        notes.append(f"{p['id']}: default cycle {cyc:g} s for {proc}")
    cav = max(1, int(_num(p.get("cavities"), 1)))
    conversion = cycle / 3600.0 * rate / cav
    tooling_usd = _num(p.get("tooling_usd"), tool)
    life = _num(prod.get("annual_volume"), DEFAULTS["annual_volume"]) * \
        _num(prod.get("lifetime_years"), DEFAULTS["lifetime_years"])
    tooling = tooling_usd / max(life, 1.0)
    unit = material + conversion + tooling
    return unit * qty, {"material": material * qty, "conversion": conversion * qty,
                        "tooling": tooling * qty, "given": None}


def analyze(spec):
    prod = dict(DEFAULTS, **(spec.get("product") or {}))
    parts = spec.get("parts") or []
    notes = []
    ids = [p.get("id") for p in parts]
    if len(set(ids)) != len(ids):
        raise ValueError("part ids must be unique")
    rows, t_total, n_min, n_total = [], 0.0, 0, 0
    mass_by_mat, cost_by_proc = {}, {}
    for p in parts:
        qty = max(1, int(_num(p.get("qty"), 1)))
        h = p.get("handling") or "easy"
        i = p.get("insertion") or ("screw" if p.get("kind") == "fastener" else "align")
        if h not in HANDLING_S:
            notes.append(f"{p['id']}: unknown handling '{h}', used 'easy'"); h = "easy"
        if i not in INSERTION_S:
            notes.append(f"{p['id']}: unknown insertion '{i}', used 'align'"); i = "align"
        if p.get("time_s") is not None:           # measured or process step time per item
            t = qty * _num(p["time_s"])
        else:
            t = qty * (HANDLING_S[h] + INSERTION_S[i])
        nec = is_necessary(p)
        nmin = qty if nec else 0
        cost, br = part_cost(p, prod, notes)
        mass = qty * _num(p.get("mass_g"))
        mat = (p.get("material") or "unspecified").lower()
        mass_by_mat[mat] = mass_by_mat.get(mat, 0.0) + mass
        proc = (p.get("process") or "purchased").lower()
        cost_by_proc[proc] = cost_by_proc.get(proc, 0.0) + cost
        rows.append({"id": p["id"], "name": p.get("name", ""), "qty": qty,
                     "subassembly": p.get("subassembly", ""), "kind": p.get("kind", "part"),
                     "material": p.get("material", ""), "process": proc, "mass_g": mass,
                     "cost_usd": cost, "cost_breakdown": br, "handling": h, "insertion": i,
                     "time_s": t, "necessary": nec, "n_min": nmin,
                     "wear_part": bool(p.get("wear_part")), "depth": int(_num(p.get("depth"), 0)),
                     "notes": p.get("notes", "")})
        t_total += t; n_min += nmin; n_total += qty
    labor = t_total / 3600.0 * _num(prod.get("labor_usd_h"), DEFAULTS["labor_usd_h"])
    parts_cost = sum(r["cost_usd"] for r in rows)
    dfa = 3.0 * n_min / t_total if t_total > 0 else 0.0
    fasteners = sum(r["qty"] for r in rows if r["kind"] == "fastener")
    joints = {}
    for r in rows:
        joints[r["insertion"]] = joints.get(r["insertion"], 0) + r["qty"]
    # Elimination candidates: parts that are not theoretically necessary, by time saved.
    candidates = sorted([r for r in rows if not r["necessary"]], key=lambda r: -r["time_s"])
    # Repairability over wear parts.
    wear = [r for r in rows if r["wear_part"]]
    rep = (prod.get("repair") or {})
    if wear:
        per = []
        for r in wear:
            rev = REVERSIBILITY.get(r["insertion"], 0.5)
            path = [REVERSIBILITY.get(x["insertion"], 0.5) for x in rows
                    if x["subassembly"] == r["subassembly"] and x["id"] != r["id"]]
            path_rev = min(path) if path else 1.0       # weakest joint guarding the subassembly
            reach = 1.0 / (1.0 + 0.15 * r["depth"])      # each part removed first costs ~15 %
            per.append({"id": r["id"], "name": r["name"], "joint": r["insertion"], "depth": r["depth"],
                        "score": 10.0 * (0.35 * rev + 0.35 * path_rev + 0.30 * reach)})
        base = sum(x["score"] for x in per) / len(per)
        bonus = (0.5 if rep.get("standard_tools", True) else -1.0) + \
                (0.5 if rep.get("spares_available") else -0.5) + (0.3 if rep.get("manual_available") else -0.3)
        repair_score = max(0.0, min(10.0, base + bonus))
    else:
        per, repair_score = [], None
        notes.append("no parts marked wear_part, repairability not scored")
    fmea = []
    for f in spec.get("fmea") or []:
        S, O, D = (int(_num(f.get(k), 1)) for k in ("S", "O", "D"))
        for k, v in (("S", S), ("O", O), ("D", D)):
            if not 1 <= v <= 10:
                raise ValueError(f"FMEA '{f.get('mode')}': {k}={v} outside 1-10")
        ap = "High" if S >= 9 or (S >= 7 and O >= 4) else ("Medium" if S >= 5 and O >= 3 else "Low")
        fmea.append(dict(f, S=S, O=O, D=D, RPN=S * O * D, AP=ap))
    fmea.sort(key=lambda f: (-{"High": 2, "Medium": 1, "Low": 0}[f["AP"]], -f["RPN"]))
    total_cost = parts_cost + labor
    price = prod.get("price_usd")
    out = {
        "product": prod.get("name", ""),
        "n_parts": n_total, "n_line_items": len(rows), "n_min": n_min, "fasteners": fasteners,
        "assembly_time_s": t_total, "dfa_index": dfa,
        "mass_g": sum(r["mass_g"] for r in rows),
        "parts_cost_usd": parts_cost, "labor_usd": labor, "should_cost_usd": total_cost,
        "price_usd": price,
        "cost_to_price": (total_cost / price) if price else None,
        "mass_by_material": dict(sorted(mass_by_mat.items(), key=lambda kv: -kv[1])),
        "cost_by_process": dict(sorted(cost_by_proc.items(), key=lambda kv: -kv[1])),
        "joints": dict(sorted(joints.items(), key=lambda kv: -kv[1])),
        "parts": sorted(rows, key=lambda r: -r["cost_usd"]),
        "elimination_candidates": [{"id": r["id"], "name": r["name"], "qty": r["qty"],
                                    "time_s": r["time_s"], "cost_usd": r["cost_usd"]} for r in candidates],
        "repairability": repair_score, "repair_parts": per,
        "fmea": fmea, "assumptions": notes,
    }
    # Pareto: how many line items make 80 % of parts cost.
    acc, k = 0.0, 0
    for r in out["parts"]:
        if parts_cost <= 0 or acc >= 0.8 * parts_cost:
            break
        acc += r["cost_usd"]; k += 1
    out["pareto80_items"] = k
    return out


# ----------------------------------------------------------------------------- text output
def text_summary(a):
    L = [f"Teardown: {a['product']}",
         f"  parts {a['n_parts']} ({a['n_line_items']} line items), theoretical minimum {a['n_min']}, "
         f"fasteners {a['fasteners']}",
         f"  assembly time {a['assembly_time_s']:.0f} s, DFA index {a['dfa_index']*100:.1f} %",
         f"  mass {a['mass_g']:.0f} g",
         f"  should-cost ${a['should_cost_usd']:.2f} (parts ${a['parts_cost_usd']:.2f} + labour ${a['labor_usd']:.2f})"
         + (f", {a['cost_to_price']*100:.0f} % of ${a['price_usd']:.2f} price" if a['cost_to_price'] else ""),
         f"  {a['pareto80_items']} line items make 80 % of parts cost",
         "  repairability " + (f"{a['repairability']:.1f}/10" if a['repairability'] is not None else "not scored"),
         "", "Top cost items:"]
    for r in a["parts"][:6]:
        L.append(f"  {r['id']:<6} {r['name'][:34]:<34} ${r['cost_usd']:7.2f}  {r['process']}")
    L += ["", "Elimination candidates (not theoretically necessary):"]
    for c in a["elimination_candidates"][:6]:
        L.append(f"  {c['id']:<6} {c['name'][:34]:<34} x{c['qty']:<3} {c['time_s']:5.1f} s")
    if a["fmea"]:
        L += ["", "FMEA (ranked):"]
        for f in a["fmea"][:5]:
            L.append(f"  [{f['AP']:<6}] RPN {f['RPN']:4d}  {f.get('item','')}: {f.get('mode','')}")
    if a["assumptions"]:
        L += ["", "Assumptions applied:"] + ["  - " + n for n in a["assumptions"]]
    return "\n".join(L)


# ----------------------------------------------------------------------------- HTML report
PALETTE = ["#1e40af", "#f97316", "#14b8a6", "#8b5cf6", "#ec4899", "#f59e0b", "#64748b", "#22c55e",
           "#0ea5e9", "#a3a3a3"]
E = html.escape


def _g(v):
    """Mass label that stays readable for watch-sized parts."""
    return f"{v:,.0f} g" if v >= 10 else (f"{v:.1f} g" if v >= 1 else f"{v:.2f} g" if v >= 0.01 else f"{v:.3f} g")


def _bars(items, unit_fmt, width=560, bar_h=22, color="#1e40af", max_items=10):
    items = list(items)[:max_items]
    if not items:
        return ""
    vmax = max(v for _, v in items) or 1.0
    lab_w = 300 if width >= 800 else 230
    h = len(items) * (bar_h + 8) + 8
    out = [f'<svg viewBox="0 0 {width} {h}" width="{width}" style="max-width:100%;height:auto" role="img">']
    for k, (lab, v) in enumerate(items):
        y = 8 + k * (bar_h + 8)
        w = (width - lab_w - 90) * v / vmax
        out.append(f'<text x="{lab_w-8}" y="{y+bar_h*0.72}" text-anchor="end" class="bl">{E(str(lab)[:34])}</text>'
                   f'<rect x="{lab_w}" y="{y}" width="{max(w,1):.1f}" height="{bar_h}" rx="4" fill="{color}"/>'
                   f'<text x="{lab_w+w+6:.1f}" y="{y+bar_h*0.72}" class="bv">{unit_fmt(v)}</text>')
    out.append("</svg>")
    return "".join(out)


def _stack(items, unit_fmt, width=560, min_share=0.03):
    tot = sum(v for _, v in items) or 1.0
    big = [(l.replace("_", " "), v) for l, v in items if v / tot >= min_share]
    small = sum(v for _, v in items if v / tot < min_share)
    items = big + ([("other", small)] if small > 0 else [])
    x, segs, leg = 0.0, [], []
    for k, (lab, v) in enumerate(items):
        w = width * v / tot
        c = PALETTE[k % len(PALETTE)]
        segs.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="34" fill="{c}"/>')
        leg.append(f'<span class="lg"><i style="background:{c}"></i>{E(lab)} {unit_fmt(v)} '
                   f'({100*v/tot:.0f} %)</span>')
        x += w
    return f'<svg viewBox="0 0 {width} 34" width="100%" class="stack">{"".join(segs)}</svg><div>{"".join(leg)}</div>'


def _gauge(value, lo, hi, good_hi=True, label=""):
    """Horizontal 0..1 meter."""
    f = 0.0 if value is None else max(0.0, min(1.0, (value - lo) / (hi - lo)))
    c = "#16a34a" if (f >= 0.6) == good_hi else ("#f59e0b" if 0.3 <= f < 0.6 else "#dc2626")
    return (f'<div class="meter"><div style="width:{100*f:.0f}%;background:{c}"></div></div>'
            f'<div class="ml"><span>{lo}</span><span>{E(label)}</span><span>{hi}</span></div>')


def _func_tree(nodes):
    if not nodes:
        return ""
    li = []
    for n in nodes:
        parts = ", ".join(n.get("parts") or [])
        li.append(f'<li><b>{E(n.get("function",""))}</b>'
                  + (f' <span class="pid">{E(parts)}</span>' if parts else "")
                  + _func_tree(n.get("subfunctions")) + "</li>")
    return "<ul>" + "".join(li) + "</ul>"


def _img(path, base):
    p = path if os.path.isabs(path) else os.path.join(base, path)
    if not path or not os.path.exists(p):
        return None
    ext = os.path.splitext(p)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "svg": "svg+xml", "webp": "webp"}.get(ext, "png")
    with open(p, "rb") as f:
        return f"data:image/{mime};base64," + base64.b64encode(f.read()).decode()


CSS = """
:root{--ink:#0f172a;--mut:#475569;--line:#e2e8f0;--acc:#f97316;--nav:#1e3a8a;--bg:#f8fafc}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Inter,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1040px;margin:0 auto;padding:0 28px 60px}
header.cover{background:linear-gradient(120deg,#0f172a,#1e3a8a 70%);color:#fff;padding:46px 0 34px;margin-bottom:26px}
header .wrap{padding-bottom:0}.kick{letter-spacing:.18em;text-transform:uppercase;font-size:12px;color:#fdba74;font-weight:700}
h1{font-size:40px;line-height:1.1;margin:8px 0 6px}.pitch{font-size:17px;color:#cbd5e1;max-width:760px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}.chip{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);border-radius:999px;padding:3px 12px;font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin:0 0 24px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.kpi .v{font-size:26px;font-weight:800;color:var(--nav)}.kpi .l{font-size:12.5px;color:var(--mut)}
section{background:#fff;border:1px solid var(--line);border-radius:16px;padding:22px 24px;margin:18px 0}
section h2{margin:0 0 12px;font-size:21px;display:flex;align-items:center;gap:10px}
section h2 .n{background:var(--acc);color:#fff;border-radius:8px;font-size:13px;padding:2px 9px}
table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9;font-weight:700;color:#334155}td.r,th.r{text-align:right;white-space:nowrap}
.tag{display:inline-block;border-radius:6px;padding:0 7px;font-size:12px;font-weight:700}
.High{background:#fee2e2;color:#991b1b}.Medium{background:#fef3c7;color:#92400e}.Low{background:#dcfce7;color:#166534}
.yes{color:#166534;font-weight:700}.no{color:#b91c1c;font-weight:700}
.bl{font-size:12.5px;fill:#334155}.bv{font-size:12.5px;fill:#0f172a;font-weight:700}
.lg{display:inline-flex;align-items:center;gap:5px;margin:6px 12px 0 0;font-size:12.5px;color:#334155}.lg i{width:11px;height:11px;border-radius:3px;display:inline-block}
.stack{border-radius:8px;overflow:hidden}
.meter{height:12px;background:#e2e8f0;border-radius:999px;overflow:hidden}.meter div{height:100%}
.ml{display:flex;justify-content:space-between;font-size:12px;color:var(--mut);margin-top:3px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px}@media(max-width:800px){.grid2{grid-template-columns:1fr}}
.card{border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:10px;padding:10px 14px;margin:8px 0}
.card b{display:block}.mut{color:var(--mut);font-size:13.5px}
ul{margin:4px 0 4px 18px;padding:0}li{margin:3px 0}.pid{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#64748b}
.gallery{display:flex;flex-direction:column;gap:18px;margin-bottom:10px}.gallery figure{margin:0;text-align:center}.gallery img{display:block;margin:0 auto;max-width:100%;max-height:820px;border-radius:10px;border:1px solid var(--line)}
.gallery figcaption{font-size:12.5px;color:var(--mut)}
.verdict{background:#0f172a;color:#f8fafc;border:none}.verdict h2{color:#fff}.verdict p{font-size:17px;margin:0}
footer{color:var(--mut);font-size:12.5px;text-align:center;margin-top:24px}
@media print{body{background:#fff}section,.kpi{break-inside:avoid}header.cover{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def render_html(spec, a, base_dir="."):
    p = spec.get("product") or {}
    money = lambda v: f"${v:,.2f}" if v >= 0 else f"&minus;${-v:,.2f}"
    grams = lambda v: f"{v:,.0f} g"
    secs = lambda v: f"{v:.0f} s"
    n = [0]

    def sec(title, body, cls=""):
        n[0] += 1
        return f'<section class="{cls}"><h2><span class="n">{n[0]:02d}</span>{E(title)}</h2>{body}</section>'

    chips = "".join(f'<span class="chip">{E(str(x))}</span>' for x in
                    [p.get("category"), p.get("maker"), p.get("model"),
                     money(p["price_usd"]) if p.get("price_usd") else None,
                     f'{int(_num(p.get("annual_volume"), DEFAULTS["annual_volume"])):,} / yr (assumed)'] if x)
    head = (f'<header class="cover"><div class="wrap"><div class="kick">Mechanical teardown</div>'
            f'<h1>{E(p.get("name",""))}</h1><div class="pitch">{E(p.get("pitch",""))}</div>'
            f'<div class="meta">{chips}</div></div></header>')
    ctp = f'{a["cost_to_price"]*100:.0f} %' if a["cost_to_price"] else "n/a"
    kp = [(str(a["n_parts"]), f'parts ({a["n_line_items"]} line items)'),
          (str(a["n_min"]), "theoretical minimum parts"),
          (f'{a["dfa_index"]*100:.1f} %', "DFA index (best practice > 25 %)"),
          (secs(a["assembly_time_s"]), "manual assembly time"),
          (money(a["should_cost_usd"]), f"should-cost, {ctp} of price"),
          (f'{a["repairability"]:.1f}/10' if a["repairability"] is not None else "n/a", "repairability")]
    kpis = '<div class="kpis">' + "".join(f'<div class="kpi"><div class="v">{v}</div><div class="l">{E(l)}</div></div>'
                                          for v, l in kp) + "</div>"
    body = []
    # 1 evidence and gallery
    imgs = []
    for im in spec.get("images") or []:
        src = _img(im.get("path", ""), base_dir)
        if src:
            imgs.append(f'<figure><img src="{src}" alt=""><figcaption>{E(im.get("caption",""))}</figcaption></figure>')
    ev = "".join(f"<li>{E(x)}</li>" for x in p.get("evidence") or [])
    body.append(sec("What was examined", (f'<div class="gallery">{"".join(imgs)}</div>' if imgs else "")
                    + (f"<ul>{ev}</ul>" if ev else "")))
    # 2 requirements and functions
    req = spec.get("requirements") or []
    rt = ("<table><tr><th>User need</th><th>Engineering metric</th><th>How the design meets it</th></tr>" +
          "".join(f'<tr><td>{E(r.get("need",""))}</td><td>{E(r.get("metric",""))}</td><td>{E(r.get("how_met",""))}</td></tr>'
                  for r in req) + "</table>") if req else ""
    body.append(sec("Requirements and function structure",
                    f'<div class="grid2"><div>{rt}</div><div>{_func_tree(spec.get("functions"))}</div></div>'))
    # 3 BOM
    bom = ["<table><tr><th>ID</th><th>Part</th><th class='r'>Qty</th><th>Subassembly</th><th>Material</th>"
           "<th>Process</th><th class='r'>Mass</th><th class='r'>Cost</th><th>Necessary?</th></tr>"]
    for r in sorted(a["parts"], key=lambda r: (r["subassembly"], r["id"])):
        bom.append(f'<tr><td class="pid">{E(r["id"])}</td><td>{E(r["name"])}</td><td class="r">{r["qty"]}</td>'
                   f'<td>{E(r["subassembly"])}</td><td>{E(r["material"])}</td><td>{E(r["process"].replace("_"," "))}</td>'
                   f'<td class="r">{_g(r["mass_g"])}</td><td class="r">{money(r["cost_usd"])}</td>'
                   f'<td class="{"yes" if r["necessary"] else "no"}">{"yes" if r["necessary"] else "no"}</td></tr>')
    bom.append("</table>")
    body.append(sec("Bill of materials", "".join(bom)))
    # 4 materials and processes
    body.append(sec("Materials and processes",
                    '<div class="grid2"><div><h3>Mass by material</h3>' + _stack(list(a["mass_by_material"].items()), grams)
                    + '</div><div><h3>Cost by process</h3>' + _stack(list(a["cost_by_process"].items()), money) + "</div></div>"))
    # 5 DFA
    cand = "".join(f'<tr><td class="pid">{E(c["id"])}</td><td>{E(c["name"])}</td><td class="r">{c["qty"]}</td>'
                   f'<td class="r">{c["time_s"]:.1f} s</td></tr>' for c in a["elimination_candidates"][:10])
    joints = ", ".join(f"{k.replace('_',' ')} x{v}" for k, v in a["joints"].items())
    dfa = (f'<div class="grid2"><div>{_gauge(a["dfa_index"]*100, 0, 60, label="DFA index %")}'
           f'<p class="mut">E = 3 &times; N<sub>min</sub> / T = 3 &times; {a["n_min"]} / {a["assembly_time_s"]:.0f} s = '
           f'<b>{a["dfa_index"]*100:.1f} %</b>. Joints: {E(joints)}. {a["fasteners"]} fasteners.</p>'
           f'<h3>Assembly time by line item</h3>'
           + _bars([(f'{r["id"]} {r["name"]}', r["time_s"]) for r in sorted(a["parts"], key=lambda r: -r["time_s"])],
                   secs, color="#14b8a6")
           + f'</div><div><h3>Parts that are not theoretically necessary</h3><table><tr><th>ID</th><th>Part</th>'
             f'<th class="r">Qty</th><th class="r">Time</th></tr>{cand}</table>'
             f'<p class="mut">Boothroyd test: a part must stay separate only if it moves relative to the others, '
             f'needs a different material, or must come apart for assembly or service.</p></div></div>')
    body.append(sec("Design for assembly", dfa))
    # 6 should-cost
    ctxt = (f'Parts {money(a["parts_cost_usd"])} + assembly labour {money(a["labor_usd"])} = '
            f'<b>{money(a["should_cost_usd"])}</b>'
            + (f', {ctp} of the {money(a["price_usd"])} retail price' if a["price_usd"] else "") +
            f'. {a["pareto80_items"]} of {a["n_line_items"]} line items make 80 % of parts cost.')
    body.append(sec("Should-cost", f'<p>{ctxt}</p>' + _bars([(f'{r["id"]} {r["name"]}', r["cost_usd"]) for r in a["parts"]],
                                                            money, width=900, color="#f97316")
                    + '<p class="mut">Estimates from mass, indicative material prices, machine rates and amortised tooling '
                      '(or given quotes). Use for ranking and comparison, not for quoting.</p>'))
    # 7 design signals
    ds = "".join(f'<div class="card"><b>{E(d.get("title",""))}</b><div>{E(d.get("evidence",""))}</div>'
                 f'<div class="mut">{E(d.get("why",""))}</div></div>' for d in spec.get("design_signals") or [])
    body.append(sec("Design decisions worth copying", ds))
    # 8 repairability
    if a["repairability"] is not None:
        rp = "".join(f'<tr><td>{E(x["name"])}</td><td>{E(x["joint"].replace("_"," "))}</td><td class="r">{x["depth"]}</td>'
                     f'<td class="r">{x["score"]:.1f}</td></tr>' for x in a["repair_parts"])
        body.append(sec("Repairability", _gauge(a["repairability"], 0, 10, label="score / 10") +
                        f'<table><tr><th>Wear / failure part</th><th>Held by</th><th class="r">Parts removed first</th>'
                        f'<th class="r">Score</th></tr>{rp}</table>'))
    # 9 FMEA
    if a["fmea"]:
        fr = "".join(f'<tr><td><span class="tag {f["AP"]}">{f["AP"]}</span></td><td>{E(f.get("item",""))}</td>'
                     f'<td>{E(f.get("mode",""))}</td><td>{E(f.get("effect",""))}</td><td>{E(f.get("cause",""))}</td>'
                     f'<td class="r">{f["S"]}/{f["O"]}/{f["D"]}</td><td class="r"><b>{f["RPN"]}</b></td>'
                     f'<td>{E(f.get("action",""))}</td></tr>' for f in a["fmea"])
        body.append(sec("Failure modes", '<table><tr><th>AP</th><th>Item</th><th>Mode</th><th>Effect</th><th>Cause</th>'
                        f'<th class="r">S/O/D</th><th class="r">RPN</th><th>Action</th></tr>{fr}</table>'))
    # 10 benchmark
    b = spec.get("benchmark") or {}
    if b.get("dimensions") and b.get("products"):
        bt = "<table><tr><th>Product</th>" + "".join(f"<th>{E(d)}</th>" for d in b["dimensions"]) + "</tr>"
        for prd in b["products"]:
            bt += f'<tr><td><b>{E(prd.get("name",""))}</b></td>' + "".join(f"<td>{E(str(v))}</td>" for v in prd.get("values", [])) + "</tr>"
        body.append(sec("Benchmark", bt + "</table>"))
    # 11 opportunities
    op = spec.get("opportunities") or []
    if op:
        ot = ("<table><tr><th>Opportunity</th><th>Change</th><th>Impact</th><th>Effort</th><th class='r'>Saving / unit (negative = adds cost)</th></tr>"
              + "".join(f'<tr><td><b>{E(o.get("title",""))}</b></td><td>{E(o.get("change",""))}</td><td>{E(o.get("impact",""))}</td>'
                        f'<td>{E(str(o.get("effort","")))}</td><td class="r">{money(_num(o.get("savings_usd")))}</td></tr>'
                        for o in op) + "</table>")
        sav = sum(max(0.0, _num(o.get("savings_usd"))) for o in op)
        add = sum(min(0.0, _num(o.get("savings_usd"))) for o in op)
        note = (f'Cost-down moves together: {money(sav)} per unit ({100*sav/max(a["should_cost_usd"],1e-9):.1f} % of should-cost; '
                f'savings can overlap).')
        if add < 0:
            note += f' Upgrades that add cost: {money(-add)} per unit.'
        body.append(sec("Redesign opportunities", ot + f'<p class="mut">{note}</p>'))
    if spec.get("verdict"):
        body.append(sec("Engineering verdict", f'<p>{E(spec["verdict"])}</p>', cls="verdict"))
    if a["assumptions"]:
        body.append(sec("Assumptions applied by the calculator", "<ul>" + "".join(f"<li>{E(x)}</li>" for x in a["assumptions"]) + "</ul>"))
    foot = ('<footer>Generated by the <b>mechanical-teardown</b> skill · '
            '<a href="https://github.com/BaratiLab/mechanical-engineering-skills">Mechanical Engineering Skills</a> · '
            'figures are engineering estimates from observation</footer>')
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Teardown: {E(p.get("name",""))}</title><style>{CSS}</style></head><body>{head}<div class="wrap">{kpis}'
            + "".join(body) + foot + "</div></body></html>")


# ----------------------------------------------------------------------------- CLI
def load(path):
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template")
    a1 = sub.add_parser("analyze"); a1.add_argument("spec"); a1.add_argument("--json", action="store_true")
    a2 = sub.add_parser("report"); a2.add_argument("spec"); a2.add_argument("-o", "--out", default="teardown_report.html")
    args = ap.parse_args(argv)
    if args.cmd == "template":
        print(json.dumps(template(), indent=2)); return 0
    spec = load(args.spec)
    a = analyze(spec)
    if args.cmd == "analyze":
        print(json.dumps(a, indent=2, default=str) if args.json else text_summary(a)); return 0
    with open(args.out, "w") as f:
        f.write(render_html(spec, a, os.path.dirname(os.path.abspath(args.spec))))
    print(text_summary(a)); print(f"\nreport -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
