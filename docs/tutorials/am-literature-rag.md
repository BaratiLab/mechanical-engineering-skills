# Tutorial: AMGPT (ask your AM library, get page-cited answers)

**Skill:** [`am-literature-rag`](https://github.com/BaratiLab/me-design-skills/tree/main/skills/am-literature-rag) · **Paper:** A. Chandrasekhar, J. Chan, F. Ogoke, O. Ajenifujah, A. Barati Farimani, *AMGPT: A large language model for contextual querying in additive manufacturing*, Additive Manufacturing Letters 11 (2024) 100232, [doi:10.1016/j.addlet.2024.100232](https://doi.org/10.1016/j.addlet.2024.100232) · **Code:** [BaratiLab/LLM_RAG](https://github.com/BaratiLab/LLM_RAG)

General chatbots answer metal-AM questions with outlines. AMGPT showed that retrieval-augmented
generation (RAG) over a curated corpus gives specific, checkable answers. The setup was about 50 AM
papers and textbooks, Mathpix PDF-to-TeX, LlamaIndex, `all-mpnet-base-v2` embeddings and
Llama2-7B. Expert graders found **80%** of its answers factual and hallucination-free (GPT-4: 86.7%),
and its answers were more specific, from a model with under 0.5% of GPT-4's parameters.

In this skill the agent is the generator. `amrag.py` is the retriever, and every passage comes with
a page-exact citation.

## Use cases
- **Lab knowledge base:** put the group's papers, theses and machine manuals in one index; answer
  "what did we use for X?" with citations.
- **Literature review support:** pull the passages on keyhole thresholds, absorptivity models or
  CT pore filtering across many papers, then synthesize.
- **Checking claims:** find where a number comes from before it goes into a proposal.
- **Onboarding:** new students query the reading list instead of skimming 50 PDFs.

## Setup
```bash
npx skills add BaratiLab/me-design-skills --skill am-literature-rag
pip install pypdf rank_bm25            # + sentence-transformers for the paper's dense retriever
cd skills/am-literature-rag
```

## 1. Build a library
We indexed the 13 Barati Farimani Lab papers used across this repo's tutorials:
```bash
python scripts/amrag.py ingest ~/papers/*.pdf --index lib/
python scripts/amrag.py list --index lib/
```
The result is 13 documents and 695 chunks. Titles, DOIs and arXiv IDs come from PDF metadata and
first-page text; reference lists are dropped. Need papers? `reading-list --topic "melt pool"` prints
AMGPT's curated corpus with DOIs.

## 2. Ask, read, answer only from the passages
```bash
python scripts/amrag.py query "How large are keyhole pores and what melt pool ratio indicates keyholing?" --index lib/ --k 5 --per-doc 2
```
Top passages:
1. AdditiveLLM, p.1
2. AdditiveLLM, p.1 (W/D below a threshold approximates keyhole porosity)
3. MeltpoolNet, p.2 (high energy density leads to keyhole mode)
4. ThermoPore, p.4 (pore thresholding)
5. ThermoPore, p.3

The pore *size* sentence wasn't in the top 5, so the agent runs a targeted follow-up:
```bash
python scripts/amrag.py query "average diameter of keyhole pores vapor column" --index lib/ --k 2
```
→ ThermoPore, p.4.

Answer written from those passages:

> Keyholing is usually inferred from melt-pool geometry: a width-to-depth ratio below a threshold
> (1.5 in AdditiveLLM's criteria) indicates likely keyhole porosity [AdditiveLLM: Large language
> models predict defects…, p.1]. It appears at high energy density, when the melt pool deepens
> beyond conduction mode [MeltpoolNet: Melt pool characteristic prediction in…, p.2]. Pores formed
> by the vapor column averaged about 47 µm in diameter in the work ThermoPore cites
> [ThermoPore: Predicting part porosity based on…, p.4].

Every sentence traces to a page. If nothing relevant comes back, the answer says the library
doesn't cover the question.

## 3. Check the retriever on your own questions
`examples/questions_lab.json` holds 12 questions with the file and a phrase the right passage must
contain:
```bash
python scripts/amrag.py eval examples/questions_lab.json --index lib/ --k 3 --backend bm25
```

| k | Hit rate (BM25) |
|---|---|
| 1 | 8 / 12 |
| 3 | 11 / 12 |
| 5 | 11 / 12 |

The miss asks for "unsafe" commands; the paper says "unintended shutdowns". Lexical retrieval can't
bridge a paraphrase like that. The dense model (`--backend dense`, AMGPT's `all-mpnet-base-v2`) or
the default `hybrid` can.

## Tips from the paper
- A **small top-k and low temperature** gave the most faithful answers. Start at k = 5 and use
  `--per-doc 2` when one paper dominates.
- A RAG answer is only as good as the corpus. Curate it: highly cited sources, on-topic, and
  covering the sub-domains you will be asked about.

Cite: Chandrasekhar et al., *Addit. Manuf. Lett.* 11 (2024) 100232.
