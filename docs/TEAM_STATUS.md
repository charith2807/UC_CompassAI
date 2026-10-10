# Team status

Verified local snapshot: 2026-10-10. Done means the listed component work and checks
completed; GitHub merging and experimental validation are separate.

| Area | Status | Verified state and remaining work |
|---|---|---|
| Infrastructure and crawl | Partial | Original setup and crawling completed. New runtime dependencies, CI and handoff changes await owner commits/review; check branch protection and board in GitHub. |
| Extraction and normalization | Partial | Original extraction completed, including the fifth PDF. 171 active docs (166 HTML, 5 PDF), four quarantined, ten table docs. New normalization/report changes await owner commits; manual table, privacy and calendar review remains. |
| Chunking and embedding | Done | 668 fixed and 2,825 structure chunks embedded with real pinned MiniLM; batched subwindow alignment tests pass. Graded strategy comparison remains pending. |
| Vector storage | Done | Both real persistent indexes built, 384-dimensional normalized vectors with cosine metric, zero orphan chunks. Persistence/filter/delete unit integration passes. |
| Retrieval and reranking | Done | Real hybrid/BM25/dense UI checks passed, 20 candidates reranked to <=5; tuition metadata filter passed. No graded quality results claimed. |
| User interface and generation | Partial | Local Groq generation verified with metadata citations. Structured follow-up state and corrected tuition columns are tested. Human evaluation and calibration remain pending. |
| Evaluation and ethics | Partial | 40 draft questions, 24 dev/16 test; safeguard tests pass. Human gold verification, dev calibration, freeze, single test run and failure labels remain pending. |
| Model artifacts | Done | Both prescribed models downloaded successfully; reranker revision pinned. Models/indexes remain local and excluded from handoffs. |
| Graded evaluation | Pending | No dev/test evaluation has run; held-out split untouched. No metrics invented. |
| Core automated checks | Done | 89 tests passed. Real backend and UI smoke evidence recorded in app_verification.json. |

## Remaining team actions

Each owner commits and opens a real PR using their own account. The infrastructure
and extraction guides include only follow-up changes since completed local HEAD;
unchanged prior work is not recommitted. Human reviewers submit actual reviews.
Golden answers, tables/privacy, and at least 15 failure labels need human checking.
Each teammate supplies their own key in the git-ignored .env or environment, never in a handoff or commit. Pin one provider for evaluation; automatic fallback is app-only.

Early sandbox DNS/socket restrictions were removed. The current server health
endpoint returns `ok`; real model/index smoke tests pass. See REPRODUCE.md for
fresh-checkout setup using privately transferred data/processed/ and prepare_app.py.
