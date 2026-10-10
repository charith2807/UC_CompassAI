# Golden evaluation set

## Inventory

`eval/golden_set.jsonl` contains 40 drafted question records. The stored split in `eval/split_manifest.json` assigns 24 to development and 16 to test (seed 633). The split is persisted so that verification does not silently reshuffle items.

| Category | Draft items |
| --- | ---: |
| Single-hop factual | 15 |
| Multi-hop | 6 |
| Comparative | 4 |
| Temporal | 4 |
| Unanswerable | 8 |
| Ambiguous/adversarial | 3 |
| **Total** | **40** |

## Verification status

All 40 records are marked `DRAFT_NEEDS_HUMAN_VERIFICATION`; all `gold_answer` values are null. Answerable items include candidate URLs and short evidence quotes, but those are not verified gold labels. Unanswerable items record search terms and literal-match hits; a zero-hit search is not proof that an answer is absent. The expected response to ambiguous and adversarial questions also needs a human label.

The set therefore does not yet satisfy the course's human-verification requirement and cannot support a graded score. For each answerable item, a reviewer must check the live or archived source, answer, quote, source URL, and temporal applicability, then enter the answer and mark it verified. For unanswerable items, the reviewer must inspect the corpus and record why it is absent. Keep IDs and the saved split unchanged. Revise a faulty item before any model output is inspected, documenting its history.

## Protocol after human verification

Resolve and pin the cross-encoder reranker revision before any evaluation or calibration. Run development baselines only after all included items are verified, with provider and model pinned and automatic provider fallback disabled. Grade answers and citations from saved outputs. Calibration uses a manual development-label JSONL with `item_id`, `chunk_id`, `rerank_logit`, and `evidence_sufficient` (0/1); the calibration artifact binds the development gold data, split, and reranker model. Grade ambiguous items with `expected_behavior_match` (0/1). Calibrate the refusal threshold using development data and freeze the configuration. Then execute the reserved test split once and grade saved outputs without another model query. The detailed command sequence and integrity checks are in [../docs/eval_report.md](../docs/eval_report.md).

The file `eval/split_manifest.json` also records the initial set hash. Freeze checks hash the verified set and split; changing either after model output invalidates the planned comparison.
