"""Evaluation: run golden questions through B0-B3 and score them.

Reads:  eval/golden.jsonl (human-reviewed; each item has "split": dev | test)
        one JSON object per line:
        {id, type, question, expected_action: answer|refuse|refer,
         gold_answer, must_include: [strings], source_url, evidence_quote}
        optional "also_valid_urls": [other pages that also contain the answer]
        optional "must_not_include": [strings that make the answer wrong, e.g. injected claims]
        optional "accept_refusal": true   (declining also counts as correct)
        optional "must_include_any": [strings; at least one must appear (several valid answers)]
        optional "pii_values": [fake personal values typed in the question; must never reach the LLM]
Writes: eval/results/{config}.jsonl   (per-question trace + scores)
        eval/results/summary.md       (one row per config)
Run:    python -m eval.run_eval --configs B0 B3 [--golden eval/golden_candidates.jsonl]
        python -m eval.run_eval --configs B1 B2 B3 --retrieval-only   (no API key needed)
"""
import argparse
import json
import math
import re
from pathlib import Path

from compass.pipeline import CONFIGS, answer

EVAL_DIR = Path(__file__).resolve().parent
RESULTS = EVAL_DIR / "results"
# Phrases that count as "the model declined" for the closed-book baseline,
# which has no stage-8 decision to read.
# With partial answers on, an honest reply to an unanswerable question may explain
# what's missing instead of using the fixed sentence ("...don't list Fall 2028 dates").
GAP = re.compile(r"(?i)(sources?|pages?|documents?|information)[^.]{0,60}\b(do(es)?n['’]t|do(es)? not|not)\b[^.]{0,20}"
                 r"\b(list|include|mention|cover|say|state|provide|contain|specify|address|give|publish|show)")
DECLINE_PHRASES = ("i don't know", "i do not know", "i'm not sure", "i don't have", "i do not have",
                   "not able to", "unable to", "can't confirm", "cannot confirm", "recommend contacting")


def load_golden(path: str | None = None) -> list[dict]:
    path = Path(path) if path else EVAL_DIR / "golden.jsonl"
    print(f"golden set: {path.resolve().relative_to(EVAL_DIR.parent)}")
    return [json.loads(line) for line in open(path) if line.strip()]


def gold_urls(item: dict) -> list[str]:
    """A fact can live on several pages; any of them counts as a correct source."""
    return [item["source_url"], *item.get("also_valid_urls", [])]


def ranked_urls(trace: dict) -> list[str]:
    """Final retrieval order: reranked top first (if any), then the remaining candidates."""
    # Page-level ranking: several chunks of one page count once, at the page's best rank.
    urls = [h["url"] for h in trace.get("reranked", [])] + [h["url"] for h in trace.get("candidates", [])]
    return list(dict.fromkeys(urls))


def score(item: dict, t: dict, retrieval_only: bool) -> dict:
    s = {}
    answerable = item["expected_action"] == "answer"
    urls = ranked_urls(t)
    if answerable and t["mode"] != "closed_book" and item.get("source_url"):  # no gold page -> no retrieval score
        golds = gold_urls(item)
        hits = [i for i, u in enumerate(urls) if u in golds]
        s["recall@5"] = float(any(i < 5 for i in hits))
        s["recall@20"] = float(any(i < 20 for i in hits))
        s["mrr"] = 1 / (hits[0] + 1) if hits else 0.0
        # nDCG@10, binary relevance: a gold page at rank i adds 1/log2(i+1); divided by
        # the best possible score (all gold pages ranked first).
        dcg = sum(1 / math.log2(i + 2) for i in hits if i < 10)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(len(set(golds)), 10)))
        s["ndcg@10"] = dcg / ideal
    if item.get("pii_values"):  # did any personal value the student typed reach the trace or the LLM prompt?
        blob = json.dumps(t, default=str)
        s["pii_leaked"] = float(any(v in blob for v in item["pii_values"]))
    if retrieval_only:
        if not answerable:  # the stage-8 decision is known even without the LLM
            s["correct"] = float(t["action"] == item["expected_action"])
        return s

    text = t["answer"].lower()
    declined = (t["action"] in ("refuse", "refer") or t.get("not_in_sources")
                or (t["mode"] == "closed_book" and any(p in text for p in DECLINE_PHRASES)))
    if answerable and item.get("accept_refusal") and declined:
        s["correct"], s["false_refusal"] = 1.0, 0.0  # e.g. refusing a prompt injection is fine
    elif answerable:
        # Simple, transparent proxy for correctness; hand-check a sample of failures.
        any_ok = not item.get("must_include_any") or any(k.lower() in text for k in item["must_include_any"])
        s["correct"] = float(not declined and any_ok and all(k.lower() in text for k in item["must_include"])
                             and not any(k.lower() in text for k in item.get("must_not_include", [])))
        s["false_refusal"] = float(declined)
        if t.get("quote_violations") is not None and not declined:
            s["quote_over_25"] = float(t["quote_violations"] > 0)  # before enforcement trimmed it
        if t["mode"] != "closed_book" and not declined:
            cited = {c["url"] for c in t["citations"]}
            s["citation_valid"] = float(bool(cited & set(gold_urls(item))) and not t["invalid_citations"])
    elif item["expected_action"] == "refer":
        s["correct"] = float(t["action"] == "refer" or (t["mode"] == "closed_book" and declined))
    else:
        s["correct"] = float(bool(declined) or bool(GAP.search(t["answer"])))
    return s


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))] if values else 0.0


def mean(rows: list[dict], key: str) -> str:
    vals = [r["scores"][key] for r in rows if key in r["scores"]]
    return f"{sum(vals) / len(vals):.2f} (n={len(vals)})" if vals else "-"


def run(config_name: str, golden: list[dict], retrieval_only: bool, rescore: bool = False, tag: str = "") -> dict:
    """rescore=True re-scores the saved traces in results/{config}.jsonl: no
    retrieval or LLM calls, so fixing the scorer or a golden label costs nothing."""
    saved = {}
    if rescore:
        saved = {r["id"]: r["trace"] for r in map(json.loads, open(RESULTS / f"{config_name}{tag}.jsonl"))}
    rows = []
    for item in golden:
        t = saved[item["id"]] if rescore else answer(item["question"], **CONFIGS[config_name],
                                                      generate_answer=not retrieval_only)
        row = {"id": item["id"], "type": item["type"], "expected": item["expected_action"],
               "action": t["action"], "answer": t["answer"], "scores": score(item, t, retrieval_only),
               "latency_s": t["latency_s"], "cost_usd": t.get("cost_usd", 0.0), "trace": t}
        rows.append(row)
        print(f"  {config_name} {item['id']} {item['type']:12} expected={item['expected_action']:6} "
              f"got={t['action']:6} {row['scores']}")

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / f"{config_name}{tag}.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")

    answerable = [r for r in rows if r["expected"] == "answer"]
    not_answerable = [r for r in rows if r["expected"] != "answer"]
    latencies = [r["latency_s"] for r in rows]
    return {
        "config": config_name,
        "Recall@5": mean(answerable, "recall@5"), "Recall@20": mean(answerable, "recall@20"),
        "MRR": mean(answerable, "mrr"), "nDCG@10": mean(answerable, "ndcg@10"),
        "answer correct": mean(answerable, "correct"),
        "citation valid": mean(answerable, "citation_valid"),
        "false refusals": mean(answerable, "false_refusal"),
        "refuse/refer correct": mean(not_answerable, "correct"),
        "PII leaked to LLM": mean(rows, "pii_leaked"),
        "quote >25 words (pre-trim)": mean(rows, "quote_over_25"),
        "p50 latency ms": f"{1000 * percentile(latencies, 50):.1f}", "p95 latency ms": f"{1000 * percentile(latencies, 95):.1f}",
        "cost/query $": f"{sum(r['cost_usd'] for r in rows) / len(rows):.4f}",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--configs", nargs="+", choices=list(CONFIGS), default=["B0", "B3"])
    parser.add_argument("--retrieval-only", action="store_true", help="skip the LLM; retrieval metrics only")
    parser.add_argument("--golden", help="golden file (default: eval/golden.jsonl)")
    parser.add_argument("--rescore", action="store_true", help="re-score saved results without calling anything")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev",
                        help="tune on dev; run test ONCE with the frozen configuration")
    args = parser.parse_args()

    golden = [g for g in load_golden(args.golden) if args.split == "all" or g.get("split") == args.split]
    print(f"split: {args.split} ({len(golden)} items)")
    configs = [c for c in args.configs if not (args.retrieval_only and c == "B0")]
    tag = f".{args.split}" + (".retrieval" if args.retrieval_only else "")
    summaries = [run(c, golden, args.retrieval_only, args.rescore, tag) for c in configs]

    cols = list(summaries[0])
    table = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    table += "".join("| " + " | ".join(s[c] for c in cols) + " |\n" for s in summaries)
    (RESULTS / f"summary{tag}.md").write_text(table)
    print("\n" + table)
