# Stage 1 (Scrape): files and commit plan

This bundle holds the Stage 1 crawler for `UC_CompassAI`. Copy it into the repo in
three commits on its own branch, then open a pull request for review.

## What's inside
```
compass/__init__.py         package marker
compass/config.py           shared settings: paths, User-Agent, 1 s delay, sitemap URL, extra seeds
compass/s1_crawl.py         the crawler
tests/__init__.py           package marker
tests/test_crawl_scope.py   scope + ID tests (no network, no API key)
```
`config.py` also defines paths that later stages use (normalized text, chunks,
Chroma); they are just constants and do nothing until those stages land.

## What the crawler does (be ready to explain this in Q&A)
1. Reads `sitemap.xml` (2,122 URLs) plus `EXTRA_SEEDS` from config.
2. Keeps only URLs that pass `is_in_scope()`: https, a `*.ucumberlands.edu` host, and an
   allow-listed section (`ALLOWED_SECTIONS`: admissions, tuition-aid, academics, ...).
   Blocks `/directory` (712 staff profiles = personal data), `/faculty-staff` and login
   pages. Result: 264 pages in scope.
3. `interleave_by_section()` round-robins across sections so a small test crawl
   samples every section.
4. `PoliteSession`: parses each host's `robots.txt` (unreadable = disallowed) and sleeps
   1.0 s before every request (<= 1 request/second); descriptive User-Agent.
5. Decides HTML vs PDF from the `Content-Type` header (not the URL), skips duplicate
   content by sha256, and queues PDF links found on crawled pages.
6. Saves raw bytes to `data/raw/{doc_id}.html|.pdf` **before any parsing**, plus one
   line per document in `data/raw/manifest.jsonl` (url, final_url, kind, section, bytes,
   sha256, fetched_at). `doc_id = sha1(url)[:12]` is deterministic, so re-crawls keep
   the same IDs.
7. Re-checks scope on the *final* URL after redirects.

`data/raw/` is git-ignored: scraped content never goes into the repo.

## Commit plan
```bash
cd UC_CompassAI
git checkout main && git pull
git checkout -b stage/crawl
```

### Commit 1: shared configuration
```bash
mkdir -p compass && cp <bundle>/compass/__init__.py <bundle>/compass/config.py compass/
git rm -q compass/.gitkeep
git add compass/
git commit -m "feat: add shared config for paths, crawl settings and .env loading" \
  -m "Central place for data paths, the sitemap URL, the descriptive User-Agent,
the 1-second request delay and extra seed URLs. Loads .env and keeps model
downloads inside the project."
```

### Commit 2: the crawler
```bash
cp <bundle>/compass/s1_crawl.py compass/
git add compass/s1_crawl.py
git commit -m "feat: add sitemap crawler with robots.txt, rate limit and scope allow-list" \
  -m "Crawl in-scope pages from the sitemap, honoring robots.txt per host and a
1 req/s delay. Save raw bytes and a JSONL manifest (url, sha256, timestamp)
before parsing, keyed by deterministic doc IDs. Exclude the staff directory,
faculty-staff and login pages; dedupe by content hash; re-check scope after
redirects."
```

### Commit 3: tests
```bash
mkdir -p tests && cp <bundle>/tests/__init__.py <bundle>/tests/test_crawl_scope.py tests/
git rm -q tests/.gitkeep
git add tests/
git commit -m "test: cover crawl scope exclusions and deterministic doc IDs" \
  -m "Check that directory, faculty-staff, login, news and non-https URLs are
rejected, that student-facing pages and university PDFs are accepted, and
that doc IDs and URL normalization are stable."
```

## Verify before pushing
```bash
python -m tests.test_crawl_scope                          # 3 passed (no network)
python -m compass.s1_crawl --max-pages 30                 # ~40 s; writes data/raw/
```
Expected from the 30-page run: about 30 HTML + a few PDFs, ~4 pages from each major
section, `skipped: none`. `git status` must show nothing under `data/raw/` (ignored).

## Pull request
```bash
git push -u origin stage/crawl
```
- **Title:** `feat: stage 1 crawler (sitemap, robots.txt, rate limit, raw store)`
- **Description:** what the crawler does (the list above), how to verify (the two
  commands), and the scope decisions (allow-list; directory and login excluded).
- **Reviewer:** one teammate approves before merge.

## Notes
- The SharePoint PDFs (calendars, handbook, ...) are **not** fetched by the crawler:
  SharePoint's robots.txt disallows all crawlers. They arrive with Stage 2 as
  hand-downloaded files with recorded sources.
- This code was written with Claude Code in a pairing session (see the README's
  "AI usage" section). Whoever commits it should read it first and be able to explain
  each step above; that's what the course's Q&A checks.
      
