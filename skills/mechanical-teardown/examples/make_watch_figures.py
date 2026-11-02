#!/usr/bin/env python3
"""Draw the two illustrations used by automatic_watch.json (vector, no external assets).

    python make_watch_figures.py      -> watch_exploded.svg, watch_train.svg
"""
import math, os

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUT, ACC, BLUE, STEEL, BRASS, RUBY = "#0f172a", "#64748b", "#f97316", "#1e40af", "#94a3b8", "#d4a24c", "#be123c"
FONT = 'font-family="Inter,Helvetica,Arial,sans-serif"'


def gear_path(cx, cy, r, teeth, sy=1.0, depth=None):
    """Toothed outline; sy squashes vertically for an oblique view."""
    depth = depth or max(1.2, r * 0.12)
    pts = []
    for k in range(teeth):
        for f, rr in ((0.0, r - depth), (0.15, r), (0.45, r), (0.6, r - depth)):
            a = 2 * math.pi * (k + f) / teeth
            pts.append(f"{cx + rr * math.cos(a):.1f},{cy + sy * rr * math.sin(a):.1f}")
    return "M" + " L".join(pts) + " Z"


def ell(cx, cy, rx, ry, fill="none", stroke=INK, sw=2, extra=""):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def label(x, y, title, sub, anchor_x):
    return (f'<line x1="{anchor_x}" y1="{y}" x2="{x - 10}" y2="{y}" stroke="{MUT}" stroke-width="1.2" stroke-dasharray="3 3"/>'
            f'<text x="{x}" y="{y - 2}" {FONT} font-size="17" font-weight="700" fill="{INK}">{title}</text>'
            f'<text x="{x}" y="{y + 17}" {FONT} font-size="13.5" fill="{MUT}">{sub}</text>')


def exploded():
    W, H, cx, sy = 1040, 1060, 300, 0.32
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<line x1="{cx}" y1="30" x2="{cx}" y2="{H - 30}" stroke="{MUT}" stroke-width="1.2" stroke-dasharray="6 6"/>']
    lx = 545
    y = 70
    # bezel
    o.append(ell(cx, y, 150, 150 * sy, fill="#1e293b", stroke=INK, sw=2))
    o.append(ell(cx, y, 122, 122 * sy, fill="#ffffff", stroke=INK, sw=2))
    for k in range(60):
        a = 2 * math.pi * k / 60
        r1, r2 = 126, (146 if k % 5 == 0 else 138)
        o.append(f'<line x1="{cx + r1 * math.cos(a):.1f}" y1="{y + sy * r1 * math.sin(a):.1f}" x2="{cx + r2 * math.cos(a):.1f}" '
                 f'y2="{y + sy * r2 * math.sin(a):.1f}" stroke="#e2e8f0" stroke-width="{2 if k % 5 == 0 else 1}"/>')
    o.append(f'<circle cx="{cx}" cy="{y - 136 * sy}" r="5" fill="#a7f3d0" stroke="{INK}" stroke-width="1.2"/>')
    o.append(label(lx, y, "Unidirectional bezel", "316L, 120-click spring underneath", cx + 160))
    # crystal
    y = 165
    o.append(ell(cx, y, 120, 120 * sy, fill="#dbeafe", stroke=BLUE, sw=2, extra='fill-opacity="0.7"'))
    o.append(f'<path d="M{cx - 70},{y - 14} q40,-14 90,-6" stroke="#ffffff" stroke-width="5" fill="none" stroke-linecap="round"/>')
    o.append(ell(cx, y + 6, 121, 121 * sy, stroke=INK, sw=1.2))
    o.append(label(lx, y, "Sapphire crystal + gasket", "AR coated; compressed rubber ring seals it", cx + 130))
    # case middle with lugs and crown
    y = 285
    for dx in (-1, 1):
        for dy in (-1, 1):
            o.append(f'<path d="M{cx + dx * 92},{y + dy * 22} L{cx + dx * 120},{y + dy * 74} L{cx + dx * 92},{y + dy * 80} '
                     f'L{cx + dx * 64},{y + dy * 30} Z" fill="#e2e8f0" stroke="{INK}" stroke-width="2"/>')
    o.append(ell(cx, y + 18, 140, 140 * sy, fill="#cbd5e1", stroke=INK))
    o.append(f'<rect x="{cx - 140}" y="{y}" width="280" height="18" fill="#cbd5e1"/>')
    o.append(ell(cx, y, 140, 140 * sy, fill="#e2e8f0", stroke=INK))
    o.append(ell(cx, y, 118, 118 * sy, fill="#f8fafc", stroke=INK, sw=1.5))
    o.append(f'<rect x="{cx + 138}" y="{y - 2}" width="34" height="26" rx="5" fill="#cbd5e1" stroke="{INK}" stroke-width="2"/>')
    for k in range(5):
        o.append(f'<line x1="{cx + 146 + 5 * k}" y1="{y}" x2="{cx + 146 + 5 * k}" y2="{y + 22}" stroke="{INK}" stroke-width="1"/>')
    o.append(label(lx, y + 4, "Case middle, lugs, screw-down crown", "316L forged + CNC; crown seals on two gaskets", cx + 180))
    # strap halves (to the left)
    o.append(f'<path d="M60,{y - 130} h70 v100 h-70 z" fill="#1f2937" stroke="{INK}" stroke-width="2"/>')
    o.append(f'<path d="M60,{y + 110} h70 v120 h-70 z" fill="#1f2937" stroke="{INK}" stroke-width="2"/>')
    for k in range(4):
        o.append(f'<circle cx="95" cy="{y + 140 + 24 * k}" r="4" fill="#94a3b8"/>')
    o.append(f'<text x="95" y="{y - 140}" text-anchor="middle" {FONT} font-size="13" fill="{MUT}">strap + spring bars</text>')
    # hands
    y = 410
    o.append(ell(cx, y, 6, 3, fill=INK, stroke=INK))
    o.append(f'<path d="M{cx},{y} L{cx - 58},{y - 14}" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>')
    o.append(f'<path d="M{cx},{y} L{cx + 92},{y - 22}" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>')
    o.append(f'<path d="M{cx - 30},{y + 6} L{cx + 70},{y - 20}" stroke="{ACC}" stroke-width="2"/>')
    o.append(f'<path d="M{cx - 45},{y - 11} L{cx - 30},{y - 7}" stroke="#a7f3d0" stroke-width="4" stroke-linecap="round"/>')
    o.append(label(lx, y, "Hands (hour, minute, seconds)", "Pressed onto hour wheel, cannon pinion, fourth arbor", cx + 110))
    # dial
    y = 490
    o.append(ell(cx, y, 116, 116 * sy, fill="#0f172a", stroke=INK))
    for k in range(12):
        a = 2 * math.pi * k / 12
        r1, r2 = 92, 108
        o.append(f'<line x1="{cx + r1 * math.cos(a):.1f}" y1="{y + sy * r1 * math.sin(a):.1f}" x2="{cx + r2 * math.cos(a):.1f}" '
                 f'y2="{y + sy * r2 * math.sin(a):.1f}" stroke="#a7f3d0" stroke-width="{5 if k % 3 == 0 else 3}"/>')
    o.append(f'<rect x="{cx + 70}" y="{y - 6}" width="18" height="12" fill="#ffffff" stroke="{MUT}"/>')
    o.append(label(lx, y, "Dial with lumed indices", "Brass, printed; date window at 3", cx + 125))
    # date disc + holding plate
    y = 565
    o.append(ell(cx, y, 110, 110 * sy, fill="#ffffff", stroke=INK))
    o.append(ell(cx, y, 92, 92 * sy, fill="#f1f5f9", stroke=INK, sw=1.2))
    o.append(label(lx, y, "Date disc and motion works", "Cannon pinion, minute and hour wheels, date jumper", cx + 120))
    # movement
    y = 680
    o.append(f'<rect x="{cx - 120}" y="{y}" width="240" height="22" fill="#e9c46a"/>')
    o.append(ell(cx, y + 22, 120, 120 * sy, fill="#e9c46a", stroke=INK))
    o.append(ell(cx, y, 120, 120 * sy, fill="#f4d58d", stroke=INK))
    o.append(f'<path d="{gear_path(cx - 40, y - 4, 34, 40, sy)}" fill="{BRASS}" stroke="{INK}" stroke-width="1.2"/>')
    o.append(f'<path d="{gear_path(cx + 22, y + 8, 22, 30, sy)}" fill="{BRASS}" stroke="{INK}" stroke-width="1.2"/>')
    o.append(f'<path d="{gear_path(cx + 60, y - 10, 14, 15, sy, 3)}" fill="#cbd5e1" stroke="{INK}" stroke-width="1.2"/>')
    o.append(ell(cx + 62, y + 18, 26, 26 * sy, fill="none", stroke=INK, sw=2))
    for k in range(4):
        a = 2 * math.pi * k / 4 + 0.4
        o.append(f'<line x1="{cx + 62}" y1="{y + 18}" x2="{cx + 62 + 26 * math.cos(a):.1f}" y2="{y + 18 + sy * 26 * math.sin(a):.1f}" stroke="{INK}" stroke-width="1"/>')
    for (dx, dy) in ((-80, 10), (-10, -22), (40, 22), (90, -4), (-60, -20)):
        o.append(f'<circle cx="{cx + dx}" cy="{y + dy}" r="3.2" fill="{RUBY}"/>')
    o.append(label(lx, y + 8, "Movement, about 130 parts", "Plate + bridges, barrel, 4-wheel train, lever escapement,", cx + 130))
    o.append(f'<text x="{lx}" y="{y + 43}" {FONT} font-size="13.5" fill="{MUT}">balance and hairspring, keyless works; jewels in red</text>')
    # rotor
    y = 810
    o.append(f'<path d="M{cx - 112},{y} A112,{112 * sy} 0 0 0 {cx + 112},{y} L{cx + 70},{y} A70,{70 * sy} 0 0 1 {cx - 70},{y} Z" '
             f'fill="{BRASS}" stroke="{INK}" stroke-width="2"/>')
    o.append(f'<path d="M{cx - 70},{y} L{cx},{y} L{cx + 70},{y}" stroke="{INK}" stroke-width="2" fill="none"/>')
    o.append(ell(cx, y, 12, 12 * sy, fill="#cbd5e1", stroke=INK))
    o.append(label(lx, y + 14, "Oscillating weight (rotor)", "On a ball bearing; pawl lever winds both ways", cx + 120))
    # caseback
    y = 930
    o.append(f'<rect x="{cx - 125}" y="{y}" width="250" height="16" fill="#cbd5e1"/>')
    o.append(ell(cx, y + 16, 125, 125 * sy, fill="#cbd5e1", stroke=INK))
    o.append(ell(cx, y, 125, 125 * sy, fill="#e2e8f0", stroke=INK))
    o.append(ell(cx, y, 100, 100 * sy, fill="#f8fafc", stroke=INK, sw=1.2))
    for k in range(6):
        a = 2 * math.pi * k / 6
        o.append(f'<rect x="{cx + 112 * math.cos(a) - 5:.1f}" y="{y + sy * 112 * math.sin(a) - 3:.1f}" width="10" height="6" fill="{INK}"/>')
    o.append(ell(cx, y - 18, 104, 104 * sy, fill="none", stroke="#16a34a", sw=3))
    o.append(label(lx, y, "Screw-down caseback + gasket", "Six wrench slots; the green ring is the seal", cx + 135))
    o.append(f'<text x="30" y="{H - 20}" {FONT} font-size="13" fill="{MUT}">Illustration of a generic automatic diver; not to scale.</text>')
    o.append("</svg>")
    return "".join(o)


def train():
    W, H = 1140, 470
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<text x="30" y="38" {FONT} font-size="20" font-weight="800" fill="{INK}">Energy and time through the movement</text>',
         f'<text x="30" y="62" {FONT} font-size="14" fill="{MUT}">wheel teeth / next pinion leaves; speed of each arbor; total reduction barrel to escape wheel 1 : 5,760</text>']
    # (name, teeth, pinion, speed text, role, radius, fill)
    items = [("Barrel", 80, None, "1 turn / 8 h", "stores ~41 h", 62, BRASS),
             ("Centre", 64, 10, "1 turn / h", "minute hand", 52, BRASS),
             ("Third", 75, 8, "8 turns / h", "", 44, BRASS),
             ("Fourth", 84, 10, "1 turn / min", "seconds hand", 48, BRASS),
             ("Escape", 15, 7, "12 turns / min", "2 beats per tooth", 30, STEEL)]
    x, cy = 110, 230
    centres = []
    for k, (n, t, p, sp, role, r, col) in enumerate(items):
        o.append(f'<path d="{gear_path(x, cy, r, min(t, 48), 1.0, 5 if t < 30 else 4)}" fill="{col}" stroke="{INK}" stroke-width="1.5"/>')
        if p:
            o.append(f'<path d="{gear_path(x, cy, 11, p, 1.0, 3)}" fill="#e2e8f0" stroke="{INK}" stroke-width="1.2"/>')
        o.append(f'<circle cx="{x}" cy="{cy}" r="3" fill="{RUBY}"/>')
        o.append(f'<text x="{x}" y="{cy + r + 30}" text-anchor="middle" {FONT} font-size="17" font-weight="800" fill="{INK}">{n}</text>')
        o.append(f'<text x="{x}" y="{cy + r + 50}" text-anchor="middle" {FONT} font-size="14" fill="{INK}">{t} T' + (f" / {p} leaves" if p else "") + '</text>')
        o.append(f'<text x="{x}" y="{cy + r + 69}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{BLUE}">{sp}</text>')
        if role:
            o.append(f'<text x="{x}" y="{cy + r + 87}" text-anchor="middle" {FONT} font-size="13" fill="{MUT}">{role}</text>')
        centres.append((x, r))
        x += r + (items[k + 1][5] if k + 1 < len(items) else 40) + 52
    for k in range(len(centres) - 1):
        (x1, r1), (x2, r2) = centres[k], centres[k + 1]
        ratio = items[k][1] / items[k + 1][2]
        mx = (x1 + r1 + x2 - r2) / 2
        o.append(f'<path d="M{x1 + r1 + 4},{cy - 92} L{x2 - r2 - 4},{cy - 92}" stroke="{ACC}" stroke-width="3" marker-end="url(#a)"/>')
        o.append(f'<text x="{mx}" y="{cy - 102}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{ACC}">x {ratio:g}</text>')
    o.insert(2, f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{ACC}"/></marker></defs>')
    # pallet fork and balance
    xe, re_ = centres[-1]
    xp = xe + re_ + 88
    o.append(f'<path d="M{xp - 34},{cy - 18} L{xp},{cy} L{xp - 34},{cy + 18} M{xp},{cy} L{xp + 60},{cy}" stroke="{INK}" stroke-width="5" fill="none" stroke-linecap="round"/>')
    o.append(f'<rect x="{xp - 40}" y="{cy - 24}" width="9" height="9" fill="{RUBY}"/><rect x="{xp - 40}" y="{cy + 15}" width="9" height="9" fill="{RUBY}"/>')
    o.append(f'<text x="{xp + 10}" y="{cy + 64}" text-anchor="middle" {FONT} font-size="17" font-weight="800" fill="{INK}">Pallet fork</text>')
    o.append(f'<text x="{xp + 10}" y="{cy + 84}" text-anchor="middle" {FONT} font-size="13" fill="{MUT}">locks and unlocks</text>')
    xb = xp + 185
    o.append(f'<circle cx="{xb}" cy="{cy}" r="58" fill="none" stroke="{INK}" stroke-width="5"/>')
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.5
        o.append(f'<line x1="{xb}" y1="{cy}" x2="{xb + 58 * math.cos(a):.1f}" y2="{cy + 58 * math.sin(a):.1f}" stroke="{INK}" stroke-width="3"/>')
    spiral = []
    for k in range(240):
        th = k / 240 * 2 * math.pi * 6
        rr = 6 + 32 * k / 240
        spiral.append(f"{xb + rr * math.cos(th):.1f},{cy + rr * math.sin(th):.1f}")
    o.append(f'<path d="M{" L".join(spiral)}" fill="none" stroke="{BLUE}" stroke-width="1.3"/>')
    o.append(f'<text x="{xb}" y="{cy + 92}" text-anchor="middle" {FONT} font-size="17" font-weight="800" fill="{INK}">Balance + hairspring</text>')
    o.append(f'<text x="{xb}" y="{cy + 112}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{BLUE}">3 Hz = 21,600 beats / h</text>')
    o.append(f'<text x="{xb}" y="{cy + 130}" text-anchor="middle" {FONT} font-size="13" fill="{MUT}">sets the rate</text>')
    o.append(f'<path d="M{xe + re_ + 6},{cy - 92} L{xb - 20},{cy - 92}" stroke="{ACC}" stroke-width="3" stroke-dasharray="6 5" marker-end="url(#a)"/>')
    o.append(f'<text x="{(xe + xb) / 2 + 20}" y="{cy - 102}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{ACC}">impulse each beat</text>')
    # rotor input
    xb0 = centres[0][0]
    o.append(f'<text x="{xb0}" y="{cy - 132}" text-anchor="middle" {FONT} font-size="14" font-weight="700" fill="{INK}">rotor + pawl lever, crown</text>')
    o.append(f'<path d="M{xb0},{cy - 122} L{xb0},{cy - 72}" stroke="{INK}" stroke-width="3" marker-end="url(#b)"/>')
    o.insert(3, f'<defs><marker id="b" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>')
    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    for name, svg in (("watch_exploded.svg", exploded()), ("watch_train.svg", train())):
        with open(os.path.join(HERE, name), "w") as f:
            f.write(svg)
        print("wrote", name)
