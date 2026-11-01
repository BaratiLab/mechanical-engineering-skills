"""Safety gate for G-code the agent wants to send to a running printer.

Only a short allowlist of *process-parameter* commands is accepted, each with absolute bounds and,
for ratcheting parameters, a per-step limit. Motion, homing, firmware, config and anything
unparseable are rejected. LLM-3D Print excluded shutdown/restart/firmware commands; this goes further,
because in the paper's own logs the agent drifted speed to 30 %, retraction to 7 mm and stacked Z offsets
layer after layer. Bounds live in LIMITS and can be overridden with a JSON file (--limits).
"""
import json
import re

LIMITS = {
    "speed_factor_pct": [50, 150],         # M220 S
    "flow_pct": [85, 115],                 # M221 S
    "flow_step_pct": 10,
    "fan": [0, 255],                       # M106 S
    "hotend_C": [170, 290],                # M104/M109 S  (also +-15 C from the start of the session)
    "hotend_step_C": 15,
    "bed_C": [0, 110],                     # M140/M190 S
    "bed_step_C": 10,
    "pressure_advance": [0.0, 0.2],        # SET_PRESSURE_ADVANCE ADVANCE=
    "retract_length_mm": [0.0, 6.0],       # SET_RETRACTION RETRACT_LENGTH=
    "retract_speed_mm_s": [10, 70],
    "z_adjust_step_mm": 0.05,              # SET_GCODE_OFFSET Z_ADJUST= per command
    "z_offset_total_mm": 0.20,             # |cumulative homing_origin z|
    "accel_mm_s2": [300, 6000],            # M204 / SET_VELOCITY_LIMIT ACCEL=
}

BLOCK = re.compile(r"^(G28|G29|G[0-3]\b|G9[0-2]|M112|M500|M502|M84|M18|FIRMWARE_RESTART|RESTART|SAVE_CONFIG|"
                   r"SHUTDOWN|CANCEL_PRINT|SDCARD|BED_MESH|PROBE|Z_TILT|QUAD_GANTRY|FORCE_MOVE|SET_KINEMATIC|"
                   r"SET_STEPPER|SET_HEATER_TEMPERATURE|TURN_OFF|SET_PIN)", re.I)


def _kv(cmd):
    out = {}
    for tok in cmd.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
        else:
            k, v = tok[0], tok[1:]
        try:
            out[k.upper()] = float(v)
        except ValueError:
            out[k.upper()] = v
    return out


def check(cmd, state, limits=None):
    """Return (ok, reason). `state` is the printer's current values (see printer.current_state)."""
    L = dict(LIMITS, **(limits or {}))
    c = cmd.strip().split(";")[0].strip()
    if not c:
        return False, "empty command"
    if "\n" in c or len(c.split()) > 6:
        return False, "one simple command per call"
    if BLOCK.match(c):
        return False, f"blocked command class: {c.split()[0]}"
    head, p = c.split()[0].upper(), _kv(c)

    def rng(v, key, what):
        lo, hi = L[key]
        if not isinstance(v, float) or not (lo <= v <= hi):
            return False, f"{what}={v} outside [{lo}, {hi}]"
        return True, "ok"

    if head == "M220":
        return rng(p.get("S"), "speed_factor_pct", "speed factor %")
    if head == "M221":
        ok, r = rng(p.get("S"), "flow_pct", "flow %")
        cur = state.get("extrude_factor", 1.0) * 100
        if ok and abs(p["S"] - cur) > L["flow_step_pct"] + 1e-9:
            return False, f"flow change {cur:.0f}% -> {p['S']:.0f}% exceeds step {L['flow_step_pct']}%"
        return ok, r
    if head in ("M106",):
        return rng(p.get("S", 255.0), "fan", "fan PWM")
    if head == "M107":
        return True, "ok"
    if head in ("M104", "M109"):
        ok, r = rng(p.get("S"), "hotend_C", "hotend C")
        ref = state.get("hotend_target_start") or state.get("hotend_target")
        if ok and ref and abs(p["S"] - ref) > L["hotend_step_C"]:
            return False, f"hotend {p['S']:.0f} C is more than {L['hotend_step_C']} C from session start {ref:.0f} C"
        return ok, r
    if head in ("M140", "M190"):
        ok, r = rng(p.get("S"), "bed_C", "bed C")
        ref = state.get("bed_target")
        if ok and ref is not None and abs(p["S"] - ref) > L["bed_step_C"]:
            return False, f"bed change exceeds {L['bed_step_C']} C"
        return ok, r
    if head == "SET_PRESSURE_ADVANCE":
        if set(p) - {"ADVANCE", "SMOOTH_TIME", "EXTRUDER"}:
            return False, "unexpected SET_PRESSURE_ADVANCE parameter"
        return rng(p.get("ADVANCE", 0.0), "pressure_advance", "pressure advance") if "ADVANCE" in p else (True, "ok")
    if head == "SET_RETRACTION":
        for k, key in (("RETRACT_LENGTH", "retract_length_mm"), ("UNRETRACT_EXTRA_LENGTH", "retract_length_mm"),
                       ("RETRACT_SPEED", "retract_speed_mm_s"), ("UNRETRACT_SPEED", "retract_speed_mm_s")):
            if k in p:
                ok, r = rng(p[k], key, k)
                if not ok:
                    return ok, r
        return (True, "ok") if p else (False, "SET_RETRACTION with no parameters")
    if head == "SET_GCODE_OFFSET":
        if set(p) - {"Z_ADJUST", "MOVE", "MOVE_SPEED"}:
            return False, "only SET_GCODE_OFFSET Z_ADJUST=… [MOVE=1] is allowed"
        dz = p.get("Z_ADJUST")
        if not isinstance(dz, float) or abs(dz) > L["z_adjust_step_mm"]:
            return False, f"Z_ADJUST must be within ±{L['z_adjust_step_mm']} mm"
        tot = state.get("z_offset", 0.0) + dz
        if abs(tot) > L["z_offset_total_mm"]:
            return False, f"cumulative Z offset {tot:+.3f} mm would exceed ±{L['z_offset_total_mm']} mm"
        return True, "ok"
    if head == "M204":
        for k in ("S", "P", "T"):
            if k in p:
                ok, r = rng(p[k], "accel_mm_s2", f"accel {k}")
                if not ok:
                    return ok, r
        return True, "ok"
    if head == "SET_VELOCITY_LIMIT":
        if set(p) - {"ACCEL", "MINIMUM_CRUISE_RATIO", "ACCEL_TO_DECEL", "SQUARE_CORNER_VELOCITY"}:
            return False, "VELOCITY= changes are not allowed mid-print; use M220"
        return rng(p["ACCEL"], "accel_mm_s2", "ACCEL") if "ACCEL" in p else (True, "ok")
    return False, f"{head} is not on the allowlist (see references/safety.md)"


def load_limits(path):
    return json.load(open(path)) if path else None
