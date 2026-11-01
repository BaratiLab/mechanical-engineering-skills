# Fine-tuning an LLM on the built dataset (optional, GPU)

`lpbf.py build --out data.parquet` writes a `text` column in the AdditiveLLM Baseline format
and four 0/1 label columns. A minimal multi-label fine-tune with Hugging Face:

```python
from datasets import Dataset
from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                          Trainer, TrainingArguments)
import pandas as pd, numpy as np

L = ["Keyholing", "Lack of Fusion", "Balling", "None"]
df = pd.read_parquet("data.parquet")

# Split by df["group"]. A random split leaks (see paper-notes.md).
g = df.group.unique(); np.random.default_rng(0).shuffle(g)
tr = df[df.group.isin(g[: int(.75 * len(g))])]
va = df[df.group.isin(g[int(.9 * len(g)):])]

tok = AutoTokenizer.from_pretrained("distilbert-base-uncased")
tok.add_special_tokens({"additional_special_tokens": ["[SEP]"]})

def enc(d):
    x = tok(list(d.text), truncation=True, max_length=64, padding="max_length")
    x["labels"] = d[L].values.astype("float32").tolist()
    return Dataset.from_dict(dict(x))

m = AutoModelForSequenceClassification.from_pretrained(
    "distilbert-base-uncased", num_labels=4, problem_type="multi_label_classification")
m.resize_token_embeddings(len(tok))
Trainer(m, TrainingArguments("out", per_device_train_batch_size=256, num_train_epochs=2,
                             learning_rate=5e-5, bf16=True),
        train_dataset=enc(tr), eval_dataset=enc(va)).train()
```

Report exact-match accuracy, meaning all four labels must be correct, on the grouped
validation set. Compare it with the tree model from `lpbf.py train`. The trees are the bar
to beat.
