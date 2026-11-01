"""Run: python tests/test_monitor.py   (starts the mock printer on a free port; ~10 s)"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SCR = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCR)
import mock_moonraker  # noqa: E402
import occupancy  # noqa: E402
import safety  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    assert cond, name
    ok += 1


# --- safety allowlist and bounds
st = {"extrude_factor": 1.0, "z_offset": 0.15, "hotend_target": 210.0, "hotend_target_start": 210.0, "bed_target": 60.0}
for g, want in [("M221 S110", True), ("M221 S112", False), ("M221 S120", False), ("M220 S75", True), ("M220 S30", False),
                ("M104 S220", True), ("M104 S240", False), ("G28", False), ("G1 X10 Y10", False), ("FIRMWARE_RESTART", False),
                ("SAVE_CONFIG", False), ("SET_GCODE_OFFSET Z_ADJUST=0.04 MOVE=1", True),
                ("SET_GCODE_OFFSET Z_ADJUST=0.05", True), ("SET_GCODE_OFFSET Z_ADJUST=-0.1", False),
                ("SET_GCODE_OFFSET Z=0.3", False), ("SET_RETRACTION RETRACT_LENGTH=7", False),
                ("SET_RETRACTION RETRACT_LENGTH=1.2 RETRACT_SPEED=40", True), ("SET_PRESSURE_ADVANCE ADVANCE=0.06", True),
                ("SET_VELOCITY_LIMIT VELOCITY=500", False), ("M106 S200", True), ("M140 S75", False), ("M112", False),
                ("FOO_BAR", False), ("M221 S105\nG28", False)]:
    check(f"safety {g!r} -> {want}", safety.check(g, st)[0] is want)
check("cumulative Z limit", safety.check("SET_GCODE_OFFSET Z_ADJUST=0.05 MOVE=1", dict(st, z_offset=0.18))[0] is False)

with tempfile.TemporaryDirectory() as d:
    # --- layer pause insertion
    src = os.path.join(d, "a.gcode")
    open(src, "w").write("G28\n;LAYER_CHANGE\n;Z:0.2\nG1 Z0.2\nG1 X1 E1\n;LAYER_CHANGE\n;Z:0.4\nG1 Z0.4\nG1 X2 E1\n"
                         ";LAYER_CHANGE\n;Z:0.6\nG1 Z0.6\nG1 X3 E1\n")
    dst = os.path.join(d, "b.gcode")
    r = json.loads(subprocess.check_output([sys.executable, os.path.join(SCR, "add_layer_pauses.py"), src, dst]))
    txt = open(dst).read()
    check("pauses inserted for layers 2 and 3", r["pauses"] == 2 and "LAYER_INSPECT LAYER=2" in txt and "LAYER_INSPECT LAYER=1" not in txt)
    open(src, "w").write("G1 Z0.2 F600\nG1 X1 E1\nG1 Z0.4\nG1 X2 E1\nG1 Z0.6\nG1 X3 E1\n")
    r = json.loads(subprocess.check_output([sys.executable, os.path.join(SCR, "add_layer_pauses.py"), src, dst, "--macro", "PAUSE"]))
    check("z-move fallback", r["detected_by"] == "z-moves" and r["pauses"] == 2)

    # --- mock printer + supervisor loop
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = mock_moonraker.serve(mock_moonraker.Printer("underextrusion", 6), port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, MOONRAKER_URL=f"http://127.0.0.1:{port}")
    sess = os.path.join(d, "run")

    def P(*args, inp=None):
        return subprocess.run([sys.executable, os.path.join(SCR, "printer.py"), "--session", sess, *args],
                              env=env, capture_output=True, text=True, input=inp)

    check("wait finds pause at layer 2", '"paused_at_layer": 2' in P("wait").stdout)
    check("detect refused before snapshot", P("record", "detect", "-", inp="{}").returncode != 0)
    snap = json.loads(P("snapshot").stdout)
    occ0 = snap["occupancy"]["top"]
    det = json.dumps({"problems": "Problems found", "failures": ["under-extrusion"], "rating": 4})
    check("record detect", P("record", "detect", "-", inp=det).returncode == 0)
    plan = json.dumps([{"gcode": "M221 S110", "why": "t"}, {"gcode": "M220 S80", "why": "t"}])
    check("plan refused before any query", P("record", "plan", "-", inp=plan).returncode != 0)
    check("query", P("query", "extruder", "gcode_move").returncode == 0)
    check("resume refused with unaddressed problems", P("resume").returncode != 0)
    bad = json.dumps([{"gcode": "M221 S110", "why": "t"}, {"gcode": "G28", "why": "t"}])
    P("record", "plan", "-", inp=bad)
    r = P("apply", "--live")
    check("partly blocked plan sends nothing", r.returncode != 0 and '"sent": true' not in r.stdout)
    P("record", "plan", "-", inp=plan)
    check("dry-run apply sends nothing", '"sent": true' not in P("apply").stdout)
    check("live apply sends", P("apply", "--live").stdout.count('"sent": true') == 2)
    check("resume", P("resume", "--live").returncode == 0)
    P("wait"); P("snapshot")
    P("record", "detect", "-", inp=det); P("query", "extruder")
    P("record", "plan", "-", inp=json.dumps([{"gcode": "M221 S115", "why": "t"}, {"gcode": "M104 S220", "why": "t"}]))
    P("apply", "--live"); P("resume", "--live"); P("wait")
    occ2 = json.loads(P("snapshot").stdout)["occupancy"]["top"]
    check(f"fix raises occupancy ({occ0:.3f} -> {occ2:.3f})", occ2 > occ0 + 0.03)
    P("record", "detect", "-", inp=json.dumps({"problems": "No problems found", "rating": 9}))
    check("no-problem layer resumes without a plan", P("resume", "--live").returncode == 0)
    rep = P("report").stdout
    check("report lists all layers", all(f"## Layer {n}" in rep for n in (2, 3, 4)))
    srv.shutdown()

    # --- occupancy on a synthetic image
    from PIL import Image, ImageDraw
    im = Image.new("L", (200, 100), 20); ImageDraw.Draw(im).rectangle([50, 25, 149, 74], fill=230)
    p = os.path.join(d, "o.png"); im.save(p)
    check("occupancy of a 25% rectangle", abs(occupancy.occupancy(p)["occupancy"] - 0.25) < 0.03)
print(f"\n{ok} checks passed")
