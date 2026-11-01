# GLU3D paper notes

Jadhav, Berthel, Hu, Panat, Beuth, Barati Farimani, *Adv. Funct. Mater.* 34 (2024) 2404165,
doi:10.1002/adfm.202404165 (open access, CC BY-NC).

## What the paper did
- **Geometry**
  - 22 TPMS families as trigonometric level sets: Eq. 1 is Primitive, Eq. 2 is Gyroid; the rest
    are in SI §S3.
  - Hybrids blend 2–4 families with sigmoid or trigonometric transitions, Eqs. 3–7, with a
    constant t.
  - Thickness comes from φ_thick = φ² − h² on a 64³ grid.
  - The dataset varies h, the bias a and t.
  - Cells with more than two surfaces or any non-manifold surface were dropped, and so was any
    cell with Dice > 0.75 against an existing sample.
  - Result: 3723 cells, split 80/20 (2978/745).
- **Homogenisation:** voxel FEM with periodic BCs (Dong et al. 2019, energy method, Eq. 8), giving
  the 6 × 6 C^H.
- **Scaling (Eq. 9):** α = atanh(φ̂min)/φmin and φ_scaled = tanh(αφ). Mesh yield at level set 0:

  | Model | Naive tanh | φ̂min = 0.25 / 0.5 / 0.75 |
  |---|---|---|
  | 14481616 | 32.7 ± 1.8% | 100% |
  | 148163264 | 51.1 ± 1.1% | 100% |

  Success means vfrac > 0.05 and a closed mesh exists.
- **DDPM**
  - 3D U-Net with ResNet blocks and learnable time embeddings.
  - The stiffness matrix is standardised element-wise to mean 50 and variance 1, then passed
    through a linear encoder and added to the time embedding.
  - Cosine schedule, T = 500, Huber loss, Adam with plateau learning-rate decay, and 20% of
    training steps with a zero conditioning vector.
  - Channel configurations: 1,4,4,8,16,16 and 1,4,8,16,32,64.
  - Training took 500 epochs and 16 h on 4× Quadro RTX 6000. Sampling takes about 16 s per
    structure (500 steps) on an RTX 2080 Ti.
- **Surrogate:** a 19,772-parameter network that predicts E1–E3 from the implicit field.
  - Test MAE is about 0.011 GPa; MSE is about 0.0025.
  - It was frozen and its loss added to the diffusion loss. Generated cells were then scored with
    it, because the voxel FEM failed to converge on cells with stray voxels or thin walls.
- **Metrics**
  - Periodicity (Eqs. 12–13): the sum over the three opposite-face pairs of the MAE between
    binary face voxels.
  - Diversity (Eqs. 14–17): best Dice, Chamfer and Hausdorff (2000 surface points) of each
    generated cell against the training set, averaged over 3 runs.
  - Trade-off: more diverse cells are less periodic.
- **Results**
  - Expected vs generated E1–E3 for 125 cells correlate strongly; error grows at high moduli,
    beyond about 2σ of the training data.
  - 16 random generated cells were FDM-printed in PLA and compressed. The force–displacement
    slope correlated with the conditioning modulus.
  - Against simple-cubic and BCC lattices (Fig. 9): the hybrid cells beat BCC in energy
    absorption, and give better properties at lower density. Wall thickness could not go below
    about 0.5 mm on the printer.
- **Stated limitation:** high-E and high-G targets are hard to hit. The authors attribute this to
  not conditioning on volume fraction; the generated vfrac distribution narrows as φ̂min grows
  (Fig. 12).
- Data is available on request. The public repository had no code when this skill was written.

## Choices and interpretations in this skill
- **Families:** SI §S3 (the 22 families) was not available. The skill ships 12 standard nodal
  approximations: primitive, gyroid, diamond, Neovius, I-WP, Fischer–Koch S, F-RD, Lidinoid,
  Split-P, P-W hybrid, double primitive and double diamond.
  - Each is normalised to max|F| = 1, so h and a mean the same across families.
  - Every term uses integer frequencies, so each cell and each blend is exactly periodic. The
    tests check this for all 12 families.
  - Add families to `FAMILIES`; anything else, such as a network-solid `--kind network`, is an
    extension.
- **Anisotropy:** the paper's scaling factors s_x, s_y, s_z (Eqs. 1–2) appear here as integer
  periods per axis (`freq`), because non-integer values would break periodicity. Every family is
  cubic-symmetric, so without this every cell and every blend has E1 = E2 = E3. A gyroid with
  freq (2,2,1) gives E3/E1 ≈ 2.8; with (1,1,2), ≈ 0.26. 35% of generated dataset cells use it.
- **Eq. 9 sign:** the paper uses positive φ̂min (0.25–0.75) while φmin < 0. Taken literally, α < 0
  and the field flips sign. The skill reads it as α = atanh(φ̂min)/|φmin|, which maps the
  most-inside value to −φ̂min, saturates the outside towards +1 and keeps the zero set. `None` gives
  the naive tanh(φ).
- **Eq. 7 (H4)** is implemented exactly as printed, where the last two terms multiply. Datasets use
  H2, H2t, H3 and H3t only.
- **"More than two surfaces or non-manifold" filter:** the skill turns this into checks a printer
  cares about:
  - the solid is one periodic component that reaches all six faces (otherwise the lattice falls
    apart);
  - every void component reaches the faces (otherwise a sealed cavity traps powder or resin).

  Sheet TPMS pass, with two interpenetrating labyrinths.
- **Stray voxels breaking the FEM:** the skill keeps the largest periodic component before
  homogenising, and the filters reject such cells for datasets. Homogenisation is therefore
  reliable, and the FEM, not the surrogate, is used for acceptance. The surrogate is still provided
  for guidance during training, as in the paper.
- **Homogenisation check:** a solid cell returns the material D exactly. A 50/50 laminate matches
  the exact layered-medium C33, C44 and C11 to 1e-6. A sheet gyroid at vf 0.25 gives E/Es ≈ 0.086
  with exact cubic symmetry, in line with published sheet-gyroid scaling (E/Es ≈ 0.3–0.4·ρ).
- **Conditioning:** the default is the 21 unique C^H entries plus volume fraction, to address the
  paper's stated limitation. `--paper-cond` uses stiffness only.
- **Fig. 9 comparison:** this is elastic only here (`compare`). Energy absorption and peak load
  need compression tests or nonlinear FEA.
- **Weakest-direction modulus:** the skill reports min and max E(d) over 600 directions, because
  E1 alone flatters simple-cubic lattices. A sheet gyroid at vf 0.25 has a weakest-direction
  modulus about 3× SC's; SC is about 1.3× stiffer along its axes.

## Changes to the generative model (and why)
A literal CPU reproduction trained on 300 cells at 16³ produced pure noise: periodicity error
about 1.5 out of a maximum of 3, and stiffness error of 100–500%. These changes produced structured,
exactly periodic samples. Stiffness error was still about 200–280%; more data and compute are
needed, as in the paper.

1. **Periodic grid with circular padding** in every 3 × 3 convolution, in both the U-Net and the
   surrogate. The duplicated face is dropped for training and added back after sampling.
   Generated cells are periodic by construction, which removes the paper's periodicity–diversity
   trade-off.
2. **Time embedding:** sinusoidal features feed a learnable MLP. The paper says "learnable
   position embeddings". A free `nn.Embedding(500, d)` table updates each step's vector only when
   that step is drawn, which is too rarely on small data. Diagnostic: at t ≈ 400 the predicted x₀
   mean was 0 instead of the data mean 0.46.
3. **Conditioning scale:** the vector, standardised to mean 50 as in the paper, is divided by 50
   inside the encoder. Otherwise the initial encoder output is about 30× the time embedding.
4. **Plateau scheduler:** patience 20 and a minimum learning rate of 1e-5. With patience 3 and a
   noisy epoch loss, the learning rate fell from 2e-3 to about 1e-6 within about 60 epochs, and
   the loss stalled at 0.10.
5. **Sampler:** the noise is recomputed from the clipped x₀ (standard DDIM-with-clipping). The
   default is the paper's 500-step ancestral DDPM (eta = 1).
6. **Volume fraction in the conditioning** (see above).
