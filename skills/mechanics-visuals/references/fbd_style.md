# Free-body diagram style

- Isolate the body: draw it alone, with supports replaced by their reactions.
- Body: light grey fill `#d9dde3`, dark outline `#2c3e50`, 1.5 pt.
- Applied loads: `#c0392b` arrows; reactions: `#1f4e79` arrows; unknowns are labelled symbolically (A_x, A_y, M_A).
- Arrow tail or head sits on the point of application. Distributed loads are drawn as a row of arrows with an envelope line labelled w (N/m).
- Moments are drawn as a curved arrow with a label.
- Dimensions: thin grey lines with end ticks, placed below or outside the body.
- Coordinate triad in the lower left. State the positive sense of moment.
- Support → reaction mapping: pin → Ax, Ay; roller → one force normal to the surface; fixed → Ax, Ay, M; cable → tension along the cable; smooth contact → normal force.

Matplotlib snippet:
```python
from matplotlib.patches import FancyArrowPatch, Rectangle
ax.add_patch(Rectangle((0, 0), L, h, fc="#d9dde3", ec="#2c3e50", lw=1.5))
ax.add_patch(FancyArrowPatch((x, y + 0.6), (x, y), arrowstyle="-|>", mutation_scale=15, color="#c0392b", lw=1.8))
ax.text(x + 0.05, y + 0.65, "P = 5 kN", color="#c0392b")
ax.set_aspect("equal"); ax.axis("off")
```
