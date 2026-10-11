"""PII audit: evidence for the report that the corpus follows the PII policy.

Reads:  data/raw/manifest.jsonl, data/normalized/*.json
Writes: nothing; prints three tables (one per layer of the policy).
Run:    python -m compass.pii_audit
"""
import json
import re
from collections import Counter

from compass import config, pii
from compass.s1_crawl import BLOCKED_WORDS

UNIVERSITY_EMAIL = re.compile(r"[\w.+-]+(?:@| \\\[at\\\] )(?:[\w-]+\.)*ucumberlands\.edu", re.IGNORECASE)
UNIVERSITY_PHONE = re.compile(r"\(?606\)?[-. ]?5[34]9[-. ]\d{4}")


def main() -> None:
    manifest = [json.loads(line) for line in open(config.MANIFEST)]
    docs = [json.loads(p.read_text()) for p in sorted(config.NORMALIZED_DIR.glob("*.json"))]

    print("Layer 1 - excluded at collection (crawl scope)")
    leaked = [r["url"] for r in manifest if any(w in r["url"].lower() for w in BLOCKED_WORDS)]
    print(f"  crawled URLs containing {BLOCKED_WORDS}: {len(leaked)} of {len(manifest)}")

    print("\nLayer 3 - redacted at ingestion (personal identifiers in documents)")
    found = Counter()
    for d in docs:
        found.update(d.get("pii_redacted", {}))
    remaining = Counter()
    for d in docs:
        remaining.update(pii.redact(d["text"], pii.CORPUS_KINDS)[1])
    print(f"  {'kind':12} {'redacted':>9} {'remaining':>10}")
    for kind in pii.CORPUS_KINDS:
        print(f"  {kind:12} {found[kind]:>9} {remaining[kind]:>10}")

    print("\nKept on purpose (policy: official contacts students need)")
    text = " ".join(d["text"] for d in docs)
    org_phones = len(pii.PATTERNS["PHONE"].findall(text))
    print(f"  university emails: {len(UNIVERSITY_EMAIL.findall(text))}, university phone numbers: "
          f"{len(UNIVERSITY_PHONE.findall(text))}, other organisations' phone numbers (hotels, hotlines): {org_phones}")

    print("\nLayer 2 - redacted from user questions at query time: see tests/test_pii.py and the")
    print("  'PII leaked to LLM' column of eval/run_eval.py (items with \"pii_values\").")


if __name__ == "__main__":
    main()
