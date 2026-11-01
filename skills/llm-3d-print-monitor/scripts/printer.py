#!/usr/bin/env python3
"""Moonraker client + layer-by-layer supervisor for agent-monitored FDM printing (after LLM-3D Print).

The agent (you) is the vision model and the planner. This script is the hands and the referee:
it captures the layer, queries the printer, enforces the stage order of the paper's multi-agent loop,
safety-checks every G-code line, and keeps an audit log.

  printer.py --url http://printer.local status
  printer.py --url URL --session runs/job1 wait                 # block until the printer pauses at a layer
  printer.py --url URL --session runs/job1 snapshot             # save camera images + occupancy for this layer
  printer.py --session runs/job1 record detect  detect.json     # your image assessment (format: references/stages.md)
  printer.py --url URL --session runs/job1 query extruder gcode_move firmware_retraction   # information gathering
  printer.py --session runs/job1 record plan    plan.json       # your fix: [{"gcode": "...", "why": "..."}]
  printer.py --url URL --session runs/job1 apply  [--live]      # safety-check + send the plan (dry-run default)
  printer.py --url URL --session runs/job1 resume [--live]
  printer.py --session runs/job1 report                         # markdown log of every layer

Stage order per layer (refused otherwise): snapshot -> detect -> [query >= 1 if problems] -> plan -> apply -> resume.
A layer whose detect says no problems may go straight to resume.
Without --live nothing is sent to the printer except read-only queries; commands are logged as dry-run.
"""
import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import safety  # noqa: E402

STATE_OBJECTS = ["print_stats", "gcode_move", "extruder", "heater_bed", "fan", "firmware_retraction", "toolhead"]


# ------------------------------------------------------------------ Moonraker HTTP
class Moonraker:
    def __init__(self, url, timeout=15):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=self.timeout) as r:
            return json.loads(r.read())

    def _post(self, path, body=None):
        req = urllib.request.Request(self.url + path, data=json.dumps(body or {}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def query(self, objects):
        q = "&".join(urllib.parse.quote(o) for o in objects)
        return self._get(f"/printer/objects/query?{q}")["result"]["status"]

    def gcode(self, script):
        return self._post("/printer/gcode/script", {"script": script})

    def resume(self):
        return self._post("/printer/print/resume")

    def webcams(self):
        try:
            return self._get("/server/webcams/list")["result"]["webcams"]
        except Exception:
            return [{"name": "default", "snapshot_url": "/webcam/?action=snapshot"}]

    def snapshot(self, cam):
        u = cam["snapshot_url"]
        u = u if u.startswith("http") else self.url + u
        with urllib.request.urlopen(u, timeout=self.timeout) as r:
            return r.read()


def current_state(st):
    g, e = st.get("gcode_move", {}), st.get("extruder", {})
    ps = st.get("print_stats", {})
    return {"state": ps.get("state"), "layer": (ps.get("info") or {}).get("current_layer"),
            "total_layers": (ps.get("info") or {}).get("total_layer"), "filename": ps.get("filename"),
            "speed_factor": g.get("speed_factor"), "extrude_factor": g.get("extrude_factor"),
            "z_offset": (g.get("homing_origin") or [0, 0, 0, 0])[2],
            "hotend_temp": e.get("temperature"), "hotend_target": e.get("target"),
            "pressure_advance": e.get("pressure_advance"),
            "bed_temp": st.get("heater_bed", {}).get("temperature"), "bed_target": st.get("heater_bed", {}).get("target"),
            "fan": st.get("fan", {}).get("speed"),
            "retract_length": st.get("firmware_retraction", {}).get("retract_length"),
            "retract_speed": st.get("firmware_retraction", {}).get("retract_speed")}


# ------------------------------------------------------------------ session (supervisor state)
class Session:
    def __init__(self, path):
        self.path = path
        os.makedirs(path, exist_ok=True)
        self.f = os.path.join(path, "session.json")
        self.d = json.load(open(self.f)) if os.path.exists(self.f) else {"layers": {}, "start": None}

    def save(self):
        json.dump(self.d, open(self.f, "w"), indent=1)

    def layer(self, n=None):
        n = str(n if n is not None else self.d.get("current"))
        return self.d["layers"].setdefault(n, {"events": []})

    def log(self, stage, payload):
        L = self.layer()
        L["events"].append({"t": datetime.datetime.now().isoformat(timespec="seconds"), "stage": stage, **payload})
        self.save()

    def stages(self):
        return [e["stage"] for e in self.layer()["events"]]

    def last(self, stage):
        ev = [e for e in self.layer()["events"] if e["stage"] == stage]
        return ev[-1] if ev else None

    def require(self, *needed):
        have = self.stages()
        miss = [s for s in needed if s not in have]
        if miss:
            sys.exit(f"refused: layer {self.d.get('current')} is missing stage(s) {miss}; have {have}")


def problems_found(det):
    v = str(det.get("problems", det.get("Problems", ""))).lower()
    return not (v.startswith("no") or v in ("", "none", "false"))


# ------------------------------------------------------------------ commands
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("MOONRAKER_URL"))
    ap.add_argument("--session")
    ap.add_argument("--limits", help="JSON overriding safety.LIMITS")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    w = sub.add_parser("wait"); w.add_argument("--timeout", type=float, default=3600); w.add_argument("--poll", type=float, default=3)
    sub.add_parser("snapshot")
    q = sub.add_parser("query"); q.add_argument("objects", nargs="+")
    r = sub.add_parser("record"); r.add_argument("stage", choices=["detect", "plan", "note"]); r.add_argument("file")
    for name in ("apply", "resume"):
        s = sub.add_parser(name); s.add_argument("--live", action="store_true")
    c = sub.add_parser("check"); c.add_argument("gcode")
    sub.add_parser("report")
    a = ap.parse_args()
    limits = safety.load_limits(a.limits)
    mr = Moonraker(a.url) if a.url else None
    S = Session(a.session) if a.session else None
    need = lambda x, what: x or sys.exit(f"--{what} is required for this command")

    if a.cmd == "status":
        print(json.dumps(current_state(need(mr, "url").query(STATE_OBJECTS)), indent=1)); return

    if a.cmd == "check":  # safety check only, never sends
        st = current_state(mr.query(STATE_OBJECTS)) if mr else {}
        ok, why = safety.check(a.gcode, st, limits)
        print(json.dumps({"gcode": a.gcode, "allowed": ok, "reason": why})); sys.exit(0 if ok else 2)

    if a.cmd == "report":
        need(S, "session"); print(report(S)); return

    need(S, "session")
    if a.cmd == "wait":
        import time
        t0 = time.time()
        while time.time() - t0 < a.timeout:
            st = current_state(need(mr, "url").query(STATE_OBJECTS))
            if st["state"] in ("complete", "cancelled", "error"):
                print(json.dumps({"done": True, **st})); return
            if st["state"] == "paused":
                n = st["layer"] or (int(S.d.get("current") or 0) + 1)
                if str(n) != str(S.d.get("current")) or "resume" in S.stages():
                    S.d["current"] = n
                    if S.d["start"] is None:
                        S.d["start"] = {k: st[k] for k in ("hotend_target", "bed_target", "speed_factor", "extrude_factor")}
                    S.layer(n)["state_at_pause"] = st; S.save()
                print(json.dumps({"paused_at_layer": n, **st})); return
            time.sleep(a.poll)
        sys.exit("timeout waiting for pause")

    if a.cmd == "snapshot":
        import occupancy
        d = os.path.join(S.path, f"layer_{S.d.get('current')}"); os.makedirs(d, exist_ok=True)
        files = {}
        for cam in need(mr, "url").webcams():
            p = os.path.join(d, f"{cam['name']}.jpg")
            open(p, "wb").write(mr.snapshot(cam)); files[cam["name"]] = p
        occ = {k: occupancy.occupancy(v)["occupancy"] for k, v in files.items()}
        S.log("snapshot", {"images": files, "occupancy": occ})
        print(json.dumps({"layer": S.d.get("current"), "images": files, "occupancy": occ}, indent=1)); return

    if a.cmd == "query":
        S.require("detect")
        res = need(mr, "url").query(a.objects)
        S.log("query", {"objects": a.objects, "result": res})
        print(json.dumps(res, indent=1)); return

    if a.cmd == "record":
        if a.stage == "detect":
            S.require("snapshot")
        if a.stage == "plan":
            S.require("detect")
            det = S.last("detect")
            if problems_found(det) and "query" not in S.stages():
                sys.exit("refused: gather information (printer.py query …) before planning a fix")
        body = json.load(sys.stdin if a.file == "-" else open(a.file))
        if a.stage == "plan":
            if not isinstance(body, list) or not all("gcode" in x for x in body):
                sys.exit('plan must be a JSON list of {"gcode": ..., "why": ...}')
        S.log(a.stage, body if isinstance(body, dict) else {"items": body}); print("recorded", a.stage); return

    if a.cmd == "apply":
        S.require("detect", "plan")
        st = current_state(need(mr, "url").query(STATE_OBJECTS))
        st["hotend_target_start"] = (S.d.get("start") or {}).get("hotend_target")
        if st["state"] != "paused":
            sys.exit(f"refused: printer state is {st['state']}, apply only while paused at a layer")
        items = S.last("plan")["items"]
        verdicts = [safety.check(i["gcode"], st, limits) for i in items]
        atomic_ok = all(ok for ok, _ in verdicts)   # all-or-nothing: a partly blocked plan sends nothing
        results = []
        for item, (ok, why) in zip(items, verdicts):
            res = {"gcode": item["gcode"], "allowed": ok, "reason": why, "sent": False}
            if ok and a.live and atomic_ok:
                res["response"] = mr.gcode(item["gcode"]); res["sent"] = True
                st = current_state(mr.query(STATE_OBJECTS)); st["hotend_target_start"] = (S.d.get("start") or {}).get("hotend_target")
            results.append(res)
        S.log("apply", {"live": a.live, "results": results, "state_after": st})
        print(json.dumps({"live": a.live, "sent_any": any(r["sent"] for r in results), "results": results}, indent=1))
        if not atomic_ok:
            sys.exit("plan refused: fix or drop the blocked line(s) and record the plan again; nothing was sent")
        return

    if a.cmd == "resume":
        S.require("detect")
        if problems_found(S.last("detect")) and "apply" not in S.stages():
            sys.exit("refused: problems were reported but no plan was applied (record an empty plan [] to resume as-is)")
        if a.live:
            need(mr, "url").resume()
        S.log("resume", {"live": a.live}); print(json.dumps({"resumed": a.live, "layer": S.d.get("current")})); return


def report(S):
    out = ["# Print monitoring log", ""]
    for n, L in sorted(S.d["layers"].items(), key=lambda kv: int(kv[0])):
        out.append(f"## Layer {n}")
        for e in L["events"]:
            s = e["stage"]
            if s == "snapshot":
                out.append(f"- snapshot: occupancy {e['occupancy']}")
            elif s == "detect":
                out.append(f"- detect: {e.get('problems', e.get('Problems'))}; failures: {e.get('failures', e.get('Failure'))};"
                           f" rating {e.get('rating', e.get('Print_Rating'))}")
            elif s == "query":
                out.append(f"- query: {', '.join(e['objects'])}")
            elif s == "plan":
                out += [f"- plan: `{i['gcode']}` — {i.get('why', '')}" for i in e["items"]] or ["- plan: (no change)"]
            elif s == "apply":
                out += [f"- apply{' LIVE' if e['live'] else ' (dry-run)'}: `{r['gcode']}` → "
                        f"{'sent' if r['sent'] else ('ok, not sent' if r['allowed'] else 'BLOCKED: ' + r['reason'])}"
                        for r in e["results"]]
            elif s == "resume":
                out.append(f"- resume{' LIVE' if e['live'] else ' (dry-run)'}")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    main()
