# AdditiveLLM — notes for this skill

Pak, P. & Barati Farimani, A. *AdditiveLLM: Large language models predict defects in metals
additive manufacturing.* Additive Manufacturing Letters 14 (2025) 100292.

## What the paper did
- Fine-tuned small LLMs (DistilBERT, SciBERT, T5, Llama-3.2-1B) to classify the L-PBF
  defect regime from process parameters given as text.
- Labels: Keyholing, Lack of Fusion, Balling, None. Several can apply at once (multi-label).
- Labels came from melt-pool dimensions in MeltpoolNet (Akbari et al., Addit. Manuf. 55
  (2022) 102817) using three criteria:
  - keyhole if W/D < 1.5
  - lack of fusion if (h/W)² + (t/D)² > 1
  - balling if L/W > π
- Augmentation: every melt pool with W and D was re-labelled over 20 hatch spacings × 20
  layer heights (0–950 µm). This took 2,779 entries to 724,764. The split was a random
  shuffle, 75/15/10.
- Two input formats:
  - **Baseline:** `material [SEP] power [SEP] velocity [SEP] beam [SEP] hatch [SEP] layer`
  - **Prompt:** natural-language sentences built from 100 templates
- Results (validation exact-match accuracy):

| Model | Baseline | Prompt |
|---|---|---|
| Llama-3.2-1B | **94.23%** (F1 0.906) | lower |
| SciBERT | 90.88% | — |
| DistilBERT | 88.41% | 82.22% |
| T5 | 71.41% | — |
| MeltpoolNet random forest (reference) | 85.78% | — |

- A demo was hosted at additivellm.ppak.net.

## How this skill differs, and why
- **No LLM weights are bundled.** The skill uses gradient-boosted trees on the same inputs.
  The paper's own baseline was a tree model, and trees train in seconds on a laptop. The
  `text` column of the built dataset is in the Baseline format, so `data.parquet` can be
  used directly to fine-tune an LLM following the paper (see `finetune.md`).
- **Physics monotonic constraints:**
  - keyhole probability is non-decreasing in power and line energy and non-increasing in speed;
  - lack-of-fusion probability is the reverse, and is non-decreasing in hatch and layer.

  These remove the islands that unconstrained trees draw in process maps. On the grouped
  split they raised exact-match accuracy from 83.9% to 87.9%.
- **Grouped split by default.** A random split puts augmentations of the same melt pool in
  both train and validation. That leaks the answer: the LoF label is a closed-form function
  of hatch and layer once W and D are memorised. With this pipeline the random split scores
  98.1% exact match and the grouped split (whole melt pools held out) scores 87.9%. Quote the
  grouped number when telling a user how far to trust a prediction for a new parameter set.
  The paper's 94% is also a random-split number.
- **Dataset size:** 324,850 rows here, against 724,764 in the paper. This skill keeps only
  PBF rows, augments only rows that have both W and D (806 melt pools × 400), and adds 1,241
  directly classified rows plus 1,209 criteria-labelled rows. The paper's exact
  inclusion rules are not fully specified.

## Known limitations of the data, which also apply to the paper
- Much of MeltpoolNet comes from single-track studies. Under the W/D < 1.5 rule, many
  conduction-to-transition tracks count as "keyhole". For SS316L the predicted defect-free
  window is therefore narrow. Treat the keyhole boundary as conservative.
- Balling labels need a melt-pool length, which only 322 regression rows have. The balling
  head is the weakest and seldom fires.
- Material properties come from the dataset medians. For an unseen alloy, pass `--props`;
  expect extrapolation.
