#!/usr/bin/env python3
"""Deterministic gates for agentic CFD (after CFD Forge, arXiv:2610.14104).

The agent PROPOSES; this script DECIDES. Its verdict is binding.

  scope    python validate.py scope   --family forward-step-2d --spec spec.json
  verdict  python validate.py verdict --evidence evidence.json
  action   python validate.py action  --evidence evidence.json --proposal proposal.json
  blind    python validate.py blind   --evidence evidence.json --out packet.json

evidence.json:
  {"family": "...",
   "request_criteria": ["transient_health"],          # what the request depends on
   "checks": {"mesh_ok": true, "throat_mach": 1.03, ...},
   "measurements": {...},                              # free-form numbers for the report
   "state": {"t": 4.0, "end_time": 4.0, "iteration": 1, "refinements": 0, "max_co": 0.2}}
proposal.json:
  {"diagnosis": "HEALTHY_COMPLETE", "action": "ACCEPT", "args": {"new_end_time": 4.0},
   "evidence_cited": [...], "competing_hypotheses": [...], "confidence": "high"}

Decisions: ACCEPT | CORRECT_AND_RERUN | REJECT | INCONCLUSIVE.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contracts as C  # noqa: E402

SAFE_ACTIONS = {"FAIL_SAFELY", "REJECT_UNSUPPORTED", "REJECT_OUTSIDE_DOMAIN",
                "REQUEST_CLARIFICATION", "REQUEST_DIAGNOSTIC"}
REFERENCE_HINTS = ("theory", "q1d", "reference", "analytic", "_vs_", "exact", "benchmark")


# ----------------------------------------------------------------- primitives
def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def eval_check(spec, value):
    if value is None:
        return "MISSING"
    op = spec["op"]
    if op == C.TRUE:
        return "PASS" if value is True else "FAIL"
    if not _finite(value):
        return "FAIL"
    thr = spec["thr"]
    ok = {"<": value < thr if op == "<" else None,
          "<=": value <= thr if op == "<=" else None,
          ">": value > thr if op == ">" else None,
          ">=": value >= thr if op == ">=" else None}.get(op)
    if op == C.RANGE:
        ok = thr[0] < value < thr[1]
    return "PASS" if ok else "FAIL"


def scope_gate(family, spec):
    c = C.get(family)
    out, ok = [], True
    for k, (lo, hi) in c["envelope"].items():
        v = spec.get(k)
        if k == "area_ratio_exit" and v is None and "r_exit_m" in spec and "r_throat_m" in spec:
            v = (spec["r_exit_m"] / spec["r_throat_m"]) ** 2
        if v is None:
            out.append({"param": k, "value": None, "range": [lo, hi], "status": "MISSING"})
            ok = False
            continue
        good = lo <= v <= hi
        ok &= good
        out.append({"param": k, "value": v, "range": [lo, hi], "status": "PASS" if good else "FAIL"})
    if spec.get("requests_unsupported_physics"):
        ok = False
        out.append({"param": "physics", "status": "FAIL", "note": "request needs physics outside the family"})
    return {"family": family, "in_scope": ok, "checks": out,
            "decision": None if ok else "REJECT (outside family envelope)"}


def evaluate(ev):
    """Scientific validator: binding verdict from registered checks only."""
    fam = ev["family"]
    c = C.get(fam)
    st = ev.get("state", {})
    req = set(ev.get("request_criteria", []))
    unregistered = sorted(req - set(c["registered_request_criteria"]))
    results = {}
    for name, spec in c["checks"].items():
        if "criterion" in spec and spec["criterion"] not in req:
            continue  # only evaluated when the request depends on it
        results[name] = {"status": eval_check(spec, ev.get("checks", {}).get(name)),
                         "value": ev.get("checks", {}).get(name), "cat": spec["cat"],
                         "threshold": spec.get("thr"), "op": spec["op"]}
    by = lambda cat, s: [k for k, r in results.items() if r["cat"] == cat and r["status"] == s]
    hard_fail, hard_miss = by("hard", "FAIL"), by("hard", "MISSING")
    dev_fail, dev_miss = by("development", "FAIL"), by("development", "MISSING")
    ref_fail, ref_miss = by("reference", "FAIL"), by("reference", "MISSING")
    budget_left = st.get("iteration", 1) < c["max_iterations"]
    reasons = []
    if hard_fail:
        decision, status = "REJECT", "FAIL"
        reasons.append(f"hard checks failed: {hard_fail}")
    elif unregistered:
        decision, status = "INCONCLUSIVE", "UNREGISTERED_CRITERION"
        reasons.append(f"request depends on criteria with no registered tolerance: {unregistered}")
    elif hard_miss or dev_miss:
        decision, status = "INCONCLUSIVE", "INSUFFICIENT_EVIDENCE"
        reasons.append(f"evidence missing for: {hard_miss + dev_miss}")
    elif dev_fail:
        if budget_left:
            decision, status = "CORRECT_AND_RERUN", "FAIL" if fam == "cd-nozzle" else "INCOMPLETE"
            reasons.append(f"healthy but incomplete: {dev_fail}; a permitted correction remains")
        else:
            decision, status = "REJECT", "STILL_DEVELOPING"
            reasons.append(f"development checks still failing with no budget left: {dev_fail}")
    elif ref_fail:
        decision, status = "REJECT", "FAIL"
        reasons.append(f"reference comparison outside registered tolerance: {ref_fail}")
    elif ref_miss:
        decision, status = "INCONCLUSIVE", "INSUFFICIENT_EVIDENCE"
        reasons.append(f"reference comparison not computed: {ref_miss}")
    else:
        decision, status = "ACCEPT", c["pass_status"]
        reasons.append("every registered check passes and every request criterion is registered")
    n_pass = sum(r["status"] == "PASS" for r in results.values())
    return {"family": fam, "contract_version": c["version"], "decision": decision, "status": status,
            "checks_passed": f"{n_pass}/{len(results)}", "reasons": reasons, "results": results,
            "note": "Acceptance is relative to this contract and this evidence; it does not certify "
                    "that all modelling or discretization uncertainty is removed."}


def validate_action(ev, prop):
    """Action validator: rules on the agent's PROPOSAL, not on the result."""
    c = C.get(ev["family"])
    st = ev.get("state", {})
    a = prop.get("action")
    args = prop.get("args", {}) or {}
    verdict = evaluate(ev)
    res = verdict["results"]
    hard_ok = not any(r["cat"] == "hard" and r["status"] != "PASS" for r in res.values())
    failing = [k for k, r in res.items() if r["status"] == "FAIL"]

    def out(ok, why):
        return {"action": a, "ruling": "APPROVED" if ok else "REFUSED", "reason": why,
                "scientific_decision": verdict["decision"], "scientific_status": verdict["status"],
                "terminal_if_refused": "STOPPED_ACTION_REFUSED -> INCONCLUSIVE" if not ok and a == "ACCEPT" else None}

    if a not in c["actions"]:
        return out(False, f"'{a}' is not in the {ev['family']} vocabulary {c['actions']}")
    if a in SAFE_ACTIONS:
        return out(True, "safe stop / information request is always permitted")
    if a == "ACCEPT":
        if verdict["decision"] == "ACCEPT":
            return out(True, "consistent with the registered checks; scientific validator returns ACCEPT")
        return out(False, f"scientific validator does not return ACCEPT: {verdict['reasons']}")
    if st.get("iteration", 1) >= c["max_iterations"]:
        return out(False, f"iteration budget exhausted ({c['max_iterations']})")
    if a == "CONTINUE_RUN":
        if not hard_ok:
            return out(False, f"continuation only for a healthy evolving solution; failing hard checks: {failing}")
        if "EXTEND_END_TIME" in c["actions"] and st.get("t", 0) >= st.get("end_time", math.inf) - 1e-12:
            return out(False, "requested horizon already reached; more physical time requires EXTEND_END_TIME")
        if verdict["decision"] == "ACCEPT":
            return out(False, "nothing to continue: all checks pass")
        return out(True, "permitted for a healthy evolving solution")
    if a == "EXTEND_END_TIME":
        new = args.get("new_end_time")
        hor = c.get("registered_horizon")
        if not hard_ok:
            return out(False, f"failing hard checks: {failing}")
        if new is None or new <= st.get("end_time", 0):
            return out(False, "new_end_time must exceed the current end_time")
        if hor is not None and new > hor + 1e-12:
            return out(False, f"bounded change: new_end_time may not exceed registered horizon {hor}")
        return out(True, f"bounded extension {st.get('end_time')} -> {new}")
    if a in c.get("refine_actions", []):
        if not hard_ok:
            return out(False, f"refinement is refused unless the current solution is healthy; failing: {failing}")
        if st.get("refinements", 0) >= c["max_refinements"]:
            return out(False, f"refinement budget ({c['max_refinements']}) used")
        return out(True, "registered bounded refinement (linear factor 2, fresh solve)")
    if a == "REDUCE_MAX_CO":
        if st.get("max_co", 1) <= 0.05:
            return out(False, "maxCo already at the family floor 0.05")
        if res.get("courant_finite", {}).get("status") == "FAIL" or "NUMERICAL_FAILURE" in str(prop.get("diagnosis")):
            return out(True, "Courant-related instability evidence")
        return out(False, "no Courant-related evidence for reducing maxCo")
    if a == "REBUILD_FROM_VALIDATED_SPEC":
        cfg = [k for k in ("recipe_hash_ok", "initial_state_ok", "mesh_ok") if res.get(k, {}).get("status") == "FAIL"]
        return out(bool(cfg), f"configuration checks failing: {cfg}" if cfg else "configuration checks all pass")
    if a == "REPAIR_MESH":
        mesh = [k for k in failing if "mesh" in k or "orthog" in k or "skew" in k]
        return out(bool(mesh), f"mesh evidence: {mesh}" if mesh else "no mesh failure in evidence")
    if a in ("RESTART_CLEAN", "REDUCE_RELAXATION"):
        return out(True, "permitted corrective action")
    return out(False, "no rule registered for this action")


def blind(ev):
    """Theory/reference-blind packet for the diagnosis step (paper Sec. 2.3)."""
    c = C.get(ev["family"])
    ref = {k for k, s in c["checks"].items() if s["cat"] == "reference"}
    pkt = json.loads(json.dumps(ev))
    pkt["checks"] = {k: v for k, v in pkt.get("checks", {}).items() if k not in ref}
    pkt["measurements"] = {k: v for k, v in pkt.get("measurements", {}).items()
                           if not any(h in k.lower() for h in REFERENCE_HINTS)}
    leaked = [k for k in list(pkt["checks"]) + list(pkt["measurements"])
              if k in ref or any(h in k.lower() for h in REFERENCE_HINTS)]
    if leaked:
        raise SystemExit(f"blind packet still contains reference keys: {leaked}")
    pkt["permitted_actions"] = c["actions"]
    pkt["permitted_diagnoses"] = C.DIAGNOSES
    pkt["iteration_budget"] = {"iteration": ev.get("state", {}).get("iteration", 1),
                               "max_iterations": c["max_iterations"]}
    pkt["hard_and_development_check_outcomes"] = {
        k: eval_check(s, ev.get("checks", {}).get(k)) for k, s in c["checks"].items() if s["cat"] != "reference"}
    return pkt


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scope"); s.add_argument("--family", required=True); s.add_argument("--spec", required=True)
    v = sub.add_parser("verdict"); v.add_argument("--evidence", required=True)
    a = sub.add_parser("action"); a.add_argument("--evidence", required=True); a.add_argument("--proposal", required=True)
    b = sub.add_parser("blind"); b.add_argument("--evidence", required=True); b.add_argument("--out")
    args = p.parse_args()
    load = lambda f: json.load(open(f))
    if args.cmd == "scope":
        spec = load(args.spec)
        res = scope_gate(args.family, spec.get("resolved", spec))
    elif args.cmd == "verdict":
        res = evaluate(load(args.evidence))
    elif args.cmd == "action":
        res = validate_action(load(args.evidence), load(args.proposal))
    else:
        res = blind(load(args.evidence))
        if args.out:
            json.dump(res, open(args.out, "w"), indent=2)
    print(json.dumps(res, indent=2, default=list))


if __name__ == "__main__":
    main()
