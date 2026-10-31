"""Registered flow-family contracts (after CFD Forge, arXiv:2610.14104).

A contract fixes, BEFORE any result exists:
  envelope   admissible request parameters (scope gate)
  defaults   values used for anything the request does not state
  checks     named acceptance checks with thresholds and a category
               hard        -> violation = REJECT (numerical failure, boundary anomaly, ...)
               development -> violation = CORRECT_AND_RERUN while a permitted correction
                              remains, REJECT once none does
               reference   -> comparison with theory/reference, checked by code AFTER diagnosis;
                              hidden from the diagnosis packet
  actions    the closed vocabulary of actions the agent may propose
  registered_request_criteria
             criteria a request may depend on (e.g. "grid_sensitivity"). A request that
             depends on an unregistered criterion can never be ACCEPTed -> INCONCLUSIVE.
  source     "paper" = threshold as published; "skill-default" = chosen for this skill,
             confirm before relying on it.

Thresholds are declared engineering tolerances. Never relax one to make a run pass:
add a new contract version instead and record why.
"""

LE, GE, LT, GT, RANGE, TRUE = "<=", ">=", "<", ">", "range", "is_true"

CONTRACTS = {
    # ------------------------------------------------------------------ nozzle
    "cd-nozzle": {
        "version": "1.0.0",
        "description": "Axisymmetric converging-diverging nozzle, inviscid compressible Euler, "
                       "perfect gas, 5 deg wedge, shockFluid (OpenFOAM Foundation v14). Steady target.",
        "solver": "foamRun -solver shockFluid",
        "envelope": {
            "r_inlet_m": (0.02, 0.2), "r_throat_m": (0.01, 0.15), "r_exit_m": (0.01, 0.2),
            "length_m": (0.1, 2.0), "p0_Pa": (5e4, 2e6), "T0_K": (200, 1500),
            "area_ratio_exit": (1.02, 3.0),
        },
        "envelope_source": "skill-default",
        "defaults": {
            "r_inlet_m": 0.0500, "r_throat_m": 0.0326, "r_exit_m": 0.0354, "length_m": 0.33,
            "p0_Pa": 2.0e5, "T0_K": 300.0, "p_ambient_Pa": 3.0e4, "gamma": 1.4, "R": 287.0,
            "axial_cells": [20, 40, 4, 48, 20], "radial_cells": 16, "wedge_deg": 5.0,
            "max_co": 0.4, "end_time_s": 6e-3, "stationarity_window_s": 2e-3,
            "flux": "Kurganov", "reconstruction": "Minmod", "ddt": "Euler",
        },
        "checks": {
            "mesh_ok":                {"cat": "hard", "op": TRUE, "source": "paper"},
            "solver_completed":       {"cat": "hard", "op": TRUE, "source": "paper"},
            "no_fatal_error":         {"cat": "hard", "op": TRUE, "source": "paper"},
            "fields_positive_finite": {"cat": "hard", "op": TRUE, "source": "paper"},
            "inlet_total_conditions_rel_err": {"cat": "hard", "op": LE, "thr": 0.01, "source": "skill-default"},
            "throat_mach":            {"cat": "hard", "op": RANGE, "thr": (0.9, 1.1), "source": "paper"},
            "outlet_min_normal_mach": {"cat": "hard", "op": GT, "thr": 1.05, "source": "paper"},
            "stagnation_enthalpy_rel_err": {"cat": "hard", "op": LE, "thr": 0.01, "source": "skill-default"},
            "horizon_reached":        {"cat": "development", "op": TRUE, "source": "paper"},
            "steady_mass_mismatch":   {"cat": "development", "op": LT, "thr": 1e-3, "source": "paper"},
            "transient_continuity":   {"cat": "development", "op": LT, "thr": 1e-4, "source": "paper"},
            "monitor_drift":          {"cat": "development", "op": LT, "thr": 2e-3, "source": "paper"},
            "field_change":           {"cat": "development", "op": LT, "thr": 2e-3, "source": "paper"},
            "exit_mach_vs_q1d":       {"cat": "reference", "op": LT, "thr": 0.03, "source": "paper"},
            "exit_p_vs_q1d":          {"cat": "reference", "op": LT, "thr": 0.05, "source": "paper"},
            "mdot_vs_q1d":            {"cat": "reference", "op": LT, "thr": 0.03, "source": "paper"},
        },
        "actions": ["ACCEPT", "CONTINUE_RUN", "REQUEST_DIAGNOSTIC", "REFINE_THROAT",
                    "REFINE_GRADIENT_REGION", "REPAIR_MESH", "RESTART_CLEAN", "REJECT_OUTSIDE_DOMAIN"],
        "refine_actions": ["REFINE_THROAT", "REFINE_GRADIENT_REGION"],
        "registered_request_criteria": ["single_mesh_acceptance", "q1d_consistency"],
        "pass_status": "PASS_SINGLE_MESH",
        "max_iterations": 4,
        "max_refinements": 1,
    },
    # ------------------------------------------------------------------ forward step
    "forward-step-2d": {
        "version": "1.1.0",
        "description": "2-D supersonic forward-facing step in a channel (L=3, H=1), inviscid Euler, "
                       "normalized gas (sound speed 1). Recipe = Foundation v14 tutorial "
                       "shockFluid/forwardStep, hash-checked. Transient: no stationarity criterion.",
        "solver": "foamRun -solver shockFluid",
        "envelope": {"mach": (1.5, 4.0), "step_height": (0.05, 0.35), "step_x": (0.3, 1.5),
                     "max_co": (0.05, 0.5), "end_time": (0.5, 10.0)},
        "envelope_source": "skill-default (paper tested Mach 2-3.5, h 0.1-0.3, x 0.6-1.0)",
        "defaults": {"length": 3.0, "height": 1.0, "step_height": 0.2, "step_x": 0.6,
                     "mach": 2.0, "dx": 0.0125, "pressure": 1.0, "temperature": 1.0,
                     "end_time": 4.0, "max_co": 0.2, "write_interval": 0.1},
        "checks": {
            "mesh_ok":                {"cat": "hard", "op": TRUE, "source": "paper"},
            "two_solution_directions": {"cat": "hard", "op": TRUE, "source": "paper"},
            "recipe_hash_ok":         {"cat": "hard", "op": TRUE, "source": "paper"},
            "initial_state_ok":       {"cat": "hard", "op": TRUE, "source": "paper"},
            "inflow_mach":            {"cat": "hard", "op": GT, "thr": 1.0, "source": "paper"},
            "solver_completed":       {"cat": "hard", "op": TRUE, "source": "paper"},
            "no_fatal_error":         {"cat": "hard", "op": TRUE, "source": "paper"},
            "fields_positive_finite": {"cat": "hard", "op": TRUE, "source": "paper"},
            "courant_finite":         {"cat": "hard", "op": TRUE, "source": "paper"},
            "wall_flux_rel":          {"cat": "hard", "op": LT, "thr": 1e-8, "source": "skill-default"},
            "mass_closure_residual":  {"cat": "hard", "op": LT, "thr": 1e-6, "source": "paper"},
            "front_measurable":       {"cat": "hard", "op": TRUE, "source": "paper"},
            "p_rise_across_front":    {"cat": "hard", "op": GT, "thr": 1.0, "source": "paper"},
            "rho_rise_across_front":  {"cat": "hard", "op": GT, "thr": 1.0, "source": "paper"},
            "T_rise_across_front":    {"cat": "hard", "op": GT, "thr": 1.0, "source": "paper"},
            "horizon_reached":        {"cat": "development", "op": TRUE, "source": "paper"},
        },
        "actions": ["ACCEPT", "CONTINUE_RUN", "EXTEND_END_TIME", "REDUCE_MAX_CO", "REFINE_MESH",
                    "REBUILD_FROM_VALIDATED_SPEC", "REQUEST_CLARIFICATION", "REJECT_UNSUPPORTED",
                    "FAIL_SAFELY"],
        "refine_actions": ["REFINE_MESH"],
        "registered_request_criteria": ["transient_health", "compression_structure"],
        # NOTE: no cross-grid tolerance is registered -> "grid_sensitivity" requests end INCONCLUSIVE
        "pass_status": "PASS_2D_FORWARD_STEP",
        "registered_horizon": 4.0,
        "max_iterations": 4,
        "max_refinements": 1,
    },
    # ------------------------------------------------------------------ cube stationarity gate
    "cube-stationarity": {
        "version": "1.0.0",
        "description": "Development gate for bluff-body URANS/LES force histories "
                       "(surface-mounted cube, Re_H = 40,000, k-omega SST, incompressibleFluid). "
                       "Applied over the final 20 convective time units.",
        "solver": "foamRun -solver incompressibleFluid",
        "envelope": {}, "defaults": {"window_tu": 20.0},
        "checks": {
            "solver_completed":       {"cat": "hard", "op": TRUE, "source": "paper"},
            "no_fatal_error":         {"cat": "hard", "op": TRUE, "source": "paper"},
            "force_drift_rel":        {"cat": "development", "op": LT, "thr": 0.02, "source": "paper"},
            "mean_lateral_rel":       {"cat": "development", "op": LT, "thr": 0.05, "source": "paper"},
            "lateral_growth_ratio":   {"cat": "development", "op": LE, "thr": 1.25, "source": "paper"},
        },
        "actions": ["ACCEPT", "CONTINUE_RUN", "EXTEND_END_TIME", "REQUEST_DIAGNOSTIC", "FAIL_SAFELY"],
        "refine_actions": [],
        "registered_request_criteria": ["statistical_stationarity"],
        "pass_status": "PASS_STATIONARY",
        "max_iterations": 4,
        "max_refinements": 0,
        "note": "Registered retrospectively in the paper (after the data existed). Register yours before running.",
    },
    # ------------------------------------------------------------------ generic templates
    "generic-steady-incompressible": {
        "version": "0.1.0",
        "description": "Template for user-registered steady RANS cases (pipes, ducts, airfoils, "
                       "manifolds) with incompressibleFluid. ALL thresholds are skill defaults: "
                       "confirm or edit them with the user and save as a new family BEFORE running.",
        "solver": "foamRun -solver incompressibleFluid",
        "envelope": {}, "defaults": {"window_iters": 500},
        "checks": {
            "mesh_ok":                {"cat": "hard", "op": TRUE, "source": "skill-default"},
            "solver_completed":       {"cat": "hard", "op": TRUE, "source": "skill-default"},
            "no_fatal_error":         {"cat": "hard", "op": TRUE, "source": "skill-default"},
            "max_non_orthogonality":  {"cat": "hard", "op": LT, "thr": 70.0, "source": "skill-default"},
            "max_skewness":           {"cat": "hard", "op": LT, "thr": 4.0, "source": "skill-default"},
            "bc_audit_ok":            {"cat": "hard", "op": TRUE, "source": "skill-default"},
            "yplus_in_model_range":   {"cat": "hard", "op": TRUE, "source": "skill-default"},
            "final_residuals_max":    {"cat": "development", "op": LT, "thr": 1e-4, "source": "skill-default"},
            "steady_mass_mismatch":   {"cat": "development", "op": LT, "thr": 1e-3, "source": "skill-default"},
            "monitor_drift":          {"cat": "development", "op": LT, "thr": 5e-3, "source": "skill-default"},
            "grid_change_rel":        {"cat": "development", "op": LT, "thr": 0.02, "source": "skill-default",
                                       "criterion": "grid_sensitivity"},
        },
        "actions": ["ACCEPT", "CONTINUE_RUN", "REFINE_MESH", "REPAIR_MESH", "REDUCE_RELAXATION",
                    "REQUEST_DIAGNOSTIC", "REQUEST_CLARIFICATION", "FAIL_SAFELY"],
        "refine_actions": ["REFINE_MESH"],
        "registered_request_criteria": ["single_mesh_acceptance", "grid_sensitivity"],
        "pass_status": "PASS_GENERIC_STEADY",
        "max_iterations": 4,
        "max_refinements": 2,
    },
}

# Diagnosis labels the agent may use (paper Sec. 2.3 / Fig. 12)
DIAGNOSES = ["HEALTHY_COMPLETE", "UNCONVERGED", "INSUFFICIENT_RUN_TIME", "LOCAL_UNDERRESOLUTION",
             "NUMERICAL_FAILURE", "BOUNDARY_ANOMALY", "OUTSIDE_ENVELOPE", "INSUFFICIENT_EVIDENCE"]


def get(family):
    if family not in CONTRACTS:
        raise SystemExit(f"unknown family '{family}'. Registered: {sorted(CONTRACTS)}")
    return CONTRACTS[family]


if __name__ == "__main__":
    import json
    import sys
    fam = sys.argv[1] if len(sys.argv) > 1 else None
    if fam:
        print(json.dumps(get(fam), indent=2, default=list))
    else:
        for k, v in CONTRACTS.items():
            print(f"{k:32s} v{v['version']:7s} {v['description'][:90]}")
