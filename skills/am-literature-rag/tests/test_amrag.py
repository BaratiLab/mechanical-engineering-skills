"""Run: python tests/test_amrag.py   (builds two tiny PDFs with matplotlib; no network)"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts", "amrag.py")
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import amrag  # noqa: E402

ok = 0
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); assert cond, name; ok += 1

def make_pdf(path, title, pages):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path, metadata={"Title": title}) as pdf:
        for body in pages:
            fig = plt.figure(figsize=(8.5, 11)); fig.text(0.05, 0.95, body, va="top", wrap=True, fontsize=9)
            pdf.savefig(fig); plt.close(fig)

filler = " ".join(["Additive manufacturing of metals involves many process variables."] * 25)
with tempfile.TemporaryDirectory() as d:
    a, b = os.path.join(d, "keyhole.pdf"), os.path.join(d, "spatter.pdf")
    make_pdf(a, "Keyhole porosity in laser powder bed fusion of Ti-6Al-4V",
             [filler, "Keyhole pores form when the width to depth ratio falls below 1.5 at high linear energy density.\n" + filler,
              "References\n[1] Someone, A paper, 2020."])
    make_pdf(b, "Spatter formation in Inconel 718",
             [filler, "Spatter ejection increased with argon flow below 2 m/s and with scan speeds above 1200 mm/s.\n" + filler])
    lib = os.path.join(d, "lib")
    out = json.loads(subprocess.check_output([sys.executable, S, "ingest", a, b, "--index", lib]))
    check("two documents ingested", out["documents"] == 2 and len(out["added"]) == 2)
    again = json.loads(subprocess.check_output([sys.executable, S, "ingest", a, "--index", lib]))
    check("re-ingest is deduplicated", again["skipped_duplicates"] == 1 and again["documents"] == 2)
    titles = [x["title"] for x in json.loads(subprocess.check_output([sys.executable, S, "list", "--index", lib]))]
    check("title from PDF metadata", any("Keyhole porosity" in t for t in titles))
    idx = amrag.Index(lib)
    check("reference section dropped", not any("Someone, A paper" in c["text"] for c in idx.chunks))
    check("chunks keep page numbers", {c["page"] for c in idx.chunks if c["doc"] == list(idx.docs)[0]} >= {1, 2})
    r = idx.search("what width to depth ratio causes keyhole pores?", 3, "bm25")["results"]
    check("keyhole question -> keyhole paper page 2", r[0]["title"].startswith("Keyhole") and r[0]["page"] == 2 and "1.5" in r[0]["text"])
    check("citation string has page", r[0]["cite"].endswith("p.2]"))
    r = idx.search("argon flow speed and spatter", 1, "bm25")["results"]
    check("spatter question -> spatter paper", "Spatter" in r[0]["title"])
    r = idx.search("x", 3, "hybrid")
    check("hybrid falls back cleanly when dense is unavailable or works", r["backend"] in ("hybrid", "bm25 (dense unavailable)"))
    q = os.path.join(d, "q.json")
    json.dump([{"question": "keyhole width depth ratio", "file": "keyhole", "must_contain": "1.5"},
               {"question": "spatter argon flow", "file": "spatter", "must_contain": "argon"}], open(q, "w"))
    ev = amrag.evaluate(idx, q, 2, "bm25")
    check("eval hit rate 1.0", ev["hit_rate"] == 1.0)
check("AMGPT reading list loads (55 titles)", len(amrag.reading_list()) == 55)
print(f"\n{ok} checks passed")
