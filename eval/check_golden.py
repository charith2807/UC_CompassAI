"""Check a golden file against the corpus: every source URL must be an indexed
document, and every evidence quote must appear (whitespace-insensitive) in it.

Run:  python -m eval.check_golden eval/golden_candidates.jsonl
"""
import argparse
import json
import re

from compass import config


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main(path: str) -> None:
    docs = {}
    for p in config.NORMALIZED_DIR.glob("*.json"):
        d = json.loads(p.read_text())
        docs[d["url"]] = squash(d["text"])

    items = [json.loads(line) for line in open(path) if line.strip()]
    problems = 0
    for it in items:
        urls = [u for u in [it.get("source_url"), *it.get("also_valid_urls", [])] if u]
        missing = [u for u in urls if u not in docs]
        quote = squash(it.get("evidence_quote", ""))
        quote_ok = not quote or quote in docs.get(it.get("source_url"), "")
        if missing or not quote_ok:
            problems += 1
            print(f"  {it['id']}: " + "; ".join(
                [f"URL not in corpus: {u[:80]}" for u in missing] + ([] if quote_ok else [f"quote not found: {quote[:70]!r}"])))
    print(f"{len(items)} items checked, {problems} with problems")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default="eval/golden_candidates.jsonl")
    main(parser.parse_args().path)
