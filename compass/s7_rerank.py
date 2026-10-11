"""Stage 7 - Rerank: re-score candidate chunks with a cross-encoder, keep the best few.

Reads:  candidate hits from stage 6
Writes: nothing. Returns hits with "rerank_score" added, best first, at most top_n.
Run:    python -m compass.s7_rerank "What is the KCTCS transfer partnership?"
"""
import argparse

from compass import config  # noqa: F401  (sets HF_HOME before the model loads)
from compass.s6_retrieve import hybrid
from sentence_transformers import CrossEncoder

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 20  # proposal: hybrid pool of at least 20
TOP_N = 5        # proposal: rerank down to no more than 5
_model = None


def get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(RERANK_MODEL)
    return _model


def rerank(query: str, hits: list[dict], top_n: int = TOP_N, rewrites: list[str] = ()) -> list[dict]:
    """The cross-encoder reads (query, chunk) together and outputs a relevance
    logit: > 0 roughly means "relevant", < 0 "not relevant". Unlike RRF scores,
    these are comparable across queries, which is what stage 8's threshold needs.

    With rewrites, each chunk is scored against the question and every rewrite and
    keeps its best score: "billing ... escalate" scores the Contact Us page below 0,
    while the rewrite "Student Financial Center contact" scores it well above."""
    if not hits:
        return []
    queries = [query, *rewrites]
    scores = get_model().predict([(q, h["text"]) for q in queries for h in hits]).reshape(len(queries), len(hits))
    for h, s in zip(hits, scores.max(axis=0)):
        h["rerank_score"] = float(s)
    return sorted(hits, key=lambda h: -h["rerank_score"])[:top_n]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("--strategy", choices=["fixed", "structure"], default="structure")
    args = parser.parse_args()
    candidates = hybrid(args.query, args.strategy, CANDIDATES)
    print(f"hybrid top 5 of {len(candidates)} candidates (before rerank):")
    for h in candidates[:5]:
        print(f"  #{h['rank']:<2} {h['title'][:30]:30} > {h['section'][:40]}")
    print(f"\nafter cross-encoder rerank (top {TOP_N}):")
    for h in rerank(args.query, candidates):
        print(f"  {h['rerank_score']:6.2f}  was #{h['rank']:<2} {h['title'][:30]:30} > {h['section'][:40]}")
