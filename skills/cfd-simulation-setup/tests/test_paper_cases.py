#!/usr/bin/env python3
"""Regression tests: replay CFD Forge's recorded decisions (arXiv:2610.14104, Tables 3-6) and
planted faults through the validators, and check reference physics and log parsing.

  python tests/test_paper_cases.py
"""
import copy
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_case as B  # noqa: E402
import evidence as E  # noqa: E402
import theory as T  # noqa: E402
import validate as V  # noqa: E402

FAILS = []


def expect(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got!r}" + ("" if ok else f", want {want!r}"))
    if not ok:
        FAILS.append(name)


def close(name, got, want, rel):
    ok = abs(got - want) / abs(want) <= rel
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got:.5g} vs {want:.5g} (tol {rel:.1%})")
    if not ok:
        FAILS.append(name)


# ------------------------------------------------------------------ evidence fixtures
STEP_OK = {"family": "forward-step-2d", "request_criteria": ["transient_health", "compression_structure"],
           "checks": {"mesh_ok": True, "two_solution_directions": True, "recipe_hash_ok": True,
                      "initial_state_ok": True, "inflow_mach": 2.000006, "solver_completed": True,
                      "no_fatal_error": True, "fields_positive_finite": True, "courant_finite": True,
                      "wall_flux_rel": 0.0, "mass_closure_residual": 5.7e-11, "front_measurable": True,
                      "p_rise_across_front": 5.18, "rho_rise_across_front": 2.9, "T_rise_across_front": 1.81,
                      "horizon_reached": True},
           "measurements": {"front_x": 0.113},
           "state": {"t": 4.0, "end_time": 4.0, "iteration": 1, "refinements": 0, "max_co": 0.2}}

NOZ_T1 = {"family": "cd-nozzle", "request_criteria": ["single_mesh_acceptance"],
          "checks": {"mesh_ok": True, "solver_completed": True, "no_fatal_error": True,
                     "fields_positive_finite": True, "inlet_total_conditions_rel_err": 0.001,
                     "throat_mach": 1.029, "outlet_min_normal_mach": 1.46,
                     "stagnation_enthalpy_rel_err": 0.001, "horizon_reached": True,
                     "steady_mass_mismatch": 0.0135, "transient_continuity": 5e-5,
                     "monitor_drift": 0.020, "field_change": 0.012,
                     "exit_mach_vs_q1d": 0.006, "exit_p_vs_q1d": 0.018, "mdot_vs_q1d": 0.011},
          "measurements": {"exit_mach": 1.513, "exit_mach_theory": 1.504},
          "state": {"t": 1e-3, "end_time": 6e-3, "iteration": 1, "refinements": 0, "max_co": 0.4}}


def verdict(ev):
    return V.evaluate(ev)["decision"]


def action(ev, a, **args):
    return V.validate_action(ev, {"action": a, "args": args})["ruling"]


def main():
    print("== Recorded decision points (paper Table 4) ==")
    noz1 = copy.deepcopy(NOZ_T1)
    expect("nozzle t=1ms verdict", verdict(noz1), "CORRECT_AND_RERUN")
    expect("nozzle t=1ms CONTINUE_RUN", action(noz1, "CONTINUE_RUN"), "APPROVED")
    expect("nozzle t=1ms premature ACCEPT", action(noz1, "ACCEPT"), "REFUSED")
    noz6 = copy.deepcopy(NOZ_T1)
    noz6["checks"] |= {"steady_mass_mismatch": 0.00055, "monitor_drift": 0.00081, "field_change": 0.00111}
    noz6["state"] |= {"t": 6e-3, "iteration": 2}
    expect("nozzle t=6ms verdict", V.evaluate(noz6)["status"], "PASS_SINGLE_MESH")
    expect("nozzle t=6ms ACCEPT", action(noz6, "ACCEPT"), "APPROVED")

    expect("step M2 t=4 verdict", V.evaluate(STEP_OK)["status"], "PASS_2D_FORWARD_STEP")
    expect("step M2 ACCEPT", action(STEP_OK, "ACCEPT"), "APPROVED")

    m3_t2 = copy.deepcopy(STEP_OK)
    m3_t2["checks"]["horizon_reached"] = False
    m3_t2["state"] |= {"t": 2.0, "end_time": 2.0}
    expect("step M3 t=2/4 verdict", verdict(m3_t2), "CORRECT_AND_RERUN")
    expect("step M3 CONTINUE_RUN after requested horizon", action(m3_t2, "CONTINUE_RUN"), "REFUSED")
    expect("step M3 EXTEND_END_TIME 2->4", action(m3_t2, "EXTEND_END_TIME", new_end_time=4.0), "APPROVED")
    expect("step M3 EXTEND beyond registered horizon", action(m3_t2, "EXTEND_END_TIME", new_end_time=6.0), "REFUSED")
    m3_t2["state"]["iteration"] = 4
    expect("step M3 EXTEND with budget exhausted", action(m3_t2, "EXTEND_END_TIME", new_end_time=4.0), "REFUSED")

    noflow = copy.deepcopy(STEP_OK)
    noflow["checks"] |= {"front_measurable": False, "p_rise_across_front": None,
                         "rho_rise_across_front": None, "T_rise_across_front": None}
    expect("step M3 h=0.3 no front verdict", verdict(noflow), "REJECT")
    expect("step M3 h=0.3 FAIL_SAFELY", action(noflow, "FAIL_SAFELY"), "APPROVED")

    sens = copy.deepcopy(STEP_OK)
    sens["request_criteria"].append("grid_sensitivity")
    expect("step sensitivity REFINE_MESH x2", action(sens, "REFINE_MESH"), "APPROVED")
    sens["state"]["refinements"] = 1
    expect("step sensitivity ACCEPT on fine grid", action(sens, "ACCEPT"), "REFUSED")
    expect("step sensitivity verdict", verdict(sens), "INCONCLUSIVE")

    print("\n== Cube development gate (paper Sec. 5.6) ==")
    cube = {"family": "cube-stationarity", "request_criteria": ["statistical_stationarity"],
            "checks": {"solver_completed": True, "no_fatal_error": True, "force_drift_rel": 0.00075,
                       "mean_lateral_rel": 0.01, "lateral_growth_ratio": 2.10},
            "state": {"iteration": 4}}
    expect("cube growth 2.10, no budget", V.evaluate(cube)["status"], "STILL_DEVELOPING")
    expect("cube verdict", verdict(cube), "REJECT")

    print("\n== Planted faults on the accepted Mach-2 step (none may be ACCEPTed) ==")
    faults = {"solver_completed": False, "no_fatal_error": False, "mesh_ok": False,
              "two_solution_directions": False, "recipe_hash_ok": False, "initial_state_ok": False,
              "inflow_mach": 0.8, "fields_positive_finite": False, "courant_finite": False,
              "wall_flux_rel": 1e-3, "mass_closure_residual": 1e-3, "front_measurable": False,
              "p_rise_across_front": 0.97, "rho_rise_across_front": float("nan"),
              "T_rise_across_front": None, "horizon_reached": False}
    accepted = 0
    for k, bad in faults.items():
        ev = copy.deepcopy(STEP_OK)
        ev["checks"][k] = bad
        d = verdict(ev)
        r = action(ev, "ACCEPT")
        accepted += d == "ACCEPT" or r == "APPROVED"
    expect(f"faults accepted out of {len(faults)}", accepted, 0)
    for k in ("mesh_ok", "two_solution_directions"):
        ev = copy.deepcopy(STEP_OK); ev["checks"][k] = False
        expect(f"REFINE_MESH on {k} fault", action(ev, "REFINE_MESH"), "REFUSED")
    ev = copy.deepcopy(STEP_OK); ev["checks"]["courant_finite"] = False
    expect("REDUCE_MAX_CO on non-finite Courant", action(ev, "REDUCE_MAX_CO"), "APPROVED")
    expect("action outside vocabulary", action(STEP_OK, "REFINE_THROAT"), "REFUSED")

    print("\n== Blind packet ==")
    pkt = V.blind(NOZ_T1)
    leaked = [k for k in pkt["checks"] if k.endswith("_vs_q1d")] + [k for k in pkt["measurements"] if "theory" in k]
    expect("reference keys stripped", leaked, [])

    print("\n== Reference physics (paper Table 6 / Sec. 5.3) ==")
    nz = T.nozzle(2e5, 300, 0.0326, 0.0354, pa=3e4)
    close("q1d exit Mach (paper 1.513 at +0.59%)", nz["exit_mach"], 1.513 / 1.0059, 0.002)
    close("q1d exit p (paper 53.14 kPa at -1.83%)", nz["exit_p"], 53140 / (1 - 0.0183), 0.002)
    close("q1d mdot (paper 1.541 at -1.11%)", nz["mdot"], 1.541 / (1 - 0.0111), 0.002)
    expect("nozzle regime", nz["regime"].split()[0], "underexpanded")
    for M, ref in ((2.0, 4.50), (3.0, 10.33), (3.5, 14.12)):
        close(f"normal shock p ratio M={M}", T.normal_shock(M)["p2_p1"], ref, 0.002)
    close("choke A*/A M=2", T.choke(2.0, 0.2)["Astar_over_A"], 0.822, 0.003)
    expect("choked M=2 h=0.2", T.choke(2.0, 0.2)["choked"], True)
    expect("not choked M=3 h=0.2", T.choke(3.0, 0.2)["choked"], False)
    expect("choked M=3 h=0.3", T.choke(3.0, 0.3)["choked"], True)

    print("\n== Evidence extraction ==")
    tmp = tempfile.mkdtemp()
    log = os.path.join(tmp, "log.foamRun")
    open(log, "w").write("sigFpe : Enabling floating point exception trapping (FOAM_SIGFPE).\n"
                         "Time = 0.001s\nCourant Number mean: 0.05 max: 0.19\n"
                         "time step continuity errors : sum local = 1e-12, global = 3e-13, cumulative = 1e-12\n"
                         "Time = 4s\nCourant Number mean: 0.06 max: 0.202\n\nEnd\n\n")
    lg = E.parse_log(log)
    expect("sigFpe start-up line is not fatal", lg["checks"]["no_fatal_error"], True)
    expect("completed run", lg["checks"]["solver_completed"], True)
    expect("final time", lg["measurements"]["t_final"], 4.0)
    open(log, "a").write("--> FOAM FATAL ERROR:\nMaximum number of iterations exceeded\n")
    expect("real fatal error caught", E.parse_log(log)["checks"]["no_fatal_error"], False)

    import numpy as np
    # storage-aware closure: unequal in/out flux balanced by stored mass; restart seam skipped
    t = np.linspace(0, 1, 201); dt = np.r_[t[1] - t[0], np.diff(t)]
    inflow = np.full_like(t, 2.0); outflow = 1.5 + 0.2 * t
    phi = outflow - inflow
    M = 10 + np.concatenate([[0], np.cumsum(-phi[1:] * dt[1:])])
    seg = (t > 0.5).astype(int)
    M[seg == 1] += 0.3  # restart jump: would be a huge residual if differenced
    csv = os.path.join(tmp, "mass.csv")
    np.savetxt(csv, np.c_[t, dt, M, phi, seg, inflow, outflow], delimiter=",",
               header="t,dt,M,Phi,segment,inflow,outflow", comments="")
    cl = E.closure(csv)
    expect("closure residual < 1e-6 with seam skipped", cl["checks"]["mass_closure_residual"] < 1e-6, True)

    # front detection: jump at x=0.113 vs a front pressed against the inlet
    x = np.linspace(0, 0.6, 481)
    for xf, want in ((0.113, True), (0.025, False)):
        p = np.where(x < xf, 1.0, 5.18); rho = np.where(x < xf, 1.0, 2.9); Tt = p / rho
        f = os.path.join(tmp, "line.csv")
        np.savetxt(f, np.c_[x, p, rho, Tt], delimiter=",", header="x,p,rho,T", comments="")
        fr = E.front(f, 0.6)
        expect(f"front measurable at x={xf}", fr["checks"]["front_measurable"], want)
    p = np.where(x < 0.113, 1.0, 5.18); rho = np.where(x < 0.113, 1.0, 2.9)
    np.savetxt(f, np.c_[x, p, rho, p / rho], delimiter=",", header="x,p,rho,T", comments="")
    close("p rise across detected front", E.front(f, 0.6)["checks"]["p_rise_across_front"], 5.18, 0.001)

    # growth ratio on a growing oscillation
    tt = np.linspace(60, 80, 4001)
    fz = 1e-3 * np.exp(0.037 * (tt - 60)) * np.sin(2 * np.pi * tt / 9)
    fx = np.full_like(tt, 0.706)
    dat = os.path.join(tmp, "forces.dat")
    np.savetxt(dat, np.c_[tt, fx, np.zeros_like(tt), fz], header="Time Fx Fy Fz")
    gr = E.growth(dat, 3, 20.0)
    expect("growing lateral force fails 1.25 gate", gr["checks"]["lateral_growth_ratio"] > 1.25, True)

    print("\n== Builders ==")
    sp = B.resolve("forward-step-2d", {"mach": 2.0, "step_height": 0.2, "step_x": 0.6})
    expect("provenance mach", sp["provenance"]["mach"], "stated_by_user")
    expect("provenance end_time", sp["provenance"]["end_time"], "inferred_from_family_defaults")
    expect("scope M2", V.scope_gate("forward-step-2d", sp["resolved"])["in_scope"], True)
    expect("scope M6 out", V.scope_gate("forward-step-2d", sp["resolved"] | {"mach": 6.0})["in_scope"], False)
    rec = B.build_forward_step(sp, os.path.join(tmp, "fs"), template=None)
    expect("forward step cells (paper 16,128)", rec["cells"], 16128)
    spn = B.resolve("cd-nozzle", {})
    recn = B.build_nozzle(spn, os.path.join(tmp, "noz"), template=None)
    expect("nozzle cells (paper 132x16 = 2,112)", recn["cells"], 2112)
    # every boundary face must point outward from its block
    bm = B.BlockMesh()
    bid = B.rect(bm, 0, 1, 0, 1, 0, 1, 1, 1)
    c = np.array([0.5, 0.5, 0.5]); bad = 0
    for f in range(6):
        P = np.array([bm.pts[i] for i in bm.face(bid, f)])
        n = np.cross(P[1] - P[0], P[2] - P[0])
        bad += np.dot(n, P.mean(0) - c) <= 0
    expect("canonical hex faces outward", int(bad), 0)

    print(f"\n{'ALL PASSED' if not FAILS else f'{len(FAILS)} FAILED: {FAILS}'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
