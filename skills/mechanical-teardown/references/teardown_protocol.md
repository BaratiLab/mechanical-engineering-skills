# Teardown protocol

## Before opening
- **Safety.**
  - Discharge or remove batteries. Lithium packs can be punctured by pry tools.
  - Unplug mains devices and wait. Bleed capacitors through a resistor and check with a meter.
  - Springs under preload (clutches, door closers, retractors) need eye protection and a plan.
- **Record the product.** Make, model, serial and date code, the label (rating, certifications),
  price paid, and where it was bought. Weigh the whole product.
- **Photograph all six faces** with a scale reference.

## Each layer
1. Photograph it before removing anything. Note the fastener types and count them (Phillips,
   Torx, security Torx, tri-wing, clips, glue).
2. Remove the parts. Bag and label them by layer (L1-01, L1-02, ...). Record the removal order:
   this order is the `depth` value for wear parts.
3. For each part, record:
   - mass, measured on a scale with 0.1 g resolution;
   - material, judged from resin codes (>PA66-GF30<), magnetism, density, color and finish;
   - process, judged from gates, ejector-pin marks, parting lines, draft, shear burrs, sintered
     porosity and machining marks;
   - joint type and assembly direction;
   - whether it moves.
4. Measure what governs function: gear tooth counts and module, spring wire diameter and free length,
   bearing designation, shaft diameters and fits, wall thickness at bosses.

## Reading the manufacturing process from the part
| Clue | Process |
|---|---|
| Gate vestige, ejector-pin circles, uniform walls, draft | Injection molding |
| Parting line flash, porosity on a cut face, thick sections, matte skin | Die casting |
| Shear and burnish zones on the edges, constant thickness | Stamping |
| Slightly porous, dull gray, sharp but not machined teeth | Powder metallurgy |
| Tool marks, chamfers, threads | Machining |
| Layer lines | Additive manufacturing |

## Secondary sources
- **Exploded parts diagrams** from service-parts sites list every part number. Use them for counts
  and names.
- **FCC ID internal photos** (fcc.report and similar): official photos of the inside of anything
  with a radio.
- **Patents** from the maker: the claims say which feature they think is new.
- **Published teardowns and repair guides**: use them for the opening sequence and known failure
  points.
