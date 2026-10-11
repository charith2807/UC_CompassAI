"""The online pipeline: question -> retrieve -> rerank -> ground -> generate.

answer() returns the final answer plus a full trace of every stage, which the
Streamlit UI shows and the evaluation scores.

Configurations used in evaluation (proposal B0-B3):
  B0 closed-book       mode="closed_book"
  B1 BM25              retriever="bm25",   strategy="structure", use_rerank=False
  B2 dense, naive      retriever="dense",  strategy="fixed",     use_rerank=False
  B3 final hybrid RAG  retriever="hybrid", strategy="structure", use_rerank=True,
                       use_rewrite=True, expand_sections=True   (default)
Ablation chain B2 -> A1 -> A2 -> A3 -> A4 -> B3 changes one thing per step (see CONFIGS).
Leave-one-out ablations of B3 (each turns exactly one feature off):
  B3-no-rewrite        use_rewrite=False      (no rewrite fallback when stage 8 would refuse)
  B3-no-expand         expand_sections=False  (send only the reranked chunks)
Run:    python -m compass.pipeline "What is the KCTCS transfer partnership?"
"""
import argparse
import json
import time

from compass import pii
from compass.rewrite import condense, rewrite
from compass.s6_retrieve import RETRIEVERS, multi_query
from compass.s7_rerank import CANDIDATES, TOP_N, rerank
from compass.s8_ground import decide
from compass.s8_ground import expand_sections as expand_sections_fn
from compass.s9_generate import generate, generate_closed_book

_OFF = {"use_rerank": False, "use_rewrite": False, "expand_sections": False}
CONFIGS = {
    # Baselines (course requirement B0-B3)
    "B0": {"mode": "closed_book"},
    "B1": {"retriever": "bm25", "strategy": "structure", **_OFF},
    "B2": {"retriever": "dense", "strategy": "fixed", **_OFF},
    # Ablation chain from B2 to B3: exactly one change per step
    "A1-structure": {"retriever": "dense", "strategy": "structure", **_OFF},          # chunking: fixed -> structure
    "A2-hybrid": {"retriever": "hybrid", "strategy": "structure", **_OFF},            # retrieval: dense -> hybrid RRF
    "A3-rerank": {"retriever": "hybrid", "strategy": "structure", **{**_OFF, "use_rerank": True}},  # + cross-encoder (+ stage-8 refusal)
    "A4-expand": {"retriever": "hybrid", "strategy": "structure",
                  **{**_OFF, "use_rerank": True, "expand_sections": True}},          # + section expansion
    "B3": {"retriever": "hybrid", "strategy": "structure", "use_rerank": True,
           "use_rewrite": True, "expand_sections": True},                           # + rewrite fallback = final
    # Leave-one-out ablations of the final system
    "B3-no-rewrite": {"retriever": "hybrid", "strategy": "structure", "use_rerank": True,
                      "use_rewrite": False, "expand_sections": True},
    "B3-no-expand": {"retriever": "hybrid", "strategy": "structure", "use_rerank": True,
                     "use_rewrite": True, "expand_sections": False},
}


def _brief(hits: list[dict]) -> list[dict]:
    keys = ("chunk_id", "rank", "score", "rerank_score", "title", "section", "url", "page_type", "effective_date")
    return [{k: h[k] for k in keys if k in h} for h in hits]


def answer(question: str, mode: str = "rag", retriever: str = "hybrid", strategy: str = "structure",
           use_rerank: bool = True, use_rewrite: bool = True, expand_sections: bool = True,
           generate_answer: bool = True, history: list[tuple[str, str]] | None = None,
           page_type: str | None = None) -> dict:
    """generate_answer=False stops before the answer-writing LLM call (retrieval-only
    evaluation). The rewrite fallback can still call the LLM (~$0.00004) when it triggers."""
    start = time.perf_counter()
    # First step, before anything else sees the text: strip personal identifiers the
    # student typed. Retrieval, the LLM call and the saved trace all get the redacted
    # question; the original is never stored.
    question, pii_removed = pii.redact(question, pii.QUERY_KINDS)
    trace = {"question": question, "pii_removed": pii_removed, "mode": mode, "retriever": retriever,
             "strategy": strategy, "use_rerank": use_rerank, "use_rewrite": use_rewrite,
             "expand_sections": expand_sections}
    rewrite_cost = 0.0
    if history:
        # Follow-up: make the question standalone first. History is redacted too.
        history = [(pii.redact(q)[0], pii.redact(a)[0]) for q, a in history]
        c = condense(question, history)
        rewrite_cost += c["cost_usd"]
        if c["question"] != question:
            trace["followup_of"], trace["question"] = question, c["question"]
            question = c["question"]

    if mode == "closed_book":
        out = generate_closed_book(question)
        trace.update(action="answer", reason="closed-book baseline (no retrieval)", **out)
    else:
        candidates = RETRIEVERS[retriever](question, strategy, CANDIDATES, page_type)
        if use_rerank:
            top = rerank(question, candidates, TOP_N)
            decision = decide(question, top)
            if use_rewrite and decision["action"] == "refuse":
                # Fallback only: the student's wording found nothing relevant, so retry
                # with rewrites in website vocabulary ("billing" -> "Student Financial
                # Center contact"). Questions that already pass never see a rewrite;
                # rewriting every question broke 5 items that hinge on exact terms.
                rw = rewrite(question)
                rewrite_cost = rw["cost_usd"]
                trace["queries"] = [question, *rw["queries"]]
                candidates = multi_query(trace["queries"], strategy, CANDIDATES, RETRIEVERS[retriever], page_type)
                top = rerank(question, candidates, TOP_N, rewrites=rw["queries"])
                decision = decide(question, top)
            trace["reranked"] = _brief(top)
        else:
            # Baselines without a reranker have no comparable score to refuse on;
            # they only keep the personal/high-stakes referral rule.
            decision = decide(question, [{**h, "rerank_score": float("inf")} for h in candidates[:TOP_N]])
        trace["candidates"] = _brief(candidates)
        trace.update(action=decision["action"], reason=decision["reason"])

        chunks = decision["chunks"]
        if decision["action"] == "answer" and expand_sections:
            chunks = expand_sections_fn(chunks, strategy)
            trace["expanded"] = [h["chunk_id"] for h in chunks if h.get("expanded")]
        if decision["action"] == "answer" and generate_answer:
            trace.update(generate(question, chunks))
            trace["context_chunk_ids"] = [h["chunk_id"] for h in chunks]
        elif decision["action"] == "answer":
            trace.update(answer="(generation skipped)", citations=[], invalid_citations=[],
                         not_in_sources=False, cost_usd=0.0, input_tokens=0, output_tokens=0)
        else:
            trace.update(answer=decision["message"], citations=[], invalid_citations=[],
                         not_in_sources=False, cost_usd=0.0, input_tokens=0, output_tokens=0)

    trace["cost_usd"] = trace.get("cost_usd", 0.0) + rewrite_cost
    trace["latency_s"] = round(time.perf_counter() - start, 4)
    return trace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--config", choices=CONFIGS, default="B3")
    args = parser.parse_args()
    print(json.dumps(answer(args.question, **CONFIGS[args.config]), indent=2, default=str))
