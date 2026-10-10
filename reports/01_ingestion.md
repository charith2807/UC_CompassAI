# Ingestion and extraction

## Extraction snapshot

The historical extraction run processed 175 source files: 170 HTML pages and five PDFs. All 175 were kept at extraction time, with zero extraction errors. A later privacy normalization pass retained 171 documents: 166 HTML pages and five PDFs. It quarantined four directory-like pages after email de-obfuscation revealed more than five distinct addresses. Ten retained documents contain extracted HTML tables. The normalized corpus also records 336 candidate contact-name lines redacted by heuristic.

| Stage or measure | Observed value |
| --- | ---: |
| Files processed by extraction | 175 |
| HTML / PDF inputs | 170 / 5 |
| Extraction errors | 0 |
| Documents after privacy normalization | 171 |
| Retained HTML / PDF | 166 / 5 |
| Directory-like documents quarantined | 4 |
| Retained documents with HTML tables | 10 |
| Candidate contact-name lines redacted | 336 |

These are counts from the saved extraction and normalization artifacts (`data/extract_log.csv`, `docs/corpus_counts.json`, and `docs/normalization_exclusions.json`). They describe different stages and should not be collapsed into a single “documents kept” count.

## Method and metadata

HTML extraction uses Trafilatura and pandas table parsing; headings are collected from the main content region. PDF text uses PyMuPDF. Normalized records include source URL, page type, explicit ISO effective date when found (otherwise null), heading paths, sections, crawl timestamp, content hashes, and normalization version. A crawl timestamp is not an effective date. Page types are inferred from URL patterns and require review before they are used as a substantive policy filter.

Normalization removes non-role email addresses and contact-block name candidates, rejects SSN-like patterns, and quarantines pages with directory-like email counts. Institutional telephone numbers are retained. These pattern checks are screening, not a complete privacy audit: organization names may be over-redacted and personal names inside prose may remain. A human privacy review is still required before any public release of corpus artifacts.

## Provenance and known limits

The extraction inputs include a manually supplied two-page Future Patriot Guide PDF linked from a university prospect site. Acquisition provenance is recorded, but crawler DNS was unavailable, robots compliance was not independently verified, and the PDF's effective date is unknown. Verify any advertised tuition against a current official tuition page. One older student-learning report is archived outside the active corpus. Several other PDFs are dated 2017–2018 and need currency review.

The saved Academic Calendar text is about 700 characters and contains introductory material and semester headings, not usable deadline details. Do not answer specific deadline questions from it. PDF tables are plain text rather than structured tables. Automated comparisons on Tuition, Cost of Attendance, and Commencement values matched the saved HTML; those checks do not verify every header, row, footnote, or current applicability. See `docs/table_spotchecks.json` and `docs/corpus_report.md`.

## Reproduction

With the private raw files available in `../data/raw/` from the project directory:

```bash
.venv/bin/python -m crawler.extract --raw-dir ../data/raw
.venv/bin/python -m crawler.normalize
.venv/bin/python scripts/table_spotcheck.py --raw-dir ../data/raw
```

The project does not publish raw or normalized source documents. See [../docs/REPRODUCE.md](../docs/REPRODUCE.md) for environment setup and privacy handling.

## Evidence status

Counts above are recorded outputs, not a claim that every retained page is current or free of all personal data. No new crawl was performed during application assembly. Personal-data and currency review remain outstanding.
