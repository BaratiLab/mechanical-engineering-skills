# Fillet-weld group unit properties (treat weld as a line; multiply by throat t = 0.707h)

| Group | Unit 2nd moment Iu (mm³) | c (mm) | Unit polar Ju (mm³) |
|---|---|---|---|
| Single vertical line, length d | d³/12 | d/2 | d³/12 |
| Two vertical lines, depth d, spacing b | d³/6 | d/2 | d(3b² + d²)/6 |
| Two horizontal lines, width b, spacing d | b d²/2 | d/2 | b(3d² + b²)/6 |
| Rectangle box b × d | d²(3b + d)/6 | d/2 | (b + d)³/6 |
| Circle, diameter D | π D³/8 | D/2 | π D³/4 |

Bending: τ'' = M c / (t Iu). Torsion: τ'' = T r / (t Ju). Combine with primary shear vectorially.
Source: Shigley 11e Tables 9-1, 9-2.
