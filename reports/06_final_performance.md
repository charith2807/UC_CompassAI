# Final performance report: evaluation not yet run

## Result status

There is no graded development or test result. The 40-item set is still draft, with 0/40 human-verified records and null gold answers. The 24-item development and 16-item test assignment is saved, but no run has been performed. Configuration is not frozen, the reserved test run has not occurred, and no final performance claim can be made.

| Required evidence | Current status |
| --- | --- |
| Golden questions human-verified | 0 of 40 |
| Development evaluation | Not run |
| Refusal-threshold calibration | Not done; configured threshold remains provisional |
| Frozen configuration and pinned reranker revision | Not done |
| Reserved test evaluation | Not run |
| Human answer/citation grading | Not done |
| Hand-labeled failures | 0; 15 required |
| Retrieval, answer, citation, refusal, latency, and cost metrics | Not measured |
| Confidence intervals or paired tests | Not available |

The only measured counts elsewhere in the reports concern corpus extraction, chunk sizes, and component checks. They are not chatbot quality scores. The Chroma integration check and UI mock results do not establish real-model retrieval or answer quality.

## Required sequence to complete this report

1. Human-verify all 40 items, their source URLs, evidence, gold answers, and expected behavior while preserving IDs and the split.
2. Download and cache the fixed embedding and cross-encoder models; build both real indexes and record their manifests. Resolve and pin the cross-encoder revision before any evaluation or calibration.
3. Pin one provider/model and disable automatic fallback for evaluation. Run the listed baselines on verified development data. Human-grade saved outputs and citations; include `expected_behavior_match` (0/1) for ambiguous items. Report retrieval metrics, correctness, citation validity, refusal and over-refusal, latency, and cost.
4. Calibrate the evidence threshold from manually labeled development JSONL rows containing `item_id`, `chunk_id`, `rerank_logit`, and `evidence_sufficient` (0/1). Bind the calibration artifact to the development gold data, split, and pinned reranker model. Configure current API pricing and freeze the code, dataset, split, model, and index hashes.
5. Run the final baselines on test exactly once. Grade those saved outputs without rerunning generation.
6. Hand-label at least 15 actual failures in `eval/failures.md`. Report paired 95% bootstrap intervals or a paired pass/fail test for every improvement claim, including the B0-incorrect subset.

Commands and safeguards are specified in [../docs/eval_report.md](../docs/eval_report.md). When those steps are complete, replace this status report with the actual outputs and reproducible commands. Do not treat this report as a completed experiment.
