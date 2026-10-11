# 00 · Proposal (as built)

**Project:** Cumberlands Compass AI, a retrieval-augmented chatbot that answers
student questions from the public University of the Cumberlands website, cites the
page for every claim, and says "I don't have that information" instead of guessing.

**Hypothesis:** a RAG chatbot combining hybrid retrieval, reranking, citations and
explicit refusal gives more accurate, better-grounded answers than a closed-book LLM
(B0) or a single-retriever system (B1/B2). Tested with the B0-B3 baselines and a
one-factor ablation chain (reports 04-06).

## Domain and corpus
Higher education, `www.ucumberlands.edu`: admissions, tuition, financial aid,
programs, calendars, student services, policies. Public, unauthenticated pages only;
staff directory, login pages and news/blog content excluded (report 01, 07).

## Stack (changes from the original proposal in bold)
| Component | Proposed | Built |
|---|---|---|
| Scraping | Requests, BeautifulSoup, robotparser | same |
| Extraction | BeautifulSoup/Trafilatura, PyMuPDF, pandas | Trafilatura + PyMuPDF; **pandas not needed** (Trafilatura keeps tables as markdown) |
| Embeddings | all-MiniLM-L6-v2 (384-d) | same, L2-normalized, cosine |
| Vector DB | ChromaDB | same (persistent, cosine HNSW) |
| Retrieval | dense, BM25, hybrid RRF | same + **fallback query rewriting** |
| Reranker | ms-marco-MiniLM-L-6-v2 | same, plus **section expansion** after reranking |
| Generation LLM | OpenAI gpt-4o-mini | **Claude Haiku 5.5** (`claude-haiku-5-5`, Anthropic SDK), pinned for cost |
| UI | Streamlit | same |

## Architecture
```
offline:  sitemap -> crawl (robots, 1 req/s) -> raw bytes + manifest
          -> extract (boilerplate removed, tables kept, PII redacted, page type, effective date)
          -> chunk (fixed | structure-aware) -> embed (MiniLM, normalized) -> index (Chroma + BM25)
online:   question -> PII redaction -> follow-up condensing -> hybrid retrieval (pool 20)
          -> cross-encoder rerank (top 5) -> refuse / refer / answer (+ rewrite fallback)
          -> section expansion -> Claude (sources only, [n] citations, quote limit)
          -> citation check -> UI (answer, sources with content age, retrieval trace)
```

## Chunk ID scheme
`{doc_id}_{strategy}_{version}_{position:03d}`, e.g. `6854bf9d3dd7_structure_v1_002`,
where `doc_id = sha1(url)[:12]`. Deterministic: the same URL and strategy always
produce the same IDs, so stale chunks can be deleted by `strategy` metadata.

## Evaluation plan
50-item golden set (proposal minimum 40), stratified 60/40 dev/test (33/17), tuned
on dev, test run once. Metrics: Recall@5/@20, MRR, nDCG@10, answer correctness,
citation validity, refusal and over-refusal rates, p50/p95 latency, cost per query,
95% bootstrap CIs and McNemar's test (reports 03, 06).

## Crawl and PII policy
robots.txt honored in code, <= 1 request/second, descriptive User-Agent; allow-listed
student-facing sections only. Personal identifiers redacted in documents and in user
questions; official university contacts kept (report 07).
