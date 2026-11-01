# LLM-SR and LLM-SRBench: notes for this skill

- **LLM-SR:** Shojaee, Meidani, Gupta, Barati Farimani, Reddy. *LLM-SR: Scientific Equation Discovery via
  Programming with Large Language Models.* ICLR 2025 (Oral). arXiv:2404.18400. Code and data:
  github.com/deep-symbolic-mathematics/LLM-SR (MIT).
- **LLM-SRBench:** Shojaee, Nguyen, Meidani, Barati Farimani, Doan, Reddy. *LLM-SRBench: A New Benchmark for
  Scientific Equation Discovery with Large Language Models.* ICML 2025. arXiv:2504.10415.
  - 239 problems in two categories:
    - LSR-Transform: known laws rewritten so they can't be recalled from memory.
    - LSR-Synth: synthetic, discovery-driven problems.
  - Data: huggingface.co/datasets/nnheui/llm-srbench.

## How LLM-SR works, and how this skill maps it
| LLM-SR | This skill |
|---|---|
| A problem *specification* (natural-language description and a Python `equation(..., params)` template, MAX_NPARAMS = 10) | `init` / `fetch` write `problem.json`; `prompt` renders the spec |
| The LLM proposes new skeletons as Python functions, conditioned on earlier good ones | **You** write the skeleton, using `prompt`'s in-context examples (worst → best, the same `equation_v{i}` style) |
| Parameter optimisation: `scipy.optimize.minimize(..., method="BFGS")` from ones, MSE loss | The same BFGS, from ones plus 4 random starts (fewer bad local minima), on NMSE; runs in an isolated subprocess with a time limit |
| Experience buffer with islands and clusters by score, sampled to build prompts | `buffer.jsonl`; `prompt` takes the best per complexity bucket, which gives diversity without islands |
| Metrics: NMSE on in-domain (ID) and out-of-domain (OOD) test splits | NMSE on train, test_id and test_ood, plus `pareto` for complexity against error |
| Benchmarks: oscillator1/2, bactgrow, stressstrain | `fetch --problem ...` downloads the LLM-SR data |

## Rehearsal on stressstrain (Al rod, stress vs strain and temperature; this skill, Claude proposing)

| Model | NMSE (train / ID / OOD) |
|---|---|
| Linear regression | 0.380 / 0.377 / 1.31 |
| Cubic polynomial | 0.161 / 0.150 / 0.680 |
| #1 linear skeleton (LLM-SR's initial template) | 2.47 (no intercept) |
| #2 Voce saturation, σ_sat linear in T (3 params) | 0.095 / 0.107 / 0.549 |
| #3 + necking `strain ** p` | failed: negative strains give NaN. The fix is `np.abs`, a lesson to keep |
| #4 + T-scaled softening (6 params) | 0.058 / 0.068 / 0.269 |
| #5 + quadratic thermal softening and T-dependent stiffness (8 params) | **0.021 / 0.025 / 0.074** |

The OOD split holds a temperature the training data doesn't contain. The physics-shaped skeletons
generalise to it about 9× better than the cubic polynomial (0.074 against 0.680).
