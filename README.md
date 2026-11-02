# Healthcare Document Extraction & Evaluation

A Python project that pulls structured data out of healthcare documents (prior-authorization letters and treatment plans) and **measures how accurate the extraction is**. It compares a rule-based regex baseline against an LLM extractor built on the Claude API.

All documents are **synthetic**. No real patient data is used. Every name, ID, and payer is made up.

## Why this project
Healthcare operations depend on information buried in documents, such as authorization numbers, procedure codes, units, and dates. Using AI to read them is only useful if the outputs are accurate and the failures are understood. This project walks through that loop in miniature: define the fields, extract them, score the results, study the errors, improve the prompt, and measure again.

## Results at a glance
| Approach | Field-level accuracy | Documents with every field correct |
|---|---|---|
| Regex baseline | 48.5% | 5% (2/40) |
| Claude (final prompt) | 99.7% | 97.5% (39/40) |

Accuracy by document layout:

| Layout | Regex | Claude |
|---|---|---|
| Clean labeled form | 77.9% | 99.2% |
| Narrative letter | 34.7% | 100.0% |
| Terse abbreviated notice | 28.9% | 100.0% |

## Example
Input (one of the synthetic letters):

```
Evergreen Mutual
Utilization Management Department

We have completed our review of the request for Maya Okafor (subscriber ID BZ711097).
The request for CPT 97151, 120 units, has been approved.
Reference #PA-15032582. Services covered from 2026-06-15 to 2026-09-13.
```

The regex baseline got 3 of the 10 fields right on this letter, because it needs exact labels like "Member ID:" and "Units Authorized:". Claude extracted all 10:

```json
{"doc_type": "auth_letter", "payer": "Evergreen Mutual", "patient_name": "Maya Okafor",
 "member_id": "BZ711097", "auth_number": "PA-15032582", "cpt_code": "97151", "units": 120,
 "start_date": "2026-06-15", "end_date": "2026-09-13", "status": "approved"}
```

## How it works
1. **Generate data.** `generate_docs.py` creates 40 synthetic documents in three layouts with varied date formats and some OCR-style character errors, along with a file of correct answers.
2. **Extract.** `extractors.py` has two methods: a regex baseline and a Claude API extractor that returns JSON using a prompt that says what each field means and to use null when a field is absent.
3. **Evaluate.** `evaluate.py` scores every field against the correct answers and reports accuracy overall, by field, by layout, and by OCR noise. Every mistake is saved to `results/errors_<extractor>.csv` for review.

## Findings
**Regex baseline.** 48.5% field-level accuracy (194/400). Accuracy depended on layout, and the weakest field was `units` (33 of 40 wrong). Errors came from requiring exact labels and formats, for example "Member ID:" instead of "subscriber ID", or MM/DD/YYYY instead of YYYY-MM-DD. It also made confident wrong answers, such as returning "Treatment Plan" as the payer on documents that had none.

**Claude extractor.** With the original prompt, two runs scored 99.5% and 99.2%. It handled all three layouts and left non-applicable fields blank instead of guessing. The misses were `provider_name` (the model dropped the "Dr." title because the prompt never said to keep it) and one corrupted diagnosis code.

**What I changed.** I edited the `provider_name` instruction to say "exactly as written, including any title such as 'Dr.'". After the change, three independent runs (cache cleared each time) each scored 99.7% (389/390), with `provider_name` at 100%.

**Remaining error.** An OCR-style character swap turned `F41.1` into `F41.l` in one document, and the model copied it as written, which is what the prompt instructs. A production system would add a format check (such as the ICD-10 pattern) and send failures to human review instead of trusting the extraction.

**Takeaway.** Several "model errors" were really gaps in the specification: the prompt did not say whether a title belongs in a name field. Clear definitions mattered as much as the model.

## Limitations
- The documents are synthetic, with three layouts and 40 samples. The results show the method works, not that it would reach this accuracy on real scanned documents, which are messier (tables, handwriting, image quality).
- Claude's outputs varied slightly between identical runs before the prompt change, so I compared several runs instead of relying on a single one.
- The regex was scored on 400 fields and Claude on 390, because the regex invented a payer on all 10 treatment plans while Claude correctly left it blank.

## What I would do next
- Add a real OCR step (for example `pytesseract`) so the input is scanned images instead of clean text.
- Add validation checks (CPT code is 5 digits, ICD-10 format, end date after start date) and a `needs_human_review` flag.
- Test on more documents and harsher noise to find where accuracy starts to break.
- Compare prompts or models on the same set.

## Run it yourself
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here     # Windows PowerShell: $env:ANTHROPIC_API_KEY="your_key_here"

python generate_docs.py --n 40            # creates data/docs/*.txt and data/labels.json
python evaluate.py --extractor regex      # baseline (no API key needed)
python evaluate.py --extractor claude     # LLM extractor
python evaluate.py --extractor both
```
Results are written to `results/report.md`, and each mistake is listed in `results/errors_<extractor>.csv`. Claude's outputs are cached in `results/cache_claude.json`, so re-scoring costs nothing. Delete the cache to get fresh answers after changing the prompt or model (`CLAUDE_MODEL=<model-name>` selects a different model).

## Files
| File | Purpose |
|---|---|
| `generate_docs.py` | Makes synthetic documents and ground-truth labels |
| `extractors.py` | Regex baseline and Claude extractor (the prompt lives in `PROMPT`) |
| `evaluate.py` | Scoring, breakdowns, and error logs |

Built with Claude as a coding assistant. I ran the experiments, reviewed the errors, and wrote the analysis.  