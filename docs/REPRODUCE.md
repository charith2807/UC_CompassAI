# Setup, execution and verification

## Local interface demo

From the repository root, run `sh app/run_demo.sh` and visit
http://localhost:8501. This starts the explicitly labelled UI mock backend using
the saved tuition document; no API key or model download is required. Try
“What is tuition?”, “What is the Wi-Fi password?”, and “Will I qualify for aid?”
to inspect citations, refusal, and referral behavior. This demo does not establish
real retrieval or generation quality. The sandbox startup attempt on 2026-10-10
failed at socket binding with `Operation not permitted`; run the launcher from
the host terminal. After local hosting permissions were enabled, `sh app/run_demo.sh` started
successfully on 2026-10-10 at http://127.0.0.1:8501.
`curl --fail --silent http://127.0.0.1:8501/_stcore/health` returned `ok`
(exit 0), and the URL was opened in the default browser. This verifies the
interface demo HTTP server; live model generation remains unverified.

Use Python 3.11 for a new installation. The current local installation is Python
3.9.6/macOS with Torch 2.8.0, Sentence Transformers 3.4.1, Chroma 0.6.3,
Streamlit 1.50.0, and OpenAI SDK 1.109.1. requirements-lock.txt records the installed
versions; use requirements.txt to resolve compatible wheels on a different platform.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export PYTHONPYCACHEPREFIX="$PWD/.cache/pycache"
export HF_HOME="$PWD/.cache/huggingface"
.venv/bin/python scripts/download_models.py
# After downloads complete, avoid HTTP lookups when running cached models:
export HF_HUB_OFFLINE=1
```

Obtain the private normalized corpus from the extraction owner and put its JSON
files in data/processed/. Do not commit it. If using existing extracted data, run:

```bash
.venv/bin/python -m crawler.normalize
.venv/bin/python -m indexing.chunking
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass_fixed
# Demonstrate strategy migration within the active collection:
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass
.venv/bin/python -m indexing.rechunk --strategy structure --collection compass
.venv/bin/python scripts/smoke.py
.venv/bin/python -m streamlit run app/streamlit_app.py
```

Indexes persist in data/index/. Build computes all new vectors before deleting the
prior strategy/version; deletion and zero-orphan checks are recorded in the manifest.
It never calls the crawler. The embedder is all-MiniLM-L6-v2 with 384 dimensions,
L2-normalized embeddings, and cosine distance. Long chunk text is split with the
actual model tokenizer and pooled rather than silently truncated. Chunk reports use
a separate, explicitly identified word/punctuation proxy.

For generated answers, put GROQ_API_KEY in the git-ignored root .env or export it in your terminal. The app loads .env automatically without overriding existing environment variables. The application
tries Groq first, then configured OpenAI and Gemini keys (OPENAI_API_KEY and
GEMINI_API_KEY). No key is needed
for retrieval-only source excerpts. Never put keys in tracked files, packages, or PRs; .env.example contains blank placeholders only. The Streamlit
sidebar selects dense/BM25/hybrid and a page-type filter. UI mock is explicitly
labelled and is only for interface checks; it is not an alternative retrieval model.

## Verification commands

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/ci_tests.py
.venv/bin/python -m compileall -q crawler indexing retrieval generation app eval scripts tests
.venv/bin/python scripts/table_spotcheck.py --raw-dir ../data/raw
```

## Actual verification on 2026-10-10

- All 89 automated tests passed, including batched embedding-window alignment,
  credential refusal, provider routing, citation checks, and Chroma lifecycle checks.
- Both real models downloaded successfully. Reranker is pinned to
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`.
- MiniLM indexes contain 668 fixed chunks and 2,825 structure chunks, with zero
  orphan chunks, 384 dimensions, L2-normalized vectors and cosine distance.
- `HF_HUB_OFFLINE=1 .venv/bin/python scripts/smoke.py` passed cited tuition,
  credential refusal, out-of-corpus weak-evidence refusal, individualized aid
  referral, tuition metadata filter, candidate count >=20 and rerank cap <=5.
- Streamlit AppTest exercised the real University corpus backend with hybrid,
  BM25 and dense modes. Each tuition request returned citations, 20 candidates,
  and at most five selected chunks, without startup errors. Refusal and referral
  passed. Observed component timings are in app_verification.json, not graded
  evaluation results or latency distributions.
- The real-backend HTTP server started at http://127.0.0.1:8501 and its health
  endpoint returned `ok`. Reload the page after an earlier failed session.
- A local Groq key is configured in the git-ignored .env. Real generation with
  openai/gpt-oss-20b has been verified; no keys are included in handoffs.
- No dev/test evaluation was run. Golden data remains draft and the held-out split
  untouched. The evidence threshold remains explicitly uncalibrated.

For a teammate's fresh checkout, first privately obtain data/processed/, install
requirements.txt, then run:

```bash
.venv/bin/python scripts/prepare_app.py
HF_HUB_OFFLINE=1 .venv/bin/python -m streamlit run app/streamlit_app.py
```

This downloads the two pinned models, normalizes and chunks the saved corpus,
creates both indexes, and runs real smoke checks. It never re-crawls. Do not commit
or package the corpus, chunks, model cache or index. Models use safetensors only;
HTTP download is used instead of Xet to avoid the observed stalled transfer.
Embedding subwindows are batched and then pooled back to each original chunk.

Numeric spot-checks on Tuition, Cost of Attendance and Commencement matched saved
HTML. Human full table and privacy reviews remain pending. Python LibreSSL and
non-fatal Chroma telemetry warnings were observed; they did not invalidate checks.
Use Python 3.11 for a clean deployment environment. Early sandbox attempts had DNS
and socket restrictions; those restrictions were removed before the successful
model downloads and real-backend HTTP checks recorded above.

## PhD/IT relevance regression checks

89 tests pass after adding acronym, program-scope, degree-change and ambiguous-fee
regressions. Real Streamlit AppTest passed generic PhD clarification, named IT PhD
retrieval and an IT-field correction in hybrid, BM25 and dense modes. Named IT
responses cite only the saved executive PhD IT program page, with no occupational
therapy evidence. A restrictive tuition category gives filter guidance.

Program scope is applied before top-20 truncation in both BM25 and dense search.
BM25 and the cross-encoder receive source titles and heading paths. IT is resolved
as Information Technology; lowercase pronoun follow-ups retain the prior degree.
Generic PhD questions ask for a subject. Fees require a study format, and career
salary snippets cannot supply fee evidence. Online requests cannot silently use
the executive program page. If the selected program's fee is not explicitly
supported, the bot refuses rather than borrowing another program's amount.

The score threshold remains uncalibrated; adding metadata context changes ranking
and therefore requires fresh verified-dev calibration before freezing evaluation.
No golden dev/test questions were run or tuned during these bug-regression checks.

## Multi-turn conversation verification

The real Streamlit UI passed tuition fee for PhD → Information technology →
executive → program requirements → done, followed by library hours → location.
The program reply retains the original tuition intent and asks for format rather
than showing a new IT overview. Requests to generation receive the resolved
question. General clarification replies, one-word follow-ups, long conversations,
per-session isolation, new topics and explicit completion are regression-tested.

Context is stored with each response in st.session_state history; it contains user
intent and pending slots, never assistant claims treated as evidence. Short replies
complete the pending question. A new facet retains the subject but replaces the
old question intent. Explicit topic changes, completion, and Clear conversation
reset context. No shared backend object stores a user's conversation.

All 89 tests pass. These are component and conversation checks, not a graded
golden-set evaluation. Fees still require matching evidence; retaining a fee
question does not authorize quoting another program's rate.

## Broader follow-up repair

Conversation state now keeps explicit degree, subject, study format, audience,
term and year selections. A comparison replaces its selection while retaining
the question intent; a new facet keeps the subject and drops the previous facet.
A standalone new topic, completion, or Clear conversation clears the old context.
The 25-case regression matrix includes comparisons in both degree directions,
subject/format corrections, international admissions, date changes, housing costs,
services, and resets. Repeated comparisons do not grow the retrieval query.

The saved tuition HTML text had shifted amounts into the bi-term column when empty
cells collapsed. Normalization now restores rows only from matching saved-table
headers and row labels, and refuses conflicting replacements. One saved tuition
document was repaired; seven fixed and 28 structure vectors were updated. Both
collections retain 668/2,825 chunks and zero missing/orphan chunks. Unit validation
rejects a correct dollar amount with an incorrect table-column unit. No recrawl
was performed. Table spot-checks still need human review.

A malformed citation gets one bounded retry with the same evidence, followed by
the same exact-quote and numeric checks. Both requests' usage is counted. Prior
assistant answers are not sent as factual context to generation. Unsupported
answers still refuse. Provider errors retain safe error types and a clearly labeled
retrieval-only fallback; these are not counted as generated-answer successes.

Some program/format combinations have no saved program page. These correctly
refuse requirements/duration questions instead of borrowing another format's
requirements. A narrowly scoped pool can have fewer than 20 available chunks;
the trace reports insufficient_pool. Do not pad it with unrelated evidence.
The threshold is still uncalibrated, and no graded dev/test evaluation was run.

Student-level source filtering now excludes explicitly graduate/program-specific sources from undergraduate follow-ups before candidate selection. Whitespace-only differences in an evidence quote map back to the exact source span; changed wording, punctuation, or amounts still fail validation. Groq rate-limit fallbacks are visibly labeled in the UI.

Final live UI smoke completed 29 turns across hybrid, BM25 and dense with
zero UI exceptions or generation/grounding errors. 16 turns completed Groq
generation; 3 requests hit Groq rate limits and displayed labeled excerpts.
Clarification, refusal and conversation-end turns do not call the provider. These
counts describe smoke execution, not answer accuracy or a graded evaluation.

Reproduce the live check (uses API quota):

```bash
HF_HUB_OFFLINE=1 .venv/bin/python scripts/conversation_smoke.py
```

Generation now selects compact identifiers for exact source spans. The app resolves
these to source text and validates chunk ownership, quote length, numbers and
table units. No source URL comes from the LLM. Unrecognized short replies request
clarification instead of silently repeating an earlier tuition answer.

### Curriculum retrieval check

The exact question `Give me course details for Phd IT` now expands to course requirements and curriculum within the resolved program scope. The real UI selected the saved Course Requirements section without an exception. A Groq completion required citation repair; its retry encountered RateLimitError, so the UI correctly fell back to labeled excerpts. A fully generated curriculum answer is not yet verified in that run. Narrow Chroma HNSW traversal failures use exact cosine ranking of the same filtered persisted vectors. Unit suite: 91 passing tests, including curriculum follow-up scope and filtered-vector fallback. This is a smoke check, not golden-set evaluation.

Invalid individual claims are now omitted when other independently validated claims support a partial answer; if none pass, the answer still fails closed. Synthetic regression verifies that fabricated numeric claims are excluded. The final live attempt remained Groq-rate-limited, so generated curriculum output still requires a live recheck after quota recovers.
