#!/usr/bin/env python3
"""Insert a layer-inspection pause into sliced G-code (Klipper), as in LLM-3D Print.

  python add_layer_pauses.py part.gcode part_monitored.gcode [--every 1] [--start 2] [--macro LAYER_INSPECT]

Layer changes are found from slicer comments (;LAYER_CHANGE  PrusaSlicer/Orca/Bambu, ;LAYER:n Cura)
or, failing that, from increases in Z on G0/G1 moves. After the first move of each selected layer
is *about to start*, i.e. right after the layer-change marker, it inserts

    SET_PRINT_STATS_INFO CURRENT_LAYER=<n>
    <MACRO> LAYER=<n>          (default LAYER_INSPECT: park + PAUSE, see references/klipper_macros.cfg)

so the agent inspects layer n-1 just after it finished. Use --macro PAUSE for a stock Klipper pause.
"""
import argparse
import json
import re
import sys

ZMOVE = re.compile(r"^G[01]\b[^;]*\bZ(-?\d*\.?\d+)", re.I)


def layer_starts(lines):
    marks = [i for i, l in enumerate(lines) if l.startswith(";LAYER_CHANGE") or re.match(r";LAYER:\d+", l)]
    if marks:
        return marks, "comments"
    starts, z = [], None
    for i, l in enumerate(lines):
        m = ZMOVE.match(l)
        if m:
            nz = float(m.group(1))
            if z is None or nz > z + 1e-6:
                starts.append(i)   # first Z move starts layer 1
                z = nz
    return starts, "z-moves"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--every", type=int, default=1, help="pause every N layers")
    ap.add_argument("--start", type=int, default=2, help="first layer to pause before (1-based; layer 1 is never paused)")
    ap.add_argument("--macro", default="LAYER_INSPECT")
    a = ap.parse_args()
    lines = open(a.src).read().splitlines()
    if any(a.macro in l for l in lines):
        sys.exit(f"{a.src} already contains {a.macro}; refusing to double-insert")
    starts, how = layer_starts(lines)
    inserts = {}
    for n, idx in enumerate(starts, start=1):
        if n >= max(a.start, 2) and (n - a.start) % a.every == 0:
            inserts[idx] = n
    out = [f"; monitored by llm-3d-print-monitor: {len(inserts)} pauses ({how}), macro {a.macro}",
           f"SET_PRINT_STATS_INFO TOTAL_LAYER={len(starts)}"]
    for i, l in enumerate(lines):
        out.append(l)
        if i in inserts:
            n = inserts[i]
            out += [f"SET_PRINT_STATS_INFO CURRENT_LAYER={n}", f"{a.macro} LAYER={n}" if a.macro != "PAUSE" else "PAUSE"]
    open(a.dst, "w").write("\n".join(out) + "\n")
    print(json.dumps({"layers": len(starts), "pauses": len(inserts), "detected_by": how, "out": a.dst}))


if __name__ == "__main__":
    main()
