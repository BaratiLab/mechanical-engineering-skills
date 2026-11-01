#!/usr/bin/env python3
"""Retrieval over your own additive-manufacturing literature, after AMGPT
(Chandrasekhar, Chan, Ogoke, Ajenifujah, Barati Farimani, Additive Manufacturing Letters 11 (2024) 100232).

AMGPT put ~50 AM papers and textbooks behind a Llama2-7B with LlamaIndex: PDF -> text -> chunks ->
all-mpnet-base-v2 embeddings -> cosine top-k -> answer. Here the agent you are talking to is the generator;
this script is the retriever, with page-level citations.

  ingest   python amrag.py ingest papers/*.pdf --index lib/          extract, chunk, index (incremental)
  query    python amrag.py query "how does hatch spacing affect lack of fusion?" --index lib/ [--k 5]
  list     python amrag.py list --index lib/                           what is in the library
  reading  python amrag.py reading-list [--topic "Melt Pool"]           AMGPT's curated corpus (DOIs) to build from
  eval     python amrag.py eval questions.json --index lib/            retrieval hit-rate@k for your own Q/A set

Retriever backends (--backend): "dense" = sentence-transformers all-mpnet-base-v2 (the paper's model; needs
`pip install sentence-transformers` and Hugging Face access), "bm25" = lexical BM25 (no model download),
"hybrid" (default) = reciprocal-rank fusion of both when dense is available, else BM25.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DENSE_MODEL = "sentence-transformers/all-mpnet-base-v2"
TOKEN = re.compile(r"[a-z0-9][a-z0-9\-\.]*[a-z0-9]|[a-z0-9]", re.I)
STOP = set("a an the of and or to in on for with by from at as is are was were be been this that these those it its "
           "we our can may which using used use than then also into such via per not no".split())


# ------------------------------------------------------------------ extraction
def pdf_pages(path):
    """Return list of page texts. pdftotext (poppler) when present, else pypdf."""
    try:
        out = subprocess.run(["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, text=True, timeout=120)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.split("\f")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    from pypdf import PdfReader
    return [p.extract_text() or "" for p in PdfReader(path).pages]


def clean(t):
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)          # de-hyphenate line breaks
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n\n", t)
    return t.strip()


def doc_meta(path, pages):
    head = "\n".join(pages[:2])
    doi = re.search(r"\b(10\.\d{4,9}/[^\s\"<>]+[^\s\"<>\.,;])", head)
    arx = re.search(r"arXiv:\s?(\d{4}\.\d{4,5})", head)
    lines = [l.strip() for l in pages[0].splitlines() if len(l.strip()) > 25][:12] if pages else []
    # title heuristic: first long line that is not a journal banner / url / licence line
    bad = re.compile(r"(journal|contents lists|homepage|http|www\.|doi|copyright|elsevier|received|available online|arxiv|"
                     r"licen[cs]e|research paper|short communication|article info)", re.I)
    banner = re.compile(r"^[A-Z][A-Za-z&\s]+ \d+ \(\d{4}\) \d+$")          # "Additive Manufacturing 95 (2024) 104503"
    title = None
    try:  # PDF metadata title, when it looks like a real title
        from pypdf import PdfReader
        mt = (PdfReader(path).metadata or {}).get("/Title")
        if mt and len(mt) > 15 and not re.search(r"(untitled|microsoft word|\.docx?|^s\d{4})", mt, re.I):
            title = mt.strip()
    except Exception:
        pass
    if not title:
        idx = next((i for i, l in enumerate(lines) if not bad.search(l) and not banner.match(l)), None)
        title = os.path.basename(path) if idx is None else lines[idx]
        if idx is not None and idx + 1 < len(lines) and not re.search(r"[.:;]$", title) and len(lines[idx + 1]) < 90 \
                and not bad.search(lines[idx + 1]) and not re.search(r"\d|,.*,", lines[idx + 1]):
            title += " " + lines[idx + 1]          # title wrapped onto a second line
    return {"title": title[:200], "doi": doi.group(1) if doi else None, "arxiv": arx.group(1) if arx else None,
            "file": os.path.basename(path), "pages": len(pages)}


def chunk_pages(pages, size=220, overlap=40, drop_references=True):
    """~size-word chunks with overlap, never crossing a page boundary (so citations are exact)."""
    out, in_refs = [], False
    for pno, text in enumerate(pages, start=1):
        text = clean(text)
        if drop_references:
            m = re.search(r"\n\s*(References|REFERENCES|Bibliography)\s*\n", text)
            if in_refs:
                continue
            if m:
                text, in_refs = text[:m.start()], True
        words = text.split()
        i = 0
        while i < len(words):
            piece = words[i:i + size]
            if len(piece) >= 30 or (i == 0 and len(piece) >= 10):
                out.append({"page": pno, "text": " ".join(piece)})
            i += size - overlap
    return out


# ------------------------------------------------------------------ index
def tokens(t):
    return [w.lower() for w in TOKEN.findall(t) if w.lower() not in STOP]


class Index:
    def __init__(self, path):
        self.path = path
        os.makedirs(path, exist_ok=True)
        self.f = os.path.join(path, "chunks.jsonl")
        self.docs_f = os.path.join(path, "docs.json")
        self.docs = json.load(open(self.docs_f)) if os.path.exists(self.docs_f) else {}
        self.chunks = [json.loads(l) for l in open(self.f)] if os.path.exists(self.f) else []

    def save(self):
        json.dump(self.docs, open(self.docs_f, "w"), indent=1)
        with open(self.f, "w") as fh:
            for c in self.chunks:
                fh.write(json.dumps(c) + "\n")
        emb = os.path.join(self.path, "dense.npy")
        if os.path.exists(emb):
            os.remove(emb)   # invalidate; rebuilt lazily

    def add(self, path, size=220, overlap=40):
        h = hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]
        if h in self.docs:
            return None
        pages = pdf_pages(path)
        meta = doc_meta(path, pages); meta["id"] = h
        ch = chunk_pages(pages, size, overlap)
        for j, c in enumerate(ch):
            c.update({"doc": h, "n": j})
        self.docs[h] = meta
        self.chunks += ch
        return {"id": h, "title": meta["title"], "chunks": len(ch), "pages": meta["pages"]}

    # ---- retrievers
    def bm25(self, q, k):
        from rank_bm25 import BM25Okapi
        bm = BM25Okapi([tokens(c["text"]) for c in self.chunks])
        s = bm.get_scores(tokens(q))
        order = sorted(range(len(s)), key=lambda i: -s[i])[:k]
        return [(i, float(s[i])) for i in order if s[i] > 0]

    def dense(self, q, k):
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(DENSE_MODEL)
        emb_f = os.path.join(self.path, "dense.npy")
        if os.path.exists(emb_f):
            E = np.load(emb_f)
        else:
            E = model.encode([c["text"] for c in self.chunks], normalize_embeddings=True, batch_size=32, show_progress_bar=False)
            np.save(emb_f, E)
        qv = model.encode([q], normalize_embeddings=True)[0]
        s = E @ qv                                             # cosine similarity (paper Sec. 3.2)
        order = np.argsort(-s)[:k]
        return [(int(i), float(s[i])) for i in order]

    def search(self, q, k=5, backend="hybrid", per_doc=None):
        used = backend
        if backend in ("dense", "hybrid"):
            try:
                dn = self.dense(q, max(k * 4, 20))
            except Exception as e:  # model or package unavailable -> lexical
                if backend == "dense":
                    raise SystemExit(f"dense retrieval unavailable ({type(e).__name__}: {e}); use --backend bm25")
                dn, used = None, "bm25 (dense unavailable)"
        if backend == "bm25" or (backend == "hybrid" and dn is None):
            hits = self.bm25(q, max(k * 4, 20))
        elif backend == "dense":
            hits = dn
        else:  # reciprocal-rank fusion
            bm = self.bm25(q, max(k * 4, 20))
            rrf = {}
            for lst in (bm, dn):
                for r, (i, _) in enumerate(lst):
                    rrf[i] = rrf.get(i, 0) + 1 / (60 + r)
            hits = sorted(rrf.items(), key=lambda x: -x[1])
        out, seen = [], {}
        for i, s in hits:
            c = self.chunks[i]
            if per_doc and seen.get(c["doc"], 0) >= per_doc:
                continue
            seen[c["doc"]] = seen.get(c["doc"], 0) + 1
            d = self.docs[c["doc"]]
            out.append({"rank": len(out) + 1, "score": round(s, 4), "doc": c["doc"], "title": d["title"], "page": c["page"],
                        "cite": f"[{short(d)}, p.{c['page']}]", "doi": d.get("doi"), "arxiv": d.get("arxiv"), "text": c["text"]})
            if len(out) == k:
                break
        return {"query": q, "backend": used, "k": k, "results": out}


def short(d):
    t = re.sub(r"[^\w\s\-:]", "", d["title"]).split()
    return " ".join(t[:6]) + ("…" if len(t) > 6 else "")


# ------------------------------------------------------------------ commands
def reading_list(topic=None):
    import csv
    rows = list(csv.DictReader(open(os.path.join(HERE, "..", "references", "amgpt_corpus.csv"), encoding="utf-8-sig")))
    rows = [{k.strip(): (v or "").strip() for k, v in r.items()} for r in rows]
    if topic:
        rows = [r for r in rows if topic.lower() in r["Topic"].lower() or topic.lower() in r["Title"].lower()]
    return [{"title": r["Title"], "doi": r["DOI"], "topic": r["Topic"], "source": r["Publication"][:90]} for r in rows]


def evaluate(idx, qfile, k, backend):
    qs = json.load(open(qfile))
    hit = []
    for q in qs:
        r = idx.search(q["question"], k, backend)["results"]
        ok = any((q.get("file") is None or idx.docs[x["doc"]]["file"].endswith(q["file"]) or q["file"] in idx.docs[x["doc"]]["file"])
                 and (q.get("must_contain") is None or q["must_contain"].lower() in x["text"].lower()) for x in r)
        hit.append(ok)
        q["retrieved"] = [x["cite"] for x in r]; q["hit"] = ok
    return {"backend": backend, "k": k, "hit_rate": round(sum(hit) / len(hit), 3), "n": len(hit), "questions": qs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("ingest"); s.add_argument("pdfs", nargs="+"); s.add_argument("--index", required=True)
    s.add_argument("--chunk-words", type=int, default=220); s.add_argument("--overlap", type=int, default=40)
    s = sub.add_parser("query"); s.add_argument("question"); s.add_argument("--index", required=True)
    s.add_argument("--k", type=int, default=5); s.add_argument("--backend", choices=["hybrid", "dense", "bm25"], default="hybrid")
    s.add_argument("--per-doc", type=int, help="max chunks per document (diversify sources)")
    s = sub.add_parser("list"); s.add_argument("--index", required=True)
    s = sub.add_parser("reading-list"); s.add_argument("--topic")
    s = sub.add_parser("eval"); s.add_argument("questions"); s.add_argument("--index", required=True)
    s.add_argument("--k", type=int, default=5); s.add_argument("--backend", default="hybrid")
    a = ap.parse_args()
    if a.cmd == "reading-list":
        print(json.dumps(reading_list(a.topic), indent=1, ensure_ascii=False)); return
    idx = Index(a.index)
    if a.cmd == "ingest":
        files = [f for p in a.pdfs for f in (glob.glob(os.path.join(p, "**", "*.pdf"), recursive=True) if os.path.isdir(p) else [p])]
        added = [r for r in (idx.add(f, a.chunk_words, a.overlap) for f in files) if r]
        idx.save()
        print(json.dumps({"added": added, "skipped_duplicates": len(files) - len(added), "documents": len(idx.docs),
                          "chunks": len(idx.chunks)}, indent=1, ensure_ascii=False))
    elif a.cmd == "query":
        print(json.dumps(idx.search(a.question, a.k, a.backend, a.per_doc), indent=1, ensure_ascii=False))
    elif a.cmd == "list":
        print(json.dumps([{"id": k, **{x: v[x] for x in ("title", "doi", "arxiv", "file", "pages")}} for k, v in idx.docs.items()],
                         indent=1, ensure_ascii=False))
    else:
        print(json.dumps(evaluate(idx, a.questions, a.k, a.backend), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
