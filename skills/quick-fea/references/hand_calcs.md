# Hand-calc anchors (linear elastic)

| Case | Max stress | Max deflection |
|---|---|---|
| Cantilever, end load F, length L | σ = F L c / I | δ = F L³ / (3 E I) |
| Cantilever, UDL w | σ = w L² c / (2I) | δ = w L⁴ / (8 E I) |
| Simply supported, center load | σ = F L c / (4I) | δ = F L³ / (48 E I) |
| Simply supported, UDL | σ = w L² c / (8I) | δ = 5 w L⁴ / (384 E I) |
| Fixed–fixed, center load | σ = F L c / (8I) | δ = F L³ / (192 E I) |
| Axial bar | σ = F/A | δ = F L / (A E) |
| Shaft torsion | τ = T r / J | φ = T L / (G J) |
| Thin-wall pressure vessel | σ_hoop = p r / t, σ_axial = p r / 2t | — |
| Thick cylinder (Lamé), internal p | σ_θ,max = p (ro² + ri²)/(ro² − ri²) | — |
| Circular plate, clamped, uniform p | σ = 3 p a² / (4 t²) at edge | δ = p a⁴ / (64 D), D = E t³/12(1−ν²) |
| Hole in wide plate (tension) | Kt ≈ 3 | — |

Rectangle b×h: I = b h³/12, c = h/2. Round d: I = π d⁴/64, J = π d⁴/32.

First natural frequency, cantilever: f₁ = (1.875²/2π) √(E I / (ρ A L⁴)).
Simply supported: f₁ = (π/2) √(E I / (ρ A L⁴)).
