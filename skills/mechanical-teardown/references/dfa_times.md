# DFA: minimum part count and manual assembly times

Method: Boothroyd–Dewhurst manual-assembly analysis (Boothroyd, Dewhurst & Knight, *Product Design for
Manufacture and Assembly*, 3rd ed., CRC Press, 2011). The script uses mid-range values condensed from
the handling and insertion tables. Use the full tables when the result has to stand up in a design review.

## Minimum part count (per part, asked in assembly order)
A part is **theoretically necessary** if, relative to the parts already assembled, any of these is true:
1. It **moves** in normal operation (rotates, slides, flexes as a spring), the part's own function.
2. It must be a **different material** (an insulator, a seal, a bearing surface, a magnet).
3. It must be **separate** so that the other parts can be assembled or serviced.

Fasteners, labels and spacers fail all three by definition. They are still sometimes the right
answer for cost or serviceability, so say so when you keep them.

DFA index:  E = 3 × N_min / T_total   (3 s = ideal time for a part that is easy to handle and insert)

| E | Reading |
|---|---|
| < 10 % | Poor. Many fasteners and separate small parts. |
| 10–20 % | Typical of products never reviewed for DFA. |
| 20–30 % | Good consumer product practice. |
| > 40 % | Excellent. Usually snap-fit, top-down, few fasteners. |

## Handling time (s), field `handling`
| Key | s | Use for |
|---|---|---|
| easy | 1.5 | One hand, no tool, symmetric or easy to see orientation |
| orient | 2.2 | Must be turned to one orientation (asymmetric, keyed) |
| small | 3.0 | Under about 6 mm, slippery, or needs tweezers or a magnetic driver |
| flexible | 4.5 | Wires, harnesses, tangling springs, gaskets, flex circuits |
| heavy | 4.0 | Two hands or a lift aid |

## Insertion time (s), field `insertion`, per item (per screw for screws)
| Key | s | Notes |
|---|---|---|
| drop_in | 1.5 | Self-locating, not secured (held by the next part) |
| snap | 2.5 | Snap fit or clip, secured on insertion |
| align | 3.0 | Needs alignment, then held by the next part |
| connector | 4.0 | Plug a wire connector |
| press | 4.5 | Press fit, bearing onto a shaft |
| rivet | 5.0 | |
| hold_down | 5.5 | Must be held in place while the next part goes on |
| screw | 6.0 | Place and power-drive one screw |
| wire_route | 8.0 | Route and dress a wire or harness through channels |
| solder | 9.0 | One manual solder joint |
| adhesive | 10.0 | Dispense, place, hold, cure fixture |
| weld | 12.0 | Spot or ultrasonic weld per joint |

## Typical consolidation moves
- Several screws → snap hooks plus one or two screws (keep a screw where a service opening is needed).
- Washers, spacers, shims → molded shoulders or bosses.
- Bracket plus fasteners → feature molded into the housing.
- Soldered leads → keyed connectors (also helps repairability).
- Separate seal → two-shot overmold.
