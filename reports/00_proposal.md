# Project proposal and final scope

## Purpose

Cumberlands Compass AI is a retrieval-augmented information assistant for prospective and current students seeking public university information about admissions, tuition, financial aid, academic programs, calendars, and student services. It is intended to locate and explain public source material, cite the pages it uses, and decline when available evidence does not support an answer. It cannot determine an individual's eligibility, award, or other personal outcome; those questions should go to the relevant university office.

## Research question

Does a grounded pipeline combining hybrid retrieval, reranking, source validation, and refusal behavior improve evidence retrieval and answer quality over closed-book generation or single-retriever baselines? This is a question for controlled evaluation, not an assumed result. Comparison requires human-verified questions, a frozen configuration, and paired uncertainty estimates.

## Data scope

The source collection is public, unauthenticated University of the Cumberlands web content. It excludes login areas and directory-like pages. The extraction run saved 175 documents (170 HTML and five PDFs) with no extraction errors. Normalization retained 171 documents (166 HTML and five PDFs), including 10 documents with HTML tables. Four directory-like pages were quarantined. See [01_ingestion.md](01_ingestion.md) for counts, provenance, and limits. The corpus is a dated snapshot, not a live policy feed.

## System design and fixed stack

The application uses Python, Streamlit, Chroma, `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), BM25, reciprocal rank fusion (RRF), a cross-encoder reranker, and a three-provider generation adapter for Groq, OpenAI, and Gemini. This provider adapter is an authorized variation from the original OpenAI-only stack. Groq is the preferred default using `openai/gpt-oss-20b`; OpenAI `gpt-4o-mini` and Gemini `gemini-3.8-flash` are supported alternatives when configured. Dense vectors are L2-normalized and compared with cosine distance. The configured retrieval pool is 20 candidates and reranking returns at most five passages. The provisional refusal threshold is 0.5 and remains explicitly uncalibrated.

The saved normalized corpus supports two deterministic chunking strategies: fixed windows and heading-aware sections. Chunk IDs encode document, strategy, version, and position. Index migration is performed from normalized files without crawling again, and stale entries are checked after deletion.

```text
Public pages and PDFs
        -> extraction and privacy normalization
        -> fixed or heading-aware chunks
        -> normalized MiniLM vectors + BM25
        -> dense, lexical, or RRF hybrid retrieval
        -> cross-encoder ranking (up to five passages)
        -> evidence and citation checks
        -> Groq (preferred), OpenAI, or Gemini, or explicit retrieval-only excerpts
        -> Streamlit answer, sources, and retrieval trace
```

## Evaluation plan and present status

The evaluation artifact contains 40 drafted items and a persisted stratified split of 24 development and 16 test items. The intended baseline sequence is closed-book generation, BM25/fixed chunks, dense/fixed chunks, and the final hybrid system, with one-factor comparisons for chunking, fusion, reranking, and grounding. Planned measurements include Recall@5/20, MRR, nDCG@10, evidence coverage, answer correctness, citation validity, refusal behavior, latency, and cost, with paired confidence intervals where a performance comparison is made.

All 40 records still require human source and answer verification; `gold_answer` remains null. No graded development or test run has been performed. No configuration is frozen, no test run has occurred, and no performance advantage is claimed. See [03_golden_set.md](03_golden_set.md), [04_retrieval_reranking.md](04_retrieval_reranking.md), and [06_final_performance.md](06_final_performance.md) for the evidence required before the research question can be answered.

## Reproduction and current evidence

Setup, model caching, corpus placement, index commands, test commands, and known environment limits are in [../docs/REPRODUCE.md](../docs/REPRODUCE.md). Confirmed so far: 36 tests passed, including Streamlit AppTest and a real Chroma integration check, and the recorded HTML table spot-checks passed. These establish component behavior only. The real embedding/reranker model download was blocked by sandbox DNS, no provider API key was available for a generation smoke run, and local HTTP startup was denied by sandbox socket restrictions.

## AI use

AI assistance was used for code and documentation drafting and local code review. Evaluation questions remain drafts until a human verifies each answer, cited source, temporal applicability, and expected behavior. No model-generated score or unverified answer is reported as a result.
