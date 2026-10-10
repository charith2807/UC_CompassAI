#!/usr/bin/env python3
"""Build sanitized, role-scoped contributor archives and SHA256 manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROLES = (
    "infra-owner",
    "extraction-owner",
    "chunking-owner",
    "vector-owner",
    "retrieval-owner",
    "ui-owner",
    "evaluation-owner",
)
REVIEWERS = {
    "infra-owner": "extraction-owner",
    "extraction-owner": "infra-owner",
    "chunking-owner": "vector-owner",
    "vector-owner": "chunking-owner",
    "retrieval-owner": "ui-owner and evaluation-owner",
    "ui-owner": "retrieval-owner",
    "evaluation-owner": "retrieval-owner",
}
PIPELINE = {
    "infra-owner": "crawl configuration, environment setup, CI, and pipeline operations",
    "extraction-owner": "HTML/PDF extraction, normalization, and ingestion quality evidence",
    "chunking-owner": "document chunking, embedding setup, and chunk-quality evaluation",
    "vector-owner": "persistent vector storage, shared configuration, and reproducibility",
    "retrieval-owner": "lexical/dense retrieval, fusion, reranking, and retrieval baselines",
    "ui-owner": "the Streamlit experience, provider selection, answer assembly, and evidence grounding",
    "evaluation-owner": "gold-set controls, split integrity, grading, refusal checks, and ethics",
}
BRANCHES = {
    "infra-owner": "devops/repo-setup",
    "extraction-owner": "extract/document-normalization",
    "chunking-owner": "chunk/structure-aware",
    "vector-owner": "vector/chromadb",
    "retrieval-owner": "retrieval/dense-hybrid",
    "ui-owner": "ui/streamlit-chat",
    "evaluation-owner": "eval/golden-set",
}
MEMBER_FILENAMES = {
    "infra-owner": "Uday_Lokesh_Varma_Sayyaparaju",
    "extraction-owner": "Gullipalli_Pramod",
    "chunking-owner": "Karuna_Ojha",
    "vector-owner": "Tejashiva_Mekapothula",
    "retrieval-owner": "Stephen_Paul_Adithela",
    "ui-owner": "UI_Owner",
    "evaluation-owner": "Saichaithanya_Bollam",
}

# Each repository path belongs to one logical commit group for its role.
COMMIT_GROUPS = {
    "infra-owner": [
        ("repository-and-ci", "Repository setup and CI", [
            ".gitignore", ".env.example", "requirements.txt", "requirements-lock.txt", "requirements-crawl.txt",
            ".github/workflows/ci.yml", "scripts/ci_tests.py", "tests/__init__.py", "tests/fixtures.py",
            "tests/test_ingestion_monitoring.py", "README.md", "docs/PROJECT_WORKFLOW.md", "docs/TEAM_STATUS.md",
            "docs/OWNERSHIP.json", "scripts/package_team.py",
        ]),
        ("crawl-foundations", "Crawl and pipeline foundations", [
            "crawler/config.py", "crawler/crawl.py", "crawler/__init__.py", "data/crawl_log.csv",
            "data/seed_decisions.csv", "data/pdf_sources.json", "generation/settings.py", "generation/__init__.py",
            "reports/00_proposal.md",
        ]),
    ],
    "extraction-owner": [
        ("source-extraction", "HTML and PDF extraction", [
            "crawler/extract.py", "scripts/table_spotcheck.py", "docs/table_spotchecks.json",
        ]),
        ("normalization-evidence", "Normalization and corpus evidence", [
            "crawler/normalize.py", "tests/test_normalization.py", "data/extract_log.csv", "docs/corpus_report.md", "docs/corpus_counts.json",
            "docs/normalization_exclusions.json", "reports/01_ingestion.md",
        ]),
    ],
    "chunking-owner": [
        ("structure-aware-chunking", "Structure-aware chunking", [
            "indexing/__init__.py", "indexing/chunking.py", "indexing/rechunk.py", "docs/chunking_report.md",
            "docs/chunking_counts.json", "tests/test_chunking.py", "reports/02_chunking.md",
        ]),
        ("embedding-and-measurement", "Embedding setup and measurement", [
            "indexing/embed.py", "eval/__init__.py", "eval/metrics.py", "tests/test_embed.py", "scripts/download_models.py",
        ]),
    ],
    "vector-owner": [
        ("vector-store", "Persistent vector store", [
            "indexing/store.py", "config/shared_config.yaml", "tests/test_store_integration.py",
        ]),
        ("reproduction-and-deployment", "Reproduction and deployment notes", [
            "docs/REPRODUCE.md", "docs/deploy_notes.md",
        ]),
        ("index-preparation", "One-command index preparation and smoke run", [
            "scripts/prepare_app.py", "docs/app_verification.json",
        ]),
    ],
    "retrieval-owner": [
        ("dense-hybrid-retrieval", "Dense and hybrid retrieval", [
            "retrieval/__init__.py", "retrieval/bm25.py", "retrieval/dense.py", "retrieval/hybrid.py",
            "retrieval/trace.py", "retrieval/query.py", "retrieval/conversation.py", "eval/baselines.py", "tests/test_retrieval.py", "tests/test_program_scope.py", "tests/test_conversation.py", "docs/retrieval_smoke.json",
        ]),
        ("reranking", "Reranking and retrieval report", [
            "retrieval/rerank.py", "reports/04_retrieval_reranking.md",
        ]),
    ],
    "ui-owner": [
        ("streamlit-chat", "Streamlit chat experience", [
            "app/__init__.py", "app/mock_backend.py", "app/streamlit_app.py", "app/presentation.py", "app/run_demo.sh",
            "tests/test_ui.py", "scripts/smoke.py", "scripts/conversation_smoke.py",
        ]),
        ("providers-and-grounded-answers", "Providers and grounded answers", [
            "generation/answer.py", "generation/prompt.py", "generation/grounding.py", "generation/providers.py",
            "tests/test_pipeline.py", "tests/test_providers.py", "reports/05_generation.md",
        ]),
    ],
    "evaluation-owner": [
        ("gold-set-and-freeze", "Golden set and split controls", [
            "eval/golden_set.jsonl", "eval/split.py", "eval/split_manifest.json", "eval/freeze.py",
            "scripts/draft_golden.py", "reports/03_golden_set.md",
        ]),
        ("grading-safety-and-ethics", "Grading, safety, and ethics", [
            "eval/run_eval.py", "eval/grade.py", "eval/failures.md", "eval/calibrate.py", "eval/test_guard.py",
            "docs/ETHICS.md", "docs/eval_report.md", "tests/test_refusal.py", "tests/test_injection.py",
            "tests/test_eval_protocol.py", "reports/06_final_performance.md", "reports/07_ethics.md",
        ]),
    ],
}

REVIEW_TESTS = {
    "infra-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_ingestion_monitoring.py' -v",
        "python -m compileall -q crawler generation scripts tests",
    ],
    "extraction-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_ingestion_monitoring.py' -v",
        "python -m compileall -q crawler scripts",
    ],
    "chunking-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_chunking.py' -v",
        "python -m unittest discover -s tests -p 'test_embed.py' -v",
        "python -m compileall -q indexing eval",
    ],
    "vector-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_store_integration.py' -v",
        "python scripts/prepare_app.py",
        "python -m compileall -q indexing config",
    ],
    "retrieval-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_retrieval.py' -v",
        "python -m compileall -q retrieval",
    ],
    "ui-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_providers.py' -v",
        "python -m unittest discover -s tests -p 'test_pipeline.py' -v",
        "python -m unittest discover -s tests -p 'test_ui.py' -v",
        "python -m compileall -q app generation",
    ],
    "evaluation-owner": [
        "python scripts/ci_tests.py",
        "python -m unittest discover -s tests -p 'test_eval_protocol.py' -v",
        "python -m unittest discover -s tests -p 'test_refusal.py' -v",
        "python -m unittest discover -s tests -p 'test_injection.py' -v",
        "python -m compileall -q eval",
    ],
}
ROLE_REVIEW = {
    "infra-owner": "Check that environment variables stay external, CI defers tests with unmerged dependencies, crawl logs preserve useful status, and seeds/exclusions are reproducible.",
    "extraction-owner": "Inspect HTML/PDF boundary cases, heading and table preservation, quarantine and exclusion accounting, and whether normalization removes personal candidates without damaging ordinary text.",
    "chunking-owner": "Compare fixed and structure-aware boundaries, verify metadata and source identity survive rechunking, and check model setup does not imply unperformed downloads.",
    "vector-owner": "Verify collection settings match the selected embedding/chunk strategy, writes survive reload, and deletion/rebuild behavior does not leave records behind.",
    "retrieval-owner": "Inspect lexical, dense, fusion, and reranking behavior separately; verify traces support citations and removed-source records do not rank.",
    "ui-owner": "Check configured-provider selection and fallback, provider/model pinning in evaluation, source/crawl-date display, retrieval-only behavior, and grounded refusal paths.",
    "evaluation-owner": "Verify source-backed gold labels, development/test isolation, freeze and leakage guards, refusal/injection evidence, and that draft items are never reported as graded metrics.",
}

USE_CASES = {
    "infra-owner": """These cases show why repeatable infrastructure matters to a campus information assistant. Reliable crawl configuration, environment setup, and CI make changes inspectable, while source dates and exclusion decisions help prevent stale or private material from appearing as current guidance. The examples are workflow scenarios, not claims that answers or refreshes have been evaluated.

- **Tuition refresh:** A prospective student asks for tuition and fee amounts. The crawl record should show when the public cost page was reached, and CI should flag a broken source or parsing dependency before a new collection is treated as current.
- **FAFSA deadline:** A student asks when to submit aid materials. Seed decisions and PDF source metadata make it possible to trace which official aid page or document was eligible for collection and whether it was refreshed.
- **Deletion request:** A department asks to remove a retired page or personal-directory URL. The source manifest and crawl workflow should make its exclusion traceable so later stages can rebuild without that source.

In each case, infrastructure supplies reproducible inputs and operational evidence; extraction, retrieval, and evaluation still determine whether the final answer is accurate.""",
    "extraction-owner": """Extraction protects the meaning and privacy of public university material before it enters search. These scenarios focus on concrete records that students may rely on; tests and spot checks should reveal parsing limits instead of implying complete coverage.

- **Tuition table:** A student asks for tuition by program and credit load. HTML or PDF extraction must preserve the table headings, row labels, and footnotes so a fee is not presented as tuition or detached from its eligibility condition.
- **FAFSA instructions:** A student asks which federal aid form and deadline apply. The extractor should retain the relevant PDF text, section headings, and source link while exposing unreadable pages or exclusions for review.
- **Deletion request:** A staff member asks to remove an obsolete personal-directory page from the collection. Normalization and exclusion records should show what was removed and prevent its text from surviving in a newly processed record.

Counts, quarantines, and table spot checks give later owners evidence about source coverage. They do not establish that every document was parsed correctly.""",
    "chunking-owner": """Chunk boundaries affect whether a retrieved passage keeps the conditions that make campus guidance useful. These cases connect structure-aware splitting and embedding preparation to questions whose meaning depends on nearby labels or exceptions.

- **Tuition comparison:** A student asks how undergraduate tuition differs from mandatory fees. Chunks should keep table labels and related footnotes together so retrieval can return the right amount with its context.
- **FAFSA eligibility:** A student asks whether a condition applies before a deadline. A structure-aware chunk should retain the section heading and nearby exception instead of splitting the rule from its qualifier.
- **Deletion request:** A retired policy is removed and the corpus is rechunked. Rechunking should produce no residual passages from the deleted document, and counts should make the changed corpus auditable.

Fixed and structure-aware counts help diagnose coverage changes, but a higher number of chunks alone cannot show that answers improved. Model-backed comparisons should record model revisions and fixed retrieval settings.""",
    "vector-owner": """A persistent vector store must mirror the approved corpus and settings so search results can be rebuilt and checked. These examples focus on lifecycle behavior: writes, reloads, configuration, and deletion all need to remain reproducible.

- **Tuition update:** The public cost page changes for a new academic year. Rebuilding the collection should replace the old document representation, preserve metadata needed for citations, and let a reviewer inspect which configuration was used.
- **FAFSA source:** A newly approved aid guide is added. The vector store should persist its embedded records and return them after reload, while the collection configuration identifies the model and chunk strategy used.
- **Deletion request:** A personal-directory or retired policy source is removed. Rebuilding or deleting its records must leave no searchable vector entries for that source; a passing write test alone is insufficient evidence.

Reproduction notes separate source data and model artifacts from the index itself. Store integration confirms lifecycle mechanics, not answer quality.""",
    "retrieval-owner": """Retrieval should find official evidence when users phrase campus questions differently from the source page, and it should stop surfacing a document after removal. Lexical and dense signals, fusion, reranking, and traces support diagnosis across these cases.

- **Tuition wording:** A student asks about “what I pay per semester,” while the page says tuition and mandatory fees. Compare lexical, dense, and fused rankings to see whether the correct cost section appears with its conditions.
- **FAFSA acronym:** A student asks whether FAFSA materials are due before a date described on an aid page. Retrieval should surface the official deadline passage, and traces should identify the contributing query terms and ranks.
- **Deletion request:** A retired or personal-directory URL is excluded and the index rebuilt. Queries about that page should no longer retrieve its chunks; a residual result is a concrete deletion failure.

Use these query forms to check exact-source ranking, semantic matching, and deletion behavior. A ranking test verifies implementation behavior; quality claims require controlled grading.""",
    "ui-owner": """The interface should make source evidence easy to inspect and should treat unsupported or removed information carefully. These scenarios connect chat behavior, provider selection, answer grounding, and visible citations to real campus questions.

- **Tuition question:** A student asks what tuition and required fees will cost. The answer should link the official cost source and show its crawl date so the student can verify program and term details.
- **FAFSA deadline:** A student asks if a deadline applies to their situation. The assistant should cite the relevant aid passage, state any source limitation, and refuse to invent eligibility details that retrieval did not support.
- **Deletion request:** A user reports that an obsolete directory entry still appears. The interface should stop displaying it after the refreshed index is deployed and provide a clear empty or updated result rather than retaining stale conversation evidence as current.

Automatic provider fallback can help normal app use; controlled comparisons must pin a provider and model. UI tests do not prove live answer correctness.""",
    "evaluation-owner": """A credible evaluation set should include ordinary campus questions and failure cases with verified source evidence. These examples help reviewers check whether a frozen protocol measures useful behavior without treating drafts as ground truth.

- **Tuition amount:** Add a question comparing tuition with a mandatory fee, and verify the expected answer against the current official source and its term. Grading should mark a missing qualifier as an error.
- **FAFSA deadline:** Add a question about a filing deadline and the population it applies to. Keep the source citation and verified answer attached, then ensure the held-out item is not used to tune retrieval or prompts.
- **Deletion request:** After excluding a retired personal-directory page, query for its content. The expected result should contain no deleted source; a refusal or no-answer result is correct when no approved replacement exists.

Record failures and protocol limitations alongside any metric. Current golden items are draft, so none of these scenarios should be reported as graded results until verified and frozen.""",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", text))


def _branch(role: str, ownership: dict | None = None) -> str:
    return (ownership or {}).get("branches", BRANCHES)[role]


def _clone_url(repo: Path) -> str:
    workflow = (repo / "docs/PROJECT_WORKFLOW.md").read_text(encoding="utf-8")
    for line in workflow.splitlines():
        if line.startswith("git clone "):
            return line.split(maxsplit=2)[2]
    raise ValueError("PROJECT_WORKFLOW.md is missing the documented git clone command")


def _is_inventory_excluded(rel: str, excluded: set[str]) -> bool:
    path = PurePosixPath(rel)
    if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in path.parts):
        return True
    if path.name == ".DS_Store" or path.suffix == ".pyc" or path.name == ".env":
        return True
    if path.name.startswith(".env.") and path.name != ".env.example":
        return True
    return any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in excluded)


def _expanded_ownership(repo: Path, ownership: dict) -> dict[str, list[Path]]:
    owners = ownership.get("owners", {})
    if set(owners) != set(ROLES):
        raise ValueError(f"ownership roles must be exactly: {', '.join(ROLES)}")
    if ownership.get("branches") != BRANCHES:
        raise ValueError("primary branches do not match the required role branches")
    excluded = set(ownership.get("excluded_from_packages", []))
    expanded: dict[str, list[Path]] = {}
    accountable: dict[str, str] = {}
    missing: list[str] = []
    for role in ROLES:
        owned: list[Path] = []
        for spec in owners[role]:
            matches = sorted(repo.glob(spec)) if any(ch in spec for ch in "*?[") else [repo / spec]
            matches = [p for p in matches if p.is_file() and not _is_inventory_excluded(p.relative_to(repo).as_posix(), excluded)]
            if not matches:
                missing.append(spec)
                continue
            for path in matches:
                rel = path.relative_to(repo).as_posix()
                if not path.resolve().is_relative_to(repo.resolve()):
                    raise ValueError(f"owned path resolves outside repository: {rel}")
                if rel in accountable:
                    raise ValueError(f"owned path appears more than once: {rel} ({accountable[rel]}, {role})")
                accountable[rel] = role
                owned.append(path)
        expanded[role] = owned
    if missing:
        raise FileNotFoundError("required owned file(s) missing; no archives written: " + ", ".join(sorted(set(missing))))
    for role, paths in expanded.items():
        if not paths:
            raise ValueError(f"no owned files resolved for {role}")
    inventory = {
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file() and not _is_inventory_excluded(path.relative_to(repo).as_posix(), excluded)
    }
    unowned = sorted(inventory - set(accountable))
    stale = sorted(set(accountable) - inventory)
    if unowned or stale:
        details = []
        if unowned:
            details.append("unowned source/document/test/config file(s): " + ", ".join(unowned))
        if stale:
            details.append("owned path(s) absent from project inventory: " + ", ".join(stale))
        raise ValueError("; ".join(details))
    for role, paths in expanded.items():
        group_paths = [p for _, _, specs in COMMIT_GROUPS[role] for spec in specs for p in _expand_spec(repo, spec)]
        if set(group_paths) != set(paths) or len(group_paths) != len(paths):
            raise ValueError(f"logical commit groups do not account for every {role} file exactly once")
    return expanded


def _expand_spec(repo: Path, spec: str) -> list[Path]:
    matches = sorted(repo.glob(spec)) if any(ch in spec for ch in "*?[") else [repo / spec]
    return [p for p in matches if p.is_file()]


def _incremental_paths(repo: Path, role: str, paths: list[Path]) -> list[Path]:
    """For infra/extraction, stage only real follow-up deltas from completed local HEAD."""
    if role not in {"infra-owner", "extraction-owner"}:
        return paths
    if subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=repo,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode != 0:
        raise ValueError("infra/extraction incremental packages need a committed HEAD baseline")
    changed: list[Path] = []
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        has_baseline = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel}"], cwd=repo,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        if not has_baseline:
            changed.append(path)
            continue
        differs = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", rel], cwd=repo,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if differs.returncode != 0:
            changed.append(path)
    return changed


def _active_groups(role: str, files: list[str]) -> list[tuple[str, str, list[str]]]:
    active = set(files)
    return [
        (slug, title, [path for path in group_files if path in active])
        for slug, title, group_files in COMMIT_GROUPS[role]
        if any(path in active for path in group_files)
    ]


def _stage_paths(repo: Path, paths: list[Path]) -> list[str]:
    return [p.relative_to(repo).as_posix() for p in paths]


def _instructions(role: str, ownership: dict, repository_url: str) -> str:
    branch = _branch(role, ownership)
    return f"""# {role} quickstart

## Your scope

This archive supports {PIPELINE[role]}. Read `FILES.md` for the exact assigned paths and for which package guides stay out of the repository. Update files on `main` only for real changes; do not create no-op commits. Commit and push with your own account. No agent commit, push, or review is included.

## Get started

1. Install Git and authenticate to the team repository with your GitHub account. Install GitHub CLI (`gh`) for terminal PR creation.
2. Clone and create your primary role branch:

```sh
git clone {repository_url}
cd UC_CompassAI
git switch main
git pull --ff-only origin main
git switch -c {branch}
```

3. Copy only the owned paths listed in `FILES.md` into the checkout, preserving paths. Read `USE_CASE.md`, inspect `git status --short`, and review the complete diff. The archive excludes credentials, raw/processed documents, chunks, indexes, models, virtual environments, caches, and distribution files.
4. Install requirements and follow `PR_GUIDE.md` for exact staging commands, active logical commits, role-specific checks, push, and PR creation. For infra/extraction, full owned files are provided as context, but stage only follow-up changes since local `HEAD`; if there are no changes, do not make a no-op commit or open an empty PR. Record exact commands and observed results in `PR_BODY.md`; mark unrun or deferred checks plainly. Never use `git add .` or `git add -A`.

## Browser path

Create branch `{branch}` in GitHub, upload or edit only owned files, open a pull request into `main`, add the assigned peer (**{REVIEWERS[role]}**), and paste `PR_BODY.md`. `PR_GUIDE.md` lists the exact files and commands for each commit group. The terminal command does not guess a reviewer account name.

## Review, merge, and completion

Use the role-specific checks and review checklist in `PR_GUIDE.md`. Suggested comments are templates; use them only when they describe checks actually performed. Approval exists only when a human reviewer submits one on the current diff. `MERGE_ORDER.md` lists role branches, dependencies, and reviewers. Done means the owned work is integrated, relevant checks have actual results, peer review is recorded, and unresolved limits are stated in the PR.

## Sanitized archive copy

Absolute user-home/profile path segments in logs, seed decisions, and PDF-source metadata are replaced with `[redacted-profile]` in the archive copy. Hashed URL placeholders and hash IDs remain intact. Source files in the working repository are not rewritten. Check copied files and do not reintroduce private paths or credentials. The supported variable names are `GROQ_API_KEY`, `OPENAI_API_KEY`, and `GEMINI_API_KEY`; key values belong only in a local environment or approved secret store, never in source, chat, PRs, or packages. Automatic provider fallback is for application use; pin provider and model during evaluation.
"""


def _group_commands(role: str, ownership: dict, files: list[str]) -> str:
    branch = _branch(role, ownership)
    sections = []
    groups = _active_groups(role, files)
    for number, (slug, title, group_files) in enumerate(groups, start=1):
        add_command = "git add " + " ".join(group_files)
        message = f"{role}: {slug.replace('-', ' ')}"
        sections.append(f"""### Commit {number}: {title}

Stage exactly this group, review it, and make a separate commit:

```sh
{add_command}
git diff --cached --check
git diff --cached --stat
git commit -m \"{message}\"
```
""")
    if not groups:
        return "No source paths differ from `HEAD`; there is no commit or PR to create. Wait for a real owned change before starting a contribution."
    sections.append(f"""### Push and open the pull request

After all commit groups are complete:

```sh
git push -u origin {branch}
gh pr create --base main --head {branch} --title \"{role}: {PIPELINE[role]}\" --body-file PR_BODY.md
```

Add the assigned reviewer (**{REVIEWERS[role]}**) in GitHub. The command does not guess a reviewer account name.
""")
    return "\n".join(sections)


def _files_doc(role: str, files: list[str], changed_files: list[str]) -> str:
    groups = []
    active_groups = _active_groups(role, changed_files)
    for number, (_, title, group_files) in enumerate(active_groups, start=1):
        paths = "\n".join(f"- `{path}`" for path in group_files)
        groups.append(f"## Commit {number}: {title}\n\n{paths}")
    if not groups:
        groups.append("No owned repository paths differ from `HEAD`; do not make an empty commit or PR.")
    changed = set(changed_files)
    context_paths = [path for path in files if path not in changed]
    context_section = "\n".join(f"- `{path}`" for path in context_paths) or "None."
    handoff = ["INSTRUCTIONS.md", "USE_CASE.md", "FILES.md", "PR_GUIDE.md", "PR_BODY.md", "MANIFEST.sha256"]
    return f"""# Files for {role}

Only the repository paths in the commit groups below belong in commits. Use one commit per group, with the exact `git add` command in `PR_GUIDE.md`.

{chr(10).join(groups)}

## Owned context files: include in review, do not stage unless changed

These files are included for context but have no active change in this contribution:

{context_section}

## Package guides: consult, do not commit

These handoff files are generated for this archive and should stay out of repository commits:

{chr(10).join(f'- `{item}`' for item in handoff)}

The archive excludes secrets, raw/processed documents, chunks, indexes, model weights, caches, and virtual environments. See the ownership manifest for the shared exclusions.
"""


def _pr_guide(role: str, files: list[str], ownership: dict) -> str:
    groups_text = _group_commands(role, ownership, files)
    test_commands = "\n".join(f"- `{cmd}`" for cmd in REVIEW_TESTS[role])
    grouped_files = "\n".join(
        f"- **{title}:** " + ", ".join(f"`{path}`" for path in paths)
        for _, title, paths in _active_groups(role, files)
    )
    if not grouped_files:
        grouped_files = "No source paths differ from `HEAD`; no commit or pull request should be created."
    return f"""# Pull request guide for {role}

## Before opening the PR

- Confirm every changed path is owned by `{role}` in `docs/OWNERSHIP.json`; coordinate an ownership transfer before editing another role's file.
- Read the relevant pipeline report and inspect the complete diff against the latest `main`.
- Run `python scripts/ci_tests.py`, plus focused checks for changed behavior. If a check is deferred, fails due to the environment, or was not run, state that plainly. Do not turn a draft or smoke test into a quality claim.
- Check `git diff --check`, ensure no secret or excluded artifact entered the diff, and verify that any log paths remain sanitized.
- Update the relevant report and `docs/TEAM_STATUS.md` through their owners when evidence changes. Existing main-branch files should be updated as needed; no-op recommits add no evidence.
- Fill in `PR_BODY.md` with exact commands and observed results. Leave unsupported claims blank or mark them pending.

## Your branch and commit groups

Primary branch: `{_branch(role, ownership)}`. Commit each active group separately, staging only changed files. There is no minimum number of commits; do not create an empty or no-op commit. The `git add` command for each group names every source path exactly. Infra/extraction packages contain the full owned files as context, while these commands include only differences from completed local `HEAD`. If an original infra or extraction PR remains outstanding, a human must check GitHub and decide whether to continue that existing PR; do not resubmit the earlier work as a new PR.

{grouped_files}

{groups_text}

## Role-specific checks

Run applicable checks after their dependencies have merged. A command that is deferred or unavailable is not a pass. Record its exact output in the PR body.

{test_commands}

### Code review focus

{ROLE_REVIEW[role]}

## Review checklist

1. **Scope:** Does the PR change only the author's assigned paths and explain any necessary shared contract?
2. **Behavior:** Can a reviewer trace the change from input to output? Are failure paths, empty inputs, stale sources, and configuration boundaries handled where applicable?
3. **Evidence:** Are tests meaningful for the changed behavior? Are output counts and metrics based on an actual run, with data and split noted?
4. **Privacy and reproducibility:** Are credentials, raw/processed content, chunks, indexes, and model files absent? Can another contributor follow the documented setup without a private local path?
5. **Integration:** Are downstream contracts and merge dependencies clear? Did the author update from the latest `main` and resolve conflicts in their own branch?
6. **Readiness:** Required checks pass, the PR body is complete, and the assigned reviewer has examined the latest diff.

## Review assignment

The assigned peer reviewer is **{REVIEWERS[role]}**. The author requests that review in GitHub. A reviewer should read the code, run relevant checks where practical, and leave actionable comments tied to a file and observed behavior. Only the human reviewer may submit an approval. The author must address comments and request another review when commits change the reviewed behavior.

## Comment templates

Use these only after you actually performed the described review or test. Replace bracketed text with direct evidence; delete any statement that does not apply. These are neutral comment starters and never represent an approval by themselves.

**Observed issue**

> In `[path:line]`, `[observed behavior]` occurs when `[reproduction or input]`. This matters because `[specific consequence]`. Could this handle `[concrete case]`? I observed this with `[command or evidence]`.

**Check result**

> I ran `[exact command]` on commit `[short SHA]`; it `[passed/failed/deferred]` with `[brief observed result]`. `[Remaining issue or no issue in the checked scope]`.

**Resolved thread**

> Verified on `[short SHA]`: `[specific change]` addresses the behavior I reported. I reran `[exact check]` and observed `[result]`.

Do not paste an approval statement unless you reviewed the current diff and intend to submit GitHub's actual Approve review. Do not post a test result from another commit as if it covered the current diff.

## Merge sequence and unresolved limits

Integration proceeds `infra-owner` → `extraction-owner` → `chunking-owner` plus `vector-owner` → `retrieval-owner` → `ui-owner` → `evaluation-owner`. The paired reviewers are infra/extraction, vector/chunking, retrieval/UI, plus evaluation reviews retrieval and retrieval reviews evaluation. Keep provider and data limitations visible. The recorded verification confirms downloaded models, both persistent corpus indexes, real backend/UI hybrid, BM25 and dense citation checks, safety/referral/filter behavior, and HTTP health. Live LLM generation still requires a provider key, and golden answers remain unverified with no graded evaluation. Read current `docs/TEAM_STATUS.md` and evidence reports before making further claims.
"""


def _pr_body(role: str, files: list[str]) -> str:
    grouped_files = "\n".join(
        f"- **{title}:** " + ", ".join(f"`{path}`" for path in paths)
        for _, title, paths in _active_groups(role, files)
    )
    if not grouped_files:
        grouped_files = "No changed source paths; do not use this template for an empty pull request."
    return f"""## Purpose

Describe the user or pipeline behavior changed and why it matters.

## Scope

Owner: `{role}`  
Primary branch: `{BRANCHES[role]}`  
Pipeline areas: {PIPELINE[role]}  
Changed owned paths:
{grouped_files}

Keep the logical commit groups separate; see `PR_GUIDE.md` for exact staging commands.

## Validation

- Command(s) actually run:
- Observed result(s):
- Deferred or failed checks and reason:

## Evidence and limitations

- Artifact, count, or metric and how it was produced:
- Limitations or pending work:

## Review and integration

- Assigned reviewer requested: {REVIEWERS[role]}
- Merge dependency: follow `docs/PROJECT_WORKFLOW.md`.
- No approval is claimed here. A reviewer records a real review on the current diff in GitHub.

## Contributor confirmation

- [ ] I used my own account for commits and opened this PR.
- [ ] The diff contains only owned paths and no credentials, raw/processed data, chunks, indexes, or models.
- [ ] The listed checks and results are accurate for the current commit.
- [ ] Existing files were changed only where there was a real update; no no-op recommit was created.
"""


def _merge_order_doc(ownership: dict) -> str:
    branch_names = ownership["branches"]
    order = ownership["merge_order"]
    rendered = []
    for step, item in enumerate(order, start=1):
        roles = item if isinstance(item, list) else [item]
        rendered.append(
            f"{step}. " + " + ".join(f"`{role}` (`{branch_names[role]}`)" for role in roles)
        )
    reviewers = "\n".join(
        f"- `{role}` reviews: {', '.join(f'`{reviewer}`' for reviewer in review_roles)}"
        for role, review_roles in ownership["review_pairs"].items()
    )
    return f"""# Pull request merge order

Merge these role branches into `main` in order. `chunking-owner` and `vector-owner` may merge in either order after extraction.

{chr(10).join(rendered)}

## Peer review assignments

{reviewers}

The author requests the assigned reviewer in GitHub. Only that human reviewer records an approval after reviewing the current diff. A template, CI pass, or prior review is not approval for a new commit.

## Integration rules

- Each contributor commits their own files with their own account, using the role-specific commit groups in `PR_GUIDE.md`.
- Later branches update from the latest `main` and resolve conflicts in the owner branch.
- Required checks must pass, and limitations or deferred checks must be stated in the pull request.
- Existing files on `main` are updated only for a real code or evidence change; no-op recommits do not satisfy ownership.
"""


def _sanitize_metadata(path: str, data: bytes) -> bytes:
    sensitive_metadata = {
        "data/crawl_log.csv",
        "data/extract_log.csv",
        "data/seed_decisions.csv",
        "data/pdf_sources.json",
    }
    if path not in sensitive_metadata:
        return data
    text = data.decode("utf-8", errors="replace")
    # Hashed URL placeholders such as url_sha256:<id> contain no home path and
    # are deliberately left byte-for-byte unchanged by these targeted rules.
    text = re.sub(r"(?i)(/(?:Users|home)/)[^/\\\s,;:'\"?#&%]+", r"\1[redacted-profile]", text)
    text = re.sub(r"(?i)([A-Z]:\\Users\\)[^\\\s,;:'\"?#&%]+", r"\1[redacted-profile]", text)
    text = re.sub(r"(?i)(%2f(?:Users|home)%2f)[^%/\s,;:'\"?#&]+", r"\1[redacted-profile]", text)
    return text.encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(repo: Path, output: Path) -> list[Path]:
    ownership_path = repo / "docs/OWNERSHIP.json"
    if not ownership_path.is_file():
        raise FileNotFoundError(f"ownership manifest not found: {ownership_path}")
    ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
    expanded = _expanded_ownership(repo, ownership)
    if set(MEMBER_FILENAMES) != set(ROLES) or len(set(MEMBER_FILENAMES.values())) != len(ROLES):
        raise ValueError("member filename map must contain one unique filename stem per role")
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in MEMBER_FILENAMES.values()):
        raise ValueError("member filename stems may contain only letters, numbers, underscore, dot, and hyphen")
    changed_paths = {
        role: _incremental_paths(repo, role, expanded[role])
        for role in ROLES
    }
    output.mkdir(parents=True, exist_ok=True)
    archives: list[Path] = []
    archive_hashes: list[str] = []
    excluded = set(ownership.get("excluded_from_packages", []))
    merge_doc = _merge_order_doc(ownership)
    (output / "MERGE_ORDER.md").write_text(merge_doc, encoding="utf-8")
    repository_url = _clone_url(repo)

    for role in ROLES:
        paths = _stage_paths(repo, expanded[role])
        changes = _stage_paths(repo, changed_paths[role])
        if not 150 <= _word_count(USE_CASES[role]) <= 250:
            raise ValueError(f"USE_CASE.md for {role} must be 150–250 words")
        guide_text = _instructions(role, ownership, repository_url)
        if _word_count(guide_text) > 500:
            raise ValueError(f"INSTRUCTIONS.md for {role} exceeds the one-page 500-word limit")
        payloads: dict[str, bytes] = {}
        for rel in paths:
            if any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in excluded):
                raise ValueError(f"excluded artifact unexpectedly owned: {rel}")
            member = PurePosixPath(rel)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"unsafe package path: {rel}")
            payloads[rel] = _sanitize_metadata(rel, (repo / rel).read_bytes())
        generated = {
            "INSTRUCTIONS.md": guide_text.encode(),
            "USE_CASE.md": ("# Role use case\n\n" + USE_CASES[role] + "\n").encode(),
            "FILES.md": _files_doc(role, paths, changes).encode(),
            "PR_GUIDE.md": _pr_guide(role, changes, ownership).encode(),
            "PR_BODY.md": _pr_body(role, changes).encode(),
        }
        payloads.update(generated)
        manifest = "".join(f"{_sha(data)}  {name}\n" for name, data in sorted(payloads.items()))
        payloads["MANIFEST.sha256"] = manifest.encode()
        member_name = MEMBER_FILENAMES[role]
        archive = output / f"{member_name}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
            for name, data in sorted(payloads.items()):
                zf.writestr(name, data)
        staging_dir = output.parent / "members" / member_name
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        for name, data in payloads.items():
            staged_path = staging_dir / PurePosixPath(name)
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_bytes(data)
        digest = _sha(archive.read_bytes())
        archive_hashes.append(f"{digest}  packages/{archive.name}\n")
        archives.append(archive)

    (output.parent / "SHA256SUMS").write_text("".join(archive_hashes), encoding="utf-8")
    return archives


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="defaults to <repo-root>/dist/packages")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = (args.output or (repo / "dist/packages")).resolve()
    try:
        archives = build(repo, output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 2
    for archive in archives:
        print(archive)
    print(output.parent / "SHA256SUMS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
