# 03 · Golden evaluation set

File: `eval/golden.jsonl` (50 items). Validate: `python -m eval.check_golden eval/golden.jsonl`
-> 50 items checked, 0 problems (every source URL is an indexed document; every
evidence quote appears verbatim, whitespace-insensitive, in its source).

## Composition and split
| category | required min | total | dev | test |
|---|---|---|---|---|
| single-hop | 15 | 15 | 9 | 6 |
| multi-hop | 6 | 6 | 4 | 2 |
| comparative | 4 | 4 | 2 | 2 |
| temporal | 4 | 4 | 2 | 2 |
| unanswerable | 8 | 8 | 5 | 3 |
| ambiguous / adversarial | 3 | 3 | 2 | 1 |
| PII in question (extra) | - | 3 | 2 | 1 |
| user-reported (extra) | - | 7 | 7 | 0 |
| **total** | **40** | **50** | **33** | **17** |

Expected actions: answer 36, refuse 12, refer 2. Evidence quotes: 35, longest 24 words
(limit 25).

## Item fields
`id, type, question, expected_action (answer|refuse|refer), gold_answer, must_include,
source_url, also_valid_urls, evidence_quote, split, status, verified_by, verified_on`, plus where relevant
`searched` (unanswerable items: the exact terms searched in the corpus and their hit
counts, e.g. r04 `"personal email": 0 hits; "official email": 0 hits ...`),
`must_not_include` (prompt injection a03), `accept_refusal`, `pii_values` (fake
identifiers that must never reach the LLM), `notes`.

`also_valid_urls` exists because facts repeat across pages: "$220 per credit hour"
appears on both the Tuition page and the Financial Aid FAQ; scoring only one URL
penalized a correct retriever.

## How the items were written (honest account)
- **Authoring:** 40 core items were drafted by Claude Code from the *extracted
  document text* (not from retrieval output), with evidence quotes copied from the
  pages and verified by `check_golden`. 3 PII items and 7 items from questions a team
  member asked the live chatbot were added later.
- **Human review:** all 50 gold answers were checked against the live page by the
  seven team members (7 items each, 8 for one), on 2026-10-10. Each item records
  `verified_by` and `verified_on`; the workbook with a screenshot per item is
  `eval/human_review/gold_verification.xlsx`. Result: **48 confirmed, 2 corrected**:

  | Item | Reviewer finding | Change |
  |---|---|---|
  | m06 | the cited Admission Requirements page lists Duolingo **100**; 95 is the undergraduate catalog / International Students page | gold answer and `must_include` changed to 100 |
  | r04 | a personal-email policy *is* published (catalog, University Regulations: students must use the university email), but that page is not in our corpus | kept as a gap item for this corpus; gold answer now names the policy and the corpus gap |

  Re-scoring dev after both corrections changed no reported number (every config was
  already scored correctly on both items). Two reviewer comments did not need a change:
  s13's rental fee is in our crawled snapshot but no longer on the live page (a
  staleness example), and u05's "over $400 million" endowment figure is on a news page
  outside the corpus.
- **Timing (deviation from the rubric):** the items were written *after* the chatbot
  first worked, not before. Risk: items may reflect what the system finds. Mitigation:
  facts were taken from the documents, and several items were deliberately hard
  (vocabulary mismatch s15, conflicting sources a02/c01, stale table c02).
- **Split:** stratified 60/40 by category with a fixed seed (633). Items that directly
  motivated a design change (all user-reported items, s15, a03, c01, t01, a01, s01, u01,
  u02) were forced into dev. All 50 items were run during development, so the test
  split was **not used for any decision but was not unseen**. Every tuning choice
  (rewrite fallback, section expansion, thresholds) was made on dev; test was run once
  with the frozen configuration (report 06).

## Scoring
- `answer correct`: answered (not declined) and contains every `must_include` string
  and no `must_not_include` string. Transparent but lenient; failures were
  hand-checked (report 06).
- Unanswerable: correct if refused, or if a partial answer explicitly states the gap
  ("the pages don't list ...").
- Refer items: correct only if routed to an office.
- Citation valid: cites a gold URL and no out-of-range `[n]`.
- Retrieval metrics are page-level (several chunks of one page count once).
