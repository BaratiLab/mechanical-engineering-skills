#!/usr/bin/env python3
"""Conceptual Figure 1 of the paper (vector): engineer -> Claude + skills -> checked deliverables.
Writes paper/figures/concept.svg and paper/figures/concept.pdf.  Run: python tools/make_concept_figure.py"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import make_icons as M

ROOT = os.path.join(os.path.dirname(__file__), "..")
FONT = "DejaVu Sans, Helvetica, Arial, sans-serif"
W, H = 1600, 860
parts = []
add = parts.append


def text(x, y, s, size=18, weight="normal", fill="#0f172a", anchor="start", style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'font-style="{style}" fill="{fill}" text-anchor="{anchor}">{s}</text>')


def rrect(x, y, w, h, r=16, fill="#fff", stroke="#cbd5e1", sw=2, extra=""):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>')


def icon(skill, x, y, size):
    inner = M.tile(skill).split(">", 1)[1].rsplit("</svg>", 1)[0].replace('id="g-', f'id="c{int(x)}{int(y)}-').replace('url(#g-', f'url(#c{int(x)}{int(y)}-')
    add(f'<g transform="translate({x},{y}) scale({size/96})">{inner}</g>')


def arrow(x1, y1, x2, y2, color="#334155", sw=4, dash=""):
    d = f'stroke-dasharray="{dash}"' if dash else ""
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" {d} marker-end="url(#ah)"/>')


add(f'''<defs>
<marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#334155"/></marker>
<linearGradient id="hub" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d97757"/><stop offset="1" stop-color="#b85c3e"/></linearGradient>
<linearGradient id="panel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f8fafc"/><stop offset="1" stop-color="#eef2f7"/></linearGradient>
</defs>''')
rrect(0, 0, W, H, 0, "#ffffff", "none", 0)

# ---------------- left: engineer, voice or text ----------------
rrect(24, 150, 300, 530, 22, "#f8fafc", "#cbd5e1")
text(174, 196, "Engineer", 26, "bold", anchor="middle")
# engineer: hard hat, face, work shirt with hi-vis vest, wrench
add('''<g>
  <path d="M96,374 C96,326 132,306 174,306 C216,306 252,326 252,374 Z" fill="#1d4ed8"/>
  <path d="M120,374 L120,322 C132,314 144,310 156,309 L174,352 L192,309 C204,310 216,314 228,322 L228,374 Z" fill="#f97316"/>
  <path d="M121,344 H160 M188,344 H227 M121,358 H164 M184,358 H227" stroke="#fde68a" stroke-width="5"/>
  <path d="M156,309 L174,352 L192,309 Z" fill="#dbeafe"/>
  <rect x="160" y="290" width="28" height="22" fill="#d6a77a"/>
  <ellipse cx="174" cy="266" rx="32" ry="35" fill="#e8b98a"/>
  <circle cx="162" cy="268" r="3.5" fill="#1f2937"/><circle cx="186" cy="268" r="3.5" fill="#1f2937"/>
  <path d="M163,284 Q174,292 185,284" stroke="#9a3412" stroke-width="3" fill="none" stroke-linecap="round"/>
  <path d="M140,252 C140,222 156,208 174,208 C192,208 208,222 208,252 Z" fill="#facc15"/>
  <path d="M174,208 V250" stroke="#eab308" stroke-width="6"/>
  <rect x="130" y="248" width="88" height="11" rx="5.5" fill="#eab308"/>
  <g transform="translate(232,300) rotate(40)">
    <rect x="-5" y="-6" width="10" height="56" rx="4" fill="#94a3b8"/>
    <path d="M-14,-14 a14,14 0 1 0 28,0 l-6,0 l0,8 l-16,0 l0,-8 z" fill="#94a3b8"/>
  </g>
</g>''')
# voice chip
rrect(52, 398, 116, 54, 27, "#e0f2fe", "#0284c7")
add('<rect x="74" y="410" width="14" height="22" rx="7" fill="#0284c7"/><path d="M68,424 a13,13 0 0 0 26,0 M81,437 v6" stroke="#0284c7" stroke-width="3" fill="none" stroke-linecap="round"/>')
text(126, 432, "Voice", 19, "bold", "#0369a1", "middle")
# text chip
rrect(180, 398, 116, 54, 27, "#e0f2fe", "#0284c7")
add('<rect x="196" y="413" width="30" height="20" rx="3" fill="none" stroke="#0284c7" stroke-width="3"/><path d="M201,420 h4 M209,420 h4 M217,420 h4 M203,427 h16" stroke="#0284c7" stroke-width="2.5" stroke-linecap="round"/>')
text(260, 432, "Text", 19, "bold", "#0369a1", "middle")
# request bubble
rrect(44, 476, 260, 168, 16, "#ffffff", "#94a3b8")
for i, line in enumerate(["“Design a light lattice", "for a 10 mm cell that is", "2.5× stiffer vertically,", "printable in PLA.”"]):
    text(174, 512 + i * 30, line, 19, style="italic", fill="#1e293b", anchor="middle")
text(174, 706, "no tool training · no local models", 16, fill="#64748b", anchor="middle")

# ---------------- centre: Claude + skills ----------------
add(f'<rect x="372" y="40" width="856" height="622" rx="26" fill="url(#panel)" stroke="#94a3b8" stroke-width="2.5"/>')
text(800, 84, "Claude  +  Mechanical Engineering Skills", 30, "bold", anchor="middle")
# hub
add('<rect x="540" y="104" width="520" height="108" rx="54" fill="url(#hub)"/>')
text(800, 140, "Claude agent", 24, "bold", "#ffffff", "middle")
text(800, 170, "understand · select · orchestrate · explain", 18, fill="#ffffff", anchor="middle")
text(800, 196, "loads a skill only when a request needs it", 15, fill="#ffedd5", anchor="middle")

groups = [("Design &amp; CAD", M.AREAS["mech"][0], ["cadsmith-text-to-cad", "query2cad-freecad", "parametric-part-cad", "sketch-to-cad", "drawing-gdt-review", "linkage-synthesis", "rocketsmith", "llm-mechanical-designer", "machine-element-sizing"]),
          ("Analysis &amp; simulation", M.AREAS["analysis"][0], ["cfd-simulation-setup", "stress-field-surrogate", "lattice-inverse-design", "equation-discovery", "quick-fea", "tolerance-stackup", "thermal-fluids-calc", "material-selection", "design-review-package", "engineering-calc-report", "worked-problem-generator", "mechanics-visuals"]),
          ("Manufacturing", M.AREAS["dfm"][0], ["agentscad-fdm-dfam", "dfm-review", "image2gcode", "lpbf-defect-prediction", "am-alloy-screening", "sls-process-optimization", "meltpool-geometry", "llm-3d-print-monitor", "thermal-porosity", "lpbf-superres", "am-literature-rag"])]
cx = [400, 674, 948]
cw = 252
size, gap = 56, 6
for (title, col, sk), x0 in zip(groups, cx):
    rrect(x0, 254, cw, 272, 18, "#ffffff", col, 2.5)
    text(x0 + cw / 2, 288, title, 19, "bold", col, "middle")
    cols = 4
    gx = x0 + (cw - (cols * size + (cols - 1) * gap)) / 2
    for i, s in enumerate(sk):
        r, c = divmod(i, cols)
        icon(s, gx + c * (size + gap), 308 + r * (size + gap), size)
    # connector hub -> card
    add(f'<path d="M800,210 C800,232 {x0+cw/2},232 {x0+cw/2},252" stroke="{col}" stroke-width="3" fill="none"/>')
text(800, 560, "32 skills · 19 package Barati Farimani Lab papers", 20, "bold", "#334155", "middle")
# anatomy strip
pills = [("SKILL.md", "when &amp; how to use"), ("scripts/", "tested tools compute"), ("tests/ + notes", "checks &amp; provenance")]
for i, (a, b) in enumerate(pills):
    x = 404 + i * 274
    rrect(x, 580, 252, 58, 29, "#fff7ed", "#f59e0b", 2)
    text(x + 126, 606, a, 18, "bold", "#9a3412", "middle")
    text(x + 126, 629, b, 16, fill="#9a3412", anchor="middle")

# ---------------- right: deliverables ----------------
rrect(1276, 150, 300, 530, 22, "#f0fdf4", "#22c55e")
text(1426, 196, "Checked results", 26, "bold", "#166534", "middle")
outs = [("CAD models", "STEP · STL"), ("Simulations", "FEA · CFD · flight"), ("Process plans", "G-code · process maps"), ("Designs", "lattices · linkages · rockets"), ("Reports", "calcs · plots · reviews")]
for i, (a, b) in enumerate(outs):
    y = 224 + i * 76
    rrect(1298, y, 256, 62, 12, "#ffffff", "#86efac", 2)
    add(f'<circle cx="1328" cy="{y+31}" r="15" fill="#22c55e"/><path d="M1320,{y+31} l6,6 l10,-12" stroke="#fff" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    text(1354, y + 27, a, 19, "bold", "#14532d")
    text(1354, y + 50, b, 15, fill="#166534")
text(1426, 618, "each with its evidence:", 16, fill="#166534", anchor="middle")
text(1426, 642, "hand calc · exact case", 16, "bold", "#166534", "middle")
text(1426, 662, "or re-simulation", 16, "bold", "#166534", "middle")

# ---------------- arrows ----------------
arrow(326, 300, 554, 160)
arrow(1046, 160, 1270, 300)

# ---------------- bottom: research -> skills ----------------
rrect(372, 712, 856, 112, 20, "#f5f3ff", "#8b5cf6", 2)
text(800, 744, "Research papers packaged as skills", 20, "bold", "#5b21b6", "middle")
papers = ["CADSmith", "LinkD", "RocketSmith", "CFD Forge", "StressD", "GLU3D", "LLM-SR", "AdditiveLLM", "+ 11 more"]
x = 392
for p in papers:
    w = 12 + len(p) * 8.9
    if x + w > 1212:
        break
    rrect(x, 764, w, 36, 18, "#ffffff", "#a78bfa", 1.5)
    text(x + w / 2, 788, p, 14, fill="#4c1d95", anchor="middle")
    x += w + 8
add('<line x1="800" y1="710" x2="800" y2="672" stroke="#8b5cf6" stroke-width="4" marker-end="url(#ah)"/>')
text(98, 752, "Runs in Claude.ai, Claude Code", 17, fill="#475569")
text(98, 778, "and other Agent Skills hosts", 17, fill="#475569")
text(1300, 752, "Install once:", 17, fill="#475569")
text(1300, 778, "npx skills add", 17, "bold", "#475569")
text(1300, 802, "BaratiLab/mechanical-…", 15, fill="#475569")

svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">' + "\n".join(parts) + "</svg>"
out = os.path.join(ROOT, "paper", "figures")
open(os.path.join(out, "concept.svg"), "w").write(svg)
import cairosvg
cairosvg.svg2pdf(bytestring=svg.encode(), write_to=os.path.join(out, "concept.pdf"))
cairosvg.svg2png(bytestring=svg.encode(), write_to="/tmp/concept.png", output_width=1600)
print("ok")
