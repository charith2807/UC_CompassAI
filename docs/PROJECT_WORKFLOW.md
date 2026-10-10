# Team workflow

## Ownership and contributions

The exact file map lives in [OWNERSHIP.json](OWNERSHIP.json). Each contributor works only on their role-owned paths, commits under their own GitHub account, and opens their own pull request. An assistant may prepare code or documentation; it does not commit, push, author a review, or claim approval on a contributor's behalf. Existing files already on `main` should be updated in place when their owner has a real change. Do not manufacture a recommit just to make the history appear complete.

The role identifiers are `infra-owner`, `extraction-owner`, `chunking-owner`, `vector-owner`, `retrieval-owner`, `ui-owner`, and `evaluation-owner`. The package builder validates that required files exist, each file has one owner, and each project source, document, test, and CI configuration file is accounted for. Evaluation helpers are required inputs to the evaluation archive.

## Integration sequence

Merge in this order: `infra-owner` → `extraction-owner` → `chunking-owner` and `vector-owner` (either order, after extraction) → `retrieval-owner` → `ui-owner` → `evaluation-owner`. Rebase or update each later branch against the newly merged default branch before requesting review. Resolve conflicts in the file owner’s branch and state the resolution in the PR.

Review assignments are reciprocal for `infra-owner` ↔ `extraction-owner` and `vector-owner` ↔ `chunking-owner`. `retrieval-owner` and `ui-owner` review each other. `evaluation-owner` reviews `retrieval-owner`, and `retrieval-owner` reviews `evaluation-owner`. The pull request author requests the assigned reviewer in GitHub. Only the assigned human reviewer records a review; a checklist or suggested comment in a package is not an approval.

## Contributor commands

For a new contributor, use the repository URL below and the exact primary branch assigned to your role. The clone destination name is `UC_CompassAI`. If the local checkout already exists, update its default branch instead of recloning.

```sh
git clone https://github.com/charith2807/UC_CompassAI
cd UC_CompassAI
git switch main
git pull --ff-only origin main
git switch -c ROLE-BRANCH
```

Primary branches: `infra-owner` → `devops/repo-setup`; `extraction-owner` → `extract/document-normalization`; `chunking-owner` → `chunk/structure-aware`; `vector-owner` → `vector/chromadb`; `retrieval-owner` → `retrieval/dense-hybrid`; `ui-owner` → `ui/streamlit-chat`; `evaluation-owner` → `eval/golden-set`.

Copy the package's owned files into this checkout, preserving their relative paths. Review `git status --short` and stage only the exact logical commit groups listed in `PR_GUIDE.md`; never use `git add .` or `git add -A`. Commit each group separately under your own authenticated account. The package supplies exact `git add`, commit, push, and `gh pr create` commands for its branch. `FILES.md` distinguishes source paths to commit from handoff guides to consult but leave uncommitted. The browser alternative is to create the same branch, upload or edit only owned paths, open a PR against `main`, add the assigned reviewer, and paste the package's PR body.

## Review and merge

Before requesting review, run the checks applicable to your pipeline areas and include the commands and actual results in the PR body. Reviewers inspect the diff, run relevant checks where practical, and leave specific comments tied to observed behavior. Address feedback in a new commit, reply with what changed, and request another review. Use an approval state only after a reviewer has examined the current diff and chosen GitHub's Approve action. Merge only when required checks pass, the assigned review is recorded, conflicts are resolved, and the PR is ready under repository policy.

## Package data boundary

Packages contain owned source paths plus role instructions. They exclude secrets, raw/processed documents, chunk files, indexes, model weights, virtual environments, caches, and distribution artifacts. Package copies of crawl/extraction logs, seed decisions, and PDF-source metadata have absolute user-home/profile path segments replaced by `[redacted-profile]`; hashed URL placeholders and hash IDs remain intact. This sanitization applies to archive copies only and is described in each package's quickstart. Never copy credentials, API keys, or private source documents into a commit or PR.
