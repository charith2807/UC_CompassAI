"""Stage 6 - Retrieve: find candidate chunks with dense, BM25, or hybrid search.

Reads:  chroma/ and data/bm25/{strategy}_v1.pkl and data/chunks/{strategy}_v1.jsonl
Writes: nothing (query time). Returns a ranked list of hits:
        {chunk_id, score, rank, url, title, section, text}
Run:    python -m compass.s6_retrieve "How much is online tuition per credit hour?"
"""
import argparse
import json
import pickle
from functools import cache

import numpy as np

from compass import config
from compass.s4_embed import embed
from compass.s5_index import get_collection, tokenize

RRF_K = 60  # standard constant from the RRF paper; dampens the gap between rank 1 and rank 2


@cache
def load_chunks(strategy: str) -> dict[str, dict]:
    return {c["chunk_id"]: c for c in map(json.loads, open(config.CHUNKS_DIR / f"{strategy}_v1.jsonl"))}


@cache
def load_bm25(strategy: str):
    with open(config.BM25_DIR / f"{strategy}_v1.pkl", "rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["ids"]


def _hit(chunk_id: str, score: float, rank: int, strategy: str) -> dict:
    c = load_chunks(strategy)[chunk_id]
    return {"chunk_id": chunk_id, "score": float(score), "rank": rank,
            **{k: c.get(k, "") for k in ("url", "title", "section", "text", "page_type", "effective_date", "fetched_at")}}


def dense(query: str, strategy: str = "structure", k: int = 20, page_type: str | None = None) -> list[dict]:
    where = {"strategy": f"{strategy}_v1"}
    if page_type:  # metadata filtering, done inside the vector database
        where = {"$and": [where, {"page_type": page_type}]}
    result = get_collection().query(
        query_embeddings=embed([query]).tolist(), n_results=k, where=where, include=["distances"],
    )
    ids, distances = result["ids"][0], result["distances"][0]
    return [_hit(cid, 1 - d, r, strategy) for r, (cid, d) in enumerate(zip(ids, distances), start=1)]


def bm25(query: str, strategy: str = "structure", k: int = 20, page_type: str | None = None) -> list[dict]:
    index, ids = load_bm25(strategy)
    scores = index.get_scores(tokenize(query))
    if page_type:
        chunks = load_chunks(strategy)
        scores = np.where([chunks[cid].get("page_type") == page_type for cid in ids], scores, 0.0)
    top = [i for i in np.argsort(-scores)[:k] if scores[i] > 0]  # zero = no shared words at all
    return [_hit(ids[i], scores[i], r, strategy) for r, i in enumerate(top, start=1)]


def hybrid(query: str, strategy: str = "structure", k: int = 20, page_type: str | None = None) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (RRF_K + rank).
    Uses only ranks, so cosine (0..1) and BM25 (0..30+) scales never get mixed."""
    pool = 2 * k
    fused = {}
    for hits in (dense(query, strategy, pool, page_type), bm25(query, strategy, pool, page_type)):
        for h in hits:
            fused[h["chunk_id"]] = fused.get(h["chunk_id"], 0.0) + 1 / (RRF_K + h["rank"])
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
    return [_hit(cid, s, r, strategy) for r, (cid, s) in enumerate(ranked, start=1)]


def multi_query(queries: list[str], strategy: str = "structure", k: int = 20, retriever=hybrid,
                page_type: str | None = None) -> list[dict]:
    """Run one retriever per query (original + rewrites) and fuse the ranked lists
    with the same RRF formula. A chunk found by several phrasings rises to the top."""
    fused = {}
    for q in queries:
        for h in retriever(q, strategy, k, page_type):
            fused[h["chunk_id"]] = fused.get(h["chunk_id"], 0.0) + 1 / (RRF_K + h["rank"])
    ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
    return [_hit(cid, s, r, strategy) for r, (cid, s) in enumerate(ranked, start=1)]


RETRIEVERS = {"dense": dense, "bm25": bm25, "hybrid": hybrid}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("--strategy", choices=["fixed", "structure"], default="structure")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--page-type", help="metadata filter, e.g. program, financial, policy, calendar")
    args = parser.parse_args()
    for name, retrieve in RETRIEVERS.items():
        print(f"\n== {name} ({args.strategy}{', page_type=' + args.page_type if args.page_type else ''})")
        for h in retrieve(args.query, args.strategy, args.k, args.page_type):
            print(f"  {h['rank']}. {h['score']:7.3f}  {h['title'][:30]:30} > {h['section'][:35]:35} {h['chunk_id'][-16:]}")
