"""Generate SYNTHETIC healthcare-style documents with labeled ground truth.

No real patient data is used anywhere. Names, IDs and payers are made up.
Documents come in several template styles on purpose, so extractors that work
on one layout can be shown to break on another.

Usage: python generate_docs.py [--n 40] [--seed 7]
Outputs: data/docs/doc_###.txt and data/labels.json
"""
import argparse, json, random
from datetime import date, timedelta
from pathlib import Path

FIELDS = ["doc_type", "payer", "patient_name", "member_id", "auth_number",
          "cpt_code", "units", "start_date", "end_date", "status",
          "diagnosis_code", "provider_name"]

FIRST = ["Maya", "Jordan", "Liam", "Sofia", "Ethan", "Aaliyah", "Noah", "Priya", "Carlos", "Hannah"]
LAST = ["Rivera", "Okafor", "Chen", "Patel", "Nguyen", "Brooks", "Kowalski", "Haddad", "Silva", "Ward"]
PAYERS = ["Northwind Health Plan", "Evergreen Mutual", "BlueHarbor Insurance", "Summit Care Partners"]
PROVIDERS = ["Dr. Elena Marsh", "Dr. Omar Reyes", "Dr. Grace Liu", "Dr. Samuel Boateng"]
CPT = ["97151", "97153", "97155", "97156"]
DX = ["F84.0", "F90.2", "F41.1", "F80.2"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fmt_date(d, style):
    if style == "us":
        return d.strftime("%m/%d/%Y")
    if style == "iso":
        return d.isoformat()
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def make_record(rng, i):
    start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 300))
    end = start + timedelta(days=rng.choice([90, 180, 365]))
    doc_type = rng.choice(["auth_letter", "auth_letter", "treatment_plan"])
    rec = {k: None for k in FIELDS}
    rec.update(doc_type=doc_type,
               patient_name=f"{rng.choice(FIRST)} {rng.choice(LAST)}",
               member_id=f"{rng.choice('ABCDEFGH')}{rng.choice('XYZW')}{rng.randint(100000, 999999)}",
               cpt_code=rng.choice(CPT),
               units=rng.choice([20, 40, 60, 80, 120, 240]),
               start_date=start.isoformat(),
               end_date=end.isoformat())
    if doc_type == "auth_letter":
        rec.update(payer=rng.choice(PAYERS),
                   auth_number=f"PA-{rng.randint(10**7, 10**8 - 1)}",
                   status=rng.choice(["approved", "approved", "denied", "pending"]))
    else:
        rec.update(diagnosis_code=rng.choice(DX), provider_name=rng.choice(PROVIDERS))
    return rec, start, end


def render(rec, start, end, style, rng):
    ds = rng.choice(["us", "iso", "long"])
    s, e = fmt_date(start, ds), fmt_date(end, ds)
    if rec["doc_type"] == "auth_letter":
        if style == 0:  # clean labeled form
            return f"""{rec['payer'].upper()}
PRIOR AUTHORIZATION DETERMINATION

Patient Name: {rec['patient_name']}
Member ID: {rec['member_id']}
Authorization Number: {rec['auth_number']}
Service Code (CPT): {rec['cpt_code']}
Units Authorized: {rec['units']}
Effective: {s} through {e}
Determination: {rec['status'].upper()}
"""
        if style == 1:  # narrative letter
            verb = {"approved": "has been approved", "denied": "has been denied",
                    "pending": "is pending additional clinical review"}[rec["status"]]
            return f"""{rec['payer']}
Utilization Management Department

Dear Provider,

We have completed our review of the request for {rec['patient_name']} (subscriber ID {rec['member_id']}).
The request for CPT {rec['cpt_code']}, {rec['units']} units, {verb}.
Reference #{rec['auth_number']}. Services covered from {s} to {e}.

Sincerely,
Clinical Review Team
"""
        # style 2: terse, reordered, abbreviated
        st = {"approved": "APPR", "denied": "DENY", "pending": "PEND"}[rec["status"]]
        return f"""{rec['payer']} | PA NOTICE
AUTH# {rec['auth_number']}   STATUS: {st}
PT: {rec['patient_name'].split()[1]}, {rec['patient_name'].split()[0]}   MBR: {rec['member_id']}
PROC {rec['cpt_code']} x {rec['units']} UNITS
DOS {s} - {e}
"""
    # treatment plans
    if style == 0:
        return f"""INDIVIDUAL TREATMENT PLAN
Client: {rec['patient_name']}        Member ID: {rec['member_id']}
Primary Dx: {rec['diagnosis_code']}
Treating Clinician: {rec['provider_name']}
Recommended service: CPT {rec['cpt_code']}, {rec['units']} units
Plan period: {s} - {e}
"""
    return f"""Treatment Plan Summary

{rec['patient_name']} (ID {rec['member_id']}) was evaluated by {rec['provider_name']}.
Diagnosis: {rec['diagnosis_code']}. The clinical team recommends {rec['units']} units of
service {rec['cpt_code']} for the period {s} to {e}.
"""


def ocr_noise(text, rng):
    """Mimic common OCR confusions on a few characters."""
    out = []
    for ch in text:
        if rng.random() < 0.012:
            ch = {"0": "O", "1": "l", "5": "S", "8": "B"}.get(ch, ch)
        out.append(ch)
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    docs = Path("data/docs")
    docs.mkdir(parents=True, exist_ok=True)
    labels = {}
    for i in range(a.n):
        rec, s, e = make_record(rng, i)
        style = rng.randint(0, 2)
        if rec["doc_type"] == "treatment_plan":
            style = min(style, 1)
        text = render(rec, s, e, style, rng)
        noisy = rng.random() < 0.25
        if noisy:
            text = ocr_noise(text, rng)
        name = f"doc_{i:03d}"
        (docs / f"{name}.txt").write_text(text)
        labels[name] = {"fields": rec, "meta": {"template": style, "ocr_noise": noisy}}
    Path("data/labels.json").write_text(json.dumps(labels, indent=2))
    print(f"Wrote {a.n} documents to {docs}/ and data/labels.json")


if __name__ == "__main__":
    main()
