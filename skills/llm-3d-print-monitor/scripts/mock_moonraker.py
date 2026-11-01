#!/usr/bin/env python3
"""A Moonraker look-alike for rehearsing the monitoring loop without a printer (tests + tutorial).

  python mock_moonraker.py --port 7125 [--fault underextrusion|stringing|none] [--layers 8] [--seed 0]

It simulates a Klipper printer paused at each layer of a two-letter part, with two webcams (top, front)
whose images are rendered from the *current* process state: under-extrusion shows as thin, broken
infill lines that heal as the effective flow approaches 100 %; stringing shows as hairs between the
letters that disappear once retraction is long enough. Supports the endpoints printer.py uses:
/printer/objects/query, /printer/gcode/script, /printer/print/resume, /server/webcams/list,
/webcam/<name>.jpg and /server/gcode_store. Commands it does not model are accepted and ignored.
"""
import argparse
import io
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class Printer:
    def __init__(self, fault="underextrusion", layers=8, seed=0):
        self.layers, self.layer, self.state = layers, 2, "paused"
        self.speed_factor, self.extrude_factor, self.z = 1.0, 1.0, 0.0
        self.hotend, self.bed, self.fan, self.pa = 210.0, 60.0, 1.0, 0.04
        self.retract_len, self.retract_speed = 0.8, 35.0
        self.clog = 0.82 if fault == "underextrusion" else 1.0      # hidden: partial clog -> 82 % actual flow
        self.stringy = fault == "stringing"
        self.rng = np.random.default_rng(seed)
        self.gstore = []
        self.lock = threading.Lock()

    # effective quantities the camera "sees"
    def flow(self):
        hot = 1 + 0.004 * (self.hotend - 210)                   # hotter -> a bit more melt throughput
        slow = 1 + 0.12 * (1 - min(self.speed_factor, 1.0))     # slower -> clog matters less
        return min(self.clog * self.extrude_factor * hot * slow, 1.3)

    def strings(self):
        if not self.stringy:
            return 0
        return int(max(0, 14 * (1.6 - self.retract_len) / 1.6 + 0.04 * (self.hotend - 210)))

    def status(self, objs):
        out = {}
        for o in objs:
            if o == "print_stats":
                out[o] = {"state": self.state, "filename": "ME_letters_monitored.gcode",
                          "info": {"current_layer": self.layer, "total_layer": self.layers}}
            elif o == "gcode_move":
                out[o] = {"speed_factor": self.speed_factor, "extrude_factor": self.extrude_factor, "speed": 60.0,
                          "homing_origin": [0, 0, self.z, 0], "absolute_coordinates": True, "absolute_extrude": False}
            elif o == "extruder":
                out[o] = {"temperature": self.hotend - 0.3, "target": self.hotend, "pressure_advance": self.pa,
                          "smooth_time": 0.04, "can_extrude": True}
            elif o == "heater_bed":
                out[o] = {"temperature": self.bed - 0.2, "target": self.bed}
            elif o == "fan":
                out[o] = {"speed": self.fan}
            elif o == "firmware_retraction":
                out[o] = {"retract_length": self.retract_len, "retract_speed": self.retract_speed,
                          "unretract_extra_length": 0.0, "unretract_speed": 25.0}
            elif o == "toolhead":
                out[o] = {"position": [200.0, 200.0, 0.2 * self.layer + 10, 0], "max_velocity": 300, "max_accel": 3000}
            else:
                out[o] = {}
        return out

    def gcode(self, script):
        for line in script.splitlines():
            c = line.split(";")[0].strip()
            if not c:
                continue
            p = dict((m[0].upper(), float(m[1])) for m in re.findall(r"([A-Za-z_]+)=?(-?\d*\.?\d+)", " ".join(c.split()[1:])))
            h = c.split()[0].upper()
            if h == "M220": self.speed_factor = p.get("S", 100) / 100
            elif h == "M221": self.extrude_factor = p.get("S", 100) / 100
            elif h in ("M104", "M109"): self.hotend = p.get("S", self.hotend)
            elif h in ("M140", "M190"): self.bed = p.get("S", self.bed)
            elif h == "M106": self.fan = p.get("S", 255) / 255
            elif h == "M107": self.fan = 0.0
            elif h == "SET_PRESSURE_ADVANCE": self.pa = p.get("ADVANCE", self.pa)
            elif h == "SET_RETRACTION":
                self.retract_len = p.get("RETRACT_LENGTH", self.retract_len)
                self.retract_speed = p.get("RETRACT_SPEED", self.retract_speed)
            elif h == "SET_GCODE_OFFSET": self.z += p.get("Z_ADJUST", 0.0)
            self.gstore.append({"message": c, "type": "command"})
        return "ok"

    def resume(self):
        if self.layer >= self.layers:
            self.state = "complete"
        else:
            self.layer += 1; self.state = "paused"

    # ---------------------------------------------------------- cameras
    def letters_mask(self, W=640, H=480):
        im = Image.new("L", (W, H), 0); d = ImageDraw.Draw(im)
        # block letters "M" and "E" from rectangles (font-independent)
        x0, y0, s = 140, 130, 22
        for r in [(0, 0, 2, 10), (8, 0, 10, 10), (2, 1, 4, 4), (4, 3, 6, 6), (6, 1, 8, 4),    # M
                  (14, 0, 16, 10), (16, 0, 22, 2), (16, 4, 20, 6), (16, 8, 22, 10)]:          # E
            d.rectangle([x0 + r[0] * s / 1.0 * 0.66, y0 + r[1] * s, x0 + r[2] * s * 0.66, y0 + r[3] * s], fill=255)
        return im

    def top(self):
        W, H = 640, 480
        bed = Image.new("RGB", (W, H), (32, 34, 38)); d = ImageDraw.Draw(bed)
        for x in range(0, W, 40):
            d.line([(x, 0), (x, H)], fill=(40, 42, 46))
        m = np.asarray(self.letters_mask(W, H)) > 0
        f = self.flow()
        lay = Image.new("L", (W, H), 0); dl = ImageDraw.Draw(lay)
        width = max(1, int(round(6 * min(f, 1.15))))
        gap_p = float(np.clip((0.97 - f) * 2.2, 0, 0.6))
        rng = np.random.default_rng(self.layer)
        ang = self.layer % 2
        for k in range(-H, W + H, 7):
            pts = [(k, 0), (k + H, H)] if ang else [(k + H, 0), (k, H)]
            # break the line into segments, dropping some when under-extruding
            n = 40
            for i in range(n):
                if rng.random() < gap_p:
                    continue
                a = (pts[0][0] + (pts[1][0] - pts[0][0]) * i / n, pts[0][1] + (pts[1][1] - pts[0][1]) * i / n)
                b = (pts[0][0] + (pts[1][0] - pts[0][0]) * (i + 1) / n, pts[0][1] + (pts[1][1] - pts[0][1]) * (i + 1) / n)
                dl.line([a, b], fill=255, width=width)
        infill = (np.asarray(lay) > 0) & m
        # perimeter
        edge = np.asarray(self.letters_mask(W, H).filter(__import__("PIL.ImageFilter").ImageFilter.FIND_EDGES)) > 0
        edge = edge & (rng.random(edge.shape) > gap_p * 0.8)
        mat = infill | edge
        arr = np.asarray(bed).copy()
        col = np.array([235, 120, 40]) * (0.85 + 0.15 * min(f, 1))
        arr[mat] = col.astype(np.uint8)
        im = Image.fromarray(arr); d = ImageDraw.Draw(im)
        for _ in range(self.strings()):  # hairs between the letters
            y = rng.uniform(140, 330)
            d.line([(282, y), (330, y + rng.uniform(-20, 20))], fill=(225, 115, 40), width=1)
        if f > 1.12:
            for _ in range(int((f - 1.1) * 120)):
                cx, cy = rng.uniform(150, 450), rng.uniform(135, 345)
                if m[int(cy), int(cx)]:
                    d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(250, 140, 50))
        d.text((8, 8), f"top  layer {self.layer}", fill=(200, 200, 200))
        return im

    def front(self):
        W, H = 640, 480
        im = Image.new("RGB", (W, H), (28, 30, 34)); d = ImageDraw.Draw(im)
        d.rectangle([0, 380, W, H], fill=(55, 58, 64))
        rng = np.random.default_rng(100 + self.layer)
        for L in range(1, self.layer + 1):
            y = 380 - L * 9
            f = self.flow() if L == self.layer else 0.95
            for x0, x1 in ((150, 280), (330, 450)):
                if f < 0.95:
                    xs = np.arange(x0, x1, 6)
                    for x in xs:
                        if rng.random() > (0.95 - f) * 2:
                            d.rectangle([x, y, x + 5, y + 8], fill=(220, 115, 40))
                else:
                    d.rectangle([x0, y, x1, y + 8], fill=(225, 118, 40))
        d.text((8, 8), f"front  layer {self.layer}", fill=(200, 200, 200))
        return im


def serve(P, port):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj, code=200):
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            with P.lock:
                if u.path == "/printer/objects/query":
                    objs = [k.split("=")[0] for k in u.query.split("&") if k]
                    return self._json({"result": {"status": P.status(objs), "eventtime": 0}})
                if u.path == "/server/webcams/list":
                    return self._json({"result": {"webcams": [{"name": "top", "snapshot_url": "/webcam/top.jpg"},
                                                              {"name": "front", "snapshot_url": "/webcam/front.jpg"}]}})
                if u.path.startswith("/webcam/"):
                    im = P.top() if "top" in u.path else P.front()
                    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90); b = buf.getvalue()
                    self.send_response(200); self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
                if u.path == "/server/gcode_store":
                    return self._json({"result": {"gcode_store": P.gstore[-50:]}})
            self._json({"error": "not found"}, 404)

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
            with P.lock:
                if u.path == "/printer/gcode/script":
                    return self._json({"result": P.gcode(body.get("script", ""))})
                if u.path == "/printer/print/resume":
                    P.resume(); return self._json({"result": "ok"})
            self._json({"error": "not found"}, 404)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    return srv


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=7125)
    ap.add_argument("--fault", choices=["underextrusion", "stringing", "none"], default="underextrusion")
    ap.add_argument("--layers", type=int, default=8); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    srv = serve(Printer(a.fault, a.layers, a.seed), a.port)
    print(f"mock Moonraker on http://127.0.0.1:{a.port}  (fault: {a.fault})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
