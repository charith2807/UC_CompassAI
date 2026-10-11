"""PII redaction shared by ingestion (stage 2) and query time (pipeline).

Policy (see docs/LEARNING.md, "PII"):
  - Official university work contacts (@ucumberlands.edu, 606-539-xxxx / 606-549-xxxx)
    are KEPT: students need them, and the university publishes them.
  - Personal identifiers are REDACTED and replaced by a typed placeholder like [SSN].
  - User questions use stricter rules than the corpus: any phone number a student
    types is probably theirs; phone numbers on public pages are hotels and hotlines.

redact(text, kinds) -> (redacted_text, {kind: count})
"""
import re
from collections import Counter

DATE = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+ \d{1,2},? \d{4}"

PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "CARD": re.compile(r"\b(?:\d{4}[ -]?){3}\d{1,4}\b"),
    # Only digits that follow an ID label: a bare 7-digit number could be anything.
    "STUDENT_ID": re.compile(r"(?i)(\b(?:student\s*)?id(?:entification)?\s*(?:number|no\.?|#)?\s*(?:is|:)?\s*)(\d{5,10})\b"),
    "DOB": re.compile(rf"(?i)(\b(?:date of birth|dob|birthday|born on)\s*(?:is|:)?\s*)({DATE})"),
    "EMAIL": re.compile(r"\b[\w.+-]+@(?!(?:[\w-]+\.)*ucumberlands\.edu\b)[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE),
    "PHONE": re.compile(r"(?<!\d)(?!\(?606\)?[-. ]?5[34]9)\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}(?!\d)"),
}
# Labelled patterns keep the label ("student ID is ") and replace only the value.
LABELLED = {"STUDENT_ID", "DOB"}

QUERY_KINDS = ("SSN", "CARD", "STUDENT_ID", "DOB", "EMAIL", "PHONE")
CORPUS_KINDS = ("SSN", "CARD", "STUDENT_ID", "DOB", "EMAIL")  # public org phone numbers stay


def redact(text: str, kinds: tuple[str, ...] = QUERY_KINDS) -> tuple[str, dict[str, int]]:
    found = Counter()
    for kind in kinds:  # SSN and CARD run before PHONE so their digits aren't misread as phones
        pattern = PATTERNS[kind]

        def replace(m, kind=kind):
            found[kind] += 1
            return (m.group(1) + f"[{kind}]") if kind in LABELLED else f"[{kind}]"

        text = pattern.sub(replace, text)
    return text, dict(found)
