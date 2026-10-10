# Evaluation status and protocol

**No graded evaluation has been run. No performance advantage is claimed.**
Forty questions were drafted from the normalized corpus before tuning, using real
URLs and <=25-word contiguous quotes. Every item is marked
DRAFT_NEEDS_HUMAN_VERIFICATION and gold_answer is null. A human must verify the
answer, source and temporal applicability, enter a gold answer, and mark VERIFIED.
Multi-hop items include evidence from at least two source pages. Unanswerable items
record literal corpus searches; lack of a literal match is not proof of absence.
Ambiguous/adversarial items require a human expected_behavior label.

The persisted split has 24 dev and 16 test items, with stratified largest-remainder
rounding. Preserve IDs and split_manifest.json when adding verification. Do not
change the split after seeing model outputs. The final test set has not been run;
config/frozen_config.yaml intentionally does not exist yet.

## Required sequence

```bash
python -m eval.split
# Human verification and annotation. Pin llm_provider to groq, openai or gemini,
# set provider_models, and pin the resolved reranker revision before calibration.
# Then verified dev runs only:
python -m eval.run_eval --split dev --baselines B0 B1 B2 A1_structure_dense A2_structure_hybrid A3_structure_rerank B3
# Human grades: one JSONL row per baseline/item with answer_correct and citation_valid (0/1/null).
# Ambiguous/adversarial items also require expected_behavior_match (0/1).
python -m eval.grade data/runtime/DEV_RUN /path/to/human_grades.jsonl
# Human dev evidence JSONL: item_id, chunk_id, rerank_logit, evidence_sufficient (0/1).
python -m eval.calibrate /path/to/human_dev_evidence.jsonl
# Verify configured provider API pricing; otherwise costs stay unknown.
python -m eval.freeze
# Exactly one reserved test run, all final baselines in one invocation:
python -m eval.run_eval --split test --baselines B0 B1 B2 B3
python -m eval.grade data/runtime/TEST_RUN /path/to/human_test_grades.jsonl
```

Freeze requires verified golden data, calibrated config, pinned reranker, and both
real index manifests. It hashes code, golden data, split, normalized corpus, chunks, index manifests and
actual Chroma documents, metadata and vectors. Test
execution requires those hashes to match and atomically reserves a one-run receipt.
A failed test run remains reserved: document the failure rather than deleting the
receipt and quietly rerunning. Grade the saved outputs without querying the model again.

B0 is the pinned provider/model in closed-book mode; B1 uses BM25 on fixed chunks; B2 dense/fixed; B3
structure-aware hybrid, cross-encoder, threshold and grounded citations. The ablation
progression changes chunking, then retrieval, then reranking, then the evidence gate.
All retrieved-generation variants keep injection and citation safeguards.

Recall@5/20, MRR, and nDCG@10 use chunks containing exact gold evidence quotes;
overlapping copies count as separate relevant IDs. Additional evidence coverage@5/20
measures support for distinct evidence units, especially useful for multi-hop questions.
For reranked runs all scored candidates are ranked for retrieval metrics; generation
sees at most five. Candidate Recall@20 is the reranker's ceiling. Traces preserve
pre/post scores and retrieval/rerank milliseconds.

Answer correctness and citation validity remain null until human grading. URL integrity
is reported separately and never called citation validity. Refusal, over-refusal,
p50/p95 latency, and token-based cost are computed from actual outputs. Unknown pricing
produces null cost. Bootstrap intervals use 2,000 deterministic resamples. Paired
ablations and B0-incorrect-subset summaries require human grades. At least 15 actual
failures must be hand-labelled in eval/failures.md; its pending rows are not results.

Models, the API key, human gold verification, calibration and failure annotations
remain prerequisites for the final performance report. Never submit this status
report as a completed experimental result.
