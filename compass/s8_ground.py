"""Stage 8 - Ground / refuse: decide whether the evidence supports an answer.

Reads:  the question + reranked hits from stage 7
Writes: nothing. Returns {"action": "answer" | "refuse" | "refer",
                          "reason": str, "chunks": [hits passed to the LLM]}
Run:    python -m compass.s8_ground "Am I eligible for a Pell Grant?"
"""
import argparse
import re

from compass.s9_generate import NOT_IN_SOURCES

from compass.s6_retrieve import hybrid
from compass.s7_rerank import CANDIDATES, rerank

# Cross-encoder logit below which we treat the corpus as not covering the
# question. First guess from stage 7 (relevant ~ +1..+7, off-topic ~ -10);
# tune it on the dev split of the golden set, never on the test split.
REFUSE_BELOW = 0.0
# Chunks scoring this far below the best one are dropped from the prompt.
KEEP_WITHIN = 4.0

# Individualized, high-stakes questions: the website can't know this student's
# record, so even a confident answer would be a guess about *them*.
PERSONAL = re.compile(
    r"\b(am i|do i|will i|can i get|should i|my (aid|grant|loan|refund|balance|account|grades?|transcript|status|eligibility|application|visa|i-?20))\b",
    re.IGNORECASE,
)
HIGH_STAKES = re.compile(
    r"\b(eligib\w*|qualif\w*|financial aid|pell|grant|loan|refund|balance|visa|i-?20|sevis|admitted|accepted|transcript|grades?)\b",
    re.IGNORECASE,
)
# "How can my parents see my grades?" asks about a process the documents explain,
# not about this student's record, so it should be answered, not referred.
PROCESS = re.compile(r"^\s*how (do|can|does|should|would) ", re.IGNORECASE)
OFFICES = [
    (re.compile(r"visa|i-?20|sevis|cpt|opt|international", re.I),
     "the International Student Office (see ucumberlands.edu/admissions/international-students)"),
    (re.compile(r"aid|pell|grant|loan|refund|balance|fafsa|scholarship|payment", re.I),
     "the Student Financial Center (see ucumberlands.edu/student-life/student-services/sfc)"),
    (re.compile(r"admit|accept|application|apply", re.I),
     "the Office of Admissions (see ucumberlands.edu/admissions)"),
]


MAX_CONTEXT_CHUNKS = 10  # after expansion; ~2,000 words (~3K tokens), still a small prompt


def expand_sections(chunks: list[dict], strategy: str = "structure") -> list[dict]:
    """Small-to-big: when a chunk from a section is chosen, also send its sibling
    chunks from the same section of the same page. The reranker scores a bare list
    (e.g. "ITS 831 - ... ITS 836 - ...") below prose, so a course list never won a
    top-5 slot on its own; it does get in as part of its "Course Requirements" section.
    Siblings closest to the chosen chunk are added first, up to MAX_CONTEXT_CHUNKS."""
    from compass.s6_retrieve import load_chunks  # local import: avoids loading the index for decide()

    all_chunks = load_chunks(strategy)
    position = lambda cid: int(cid.rsplit("_", 1)[1])
    chosen = {h["chunk_id"] for h in chunks}
    groups = []
    for h in chunks:
        group = [h]
        section = all_chunks[h["chunk_id"]]["section"]
        if section:  # fixed-size chunks have no sections to expand
            doc_id = h["chunk_id"].rsplit("_", 3)[0]  # chunk_id = {doc_id}_{strategy}_v1_{pos}
            siblings = [c for c in all_chunks.values()
                        if c["doc_id"] == doc_id and c["section"] == section and c["chunk_id"] not in chosen]
            for c in sorted(siblings, key=lambda c: abs(position(c["chunk_id"]) - position(h["chunk_id"]))):
                if len(chosen) >= MAX_CONTEXT_CHUNKS:
                    break
                chosen.add(c["chunk_id"])
                group.append({**{k: c.get(k, "") for k in ("chunk_id", "url", "title", "section", "text",
                                                          "page_type", "effective_date", "fetched_at")},
                              "expanded": True})
        groups.append(sorted(group, key=lambda g: position(g["chunk_id"])))  # reading order
    return [g for group in groups for g in group]


def office_for(query: str) -> str:
    return next((office for pattern, office in OFFICES if pattern.search(query)),
                "the appropriate university office (see ucumberlands.edu/about/contact-us)")


def decide(query: str, reranked: list[dict]) -> dict:
    if PERSONAL.search(query) and HIGH_STAKES.search(query) and not PROCESS.search(query):
        office = office_for(query)
        return {"action": "refer", "chunks": [],
                "reason": f"Personal, high-stakes question: refer to {office}.",
                "message": f"That depends on your own student record, so I can't answer it reliably. "
                           f"Please contact {office}."}
    if not reranked or reranked[0]["rerank_score"] < REFUSE_BELOW:
        best = reranked[0]["rerank_score"] if reranked else float("-inf")
        return {"action": "refuse", "chunks": [],
                "reason": f"Best evidence score {best:.2f} is below the threshold {REFUSE_BELOW}.",
                "message": NOT_IN_SOURCES + " I'd rather not guess. Try rephrasing, or contact "
                           "the university (ucumberlands.edu/about/contact-us)."}
    best = reranked[0]["rerank_score"]
    kept = [h for h in reranked if h["rerank_score"] >= best - KEEP_WITHIN]
    return {"action": "answer", "chunks": kept,
            "reason": f"Best evidence score {best:.2f}; passing {len(kept)} chunk(s)."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    args = parser.parse_args()
    d = decide(args.query, rerank(args.query, hybrid(args.query, "structure", CANDIDATES)))
    print(f"{d['action'].upper()}: {d['reason']}")
    for h in d["chunks"]:
        print(f"  {h['rerank_score']:6.2f}  {h['title'][:30]} > {h['section'][:40]}")
