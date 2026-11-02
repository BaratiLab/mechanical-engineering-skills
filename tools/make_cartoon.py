#!/usr/bin/env python3
"""Cartoon use-case video: an engineer clears a morning of six tasks by asking Claude with
Mechanical Engineering Skills, by voice or text. Vector frames (SVG -> cairo), 1920x1080, 30 fps,
synthesized soundtrack. Run: python tools/make_cartoon.py [--out cartoon.mp4] [--still SCENE:FRAME ...]"""
import base64, io, math, os, subprocess, sys, wave
import numpy as np
import cairosvg
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import make_icons as M

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG = os.path.join(ROOT, "docs", "img")
W, H, FPS = 1920, 1080, 30
FONT = "Inter"
MONO = "DejaVu Sans Mono"

CASES = [  # mode, request, skills, steps, result label, visual, note on the task board, place
    ("voice", "Size the shaft and bearings for a 2 kW gearbox at 300 rpm.", ["machine-element-sizing"],
     ["Loaded machine-element-sizing", "Torque 63.7 N·m · fatigue check", "Hand calculation agrees"],
     "Shaft, bearings and safety factors", "shaft", "Shaft + bearings", "office"),
    ("text", "Make an L-bracket for M6 bolts, 3 mm wall, printable without supports.", ["cadsmith-text-to-cad", "agentscad-fdm-dfam"],
     ["CadQuery model built", "Kernel + three-view check", "Reoriented, teardrop holes added"],
     "Validated STEP + STL", "bracket", "Printable bracket", "office"),
    ("text", "Set up air flow over this heat sink at 2 m/s. Is it converged?", ["cfd-simulation-setup", "thermal-fluids-calc"],
     ["OpenFOAM case built and run", "Residuals and mass balance pass", "Agrees with correlation"],
     "Converged: accept", "cfd", "Heat-sink CFD", "office"),
    ("voice", "Design a lattice infill 2.5x stiffer vertically, as light as possible.", ["lattice-inverse-design"],
     ["Searched homogenized cells", "Re-checked at higher resolution", "Tiled STL exported"],
     "Lattice + stiffness matrix", "glu3d_search.png", "Lattice infill", "office"),
    ("voice", "Layer 140 looks stringy. What's wrong and what should I change?", ["llm-3d-print-monitor"],
     ["Read camera and printer state", "Diagnosis: under-extrusion", "Bounded fix, waiting for approval"],
     "Fix approved and applied", "printmonitor_layers.png", "Printer issue", "shop"),
    ("text", "Which layers of yesterday's build should go to CT first?", ["thermal-porosity"],
     ["Aligned the pyrometry frames", "Pore maps for every layer", "Ranked for inspection"],
     "CT priority list", "thermopore_layer.png", "CT priority", "office"),
]
CASE_F = 165   # 5.5 s per case
SCENES = [("morning", 240), ("ask", 150)] + [(f"case{i}", CASE_F) for i in range(len(CASES))] + [("lunch", 210), ("end", 270)]


def ease(t): t = min(max(t, 0), 1); return 1 - (1 - t) ** 3
def back(t, s=1.6):
    t = min(max(t, 0), 1) - 1; return t * t * ((s + 1) * t + s) + 1
def c01(t): return min(max(t, 0.0), 1.0)
def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt(x, y, s, size=30, weight=400, fill="#0f172a", anchor="start", family=FONT, opacity=1, italic=False):
    st = ' font-style="italic"' if italic else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" opacity="{opacity:.3f}"{st}>{esc(s)}</text>')


def wrap(s, n):
    out, cur = [], ""
    for w_ in s.split():
        if len(cur) + len(w_) + 1 > n and cur:
            out.append(cur); cur = w_
        else:
            cur = (cur + " " + w_).strip()
    return out + [cur]


def icon(skill, x, y, size, opacity=1):
    inner = M.tile(skill).split(">", 1)[1].rsplit("</svg>", 1)[0]
    uid = f"i{abs(hash((skill, int(x), int(y)))) % 10**8}"
    inner = inner.replace('id="g-', f'id="{uid}-').replace('url(#g-', f'url(#{uid}-')
    return f'<g transform="translate({x:.1f},{y:.1f}) scale({size/96:.4f})" opacity="{opacity:.3f}">{inner}</g>'


_img_cache = {}
def image(name, x, y, w, h, opacity=1):
    key = (name, w, h)
    if key not in _img_cache:
        p = Image.open(os.path.join(IMG, name)).convert("RGB")
        g = np.asarray(p.convert("L")); ys, xs = np.where(g < 245)
        if len(xs):
            p = p.crop((max(xs.min() - 10, 0), max(ys.min() - 10, 0), min(xs.max() + 10, p.width), min(ys.max() + 10, p.height)))
        s = min(w / p.width, h / p.height)
        p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
        b = io.BytesIO(); p.save(b, "JPEG", quality=90)
        _img_cache[key] = (p.width, p.height, base64.b64encode(b.getvalue()).decode())
    iw, ih, data = _img_cache[key]
    return (f'<image x="{x + (w - iw) / 2:.1f}" y="{y + (h - ih) / 2:.1f}" width="{iw}" height="{ih}" opacity="{opacity:.3f}" '
            f'href="data:image/jpeg;base64,{data}" xlink:href="data:image/jpeg;base64,{data}"/>')


# ------------------------------------------------------------------------------------------------
# characters and props
def engineer(cx, cy, s=1.0, mood="neutral", talk=0.0, blink=False, hat=False, typing=0.0, wave_arm=0.0, coffee=False):
    """Cartoon engineer; (cx, cy) is the centre of the head. mood: neutral|stressed|happy."""
    g = [f'<g transform="translate({cx:.1f},{cy:.1f}) scale({s:.3f})">']
    # body
    g.append('<path d="M-150,330 C-150,190 -85,140 0,140 C85,140 150,190 150,330 Z" fill="#1d4ed8"/>')
    g.append('<path d="M-30,140 L0,200 L30,140 Z" fill="#dbeafe"/>')
    g.append('<rect x="-22" y="96" width="44" height="54" rx="8" fill="#d6a77a"/>')
    # arms
    ty = 8 * math.sin(typing * 2 * math.pi)
    if wave_arm > 0:
        ang = -40 - 20 * math.sin(wave_arm * 2 * math.pi)
        g.append(f'<g transform="translate(118,200) rotate({ang:.1f})"><rect x="-22" y="-10" width="44" height="140" rx="22" fill="#1d4ed8"/>'
                 '<circle cx="0" cy="138" r="24" fill="#e8b98a"/></g>')
    else:
        g.append(f'<path d="M110,190 C150,230 170,270 175,{300 + ty:.1f}" stroke="#1d4ed8" stroke-width="44" stroke-linecap="round" fill="none"/>'
                 f'<circle cx="182" cy="{318 + ty:.1f}" r="24" fill="#e8b98a"/>')
    g.append(f'<path d="M-110,190 C-150,230 -165,270 -160,{300 - ty:.1f}" stroke="#1d4ed8" stroke-width="44" stroke-linecap="round" fill="none"/>'
             f'<circle cx="-158" cy="{318 - ty:.1f}" r="24" fill="#e8b98a"/>')
    if coffee:
        g.append('<g transform="translate(150,250)"><rect x="-26" y="-40" width="52" height="64" rx="8" fill="#f8fafc" stroke="#94a3b8" stroke-width="4"/>'
                 '<path d="M26,-24 a16,16 0 1 1 0,30" stroke="#94a3b8" stroke-width="6" fill="none"/>'
                 '<path d="M-10,-56 q8,-14 0,-26 M8,-56 q8,-14 0,-26" stroke="#cbd5e1" stroke-width="4" fill="none" stroke-linecap="round"/></g>')
    # head
    g.append('<ellipse cx="0" cy="0" rx="96" ry="104" fill="#e8b98a"/>')
    g.append('<ellipse cx="-96" cy="10" rx="14" ry="22" fill="#d6a77a"/><ellipse cx="96" cy="10" rx="14" ry="22" fill="#d6a77a"/>')
    if hat:
        g.append('<path d="M-92,-30 C-92,-118 -46,-150 0,-150 C46,-150 92,-118 92,-30 Z" fill="#facc15"/>'
                 '<path d="M0,-150 V-34" stroke="#eab308" stroke-width="14"/>'
                 '<rect x="-118" y="-42" width="236" height="26" rx="13" fill="#eab308"/>')
    else:
        g.append('<path d="M-96,-20 C-104,-96 -50,-124 0,-124 C58,-124 104,-96 96,-24 C80,-60 40,-78 -10,-74 C-50,-70 -80,-52 -96,-20 Z" fill="#3f2d20"/>')
    # brows, eyes, mouth
    if mood == "stressed":
        g.append('<path d="M-58,-38 L-22,-28 M58,-38 L22,-28" stroke="#3f2d20" stroke-width="8" stroke-linecap="round"/>')
    else:
        g.append('<path d="M-58,-34 Q-40,-46 -22,-36 M58,-34 Q40,-46 22,-36" stroke="#3f2d20" stroke-width="7" fill="none" stroke-linecap="round"/>')
    if blink:
        g.append('<path d="M-52,-6 h26 M26,-6 h26" stroke="#1f2937" stroke-width="7" stroke-linecap="round"/>')
    else:
        g.append('<ellipse cx="-38" cy="-6" rx="11" ry="14" fill="#1f2937"/><ellipse cx="38" cy="-6" rx="11" ry="14" fill="#1f2937"/>'
                 '<circle cx="-34" cy="-11" r="4" fill="#fff"/><circle cx="42" cy="-11" r="4" fill="#fff"/>')
    g.append('<ellipse cx="-62" cy="26" rx="14" ry="8" fill="#f9a8a8" opacity="0.6"/><ellipse cx="62" cy="26" rx="14" ry="8" fill="#f9a8a8" opacity="0.6"/>')
    if talk > 0.05:
        g.append(f'<ellipse cx="0" cy="46" rx="22" ry="{6 + 16 * talk:.1f}" fill="#7f1d1d"/>')
    elif mood == "stressed":
        g.append('<path d="M-24,54 Q0,38 24,54" stroke="#7f1d1d" stroke-width="7" fill="none" stroke-linecap="round"/>')
        g.append('<path d="M84,-60 q10,18 0,28 q-10,-10 0,-28 Z" fill="#7dd3fc"/>')   # sweat drop
    else:
        g.append('<path d="M-30,38 Q0,66 30,38" stroke="#7f1d1d" stroke-width="7" fill="none" stroke-linecap="round"/>')
    g.append("</g>")
    return "".join(g)


def office(t, sky=0.0, dim=0.0):
    """Office backdrop. sky: 0 morning -> 1 noon."""
    top = "#fde68a" if sky < 0.5 else "#7dd3fc"
    sky_c = f"rgb({int(253 - 128 * sky)},{int(230 - 19 * sky)},{int(138 + 114 * sky)})"
    s = [f'<rect width="{W}" height="{H}" fill="#e7edf6"/>',
         '<rect y="840" width="1920" height="240" fill="#c9b18f"/>',
         '<rect y="836" width="1920" height="10" fill="#b39a76"/>',
         # window
         '<rect x="70" y="110" width="380" height="340" rx="14" fill="#cbd5e1"/>',
         f'<rect x="86" y="126" width="348" height="308" rx="8" fill="{sky_c}"/>',
         f'<circle cx="{180 + 160 * sky:.1f}" cy="{330 - 170 * sky:.1f}" r="40" fill="#fff7cc"/>',
         '<path d="M86,360 C150,330 220,350 270,330 S380,320 434,340 V434 H86 Z" fill="#94a3b8" opacity="0.7"/>',
         '<path d="M260,126 V434 M86,280 H434" stroke="#cbd5e1" stroke-width="10"/>',
         # plant
         '<rect x="1500" y="700" width="90" height="140" rx="14" fill="#b45309"/>',
         '<path d="M1545,700 C1500,620 1480,560 1520,520 C1530,600 1545,640 1545,700 C1555,620 1590,570 1620,540 C1615,610 1580,660 1545,700 Z" fill="#16a34a"/>']
    if dim:
        s.append(f'<rect width="{W}" height="{H}" fill="#0f172a" opacity="{dim:.3f}"/>')
    return "".join(s)


def clock(x, y, hours, r=70):
    hm = (hours % 12) / 12 * 360; mm = (hours * 60 % 60) / 60 * 360
    return (f'<g transform="translate({x},{y})"><circle r="{r}" fill="#fff" stroke="#334155" stroke-width="8"/>'
            + "".join(f'<line x1="0" y1="{-r + 10}" x2="0" y2="{-r + 22}" stroke="#334155" stroke-width="5" transform="rotate({k * 30})"/>' for k in range(12))
            + f'<line x1="0" y1="0" x2="0" y2="{-r * 0.5:.1f}" stroke="#0f172a" stroke-width="9" stroke-linecap="round" transform="rotate({hm:.1f})"/>'
            + f'<line x1="0" y1="0" x2="0" y2="{-r * 0.78:.1f}" stroke="#0f172a" stroke-width="5" stroke-linecap="round" transform="rotate({mm:.1f})"/>'
            + '<circle r="7" fill="#d97757"/></g>')


def task_board(x, y, done, appear=1.0, highlight=-1, scale=1.0):
    notes = [c[6] for c in CASES]
    colors = ["#fde68a", "#bbf7d0", "#bfdbfe", "#fecaca", "#ddd6fe", "#fed7aa"]
    s = [f'<g transform="translate({x},{y}) scale({scale})"><rect width="420" height="470" rx="16" fill="#b7895b"/>'
         '<rect x="14" y="14" width="392" height="442" rx="10" fill="#d4a373"/>',
         txt(210, 58, "TODAY", 30, 800, "#5b3a1e", "middle")]
    for k, n in enumerate(notes):
        a = c01((appear * 6) - k)
        if a <= 0:
            continue
        r_, c_ = divmod(k, 2)
        nx, ny = 34 + c_ * 190, 84 + r_ * 124
        rot = [-3, 2, 3, -2, -1, 3][k]
        sc = back(a)
        s.append(f'<g transform="translate({nx + 85},{ny + 52}) rotate({rot}) scale({sc:.3f}) translate(-85,-52)">'
                 f'<rect width="170" height="104" fill="{colors[k]}" stroke="{"#d97757" if k == highlight else "none"}" stroke-width="6"/>'
                 f'<circle cx="85" cy="10" r="7" fill="#dc2626"/>')
        for j, line in enumerate(wrap(n, 13)):
            s.append(txt(85, 50 + j * 28, line, 23, 700, "#1f2937", "middle"))
        if done[k] > 0:
            d = done[k]
            s.append(f'<path d="M30,62 l30,30 l80,-80" stroke="#16a34a" stroke-width="14" fill="none" stroke-linecap="round" '
                     f'stroke-linejoin="round" stroke-dasharray="170" stroke-dashoffset="{170 * (1 - d):.1f}"/>')
        s.append("</g>")
    s.append("</g>")
    return "".join(s)


def task_strip(x, y, done, highlight=-1, w=150, gap=14):
    notes = [c[6] for c in CASES]
    colors = ["#fde68a", "#bbf7d0", "#bfdbfe", "#fecaca", "#ddd6fe", "#fed7aa"]
    s = []
    for k, n_ in enumerate(notes):
        nx = x + k * (w + gap); h = 104
        s.append(f'<g transform="translate({nx},{y}) rotate({[-2, 1, 2, -1, -2, 1][k]} {w / 2} {h / 2})">'
                 f'<rect width="{w}" height="{h}" fill="{colors[k]}" stroke="{"#d97757" if k == highlight else "none"}" stroke-width="6"/>')
        for j, line in enumerate(wrap(n_, 12)):
            s.append(txt(w / 2, 44 + j * 26, line, 22, 700, "#1f2937", "middle"))
        if done[k] > 0:
            s.append(f'<path d="M{w * 0.2:.0f},60 l{w * 0.17:.0f},28 l{w * 0.45:.0f},-70" stroke="#16a34a" stroke-width="12" fill="none" stroke-linecap="round" '
                     f'stroke-linejoin="round" stroke-dasharray="160" stroke-dashoffset="{160 * (1 - done[k]):.1f}"/>')
        s.append("</g>")
    return "".join(s)


def desk_and_monitor(screen_svg=""):
    return ('<rect x="560" y="800" width="840" height="34" rx="8" fill="#8b5e34"/>'
            '<rect x="600" y="834" width="30" height="200" fill="#6b4423"/><rect x="1330" y="834" width="30" height="200" fill="#6b4423"/>'
            '<rect x="930" y="740" width="60" height="62" fill="#475569"/><rect x="860" y="790" width="200" height="14" rx="7" fill="#334155"/>'
            '<rect x="700" y="420" width="520" height="330" rx="18" fill="#1e293b"/>'
            f'<g><rect x="716" y="436" width="488" height="298" rx="8" fill="#0b1220"/>{screen_svg}</g>'
            '<rect x="640" y="806" width="300" height="20" rx="8" fill="#cbd5e1"/>')


def claude_orb(x, y, r, pulse=0.0):
    return (f'<circle cx="{x}" cy="{y}" r="{r * (1 + 0.6 * pulse):.1f}" fill="#d97757" opacity="{0.35 * (1 - pulse):.3f}"/>'
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="#d97757"/>'
            + "".join(f'<line x1="{x}" y1="{y}" x2="{x + r * 0.62 * math.cos(a):.1f}" y2="{y + r * 0.62 * math.sin(a):.1f}" '
                      f'stroke="#fff" stroke-width="{r * 0.16:.1f}" stroke-linecap="round"/>' for a in np.linspace(0, 2 * math.pi, 9)[:-1]))


def speech(x, y, w, lines, mode, opacity=1, tail="left", size=30):
    h = 40 + len(lines) * (size + 10) + 34
    tx = x + 60 if tail == "left" else x + w - 60
    s = [f'<g opacity="{opacity:.3f}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="#fff" stroke="#0f172a" stroke-width="4"/>',
         f'<path d="M{tx - 22},{y + h - 2} L{tx - (40 if tail == "left" else -40)},{y + h + 46} L{tx + 22},{y + h - 2} Z" fill="#fff" stroke="#0f172a" stroke-width="4" stroke-linejoin="round"/>',
         f'<rect x="{tx - 20}" y="{y + h - 8}" width="40" height="10" fill="#fff"/>']
    badge = "#0284c7" if mode == "voice" else "#7c3aed"
    s.append(f'<rect x="{x + 24}" y="{y + 18}" width="{120 if mode == "voice" else 104}" height="34" rx="17" fill="{badge}"/>')
    s.append(txt(x + 24 + (60 if mode == "voice" else 52), y + 43, "VOICE" if mode == "voice" else "TEXT", 20, 800, "#fff", "middle"))
    for k, line in enumerate(lines):
        s.append(txt(x + 28, y + 62 + (k + 1) * (size + 10) - 8, line, size, 600, "#0f172a", italic=True))
    s.append("</g>")
    return "".join(s)


def sound_waves(x, y, t, n=3):
    out = []
    for k in range(n):
        ph = (t * 1.5 + k / n) % 1
        r = 30 + ph * 70
        out.append(f'<path d="M{x + r * 0.5:.1f},{y - r * 0.8:.1f} A{r:.1f},{r:.1f} 0 0 1 {x + r * 0.5:.1f},{y + r * 0.8:.1f}" '
                   f'stroke="#0284c7" stroke-width="6" fill="none" opacity="{(1 - ph) * 0.9:.3f}" stroke-linecap="round"/>')
    return "".join(out)


def caption(s, opacity=1, y=1020):
    return (f'<g opacity="{opacity:.3f}"><rect x="{W / 2 - 22 * len(s) / 2 - 40:.1f}" y="{y - 52}" width="{22 * len(s) + 80:.1f}" height="74" rx="37" fill="#0f172a" opacity="0.88"/>'
            + txt(W / 2, y, s, 38, 700, "#fff", "middle") + "</g>")


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">{body}</svg>')


# ------------------------------------------------------------------------------------------------
def scene_morning(f, n):
    t = f / FPS
    hours = 8 + 0.25 * c01(f / n)
    books = ["FEA manual", "OpenFOAM guide", "CAD API docs", "Printer firmware", "Lattice papers", "CT pipeline"]
    b = [office(t, 0.0), clock(1320, 360, hours), task_board(1440, 90, [0] * 6, appear=c01((f - 20) / 60))]
    b.append(desk_and_monitor('<text x="960" y="600" font-family="Inter" font-size="40" font-weight="700" fill="#334155" text-anchor="middle">8:00 AM</text>'))
    # stack of manuals growing on the desk
    for k, name in enumerate(books):
        a = c01((f - 70 - k * 14) / 10)
        if a <= 0:
            continue
        yy = 790 - (k + 1) * 46 + (1 - back(a)) * -200
        col = ["#ef4444", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"][k]
        b.append(f'<g transform="translate(1210,{yy:.1f}) rotate({[-4, 3, -2, 5, -3, 2][k]})"><rect x="0" y="0" width="200" height="42" rx="6" fill="{col}"/>'
                 + txt(100, 29, name, 19, 700, "#fff", "middle") + "</g>")
    blink = (f % 75) in (0, 1, 2)
    b.append(engineer(420, 520, 1.0, mood="stressed" if f > 90 else "neutral", blink=blink, typing=t * 3 if f < 90 else 0))
    if f > 120:
        b.append(speech(250, 150, 560, ["Six tasks. Six tools.", "Where do I even start?"], "text", opacity=c01((f - 120) / 10)).replace("TEXT", "THINKS").replace('#7c3aed', '#64748b'))
    b.append(caption("Monday, 8:00 AM", c01(f / 12) * (1 - c01((f - 110) / 12)), y=1030))
    return svg("".join(b))


def scene_ask(f, n):
    t = f / FPS
    b = [office(t, 0.05), clock(1320, 360, 8.25), task_board(1440, 90, [0] * 6)]
    p = back((f - 30) / 15)
    screen = ""
    if f > 30:
        screen = (claude_orb(960, 560, 70 * p, pulse=(t * 1.2) % 1)
                  + txt(960, 690, "Claude + Mechanical Engineering Skills", 24, 700, "#fdba74", "middle", opacity=c01((f - 40) / 10)))
    b.append(desk_and_monitor(screen))
    talk = abs(math.sin(t * 14)) if 10 < f < 80 else 0
    b.append(engineer(420, 520, 1.0, mood="neutral" if f < 60 else "happy", talk=talk, blink=(f % 70) < 3))
    if 8 < f:
        b.append(sound_waves(540, 560, t) if f < 85 else "")
        b.append(speech(560, 120, 820, ["Hey Claude, let's get through", "this list together."], "voice", opacity=c01((f - 8) / 8)))
    b.append(caption("Just ask, by voice or text.", c01((f - 70) / 12), y=1030))
    return svg("".join(b))


def visual(kind, x, y, w, h, prog, t):
    """Result visual inside the Claude window."""
    a = c01(prog)
    if kind.endswith(".png"):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#fff" opacity="{a:.3f}"/>'
                + image(kind, x + 14, y + 14, w - 28, h - 28, opacity=a))
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#f8fafc" opacity="{a:.3f}"/>', f'<g opacity="{a:.3f}">']
    cx, cy = x + w / 2, y + h / 2
    if kind == "shaft":
        s.append(f'<rect x="{cx - 260}" y="{cy - 22}" width="520" height="44" rx="10" fill="#94a3b8"/>'
                 f'<rect x="{cx - 120}" y="{cy - 40}" width="150" height="80" rx="10" fill="#64748b"/>')
        for bx in (cx - 210, cx + 170):
            s.append(f'<rect x="{bx}" y="{cy - 60}" width="44" height="120" rx="8" fill="#f59e0b"/>'
                     f'<circle cx="{bx + 22}" cy="{cy}" r="16" fill="#fff" opacity="0.7"/>')
        s.append(f'<path d="M{cx - 260},{cy + 90} H{cx + 260}" stroke="#0f172a" stroke-width="3"/>'
                 + txt(cx, cy + 128, "T = 63.7 N·m  ·  fatigue SF checked  ·  bearing life checked", 22, 600, "#0f172a", "middle"))
    elif kind == "bracket":
        rot = 10 * math.sin(t * 1.5)
        s.append(f'<g transform="translate({cx},{cy}) rotate({rot:.1f})">'
                 '<path d="M-150,40 L60,-60 L170,-10 L-40,90 Z" fill="#93c5fd" stroke="#1e3a8a" stroke-width="4"/>'
                 '<path d="M-150,40 L-150,-110 L60,-210 L60,-60 Z" fill="#60a5fa" stroke="#1e3a8a" stroke-width="4"/>'
                 '<path d="M-40,90 L-40,110 L-150,60 L-150,40 Z" fill="#3b82f6" stroke="#1e3a8a" stroke-width="4"/>'
                 '<path d="M-90,-110 a18,18 0 1 0 22,-8 l-6,-20 Z" fill="#1e3a8a"/><path d="M0,-150 a18,18 0 1 0 22,-8 l-6,-20 Z" fill="#1e3a8a"/>'
                 '<ellipse cx="40" cy="20" rx="20" ry="11" fill="#1e3a8a"/></g>'
                 + txt(cx, y + h - 20, "teardrop holes · no supports · STEP + STL", 22, 600, "#0f172a", "middle"))
    elif kind == "cfd":
        for k in range(7):
            s.append(f'<rect x="{cx - 120 + k * 40}" y="{cy - 70}" width="16" height="150" rx="4" fill="#64748b"/>')
        s.append(f'<rect x="{cx - 140}" y="{cy + 70}" width="300" height="20" fill="#475569"/>')
        for k in range(8):
            yy = y + 40 + k * (h - 80) / 7
            ph = (t * 0.8 + k * 0.13) % 1
            s.append(f'<path d="M{x + 20},{yy:.1f} C{cx - 200},{yy:.1f} {cx - 160},{cy + (yy - cy) * 1.4:.1f} {cx},{cy + (yy - cy) * 1.5:.1f} '
                     f'S{x + w - 120},{yy:.1f} {x + w - 20},{yy:.1f}" stroke="#38bdf8" stroke-width="4" fill="none" stroke-dasharray="30 18" '
                     f'stroke-dashoffset="{-ph * 96:.1f}" opacity="0.85"/>')
        s.append(txt(cx, y + h - 18, "residuals ✓  mass balance ✓  correlation ✓", 22, 600, "#0f172a", "middle"))
    s.append("</g>")
    return "".join(s)


def claude_window(case, f, t, x=820, y=70, w=1050, h=790):
    mode, req, skills, steps, result, vis, _, _ = case
    s = [f'<rect x="{x}" y="{y + 10}" width="{w}" height="{h}" rx="28" fill="#000" opacity="0.18"/>',
         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="#ffffff"/>',
         f'<rect x="{x}" y="{y}" width="{w}" height="84" rx="28" fill="#fff7ed"/><rect x="{x}" y="{y + 56}" width="{w}" height="28" fill="#fff7ed"/>',
         claude_orb(x + 52, y + 42, 22, pulse=(t * 1.4) % 1 if f < 110 else 0),
         txt(x + 92, y + 52, "Claude", 30, 800, "#9a3412")]
    for k, sk in enumerate(skills):
        a = c01((f - 18 - k * 6) / 8)
        s.append(icon(sk, x + w - 70 - k * 66, y + 14, 56, a))
    # steps
    for k, st in enumerate(steps):
        a = c01((f - 28 - k * 18) / 8)
        if a <= 0:
            continue
        yy = y + 130 + k * 50
        done = f > 40 + k * 18
        s.append(f'<g opacity="{a:.3f}"><circle cx="{x + 52}" cy="{yy - 9}" r="15" fill="{"#22c55e" if done else "#cbd5e1"}"/>'
                 + ('<path d="M{0},{1} l6,6 l11,-12" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'.format(x + 44, yy - 10) if done else "")
                 + txt(x + 82, yy, st, 28, 600, "#0f172a") + "</g>")
    vy = y + 300
    s.append(visual(vis, x + 40, vy, w - 80, h - 300 - 100, (f - 80) / 14, t))
    a = c01((f - 100) / 10)
    s.append(f'<g opacity="{a:.3f}"><rect x="{x + 40}" y="{y + h - 84}" width="{w - 80}" height="60" rx="30" fill="#dcfce7"/>'
             f'<circle cx="{x + 80}" cy="{y + h - 54}" r="18" fill="#22c55e"/>'
             f'<path d="M{x + 71},{y + h - 55} l7,7 l13,-14" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
             + txt(x + 112, y + h - 44, result, 30, 800, "#14532d") + "</g>")
    return "".join(s)


def shop_floor(t):
    s = [f'<rect width="{W}" height="{H}" fill="#e2e8f0"/>', '<rect y="840" width="1920" height="240" fill="#94a3b8"/>',
         '<path d="M0,840 H1920" stroke="#64748b" stroke-width="8"/>']
    for k in range(6):   # hazard stripes on the floor
        s.append(f'<path d="M{60 + k * 120},1080 l60,-60 h40 l-60,60 Z" fill="#facc15"/>')
    # 3D printer
    s.append('<rect x="80" y="380" width="380" height="460" rx="20" fill="#334155"/><rect x="110" y="410" width="320" height="330" rx="10" fill="#0f172a"/>'
             f'<rect x="{180 + 90 * math.sin(t * 3):.1f}" y="460" width="60" height="40" rx="6" fill="#f97316"/>'
             '<rect x="150" y="690" width="240" height="22" fill="#64748b"/><rect x="190" y="650" width="160" height="40" rx="6" fill="#38bdf8"/>'
             '<circle cx="410" cy="790" r="18" fill="#22c55e"/>')
    return "".join(s)


def scene_case(i):
    case = CASES[i]
    mode, req, *_ , place = case
    def draw(f, n):
        t = f / FPS
        b = [shop_floor(t) if place == "shop" else office(t, sky=(i + f / n) / len(CASES), dim=0.0)]
        # engineer on the left, talking or typing
        talking = mode == "voice" and 6 < f < 70
        talk = abs(math.sin(t * 14)) if talking else 0
        b.append(engineer(330 if place != "shop" else 640, 560, 0.9, mood="happy" if f > 100 else "neutral", talk=talk,
                          hat=(place == "shop"), typing=(t * 4 if (mode == "text" and f < 70) else 0), blink=(f % 80) < 3))
        if mode == "text" and f < 70:
            b.append('<rect x="120" y="840" width="420" height="40" rx="10" fill="#334155"/>'
                     + "".join(f'<rect x="{136 + k * 30}" y="850" width="22" height="20" rx="4" fill="{"#94a3b8" if (int(t * 12) + k) % 5 else "#e2e8f0"}"/>' for k in range(13)))
        if talking:
            b.append(sound_waves(430 if place != "shop" else 740, 600, t))
        lines = wrap(req, 30)
        b.append(speech(60 if place != "shop" else 340, 90, 700 if place != "shop" else 460, lines, mode,
                        opacity=c01(f / 6) * (1 - 0.65 * c01((f - 120) / 20)), size=30 if place != "shop" else 26))
        b.append(claude_window(case, f, t, x=820 if place != "shop" else 1060, w=1050 if place != "shop" else 820))
        done = [1.0 if k < i else (c01((f - 120) / 20) if k == i else 0) for k in range(6)]
        b.append(task_strip(850, 930, done, highlight=i) if place != "shop" else task_strip(1066, 935, done, highlight=i, w=122, gap=12))
        b.append(f'<rect width="{W}" height="{H}" fill="#fff" opacity="{0.6 * (1 - c01(f / 4)):.3f}"/>')
        return svg("".join(b))
    return draw


def scene_lunch(f, n):
    t = f / FPS
    b = [office(t, 1.0), clock(1320, 360, 11.5), task_board(1440, 90, [1] * 6)]
    b.append(desk_and_monitor('<path d="M880,590 l50,50 l110,-120" stroke="#22c55e" stroke-width="22" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'))
    b.append(engineer(420, 520, 1.0, mood="happy", coffee=True, blink=(f % 70) < 3, wave_arm=0))
    a = c01((f - 20) / 14)
    b.append(f'<g opacity="{a:.3f}">' + txt(940, 120, "11:30 AM. Six tasks done.", 62, 800, "#0f172a", "middle") + "</g>")
    for k, line in enumerate(["No manuals. No setup. No models to install.", "Every answer came with its check."]):
        a = c01((f - 50 - k * 20) / 14)
        b.append(f'<g opacity="{a:.3f}">' + txt(940, 200 + k * 56, line, 36, 600, "#334155", "middle") + "</g>")
    # confetti
    rng = np.random.default_rng(1)
    for k in range(60):
        x0, sp, col = rng.uniform(0, W), rng.uniform(200, 420), ["#f97316", "#22c55e", "#3b82f6", "#eab308", "#ec4899"][k % 5]
        yy = -40 + sp * (t - 0.2) - 50 * (k % 7)
        if 0 < yy < H:
            b.append(f'<rect x="{x0 + 30 * math.sin(t * 3 + k):.1f}" y="{yy:.1f}" width="14" height="22" fill="{col}" transform="rotate({(t * 200 + k * 37) % 360:.0f} {x0:.0f} {yy:.0f})"/>')
    return svg("".join(b))


def scene_end(f, n):
    t = f / FPS
    b = [f'<rect width="{W}" height="{H}" fill="#0b1220"/>']
    order = list(M.G)
    for k, sk in enumerate(order):
        r_, c_ = divmod(k, 16)
        a = c01((f - k * 1.2) / 8)
        b.append(icon(sk, 160 + c_ * 102, 560 + r_ * 104 + (1 - back(a)) * 40, 86, a))
    b.append(txt(W / 2, 250, "Mechanical Engineering Skills", 92, 800, "#ffffff", "middle", opacity=c01((f - 10) / 14)))
    b.append(txt(W / 2, 330, "Engineering, on demand. Just ask Claude, by voice or text.", 40, 500, "#cbd5e1", "middle", opacity=c01((f - 24) / 14)))
    cmd = "npx skills add BaratiLab/mechanical-engineering-skills"
    k = int(len(cmd) * c01((f - 40) / 50))
    b.append(f'<rect x="{W / 2 - 600}" y="400" width="1200" height="84" rx="20" fill="#111827" stroke="#334155" stroke-width="3" opacity="{c01((f - 36) / 8):.3f}"/>')
    b.append(txt(W / 2 - 560, 455, "$ " + cmd[:k] + ("▌" if (f // 8) % 2 == 0 else ""), 36, 700, "#7dd3fc", family=MONO))
    b.append(txt(W / 2, 860, "Barati Farimani Lab · Carnegie Mellon University", 34, 600, "#94a3b8", "middle", opacity=c01((f - 90) / 14)))
    if f > n - 24:
        b.append(f'<rect width="{W}" height="{H}" fill="#000" opacity="{c01((f - (n - 24)) / 24):.3f}"/>')
    return svg("".join(b))


def drawer(name):
    if name.startswith("case"):
        return scene_case(int(name[4:]))
    return {"morning": scene_morning, "ask": scene_ask, "lunch": scene_lunch, "end": scene_end}[name]


# ------------------------------------------------------------------------------------------------
def soundtrack(path, seconds, sr=44100):
    """Playful 110 BPM track: plucky marimba-like melody over bass and soft drums; a 'ding' on each
    completed task and a lift into the montage."""
    n = int(seconds * sr); out = np.zeros(n); rng = np.random.default_rng(2)
    beat = 60 / 110
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    def add(sig, start, gain=1.0):
        i = int(start * sr); j = min(n, i + len(sig))
        if 0 <= i < n: out[i:j] += gain * sig[:j - i]
    def pluck(m, dur=0.35, bright=3):
        x = np.arange(int(dur * sr)) / sr; f0 = hz(m)
        return sum(np.sin(2 * np.pi * f0 * h * x) / h ** 1.5 for h in range(1, bright + 1)) * np.exp(-x / 0.12)
    prog = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]   # C Am F G
    melody = [72, 76, 79, 76, 74, 72, 74, 76, 77, 76, 74, 72, 71, 72, 74, 79]
    morning_end, ask_end = 8.0, 13.0
    nb = int(seconds / beat)
    kick = np.sin(2 * np.pi * 55 * np.arange(int(0.25 * sr)) / sr * (1 + np.exp(-np.arange(int(0.25 * sr)) / sr / 0.02))) * np.exp(-np.arange(int(0.25 * sr)) / sr / 0.08)
    for b in range(nb):
        st = b * beat; ch = prog[(b // 4) % 4]
        busy = st >= ask_end and st < seconds - 3
        tense = st < morning_end
        if busy:
            add(kick, st, 0.6)
            if b % 2 == 1:
                add(rng.standard_normal(int(0.12 * sr)) * np.exp(-np.arange(int(0.12 * sr)) / sr / 0.03), st, 0.12)
            add(pluck(melody[b % 16], 0.3), st, 0.22)
            add(pluck(melody[(b + 3) % 16] - 12, 0.25, 2), st + beat / 2, 0.12)
        elif tense:
            add(pluck(ch[0] - 12 + (1 if b % 2 else 0), 0.4, 2), st, 0.18)     # anxious tick-tock
        else:
            add(pluck(ch[b % 3], 0.4), st, 0.18)
        x = np.arange(int(beat * sr)) / sr
        add(np.sin(2 * np.pi * hz(ch[0] - 24) * x) * np.exp(-x / 0.25), st, 0.25)
        if b % 4 == 0:
            x = np.arange(int(4 * beat * sr)) / sr
            pad = sum(np.sin(2 * np.pi * hz(m) * x) for m in ch) * np.minimum(1, x / 0.3) * np.minimum(1, (4 * beat - x) / 0.4)
            add(pad, st, 0.03)
    for i in range(len(CASES)):    # ding when a task is checked off
        tdone = ask_end + i * CASE_F / FPS + 120 / FPS
        x = np.arange(int(0.6 * sr)) / sr
        add((np.sin(2 * np.pi * 1318.5 * x) + 0.5 * np.sin(2 * np.pi * 1975.5 * x)) * np.exp(-x / 0.18), tdone, 0.16)
    x = np.arange(int(1.2 * sr)) / sr   # whoosh into the montage
    add(rng.standard_normal(len(x)) * (x / x[-1]) ** 2 * 0.15, ask_end - 1.2)
    t = np.arange(n) / sr
    out *= np.minimum(1, (seconds - t) / 2.5)
    out = np.tanh(out * 1.3) / np.tanh(1.3)
    out = (out / max(1e-9, np.abs(out).max()) * 0.85 * 32767).astype(np.int16)
    with wave.open(path, "wb") as w_:
        w_.setnchannels(2); w_.setsampwidth(2); w_.setframerate(sr); w_.writeframes(np.stack([out, out], 1).tobytes())


def frame_png(name, f, n):
    return cairosvg.svg2png(bytestring=drawer(name)(f, n).encode(), output_width=W, output_height=H)


def render_scene(name, n, out):
    tmp = out + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                          "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        im = Image.open(io.BytesIO(frame_png(name, f, n))).convert("RGB")
        p.stdin.write(im.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(name)
    os.replace(tmp, out)


def main():
    import argparse
    from concurrent.futures import ProcessPoolExecutor
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cartoon.mp4"); ap.add_argument("--work", default="/tmp/mes_cartoon")
    ap.add_argument("--still", nargs="*"); ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    if a.still:
        for s in a.still:
            name, fr = s.split(":"); n = dict(SCENES)[name]
            open(os.path.join(a.work, f"still_{name}_{fr}.png"), "wb").write(frame_png(name, int(fr), n))
        return
    files = [os.path.join(a.work, f"{k:02d}_{name}.mp4") for k, (name, _) in enumerate(SCENES)]
    with ProcessPoolExecutor(a.jobs) as ex:
        list(ex.map(render_scene, [s[0] for s in SCENES], [s[1] for s in SCENES], files))
    total = sum(s[1] for s in SCENES) / FPS
    lst = os.path.join(a.work, "list.txt"); open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    soundtrack(os.path.join(a.work, "music.wav"), total)
    silent = os.path.join(a.work, "silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", os.path.join(a.work, "music.wav"), "-map", "0:v",
                    "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    print(a.out, f"{total:.1f}s")


if __name__ == "__main__":
    main()
