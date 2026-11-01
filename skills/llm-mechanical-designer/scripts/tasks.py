"""Task presets from Table 1 of arXiv:2404.17525 (LLM Agent as a Mechanical Designer).

Load format [magnitude, angle_deg] with Fx = m cos a, Fy = m sin a (reference-code convention).
Mass = sum(L * area value). Units as in the paper (stress "Pa", length "m").
"""
AREA = {"0": 1.0, "1": 0.195, "2": 0.782, "3": 1.759, "4": 3.128, "5": 4.887,
        "6": 7.037, "7": 9.578, "8": 12.511, "9": 15.834, "10": 19.548}

_T1 = {"nodes": {"node_1": [0.0, 0.0], "node_2": [6.0, 0.0], "node_3": [2.0, 0.0]},
       "load": {"node_3": [-10.0, -45.0]},
       "supports": {"node_1": "pinned", "node_2": "roller"},
       "objective": "min_max_stress"}
_T2 = {"nodes": {"node_1": [0.0, 0.0], "node_2": [6.0, 0.0], "node_3": [2.0, 0.0]},
       "load": {"node_3": [-15.0, -30.0]},
       "supports": {"node_1": "pinned", "node_2": "roller", "node_3": "roller"},
       "objective": "min_swr"}

TASKS = {
    "t1v1": _T1 | {"constraints": {"max_stress": 15.0, "max_mass": 30.0}},
    "t1v2": _T1 | {"constraints": {"max_stress": 20.0, "max_mass": 30.0}},
    "t1v3": _T1 | {"constraints": {"max_stress": 30.0, "max_mass": 30.0}},
    "t2v1": _T2 | {"constraints": {"max_swr": 0.5, "max_mass": 30.0}},
    "t2v2": _T2 | {"constraints": {"max_swr": 0.75, "max_mass": 30.0}},
    "t2v3": _T2 | {"constraints": {"max_swr": 1.0, "max_mass": 30.0}},
}


def custom(path):
    """Load a user-defined task JSON with the same keys (nodes, load, supports, objective, constraints)."""
    import json
    t = json.load(open(path))
    t.setdefault("objective", "min_max_stress")
    return t
