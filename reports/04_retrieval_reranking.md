# Retrieval and reranking

## Implemented design

The project exposes dense, BM25, and hybrid retrieval. Dense retrieval uses Chroma cosine distance over L2-normalized 384-dimensional `all-MiniLM-L6-v2` embeddings. BM25 ranks lexical matches. Hybrid retrieval combines their ranked lists with reciprocal rank fusion using configured constant `k=60`; it does not add incomparable raw score scales. The configured candidate pool is 20. A cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) scores candidates and returns at most five passages for generation. The reranker is pinned to `233902d25c440f23af6f7d6e94d2946bac0bee0a`. The calibration artifact must bind the development gold data, split, and pinned reranker model.

Page-type metadata filtering is supported. Retrieval traces preserve candidates, ranks, scores, and timing so that the reranker ceiling and added latency can be measured. Candidate Recall@20 is the maximum evidence recall available to any reranking of that pool.

## Evidence available

Real Chroma persistence, metadata filtering, strategy deletion, and zero-stale assertions passed with synthetic vectors. This is integration evidence for the store lifecycle, not a retrieval-quality experiment. Real model downloads and both corpus indexes completed. Real-backend Streamlit smoke checks passed BM25, dense and hybrid retrieval, 20 candidates, top-five rerank cap, metadata filtering and cited tuition evidence. Graded Recall@5/20, MRR, nDCG@10, reranker lift and latency comparisons remain unavailable.

## Planned measurements

After human verification of the golden set, pin the provider/model and resolved reranker revision, then compare BM25, dense, and hybrid on the same development questions. Automatic provider fallback must be disabled for evaluation. For reranking, retain pre-rerank candidate ranks and scores, reranker scores for the full candidate pool, the top-five evidence, and latency for each stage. Report Recall@20 as the reranker ceiling and quantify changes against the same items. Use paired per-item resampling or a paired test before describing differences as improvements. Do not use the reserved test split for tuning.

## Reproduction

```bash
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass_fixed
.venv/bin/python -m indexing.rechunk --strategy structure --collection compass
.venv/bin/python -m eval.run_eval --split dev --baselines B0 B1 B2 A1_structure_dense A2_structure_hybrid A3_structure_rerank B3
```

Models are cached; evaluation still requires human verification of every development item used and a pinned provider. See [../docs/eval_report.md](../docs/eval_report.md) for definitions, grading, freezing, and the one-time test protocol.

## Program relevance correction

PhD program scope now filters candidates before truncation in both retrievers.
Source titles and headings are included in BM25 and cross-encoder text. Regression
checks cover the IT acronym, degree continuity, generic PhD clarification, study
format for fees, and exclusion of other programs. A real UI regression passed all
three retrieval modes without occupational-therapy evidence or index errors.
This is a bug fix and component verification, not a graded retrieval improvement.
The provisional evidence threshold still needs verified-dev calibration.

Multi-turn query resolution now retains pending clarification intent and topic
references across questions. Subject replies complete the original request; new
facets replace the earlier facet while keeping the named program. Generic topics
and explicit conversation completion are covered by regression checks.
