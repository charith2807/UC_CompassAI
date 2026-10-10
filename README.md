# Cumberlands Compass AI

A retrieval-augmented (RAG) chatbot that answers student questions using only public
University of the Cumberlands web pages and documents. Every answer cites the page it
came from; when the pages don't support an answer, the bot says
"I don't have that information" instead of guessing. MSAI 633 residency project.

## Pipeline
```
offline:  crawl -> extract -> chunk -> embed -> index
online:   question -> retrieve (dense + BM25 + hybrid) -> rerank -> answer / refuse / refer
          -> generate a cited answer -> chat UI with sources and a retrieval trace
```

| Stage | Module (`compass/`) | What it does |
|---|---|---|
| 1 Crawl | `s1_crawl.py` | sitemap-driven crawl; robots.txt, <= 1 req/s, allow-listed sections only |
| 2 Extract | `s2_extract.py` | clean text from HTML and PDFs; tables kept; PII redacted; page type and dates |
| 3 Chunk | `s3_chunk.py` | fixed-size vs structure-aware chunks with heading paths |
| 4 Embed | `s4_embed.py` | `all-MiniLM-L6-v2`, 384-d, L2-normalized |
| 5 Index | `s5_index.py` | ChromaDB (cosine) + BM25; stale-chunk check on re-index |
| 6 Retrieve | `s6_retrieve.py` | dense, BM25, hybrid Reciprocal Rank Fusion; page-type filter |
| 7 Rerank | `s7_rerank.py` | cross-encoder `ms-marco-MiniLM-L-6-v2`, pool 20 -> top 5 |
| 8 Decide | `s8_ground.py` | answer, refuse, or refer to a university office |
| 9 Generate | `s9_generate.py` | Claude Haiku 5.5 answers from sources only, with `[n]` citations |
| UI | `app.py` | Streamlit chat with citations, refusals and a retrieval trace |

## Repository layout
```
compass/   pipeline stages and shared config
eval/      golden question set, evaluation runner, statistics
reports/   00_proposal ... 07_ethics (course report set)
docs/      learning notes and design decisions
tests/     unit tests (PII redaction, crawl scope)
data/      local data; raw and derived data are git-ignored (scraped content is not published)
```
Modules land stage by stage in follow-up pull requests.

## Setup
```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt     # pinned versions
cp .env.example .env                          # then set ANTHROPIC_API_KEY=...
```
Never commit `.env` or any key: `.env` is git-ignored, and a committed key is an
automatic zero.

## Working agreement
- `main` is protected: all work goes through short-lived feature branches
  (`stage/crawl`, `eval/golden-set`, ...) and pull requests with at least one
  teammate's review.
- Commit messages: short, present tense, with a type prefix
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Every member contributes commits to more than one pipeline stage.
- AI tools are allowed and are documented in this README's "AI usage" section as
  they are used.

## AI usage
- Claude Code (Claude Opus 5.5) is used as a pair programmer for pipeline code,
  evaluation tooling and report drafts; every change is reviewed by a team member
  through a pull request.
