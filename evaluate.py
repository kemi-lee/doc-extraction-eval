"""Run extractors over the synthetic documents and score them against labels.

Usage:
  python evaluate.py --extractor regex
  python evaluate.py --extractor claude      (needs ANTHROPIC_API_KEY)
  python evaluate.py --extractor both

Outputs: results/report.md and results/errors_<extractor>.csv
Claude outputs are cached in results/cache_claude.json so reruns are free.
"""
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from extractors import regex_extract, claude_extract
from generate_docs import FIELDS

SCORED = [f for f in FIELDS if f != "doc_type"] + ["doc_type"]


def norm(v):
    if v is None:
        return None
    return str(v).strip().upper()


def run(name, docs, cache_path=None):
    preds = {}
    cache = {}
    if name == "claude" and cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())
    for doc_id, text in docs.items():
        if name == "regex":
            preds[doc_id] = regex_extract(text)
        else:
            if doc_id not in cache:
                cache[doc_id] = claude_extract(text)
            preds[doc_id] = cache[doc_id]
    if name == "claude" and cache_path:
        cache_path.write_text(json.dumps(cache, indent=2))
    return preds


def score(preds, labels):
    field_ok, field_n = defaultdict(int), defaultdict(int)
    by_tmpl = defaultdict(lambda: [0, 0])
    by_noise = defaultdict(lambda: [0, 0])
    exact = 0
    errors = []
    for doc_id, lab in labels.items():
        truth, meta = lab["fields"], lab["meta"]
        pred = preds[doc_id]
        all_ok = True
        for f in SCORED:
            t, p = norm(truth[f]), norm(pred.get(f))
            if t is None and p is None:
                continue  # field not applicable to this document
            field_n[f] += 1
            ok = t == p
            field_ok[f] += ok
            by_tmpl[meta["template"]][0] += ok
            by_tmpl[meta["template"]][1] += 1
            by_noise[meta["ocr_noise"]][0] += ok
            by_noise[meta["ocr_noise"]][1] += 1
            if not ok:
                all_ok = False
                errors.append([doc_id, meta["template"], meta["ocr_noise"], f, truth[f], pred.get(f)])
        exact += all_ok
    return field_ok, field_n, by_tmpl, by_noise, exact, errors


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extractor", choices=["regex", "claude", "both"], default="regex")
    a = ap.parse_args()
    labels = json.loads(Path("data/labels.json").read_text())
    docs = {k: Path(f"data/docs/{k}.txt").read_text() for k in labels}
    Path("results").mkdir(exist_ok=True)
    names = ["regex", "claude"] if a.extractor == "both" else [a.extractor]

    lines = [f"# Extraction evaluation ({len(labels)} synthetic documents)\n"]
    for name in names:
        preds = run(name, docs, Path("results/cache_claude.json"))
        fo, fn, bt, bn, exact, errors = score(preds, labels)
        total_ok, total_n = sum(fo.values()), sum(fn.values())
        with open(f"results/errors_{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["doc", "template", "ocr_noise", "field", "expected", "got"])
            w.writerows(errors)
        lines += [f"## {name}\n",
                  f"- Field-level accuracy: **{pct(total_ok, total_n)}** ({total_ok}/{total_n})",
                  f"- Documents with every field correct: **{pct(exact, len(labels))}** ({exact}/{len(labels)})\n",
                  "| Field | Accuracy |", "|---|---|"]
        lines += [f"| {f} | {pct(fo[f], fn[f])} |" for f in SCORED if fn[f]]
        lines += ["", "| Template | Accuracy |", "|---|---|"]
        lines += [f"| style {t} | {pct(*bt[t])} |" for t in sorted(bt)]
        lines += ["", "| OCR noise | Accuracy |", "|---|---|"]
        lines += [f"| {'noisy' if k else 'clean'} | {pct(*bn[k])} |" for k in sorted(bn)]
        lines.append("")
    Path("results/report.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print("Wrote results/report.md (error details are in results/errors_*.csv)")


if __name__ == "__main__":
    main()
