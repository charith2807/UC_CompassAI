# Cumberlands Compass AI

A retrieval-augmented chatbot for University of the Cumberlands students. It answers
only from public `ucumberlands.edu` pages (plus 7 hand-downloaded university PDFs),
cites the page for every claim, shows content age, redacts personal data, and says
"I don't have that information" instead of guessing. MSAI 633 residency project.

Reports: [`reports/`](reports/) · learning log: [`docs/LEARNING.md`](docs/LEARNING.md)

## Setup
```bash
/opt/homebrew/bin/python3.12 -m venv .venv          # Python 3.12
.venv/bin/pip install -r requirements.txt           # pinned versions
cp .env.example .env                                # then set ANTHROPIC_API_KEY=...
```
Model downloads (MiniLM embedder, MiniLM cross-encoder) are cached in `./.cache/`.
Generation uses `claude-haiku-5-5` (pinned in `compass/s9_generate.py`); a full
evaluation run costs about $0.01-0.03.

## Build the corpus and index (offline stages, no API key needed)
```bash
python -m compass.s1_crawl --max-pages 300 --max-pdfs 15   # ~8 min at 1 req/s -> data/raw/
# put the hand-downloaded PDFs listed in data/manual_sources.jsonl into data/raw/manual/
python -m compass.s2_extract                                # -> data/normalized/
python -m compass.s3_chunk --strategy both                  # -> data/chunks/
python -m compass.s4_embed --strategy both                  # -> data/embeddings/
python -m compass.s5_index --strategy both                  # -> chroma/ + data/bm25/
```
Raw and derived data are git-ignored (scraped content is not published).

## Run the chatbot
```bash
.venv/bin/streamlit run app.py           # http://localhost:8501
python -m compass.pipeline "When does the Fall 2026 semester start?"   # one question, full JSON trace
```

## Reproduce every reported number
| Report / number | Command |
|---|---|
| 01 ingestion counts, PII audit | `python -m compass.pii_audit` |
| 02 chunk counts and token-length distributions | `python -m compass.chunk_stats` |
| 02 re-chunk migration (stale = 0) | `python -m compass.s5_index --strategy both` |
| 03 golden set validity (URLs, quotes) | `python -m eval.check_golden eval/golden.jsonl` |
| 04-06 all metrics, dev split | `python -m eval.run_eval --configs B0 B1 B2 A1-structure A2-hybrid A3-rerank A4-expand B3 --split dev` |
| 06 final test run (run once) | same with `--split test` |
| 04-06 CIs and McNemar | `python -m eval.compare --chain B2 A1-structure A2-hybrid A3-rerank A4-expand B3 --split test` and `python -m eval.compare B0 B3 --split test` |
| 06 failure list for hand labelling | `python -m eval.failures B3 A3-rerank B2 B1 --split test` |
| Blank human review workbook + charts | `python -m eval.report_artifacts` -> `eval/Human_Review.xlsx`, `reports/figures/` |
| 03, 06 completed human reviews (gold verification, 15 failure labels) | `eval/human_review/gold_verification.xlsx`, `eval/human_review/failure_labels.xlsx` |
| 07 planted prompt injection | `python -m eval.injection_test` |
| 07 PII unit tests | `python -m tests.test_pii` |
| Re-score saved runs without API calls | add `--rescore` to `run_eval` |

## Repository layout
```
compass/   s1_crawl s2_extract s3_chunk s4_embed s5_index s6_retrieve s7_rerank
           s8_ground s9_generate pipeline rewrite pii pii_audit chunk_stats config
eval/      golden.jsonl (50 items, dev/test) run_eval compare failures check_golden injection_test
reports/   00_proposal ... 07_ethics
app.py     Streamlit UI
```

## Notes
- The SharePoint PDFs (calendars, handbook, ...) are **not** fetched by the crawler:
  SharePoint's robots.txt disallows all crawlers. They arrive with Stage 2 as
  hand-downloaded files with recorded sources.
- This code was written with Claude Code in a pairing session (see the README's
  "AI usage" section). Whoever commits it should read it first and be able to explain
  each step above; that's what the course's Q&A checks.
      
