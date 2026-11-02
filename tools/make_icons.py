#!/usr/bin/env python3
"""Generate the skill icons (docs/icons/*.svg) and the README banner (docs/img/banner.svg).

One flat, two-tone tile per skill: the colour says the area, the white glyph says what it does.
Run: python tools/make_icons.py
"""
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "docs", "icons")

AREAS = {   # area: (dark, light, label)
    "cad":        ("#3730a3", "#6366f1", "CAD"),
    "mech":       ("#1e40af", "#3b82f6", "Mechanisms & structures"),
    "analysis":   ("#115e59", "#14b8a6", "Analysis & simulation"),
    "decide":     ("#334155", "#64748b", "Decisions & documentation"),
    "dfm":        ("#9a3412", "#f97316", "Design for manufacture"),
    "process":    ("#92400e", "#f59e0b", "Process planning"),
    "monitor":    ("#9d174d", "#ec4899", "In-process monitoring"),
    "knowledge":  ("#5b21b6", "#8b5cf6", "Knowledge"),
    "teach":      ("#166534", "#22c55e", "Teaching"),
}

S = 'stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"'
T = 'stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"'
F = 'fill="#fff"'
W = 'fill="#fff" fill-opacity="0.35"'


def cube(cx, cy, r):
    h = r * 0.5
    return (f'<path {S} d="M{cx},{cy-r} L{cx+r},{cy-h} L{cx+r},{cy+h} L{cx},{cy+r} L{cx-r},{cy+h} '
            f'L{cx-r},{cy-h} Z M{cx-r},{cy-h} L{cx},{cy} L{cx+r},{cy-h} M{cx},{cy} L{cx},{cy+r}"/>')


G = {
    # ---------------- design ----------------
    "cadsmith-text-to-cad": ("cad", "Text → validated CAD", f'''
        <path {S} d="M18,24 H40 M18,33 H34 M18,42 H38"/>
        <path {T} d="M40,52 l8,0 m-3,-3 l3,3 l-3,3"/>
        {cube(64, 58, 16)}'''),
    "query2cad-freecad": ("cad", "Text → FreeCAD macro", f'''
        <path {S} d="M18,22 H66 a6,6 0 0 1 6,6 V48 a6,6 0 0 1 -6,6 H38 L28,64 V54 H24 a6,6 0 0 1 -6,-6 V28 a6,6 0 0 1 6,-6 Z"/>
        {cube(46, 38, 10)}
        <circle cx="72" cy="70" r="8" {S}/><path {S} d="M72,62 v-3 M72,78 v3 M64,70 h-3 M80,70 h3"/>'''),
    "parametric-part-cad": ("cad", "Spec → parametric part", f'''
        <path {S} d="M22,30 H40 V58 H70 V72 H22 Z"/>
        <circle cx="31" cy="44" r="4" {S}/>
        <path {T} d="M22,20 H40 M22,16 v8 M40,16 v8 M78,58 V72 M74,58 h8 M74,72 h8"/>'''),
    "sketch-to-cad": ("cad", "Sketch / photo → CAD", f'''
        <path {S} d="M18,62 C24,48 30,70 36,56 S46,50 50,58"/>
        <path {S} d="M28,40 L50,18 L58,26 L36,48 L26,50 Z M46,22 l8,8"/>
        {cube(66, 60, 13)}'''),
    "drawing-gdt-review": ("cad", "Drawing & GD&T audit", f'''
        <rect x="16" y="30" width="64" height="20" rx="2" {S}/>
        <path {S} d="M36,30 V50 M58,30 V50"/>
        <circle cx="26" cy="40" r="6" {T}/><path {T} d="M26,31 v18 M17,40 h18"/>
        <path {T} d="M41,40 h12"/><path {T} d="M66,35 l4,10 l4,-10"/>
        <path {S} d="M34,66 l8,8 l16,-16"/>'''),
    "linkage-synthesis": ("mech", "Target path → linkage", f'''
        <path {T} stroke-dasharray="3 5" d="M52,26 C70,16 84,30 74,40 C66,48 50,44 52,26 Z"/>
        <path {S} d="M24,68 L30,44 L62,36 L66,68"/>
        <circle cx="30" cy="44" r="3.5" {F}/><circle cx="62" cy="36" r="3.5" {F}/>
        <path {S} d="M30,44 L58,30"/><circle cx="58" cy="30" r="3.5" {F}/>
        <path {S} d="M18,74 h14 l-7,-6 z M59,74 h14 l-7,-6 z"/>'''),
    "rocketsmith": ("mech", "Printed rockets: stability & flight", f'''
        <path {S} d="M48,14 C58,24 60,38 58,56 H38 C36,38 38,24 48,14 Z"/>
        <circle cx="48" cy="34" r="5" {S}/>
        <path {S} d="M38,48 L28,62 L38,60 M58,48 L68,62 L58,60"/>
        <path {S} d="M42,64 l-2,10 M48,64 v14 M54,64 l2,10"/>'''),
    "llm-mechanical-designer": ("mech", "LLM ↔ FEM truss design", f'''
        <path {S} d="M18,62 H78 L64,38 H32 Z M32,38 L48,62 L64,38"/>
        <path {S} d="M18,62 l-4,8 h8 z M78,62 l-4,8 h8 z"/>
        <path {S} d="M48,16 V30 m-5,-5 l5,5 l5,-5"/>'''),
    "machine-element-sizing": ("mech", "Bolts, shafts, gears, springs", f'''
        <path {S} d="M48,18 l5,6 l8,-2 l2,8 l8,2 l-2,8 l6,5 l-6,5 l2,8 l-8,2 l-2,8 l-8,-2 l-5,6 l-5,-6 l-8,2 l-2,-8 l-8,-2 l2,-8 l-6,-5 l6,-5 l-2,-8 l8,-2 l2,-8 l8,2 Z"/>
        <circle cx="48" cy="47" r="10" {S}/>'''),
    "cfd-simulation-setup": ("analysis", "OpenFOAM setup & diagnosis", f'''
        <ellipse cx="44" cy="48" rx="14" ry="9" {S}/>
        <path {T} d="M14,30 C30,30 34,32 44,34 S66,30 82,30 M14,48 H26 M62,48 H82 M14,66 C30,66 34,64 44,62 S66,66 82,66"/>
        <path {T} d="M76,26 l6,4 l-6,4"/>'''),
    "stress-field-surrogate": ("analysis", "Instant stress fields", f'''
        <path {S} d="M18,20 V76"/><path {T} d="M18,28 l-6,6 M18,40 l-6,6 M18,52 l-6,6 M18,64 l-6,6"/>
        <rect x="18" y="38" width="58" height="20" {S}/>
        <path d="M20,40 h18 v16 h-18 z" {W}/><path d="M38,40 h14 v16 h-14 z" fill="#fff" fill-opacity="0.18"/>
        <path {S} d="M76,22 V36 m-5,-5 l5,5 l5,-5"/>'''),
    "lattice-inverse-design": ("analysis", "Target stiffness → lattice", f'''
        {cube(48, 48, 28)}
        <ellipse cx="48" cy="34" rx="9" ry="4.5" {T}/>
        <ellipse cx="34" cy="57" rx="5" ry="8" transform="rotate(-28 34 57)" {T}/>
        <ellipse cx="62" cy="57" rx="5" ry="8" transform="rotate(28 62 57)" {T}/>'''),
    "equation-discovery": ("analysis", "Data → interpretable equations", f'''
        <path {S} d="M18,18 V76 H80"/>
        <circle cx="28" cy="66" r="2.5" {F}/><circle cx="36" cy="58" r="2.5" {F}/><circle cx="46" cy="50" r="2.5" {F}/>
        <circle cx="54" cy="40" r="2.5" {F}/><circle cx="64" cy="34" r="2.5" {F}/><circle cx="74" cy="30" r="2.5" {F}/>
        <path {S} d="M24,70 C40,52 56,32 78,28"/>
        <text x="30" y="34" font-family="Georgia,serif" font-style="italic" font-size="16" fill="#fff">f(x)</text>'''),
    "quick-fea": ("analysis", "Quick FEA + hand check", f'''
        <path {S} d="M18,70 L36,24 L60,30 L78,64 Z"/>
        <path {T} d="M36,24 L44,52 L18,70 M44,52 L60,30 M44,52 L78,64 M44,52 L54,68"/>
        <circle cx="44" cy="52" r="3" {F}/>'''),
    "tolerance-stackup": ("analysis", "Tolerance stack-ups", f'''
        <rect x="16" y="60" width="22" height="14" {S}/><rect x="38" y="60" width="16" height="14" {S}/><rect x="54" y="60" width="26" height="14" {S}/>
        <path {S} d="M22,50 C34,50 38,18 48,18 S62,50 74,50"/>
        <path {T} d="M48,18 V54"/>'''),
    "thermal-fluids-calc": ("analysis", "Pipes, heat exchangers, fins", f'''
        <path {S} d="M14,34 H58 M14,58 H58"/>
        <path {T} d="M18,46 H46 m-6,-5 l6,5 l-6,5"/>
        <path {S} d="M72,20 a6,6 0 0 1 6,6 V54 a10,10 0 1 1 -12,0 V26 a6,6 0 0 1 6,-6 Z"/>
        <circle cx="72" cy="63" r="5" {F}/><path {S} d="M72,62 V36"/>'''),
    "material-selection": ("decide", "Ashby charts & indices", f'''
        <path {S} d="M18,18 V76 H80"/>
        <ellipse cx="34" cy="60" rx="9" ry="6" {W}/><ellipse cx="54" cy="44" rx="10" ry="7" {W}/><ellipse cx="68" cy="28" rx="8" ry="6" {W}/>
        <path {T} stroke-dasharray="4 4" d="M22,72 L78,22"/>
        <circle cx="54" cy="44" r="3" {F}/>'''),
    "design-review-package": ("decide", "Requirements, FMEA, BOM", f'''
        <rect x="22" y="20" width="52" height="60" rx="5" {S}/>
        <path {S} d="M38,16 h20 v8 h-20 z"/>
        <path {T} d="M30,38 l3,3 l6,-6 M30,52 l3,3 l6,-6 M30,66 l3,3 l6,-6 M46,38 h18 M46,52 h18 M46,66 h14"/>'''),
    "engineering-calc-report": ("decide", "Calc reports for sign-off", f'''
        <path {S} d="M24,16 H58 L72,30 V80 H24 Z M58,16 V30 H72"/>
        <text x="31" y="56" font-family="Georgia,serif" font-size="24" fill="#fff">Σ</text>
        <path {T} d="M50,46 h14 M50,54 h10 M32,68 h32"/>'''),
    # ---------------- manufacturing ----------------
    "agentscad-fdm-dfam": ("dfm", "Make STEP parts printable", f'''
        <path {S} d="M14,76 H82"/>
        <path {S} d="M24,70 V34 H72 V70 Z"/>
        <path {S} d="M48,44 L56,56 A9,9 0 1 1 40,56 Z"/>
        <path {T} d="M72,34 L80,26 M24,34 L16,26"/>'''),
    "dfm-review": ("dfm", "DFM review", f'''
        <path {S} d="M16,70 V40 H40 V56 H56 V70 Z"/>
        <circle cx="60" cy="36" r="14" {S}/>
        <path {S} d="M70,46 L82,58"/>
        <path {T} d="M54,36 l4,4 l8,-8"/>'''),
    "mechanical-teardown": ("dfm", "Product teardown", f'''
        <path {S} d="M18,66 H78 V80 H18 Z"/>
        <path {S} d="M18,14 H78 V24 H18 Z"/>
        <path {T} d="M50.9,45.6 L50.9,48.4 L47.7,49.1 L46.9,51.0 L48.7,53.7 L46.7,55.7 L44.0,53.9 L42.1,54.7 L41.4,57.9 L38.6,57.9 L37.9,54.7 L36.0,53.9 L33.3,55.7 L31.3,53.7 L33.1,51.0 L32.3,49.1 L29.1,48.4 L29.1,45.6 L32.3,44.9 L33.1,43.0 L31.3,40.3 L33.3,38.3 L36.0,40.1 L37.9,39.3 L38.6,36.1 L41.4,36.1 L42.1,39.3 L44.0,40.1 L46.7,38.3 L48.7,40.3 L46.9,43.0 L47.7,44.9 Z"/><circle cx="40" cy="47" r="3" {F}/>
        <path {T} d="M62,38 h10 M67,38 V56 M64,42 h6 M64,46 h6 M64,50 h6"/>
        <path {T} stroke-dasharray="2 4" d="M24,28 V62 M84,40 V60"/>
        <path {T} d="M84,34 V20 m-4,4 l4,-4 l4,4"/>'''),
    "image2gcode": ("process", "Image → G-code", f'''
        <rect x="14" y="22" width="30" height="26" rx="3" {S}/>
        <path {T} d="M18,44 l8,-10 l6,6 l4,-4 l6,8"/><circle cx="34" cy="30" r="2.5" {F}/>
        <path {S} d="M50,62 h28 v-6 h-28 v-6 h28 v-6 h-28"/>
        <path {T} d="M40,58 l6,4 l-6,4"/>'''),
    "lpbf-defect-prediction": ("process", "L-PBF defect regimes", f'''
        <path {S} d="M18,18 V76 H80"/>
        <path d="M20,74 L20,20 C34,40 44,56 78,62 L78,74 Z" fill="#fff" fill-opacity="0.18"/>
        <path {T} d="M20,22 C34,40 44,56 78,62 M38,74 C44,60 56,48 78,40"/>
        <circle cx="52" cy="58" r="4.5" {F}/>'''),
    "am-alloy-screening": ("process", "Which alloy prints", f'''
        <rect x="16" y="16" width="18" height="18" rx="2" {S}/><rect x="38" y="16" width="18" height="18" rx="2" {S}/>
        <rect x="60" y="16" width="18" height="18" rx="2" {S}/>
        <rect x="16" y="38" width="18" height="18" rx="2" {S}/><rect x="38" y="38" width="18" height="18" rx="2" fill="#fff"/>
        <rect x="60" y="38" width="18" height="18" rx="2" {S}/>
        <text x="40.5" y="52" font-family="Arial,sans-serif" font-weight="bold" font-size="12" fill="#92400e">Ni</text>
        <path {S} d="M34,70 l6,6 l14,-14"/>'''),
    "sls-process-optimization": ("process", "SLS settings batch by batch", f'''
        <path {S} d="M14,70 H58 M14,62 H58 M14,54 H58"/>
        <path {S} d="M36,16 V48"/><path {T} d="M30,48 l6,6 l6,-6"/>
        <path {S} d="M64,70 L72,56 L78,62 L84,44"/><path {T} d="M78,44 h6 v6"/>'''),
    "meltpool-geometry": ("process", "Melt-pool size & mode", f'''
        <path {S} d="M14,44 H82"/>
        <path d="M30,44 A18,14 0 0 0 66,44 Z" fill="#fff" fill-opacity="0.4"/>
        <path {S} d="M30,44 A18,14 0 0 0 66,44"/>
        <path {S} d="M48,14 V40"/><path {T} d="M42,20 L48,14 L54,20"/>
        <path {T} d="M30,66 H66 M30,62 v8 M66,62 v8"/>'''),
    "llm-3d-print-monitor": ("monitor", "Watch & fix prints layer by layer", f'''
        <path {S} d="M36,16 H60 V26 L52,36 H44 L36,26 Z"/>
        <path {S} d="M22,74 H74 M28,74 V64 H68 V74 M32,64 V56 H64 V64"/>
        <path {T} d="M66,40 C72,32 80,32 84,40 C80,48 72,48 66,40 Z"/><circle cx="75" cy="40" r="2.5" {F}/>'''),
    "thermal-porosity": ("monitor", "Pores from thermal images", f'''
        <rect x="16" y="30" width="64" height="44" rx="3" {S}/>
        <circle cx="34" cy="48" r="4" {F}/><circle cx="56" cy="60" r="3" {F}/><circle cx="64" cy="42" r="5" {F}/><circle cx="44" cy="64" r="2.5" {F}/>
        <path {T} d="M28,14 c-4,5 4,9 0,14 M48,14 c-4,5 4,9 0,14 M68,14 c-4,5 4,9 0,14"/>'''),
    "lpbf-superres": ("monitor", "Webcam → high-res layers", f'''
        <path d="M14,30 h8 v8 h-8 z M22,38 h8 v8 h-8 z M14,46 h8 v8 h-8 z M30,30 h8 v8 h-8 z M30,46 h8 v8 h-8 z" fill="#fff" fill-opacity="0.75"/>
        <rect x="14" y="30" width="24" height="24" {T}/>
        <path {T} d="M44,42 h8 m-4,-4 l4,4 l-4,4"/>
        <circle cx="70" cy="42" r="13" {S}/><path {T} d="M62,42 a8,8 0 0 1 8,-8"/>
        <path {T} d="M14,70 H82"/>'''),
    "am-literature-rag": ("knowledge", "Page-cited answers from papers", f'''
        <path {S} d="M14,24 C24,20 34,20 44,26 V72 C34,66 24,66 14,70 Z M44,26 C52,20 60,20 66,22"/>
        <circle cx="64" cy="48" r="12" {S}/><path {S} d="M73,57 L82,66"/>
        <path {T} d="M22,34 h14 M22,44 h14 M22,54 h10"/>'''),
    "worked-problem-generator": ("teach", "Problems with verified solutions", f'''
        <path {S} d="M38,62 C30,56 26,48 26,40 a22,22 0 0 1 44,0 c0,8 -4,16 -12,22 Z"/>
        <path {S} d="M40,70 h16 M42,78 h12"/>
        <path {T} d="M40,40 l6,6 l10,-12"/>'''),
    "mechanics-visuals": ("teach", "FBDs, Mohr's circle, diagrams", f'''
        <path {S} d="M14,48 H82 M30,18 V78"/>
        <circle cx="52" cy="48" r="20" {S}/>
        <path {T} d="M38,34 L66,62"/><circle cx="38" cy="34" r="3" {F}/><circle cx="66" cy="62" r="3" {F}/>'''),
}


def tile(skill, size=96):
    area, _, glyph = G[skill]
    dark, light, _ = AREAS[area]
    gid = f"g-{skill}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 96 96">
  <defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></linearGradient></defs>
  <rect width="96" height="96" rx="22" fill="url(#{gid})"/>{glyph}
</svg>'''


def banner(path):
    order = list(G)
    tiles = []
    n = (len(order) + 1) // 2                      # two rows of tiles, all skills shown
    pitch = min(70, (1200 - 80 - 58) / (n - 1))
    for i, sk in enumerate(order):
        r, c = divmod(i, n)
        x, y = 40 + c * pitch, 228 + r * 70
        inner = tile(sk).split(">", 1)[1].rsplit("</svg>", 1)[0]
        tiles.append(f'<g transform="translate({x},{y}) scale(0.6)">{inner}</g>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1220"/><stop offset="1" stop-color="#1e293b"/></linearGradient></defs>
  <rect width="1200" height="400" rx="24" fill="url(#bg)"/>
  <text x="40" y="78" font-family="Helvetica,Arial,sans-serif" font-size="46" font-weight="700" fill="#fff">Mechanical Engineering Skills</text>
  <text x="40" y="118" font-family="Helvetica,Arial,sans-serif" font-size="22" fill="#cbd5e1">33 agent skills for design, analysis and manufacturing · 19 from Barati Farimani Lab papers</text>
  <rect x="40" y="142" width="660" height="44" rx="10" fill="#111827" stroke="#334155"/>
  <text x="58" y="171" font-family="Menlo,Consolas,monospace" font-size="19" fill="#7dd3fc">$ npx skills add BaratiLab/mechanical-engineering-skills</text>
  <text x="1160" y="171" text-anchor="end" font-family="Helvetica,Arial,sans-serif" font-size="16" fill="#94a3b8">Claude Code · Claude.ai · Codex · Cursor · Gemini CLI</text>
  {"".join(tiles)}
</svg>'''


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for sk in G:
        with open(os.path.join(OUT, f"{sk}.svg"), "w") as f:
            f.write(tile(sk))
    with open(os.path.join(ROOT, "docs", "img", "banner.svg"), "w") as f:
        f.write(banner(None))
    print(f"{len(G)} icons + banner")
