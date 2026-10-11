"""Checks for stage 6 fusion logic, using fake retrievers (no index or model needed).

Run:  python -m tests.test_retrieve
"""
from compass import s6_retrieve
from compass.s6_retrieve import RRF_K


def fake(ranking):
    """A stand-in retriever that returns chunk IDs in a fixed order."""
    return lambda query, strategy="structure", k=20, page_type=None: [
        {"chunk_id": cid, "rank": r} for r, cid in enumerate(ranking[:k], start=1)]


def with_fakes(dense_order, bm25_order, fn):
    saved = s6_retrieve.dense, s6_retrieve.bm25, s6_retrieve._hit
    s6_retrieve.dense, s6_retrieve.bm25 = fake(dense_order), fake(bm25_order)
    s6_retrieve._hit = lambda cid, score, rank, strategy: {"chunk_id": cid, "score": score, "rank": rank}
    try:
        return fn()
    finally:
        s6_retrieve.dense, s6_retrieve.bm25, s6_retrieve._hit = saved


def test_rrf_rewards_chunks_found_by_both_retrievers():
    # A is mid-ranked by both; B and C are each #1 in only one list.
    hits = with_fakes(["B", "x", "A"], ["C", "y", "A"], lambda: s6_retrieve.hybrid("q", k=3))
    assert hits[0]["chunk_id"] == "A"
    assert abs(hits[0]["score"] - 2 / (RRF_K + 3)) < 1e-12      # 1/63 + 1/63


def test_rrf_uses_ranks_not_raw_scores():
    # Only positions matter: the same orders always give the same fused result.
    a = with_fakes(["A", "B"], ["B", "A"], lambda: s6_retrieve.hybrid("q", k=2))
    assert [h["chunk_id"] for h in a] in (["A", "B"], ["B", "A"]) and a[0]["score"] == a[1]["score"]


def test_multi_query_fuses_results_across_phrasings():
    by_query = {"billing": ["X", "contact"], "student financial center contact": ["contact", "Y"]}
    retriever = lambda q, strategy="structure", k=20, page_type=None: [
        {"chunk_id": c, "rank": r} for r, c in enumerate(by_query[q], start=1)]
    hits = with_fakes([], [], lambda: s6_retrieve.multi_query(list(by_query), k=3, retriever=retriever))
    assert hits[0]["chunk_id"] == "contact"                        # found by both phrasings


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
