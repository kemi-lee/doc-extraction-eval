"""Two ways to pull structured fields out of a document's text.

1. regex_extract  - a rule-based baseline (fast, brittle).
2. claude_extract - an LLM extractor using the Claude API (flexible, needs checking).

Both return a dict with the keys in FIELDS (missing values are None).
"""
import json, os, re
from generate_docs import FIELDS

# ---------- baseline ----------
_PATTERNS = {
    "payer": r"^([A-Z][A-Za-z ]+(?:Plan|Mutual|Insurance|Partners))",
    "patient_name": r"(?:Patient Name|Client):\s*([A-Z][a-z]+ [A-Z][a-z]+)",
    "member_id": r"Member ID:\s*([A-Z]{2}\d{6})",
    "auth_number": r"Authorization Number:\s*(PA-\d+)",
    "cpt_code": r"CPT\)?:?\s*(\d{5})",
    "units": r"Units Authorized:\s*(\d+)",
    "diagnosis_code": r"Primary Dx:\s*([A-Z]\d{2}\.\d)",
    "provider_name": r"Treating Clinician:\s*(Dr\. [A-Z][a-z]+ [A-Z][a-z]+)",
}


def regex_extract(text):
    out = {k: None for k in FIELDS}
    for key, pat in _PATTERNS.items():
        m = re.search(pat, text, re.M | re.I if key == "payer" else re.M)
        if m:
            out[key] = m.group(1).strip()
    if "units" in out and out["units"]:
        out["units"] = int(out["units"])
    out["doc_type"] = "treatment_plan" if re.search(r"treatment plan", text, re.I) else "auth_letter"
    m = re.search(r"Determination:\s*(\w+)", text)
    if m:
        out["status"] = m.group(1).lower()
    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*(?:through|-|to)\s*(\d{2}/\d{2}/\d{4})", text)
    if m:  # only handles US-format dates: a deliberate weakness to measure
        for key, g in (("start_date", m.group(1)), ("end_date", m.group(2))):
            mm, dd, yy = g.split("/")
            out[key] = f"{yy}-{mm}-{dd}"
    return out


# ---------- LLM extractor ----------
PROMPT = """You extract structured data from a healthcare document. The text may contain
OCR-style character errors. Return ONLY a JSON object (no prose, no code fences) with exactly these keys:

doc_type        "auth_letter" or "treatment_plan"
payer           insurance company name, or null
patient_name    "First Last" (convert "Last, First" to "First Last")
member_id       the member/subscriber ID, exactly as written
auth_number     authorization/reference number (e.g. PA-12345678), or null
cpt_code        5-digit procedure code
units           integer number of units
start_date      ISO format YYYY-MM-DD
end_date        ISO format YYYY-MM-DD
status          "approved", "denied", or "pending" (auth letters only), else null
diagnosis_code  ICD-10 code, or null
provider_name   clinician name exactly as written, including any title such as "Dr.", or null

Rules: use null when a field is not present. Never guess or invent a value.
If a value looks like an OCR error (e.g. letter O in a numeric ID), report it as written.

Document:
---
{doc}
---"""


def claude_extract(text, model=None):
    import anthropic  # imported lazily so the regex baseline runs without the SDK
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    resp = client.messages.create(
        model=model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
        max_tokens=500,
        messages=[{"role": "user", "content": PROMPT.format(doc=text)}],
    )
    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {k: None for k in FIELDS} | {"_parse_error": raw[:200]}
    return {k: data.get(k) for k in FIELDS}
