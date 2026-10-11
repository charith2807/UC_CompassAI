"""Collect failures for hand-labelling (course requirement: label >= 15 failures).

Writes eval/failures_to_label.csv with a SUGGESTED label inferred from the trace.
A person must read each row, check the answer against the page, and fill in
human_label (one of the categories below) - the suggestion is only a starting point.

Categories (from the course rubric): retrieval miss, rank failure, chunk boundary,
extraction failure, stale content, reranker demotion, generator ignored context,
invalid citation, over-refusal, hallucination.

Run:  python -m eval.failures B3 B2 B1 --split test
"""
import argparse
import csv
import json

from eval.run_eval import RESULTS, load_golden, gold_urls


def suggest(item: dict, r: dict) -> str:
    s, t = r["scores"], r["trace"]
    if r["expected"] != "answer":
        return "hallucination" if r["action"] == "answer" else "wrong decision (refer vs refuse)"
    if s.get("false_refusal"):
        return "over-refusal"
    if t.get("mode") == "closed_book":
        return "hallucination"
    if t.get("invalid_citations"):
        return "invalid citation"
    if "recall@20" in s and not s["recall@20"]:
        return "retrieval miss"
    golds = set(gold_urls(item))
    pre = [h["url"] for h in t.get("candidates", [])[:5]]
    post = [h["url"] for h in t.get("reranked", [])]
    if post and golds & set(pre) and not golds & set(post):
        return "reranker demotion"
    if "recall@5" in s and not s["recall@5"]:
        return "rank failure"
    return "generator ignored context (or chunk boundary / extraction failure / stale content: check the page)"


def main(configs: list[str], split: str) -> None:
    golden = {g["id"]: g for g in load_golden()}
    rows = []
    for config in configs:
        for r in map(json.loads, open(RESULTS / f"{config}.{split}.jsonl")):
            if r["scores"].get("correct", 1.0) == 0.0:
                g = golden[r["id"]]
                rows.append({"config": config, "split": split, "id": r["id"], "type": r["type"],
                             "question": g["question"], "gold_answer": g["gold_answer"],
                             "expected": r["expected"], "got": r["action"],
                             "answer": r["answer"][:400].replace("\n", " "),
                             "suggested_label": suggest(g, r), "human_label": "", "notes": ""})
    out = RESULTS.parent / "failures_to_label.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"{len(rows)} failures -> {out}")
    for label, n in Counter(r["suggested_label"].split(" (")[0] for r in rows).most_common():
        print(f"  {n:>3}  {label}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("configs", nargs="+")
    parser.add_argument("--split", default="test")
    a = parser.parse_args()
    main(a.configs, a.split)
