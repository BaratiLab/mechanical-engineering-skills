#!/usr/bin/env python3
"""One-minute launch video for Mechanical Engineering Skills (1920x1080, 30 fps, with a synthesized
soundtrack). Scenes are cut on the beat (120 BPM). Run: python tools/make_video.py [--out video.mp4]
[--still SCENE:FRAME] to draw single frames for checking."""
import io, math, os, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import cairosvg

sys.path.insert(0, os.path.dirname(__file__))
import make_icons as M

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG = os.path.join(ROOT, "docs", "img")
W, H, FPS = 1920, 1080, 30
BEAT = 0.5
FONT = "/usr/share/fonts/opentype/inter/"
F = lambda name, size: ImageFont.truetype(FONT + name, size)
MONO = lambda size: ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", size)
NAVY = (11, 18, 32)

RESEARCH = [  # skill, paper chip, tagline, image
    ("cadsmith-text-to-cad", "CADSmith", "Describe a part in words. Get a validated CAD model.", "cadsmith_coupling_views.png"),
    ("query2cad-freecad", "Query2CAD", "Plain language to a FreeCAD macro, checked by vision.", "query2cad_star_v1_v2.png"),
    ("linkage-synthesis", "LinkD", "Draw a motion path. Get the linkage that traces it.", "linkage_bean.png"),
    ("llm-mechanical-designer", "LLM Mechanical Designer", "The model proposes trusses. Exact FEM judges them.", "truss_best.png"),
    ("rocketsmith", "RocketSmith", "Printed rockets: stable, simulated, ready to fly.", "rocketsmith_parts.png"),
    ("cfd-simulation-setup", "CFD Forge", "A flow question becomes a physics-checked OpenFOAM run.", None),
    ("stress-field-surrogate", "StressD", "Geometry and loads to a full stress field in milliseconds.", "stressd_regression_unseen.png"),
    ("lattice-inverse-design", "GLU3D", "Target stiffness to a printable TPMS lattice.", "glu3d_gallery.png"),
    ("equation-discovery", "LLM-SR · ICLR Oral", "Test data to an equation you can read.", "eqdisc_pareto.png"),
    ("agentscad-fdm-dfam", "AgentsCAD", "Any STEP part, made printable without supports.", "agentscad_birdhouse_after.png"),
    ("image2gcode", "Image2Gcode", "A photo or sketch, straight to G-code.", "image2gcode_toolpaths.png"),
    ("lpbf-defect-prediction", "AdditiveLLM", "Laser settings in. Keyhole, lack of fusion or safe out.", "lpbf_map_ti64.png"),
    ("am-alloy-screening", "Agentic alloy evaluation", "Will this alloy print? Ranked, with its process map.", "alloy_known_maps.png"),
    ("sls-process-optimization", "Agentic SLS", "Test results in. Next batch settings out.", "sls_onyx_history.png"),
    ("meltpool-geometry", "MeltpoolNet", "Melt-pool size and mode from power, speed and alloy.", "meltpool_parity.png"),
    ("llm-3d-print-monitor", "LLM-3D Print", "Watches every layer and fixes the print, safely.", "printmonitor_layers.png"),
    ("thermal-porosity", "ThermoPore", "Thermal images to pores, layer by layer.", "thermopore_layer.png"),
    ("lpbf-superres", "Diffusion super-resolution", "A cheap webcam, sharpened into high-resolution layers.", "superres_patches.png"),
    ("am-literature-rag", "AMGPT", "Page-cited answers from your own AM papers.", None),
]
CORE = ["parametric-part-cad", "sketch-to-cad", "drawing-gdt-review", "machine-element-sizing", "quick-fea",
        "tolerance-stackup", "thermal-fluids-calc", "material-selection", "design-review-package",
        "engineering-calc-report", "dfm-review", "mechanical-teardown", "worked-problem-generator", "mechanics-visuals"]
CATEGORY = {"design": ("DESIGN & CAD", "mech"), "analysis": ("ANALYSIS & SIMULATION", "analysis"),
            "manufacturing": ("MANUFACTURING", "dfm")}
CAT_OF = {s: ("design" if i < 5 else "analysis" if i < 9 else "manufacturing") for i, (s, *_ ) in enumerate(RESEARCH)}

# timeline in beats (0.5 s): title 8, voice 10, research 19 x 3, core 15 (14 skills), numbers 12, end 18  -> 120 beats = 60 s
SCENES = [("title", 8), ("voice", 10)] + [(f"skill{i}", 3) for i in range(len(RESEARCH))] + [("core", 15), ("numbers", 12), ("end", 18)]


def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out(t): t = min(max(t, 0), 1); return 1 - (1 - t) ** 3
def ease_back(t, s=1.7):
    t = min(max(t, 0), 1) - 1; return t * t * ((s + 1) * t + s) + 1
def clamp01(t): return min(max(t, 0.0), 1.0)


_icon_cache = {}
def icon(skill, size):
    k = (skill, size)
    if k not in _icon_cache:
        png = cairosvg.svg2png(bytestring=M.tile(skill).encode(), output_width=size, output_height=size)
        _icon_cache[k] = Image.open(io.BytesIO(png)).convert("RGBA")
    return _icon_cache[k]


def scaled(im, s):
    s = max(s, 0.01)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def paste_center(base, im, cx, cy, alpha=1.0):
    if alpha < 1:
        im = im.copy(); a = im.getchannel("A").point(lambda v: int(v * alpha)); im.putalpha(a)
    base.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


def text_img(txt, font, fill=(255, 255, 255)):
    bbox = font.getbbox(txt)
    im = Image.new("RGBA", (bbox[2] + 8, bbox[3] + 12), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, 0), txt, font=font, fill=fill)
    return im


def put_text(base, txt, font, x, y, fill=(255, 255, 255), alpha=1.0, dx=0, anchor="l"):
    im = text_img(txt, font, fill)
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if anchor == "c":
        x = x - im.width / 2
    base.alpha_composite(im, (int(x + dx), int(y)))


def wrap(txt, font, width):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    return lines + [cur]


_bg = None
def background(t, glow=None, gx=0.25, gy=0.45):
    """Dark navy gradient + slowly drifting blueprint grid + optional coloured glow."""
    global _bg
    if _bg is None:
        y = np.linspace(0, 1, H)[:, None]; x = np.linspace(0, 1, W)[None, :]
        g = 1 - 0.55 * np.hypot(x - 0.5, y - 0.5)
        arr = np.stack([NAVY[i] + (30, 41, 59)[i] * (g - 0.4) for i in range(3)], -1)
        _bg = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    im = _bg.copy()
    d = ImageDraw.Draw(im)
    off = (t * 18) % 80
    for x in np.arange(-80, W + 80, 80):
        d.line([(x + off, 0), (x + off, H)], fill=(148, 163, 184, 14), width=1)
    for y in np.arange(-80, H + 80, 80):
        d.line([(0, y + off * 0.5), (W, y + off * 0.5)], fill=(148, 163, 184, 14), width=1)
    if glow:
        im.alpha_composite(glow_img(glow), (int(gx * W - 700), int(gy * H - 700)))
    return im


_glow_cache = {}
def glow_img(color):
    if color not in _glow_cache:
        r = 700; y, x = np.mgrid[-r:r, -r:r]
        a = np.clip(1 - np.hypot(x, y) / r, 0, 1) ** 2 * 120
        c = hexrgb(color)
        arr = np.zeros((2 * r, 2 * r, 4), np.uint8); arr[..., :3] = c; arr[..., 3] = a.astype(np.uint8)
        _glow_cache[color] = Image.fromarray(arr, "RGBA")
    return _glow_cache[color]


def rounded_card(w, h, fill=(255, 255, 255, 255), r=28, shadow=True):
    im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((30, 40, 30 + w, 40 + h), r, fill=(0, 0, 0, 150))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(im).rounded_rectangle((30, 30, 30 + w, 30 + h), r, fill=fill)
    return im


def pill(txt, font, fg, bg, pad=(22, 10)):
    w = int(font.getlength(txt)) + 2 * pad[0]; h = font.size + 2 * pad[1] + 6
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg)
    d.text((pad[0], pad[1]), txt, font=font, fill=fg)
    return im


# ------------------------------------------------------------------------------------------------
def scene_title(f, n):
    t = f / FPS
    im = background(t, "#3b82f6", 0.5, 0.3)
    order = list(M.G)
    rng = random.Random(3)
    starts = [(rng.uniform(-200, W + 200), rng.uniform(-200, H + 200)) for _ in order]
    cols, size, gap = (len(order) + 1) // 2, 92, 18
    for i, s in enumerate(order):
        r, c = divmod(i, cols)
        nrow = min(cols, len(order) - r * cols)
        x0 = (W - (nrow * size + (nrow - 1) * gap)) / 2
        tx, ty = x0 + c * (size + gap) + size / 2, 640 + r * (size + gap) + size / 2
        p = ease_out((f - i * 0.7) / 34)
        sx, sy = starts[i]
        x, y = sx + (tx - sx) * p, sy + (ty - sy) * p
        paste_center(im, scaled(icon(s, 160), (size / 160) * (0.4 + 0.6 * p)), x, y, alpha=clamp01(p * 1.5))
    a = clamp01((f - 22) / 14); dy = (1 - ease_out((f - 22) / 18)) * 40
    put_text(im, "Mechanical Engineering Skills", F("Inter-ExtraBold.otf", 104), W / 2, 270 + dy, alpha=a, anchor="c")
    a2 = clamp01((f - 40) / 14)
    put_text(im, "33 agent skills for design, analysis and manufacturing", F("Inter-Medium.otf", 42), W / 2, 410,
             (203, 213, 225), alpha=a2, anchor="c")
    a3 = clamp01((f - 62) / 14)
    put_text(im, "BARATI FARIMANI LAB  ·  CARNEGIE MELLON UNIVERSITY", F("Inter-SemiBold.otf", 26), W / 2, 490,
             (125, 211, 252), alpha=a3, anchor="c")
    if f < 6:   # opening flash
        im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * (1 - f / 6)))))
    return im


_concept = None
def concept_layers():
    global _concept
    if _concept is None:
        svg = open(os.path.join(ROOT, "paper", "figures", "concept.svg")).read()
        svg = svg.replace('<rect x="0" y="0" width="1600" height="860" rx="0" fill="#ffffff" stroke="none" stroke-width="0" />', "")
        import re
        svg = re.sub(r'<line[^>]*marker-end="url\(#ah\)"/>', "", svg)   # drop arrows; drawn live
        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=1920)
        full = Image.open(io.BytesIO(png)).convert("RGBA")
        s = 1.2
        crop = lambda x0, y0, x1, y1: full.crop((int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s)))
        _concept = {"eng": crop(20, 146, 330, 686), "mid": crop(368, 36, 1232, 666), "res": crop(1272, 146, 1580, 686)}
    return _concept


def scene_voice(f, n):
    t = f / FPS
    im = background(t, "#d97757", 0.5, 0.35)
    L = concept_layers()
    put_text(im, "Ask by voice or text.", F("Inter-ExtraBold.otf", 60), W / 2, 22, alpha=clamp01(f / 10), anchor="c")
    sub = "Claude picks the skill, runs the tools and checks the answer."
    put_text(im, sub, F("Inter-Medium.otf", 38), W / 2, 960, (203, 213, 225), alpha=clamp01((f - 60) / 14), anchor="c")
    sc = 1.0
    eng, mid, res = scaled(L["eng"], sc), scaled(L["mid"], sc), scaled(L["res"], sc)
    pe = ease_out(f / 18)
    ex, ey = 34 - (1 - pe) * 400, 140
    im.alpha_composite(eng, (int(ex), int(ey)))
    # sound rings from the mic
    mx, my = ex + 0.196 * eng.width, ey + 0.509 * eng.height
    d = ImageDraw.Draw(im)
    for k in range(3):
        ph = ((t * 1.6 + k / 3) % 1)
        rr = 16 + ph * 70
        d.ellipse((mx - rr, my - rr, mx + rr, my + rr), outline=(56, 189, 248, int(150 * (1 - ph))), width=3)
    pm = ease_back((f - 16) / 18)
    if f > 16:
        m2 = scaled(mid, max(pm, 0.05))
        paste_center(im, m2, W / 2, 112 + mid.height / 2, alpha=clamp01((f - 16) / 8))
    pr = ease_out((f - 60) / 18)
    if f > 60:
        im.alpha_composite(res, (int(W - 34 - res.width + (1 - pr) * 400), int(ey)))
    # pulse on the Claude hub while it 'thinks', and on the results card when it arrives
    if f > 34:
        ph = (t * 1.2) % 1
        hx, hy, hw, hh = W / 2 - 0.301 * mid.width, 112 + 0.108 * mid.height, 0.602 * mid.width, 0.171 * mid.height
        g = 8 + ph * 26
        d.rounded_rectangle((hx - g, hy - g, hx + hw + g, hy + hh + g), int(hh / 2 + g), outline=(253, 186, 116, int(170 * (1 - ph))), width=4)
    if f > 76:
        ph = ((t - 2.5) * 1.2) % 1
        rx0 = W - 34 - res.width; g = 6 + ph * 22
        d.rounded_rectangle((rx0 - g, ey - g, rx0 + res.width + g, ey + res.height + g), int(24 + g), outline=(134, 239, 172, int(160 * (1 - ph))), width=4)
    return im


def scene_skill(i):
    skill, paper, tagline, img = RESEARCH[i]
    cat = CAT_OF[skill]
    label, area = CATEGORY[cat]
    dark, light, _ = M.AREAS[area]
    pic = None
    if img:
        p = Image.open(os.path.join(IMG, img)).convert("RGBA")
        g = np.asarray(p.convert("L")); ys, xs = np.where(g < 245)   # trim white margins
        if len(xs):
            p = p.crop((max(xs.min() - 12, 0), max(ys.min() - 12, 0), min(xs.max() + 12, p.width), min(ys.max() + 12, p.height)))
        bw, bh = 800, 600
        s = min((bw - 40) / p.width, (bh - 40) / p.height)
        pic = scaled(p, s)

    def draw(f, n):
        t = f / FPS
        im = background(t + i * 1.5, light, 0.22, 0.5)
        # header
        put_text(im, "MECHANICAL ENGINEERING SKILLS", F("Inter-SemiBold.otf", 24), 110, 58, (148, 163, 184))
        put_text(im, f"{i + 1:02d} / {len(RESEARCH)}", F("Inter-Bold.otf", 30), W - 110 - 120, 52, hexrgb(light))
        ch = pill(label, F("Inter-Bold.otf", 22), (255, 255, 255), hexrgb(dark) + (255,))
        im.alpha_composite(ch, (110, 120))
        # icon pop
        p_ic = ease_back(f / 11)
        paste_center(im, scaled(icon(skill, 300), 0.3 + 0.7 * p_ic), 110 + 130, 380, alpha=clamp01(f / 5))
        # name
        a = clamp01((f - 4) / 8); dx = (1 - ease_out((f - 4) / 10)) * -40
        put_text(im, skill, MONO(52), 110, 560, alpha=a, dx=dx)
        # paper chip
        if f >= 8:
            cp = pill("Paper: " + paper, F("Inter-SemiBold.otf", 26), (255, 255, 255), hexrgb(light) + (255,))
            cp.putalpha(cp.getchannel("A").point(lambda v: int(v * clamp01((f - 8) / 6))))
            im.alpha_composite(cp, (110, 650))
        # tagline
        a = clamp01((f - 11) / 8)
        for k, line in enumerate(wrap(tagline, F("Inter-Bold.otf", 46), 780)):
            put_text(im, line, F("Inter-Bold.otf", 46), 110, 740 + k * 60, alpha=a)
        # visual card
        pc = ease_out((f - 2) / 14)
        cx, cy = 1400 + (1 - pc) * 300, 520
        if pic is not None:
            z = 1 + 0.05 * f / n
            card = rounded_card(840, 640)
            inner = scaled(pic, z)
            box = Image.new("RGBA", (800, 600), (255, 255, 255, 255))
            box.alpha_composite(inner, (int((800 - inner.width) / 2), int((600 - inner.height) / 2)))
            mask = Image.new("L", (800, 600), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, 799, 599), 18, fill=255)
            card.paste(box, (50, 50), mask)
        else:
            card = rounded_card(840, 640, fill=hexrgb(dark) + (255,))
            d = ImageDraw.Draw(card)
            for k in range(4):
                ph = ((t * 0.8 + k / 4) % 1); rr = 120 + ph * 260
                d.ellipse((450 - rr, 350 - rr, 450 + rr, 350 + rr), outline=(255, 255, 255, int(120 * (1 - ph))), width=5)
            ic = icon(skill, 340); card.alpha_composite(ic, (450 - 170, 350 - 170))
        paste_center(im, card, cx, cy, alpha=clamp01((f - 2) / 6))
        # progress bar
        seg = (W - 220) / len(RESEARCH)
        d = ImageDraw.Draw(im)
        for k in range(len(RESEARCH)):
            col = hexrgb(light) + (255,) if k < i else ((255, 255, 255, 255) if k == i else (71, 85, 105, 255))
            w = seg - 8
            if k == i:
                w = (seg - 8) * clamp01(f / n * 1.05)
                d.rounded_rectangle((110 + k * seg, 1010, 110 + k * seg + seg - 8, 1018), 4, fill=(71, 85, 105, 255))
            d.rounded_rectangle((110 + k * seg, 1010, 110 + k * seg + max(w, 1), 1018), 4, fill=col)
        if f < 3:   # cut flash
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(70 * (1 - f / 3)))))
        return im
    return draw


def scene_core(f, n):
    t = f / FPS
    im = background(t, "#64748b", 0.5, 0.5)
    put_text(im, "+ 14 core engineering skills", F("Inter-ExtraBold.otf", 72), W / 2, 90, alpha=clamp01(f / 10), anchor="c")
    put_text(im, "sizing  ·  FEA  ·  tolerances  ·  thermal-fluids  ·  CAD  ·  DFM  ·  teardowns  ·  reports  ·  teaching",
             F("Inter-Medium.otf", 32), W / 2, 200, (203, 213, 225), alpha=clamp01((f - 6) / 10), anchor="c")
    rows = [CORE[:7], CORE[7:]]
    size, gapx = 150, 108
    for r, row in enumerate(rows):
        x0 = (W - (len(row) * size + (len(row) - 1) * gapx)) / 2
        for c, s in enumerate(row):
            k = r * 7 + c
            p = ease_back((f - 10 - k * 5) / 10)
            if f < 10 + k * 5:
                continue
            bob = 6 * math.sin(t * 3 + k)
            cx, cy = x0 + c * (size + gapx) + size / 2, 400 + r * 300 + bob
            paste_center(im, scaled(icon(s, size), 0.3 + 0.7 * p), cx, cy, alpha=clamp01((f - 10 - k * 5) / 5))
            for j, line in enumerate(wrap(s.replace("-", "- "), MONO(22), 230)):
                put_text(im, line.replace("- ", "-"), MONO(22), cx, cy + 92 + j * 28, (226, 232, 240),
                         alpha=clamp01((f - 14 - k * 5) / 6), anchor="c")
    return im


def scene_numbers(f, n):
    t = f / FPS
    im = background(t, "#8b5cf6", 0.5, 0.5)
    stats = [("33", "skills"), ("19", "research papers"), ("1", "command to install"), ("0", "models to run locally")]
    put_text(im, "Engineering, on demand.", F("Inter-ExtraBold.otf", 68), W / 2, 150, alpha=clamp01(f / 10), anchor="c")
    for k, (num, lab) in enumerate(stats):
        st = 12 + k * 18
        if f < st:
            continue
        p = ease_back((f - st) / 12)
        val = int(num); shown = str(int(round(val * clamp01((f - st) / 14)))) if val > 1 else num
        cx = W / 2 + (k - 1.5) * 420
        big = scaled(text_img(shown, F("Inter-Black.otf", 190), hexrgb(["#60a5fa", "#2dd4bf", "#fbbf24", "#f472b6"][k])), 0.5 + 0.5 * p)
        paste_center(im, big, cx, 520, alpha=clamp01((f - st) / 5))
        put_text(im, lab, F("Inter-SemiBold.otf", 36), cx, 660, (226, 232, 240), alpha=clamp01((f - st - 4) / 8), anchor="c")
    a = clamp01((f - 96) / 12)
    put_text(im, "Ask by voice or text in Claude. The tools compute. Every answer comes with its check.",
             F("Inter-Medium.otf", 36), W / 2, 830, (203, 213, 225), alpha=a, anchor="c")
    return im


_banner = None
def scene_end(f, n):
    global _banner
    t = f / FPS
    im = background(t, "#3b82f6", 0.5, 0.42)
    if _banner is None:
        png = cairosvg.svg2png(url=os.path.join(ROOT, "docs", "img", "banner.svg"), output_width=1680)
        _banner = Image.open(io.BytesIO(png)).convert("RGBA")
    z = 0.92 + 0.08 * ease_out(f / 30) + 0.02 * f / n
    paste_center(im, scaled(_banner, z), W / 2, 420, alpha=clamp01(f / 12))
    url = "github.com/BaratiLab/mechanical-engineering-skills"
    k = int(len(url) * clamp01((f - 30) / 45))
    put_text(im, url[:k] + ("▏" if (f // 8) % 2 == 0 and k < len(url) + 1 else ""), MONO(44), W / 2 - MONO(44).getlength(url) / 2, 800, (125, 211, 252))
    put_text(im, "Barati Farimani Lab  ·  Carnegie Mellon University", F("Inter-SemiBold.otf", 32), W / 2, 890,
             (203, 213, 225), alpha=clamp01((f - 80) / 15), anchor="c")
    if f > n - 24:
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * clamp01((f - (n - 24)) / 24)))))
    return im


def drawer(name):
    if name.startswith("skill"):
        return scene_skill(int(name[5:]))
    return {"title": scene_title, "voice": scene_voice, "core": scene_core, "numbers": scene_numbers, "end": scene_end}[name]


# ------------------------------------------------------------------------------------------------
def soundtrack(path, seconds=60.0, sr=44100):
    """120 BPM electronic bed: kick, clap, hats, bass and pad on Am-F-C-G, a riser into the skill
    section and a tick on every skill cut."""
    n = int(seconds * sr); t = np.arange(n) / sr; out = np.zeros(n)
    beat = BEAT
    def env(length, decay):
        x = np.arange(int(length * sr)) / sr; return np.exp(-x / decay)
    def add(sig, start):
        i = int(start * sr); j = min(n, i + len(sig))
        if i < n: out[i:j] += sig[:j - i]
    kick_len = 0.35; kt = np.arange(int(kick_len * sr)) / sr
    kick = np.sin(2 * np.pi * (50 * kt + 60 * (1 - np.exp(-kt / 0.03)) * 0.03 * 10)) * env(kick_len, 0.12)
    rng = np.random.default_rng(0)
    clap = rng.standard_normal(int(0.2 * sr)) * env(0.2, 0.05)
    hat = np.diff(rng.standard_normal(int(0.05 * sr) + 1)) * env(0.05, 0.012)
    chords = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]   # Am F C G (MIDI)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    nb = int(seconds / beat)
    for b in range(nb):
        st = b * beat; sect = st
        intro = sect < 4.0; outro = sect > 57.5
        if not intro and not outro:
            add(kick * 0.9, st)
            if b % 2 == 1:
                add(clap * 0.25, st)
            add(hat * 0.18, st + beat / 2)
        elif intro and b % 2 == 0:
            add(kick * 0.5, st)
        ch = chords[(b // 8) % 4]
        root = hz(ch[0] - 24)
        bl = np.arange(int(beat * sr)) / sr
        bass = np.sign(np.sin(2 * np.pi * root * bl)) * 0.5 + np.sin(2 * np.pi * root * bl)
        add(bass * env(beat, 0.18) * (0.10 if not outro else 0.05), st)
        if b % 8 == 0:   # pad for 4 s
            pl = np.arange(int(4.0 * sr)) / sr
            pad = sum(np.sin(2 * np.pi * hz(m) * pl) + 0.5 * np.sin(2 * np.pi * hz(m) * 1.003 * pl) for m in ch)
            pad *= np.minimum(1, pl / 0.4) * np.minimum(1, (4.0 - pl) / 0.6) * 0.045
            add(pad, st)
        # arpeggio 16ths during the skill section
        if 9.0 <= st < 37.5 or 45 <= st < 51:
            for q in range(4):
                m = ch[(b * 4 + q) % 3] + 12
                al = np.arange(int(beat / 4 * sr)) / sr
                add(np.sin(2 * np.pi * hz(m) * al) * env(beat / 4, 0.05) * 0.06, st + q * beat / 4)
    # riser into the skill section and into the end card
    for s0, s1 in ((7.0, 9.0), (49.0, 51.0)):
        rl = np.arange(int((s1 - s0) * sr)) / sr
        noise = rng.standard_normal(len(rl)) * (rl / rl[-1]) ** 2 * 0.12
        sweep = np.sin(2 * np.pi * (200 * rl + 400 * rl ** 2 / (s1 - s0))) * (rl / rl[-1]) ** 2 * 0.05
        add(noise + sweep, s0)
    for i in range(len(RESEARCH)):   # tick on each skill cut
        tl = np.arange(int(0.06 * sr)) / sr
        add(np.sin(2 * np.pi * 1760 * tl) * env(0.06, 0.015) * 0.12, 9.0 + i * 1.5)
    out *= np.minimum(1, (seconds - t) / 2.5)
    out = np.tanh(out * 1.4) / np.tanh(1.4)
    out = (out / max(1e-9, np.abs(out).max()) * 0.85 * 32767).astype(np.int16)
    st = np.stack([out, out], 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(st.tobytes())


def render_scene(name, beats, out):
    n = int(round(beats * BEAT * FPS))
    draw = drawer(name)
    tmp = out + ".part.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                          "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(draw(f, n).convert("RGB").tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, out)
    else:
        raise RuntimeError(name)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="mechanical_engineering_skills.mp4")
    ap.add_argument("--work", default="/tmp/mes_video")
    ap.add_argument("--still", nargs="*", help="name:frame ... -> PNGs for checking")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    if a.still:
        for s in a.still:
            name, fr = s.split(":")
            beats = dict(SCENES)[name]; n = int(round(beats * BEAT * FPS))
            drawer(name)(int(fr), n).convert("RGB").save(os.path.join(a.work, f"still_{name}_{fr}.png"))
        return
    files = []
    for k, (name, beats) in enumerate(SCENES):
        out = os.path.join(a.work, f"{k:02d}_{name}.mp4")
        render_scene(name, beats, out); files.append(out)
        print("rendered", name, file=sys.stderr)
    lst = os.path.join(a.work, "list.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    soundtrack(os.path.join(a.work, "music.wav"))
    silent = os.path.join(a.work, "silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", os.path.join(a.work, "music.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    print(a.out)


if __name__ == "__main__":
    main()
