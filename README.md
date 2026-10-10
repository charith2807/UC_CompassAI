# Cumberlands Compass AI

A university information assistant built from saved public university pages. The
pipeline normalizes documents, compares fixed and heading-aware chunks, embeds with
MiniLM, stores normalized vectors in persistent Chroma, retrieves with BM25/dense/RRF,
reranks with a cross-encoder, and generates evidence-cited answers through Groq, OpenAI, or Gemini.
Streamlit displays conversation history, source links, crawl dates and retrieval traces.

## Run

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/download_models.py
export HF_HUB_OFFLINE=1
.venv/bin/python -m crawler.normalize
.venv/bin/python -m indexing.chunking
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass_fixed
.venv/bin/python -m indexing.rechunk --strategy structure --collection compass
.venv/bin/python -m streamlit run app/streamlit_app.py
```

Place the privately shared normalized corpus in data/processed/ first. For extraction
from the sibling raw folder: `python -m crawler.extract --raw-dir ../data/raw`.
Set GROQ_API_KEY locally for preferred Groq generation. OPENAI_API_KEY and
GEMINI_API_KEY enable fallback providers, in that order. The git-ignored root .env is loaded into the environment without overriding existing variables. If no configured provider succeeds, the app labels retrieval-only
source excerpts. Evaluation pins one provider and rejects fallback. UI mock is a separately labelled interface demonstration.

The real backend and all three retrievers passed local smoke checks; 89 automated
tests passed. See the reproduction log for evidence. A fresh checkout requires the
private corpus and `.venv/bin/python scripts/prepare_app.py` before starting chat.

## Evidence and limits

See [reproduction and actual smoke evidence](docs/REPRODUCE.md),
[corpus report](docs/corpus_report.md), [chunk comparison](docs/chunking_report.md),
[evaluation protocol](docs/eval_report.md), and [ethics safeguards](docs/ETHICS.md).
No retrieval-quality improvement or final evaluation results are claimed yet. The
40 golden items require human verification; the final test split has not been run.
The refusal threshold is provisional. Old PDFs, calendar extraction, name-redaction
coverage, PDF tables, and claim entailment remain known limitations.

## Collaboration

The code is handed off by role, with no new build commits made by the assistant.
Each owner must inspect, test, and commit their own files using their own account,
then receive actual teammate approval on a PR into protected main. See
[the workflow](docs/PROJECT_WORKFLOW.md) and [team status](docs/TEAM_STATUS.md).
Never commit .env, raw/processed documents, chunks, models or local indexes.

## AI usage

Codex assisted with extraction improvements, normalization, pipeline implementation,
tests, draft golden questions, report drafting, and owner-package preparation. The
team must verify gold answers, tables, privacy filtering and experimental results,
and explain the code and formulas. Drafts and mock tests are not human verification.
No review, approval, metric or gold answer is fabricated. Earlier extraction commits
exist; the full application build has not been committed or pushed by the assistant.

Technical references: [Sentence Transformers](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html),
[Chroma explicit embeddings](https://docs.trychroma.com/docs/collections/add-data),
[OpenAI structured output API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
and [Streamlit chat input](https://docs.streamlit.io/develop/api-reference/chat/st.chat_input).
