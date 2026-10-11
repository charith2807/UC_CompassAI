# 01 · Ingestion (crawl + extraction)

Reproduce: `python -m compass.s1_crawl --max-pages 300 --max-pdfs 15` then
`python -m compass.s2_extract`; audit with `python -m compass.pii_audit`.

## Crawl
| | value |
|---|---|
| Source | `https://www.ucumberlands.edu/sitemap.xml` (2,122 URLs) |
| In scope after allow-list | 264 pages (+1 seed PDF) |
| Fetched (HTML / PDF) | 264 / 4 = 268 documents, 43.7 MB raw |
| Crawl window | 2026-10-10 19:20:46 -> 19:28:50 UTC (~8 min) |
| Skipped by robots.txt / errors / duplicates | 0 / 0 / 0 |
| Politeness | robots.txt parsed per host in code (`PoliteSession.allowed`), 1.0 s sleep before every request, User-Agent `CumberlandsCompassAI/0.1 (student RAG course project; +repo URL)` |
| Raw store | `data/raw/{doc_id}.html|.pdf` + `manifest.jsonl` (doc_id, url, final_url, kind, section, bytes, sha256, fetched_at), written before any parsing |

**Scope.** Allow-list of student-facing sections (`about, academics, admissions,
admission-aid, tuition-aid, student-life, current-students, prospective-students,
parents, privacy-policy, graduate-education-resources`). Excluded by design: 712
`/directory` staff profiles (PII), `/faculty-staff`, login pages, 1,115 news/blog/story
pages (dated marketing content). The crawl initially used a 160-page cap with
round-robin sampling, which skipped every graduate program page; the final crawl
takes all 264 in-scope pages.

**PDFs (9 in corpus, requirement >= 5).**
| PDF | Year | Source |
|---|---|---|
| Student Handbook 2026-2027 | 2026 | SharePoint, downloaded by hand |
| Stop Campus Hazing Act Transparency Report | June 2026 | SharePoint, by hand |
| Academic Calendars Fall 2026 / Spring 2027 / Summer 2027 | 2026-27 | SharePoint, by hand |
| KCTCS to UC Course Equivalency Guide | 2024 | SharePoint, by hand |
| What To Bring (Residence Life) | 2019 | SharePoint, by hand |
| Consent to Disclosure (blank FERPA form) | 2014 | crawled |
| Visitors Guide | 2013 | crawled (seeded) |

Every current university PDF is hosted on `cumber-my.sharepoint.com`, whose
robots.txt is `Disallow: /` and which returns 403 to scripts. The crawler therefore
never fetches them. Seven were downloaded manually in a browser from links on
official pages; `data/manual_sources.jsonl` records each file's SharePoint URL (cited
in answers) and the page linking it. This is a deliberate, documented exception
(report 07).

**Two crawled "PDFs" were fake:** `Cooperating-Teacher-Guide-Fall-2018.cleaned.pdf`
and `CACREPVitalStatistics-2017.pdf` contain a printout of the homepage. Extraction
drops any PDF whose text starts with the site navigation; before this guard, tuition
answers cited "CACREP 2017".

## Extraction
| | value |
|---|---|
| Normalized documents | 273 (264 HTML + 9 PDF); 2 dropped (saved web pages) |
| Text | 2.97 M characters, median 8,202 per document |
| Documents with data tables (requirement >= 3) | 15 (Tuition, Cost of Attendance, Dining, SAP, program pages, ...) |
| Deduplication | sha256 of raw bytes, checked during crawl (0 duplicates) |
| Stored per document | doc_id, url, title, kind, page_type, effective_date, fetched_at, sha256, pii_redacted, text |

- **HTML:** Trafilatura (markdown output, tables kept, links dropped). Tuition page:
  122 KB HTML -> 8.6 KB text.
- **PDF:** PyMuPDF, one `## Page N` heading per page; dates printed above their
  event are re-joined (`Monday, August 24, 2026: Classes Begin`), see report 05.
- **Course lists:** program pages link each course to the catalog and Trafilatura
  dropped link-heavy lists as navigation (PhD in IT: 16 courses in HTML, 0 in text).
  Catalog links are unwrapped before extraction (16 / 22 / 12 course codes on
  sample pages).
- **Cleaning:** footnote tags, TOC dot leaders and form blanks collapsed (one
  handbook chunk had 147 words but 4,337 tokens before).
- **Heading path:** kept as markdown headings in the text; carried into each
  structure chunk as `Title > Section > Subsection` (report 02).

**Page type** (rule-based on URL/title): program 142, student-life 47, general 28,
admissions 21, financial 17, policy 9, about 5, calendar 4.

**Effective date** (first academic year / term / "revised" date in the title or
first 3,000 characters): found for 17 documents. Reliable for PDFs and tables (Cost
of Attendance "2025-2026", Tuition rates "Summer 2023", Handbook "2026-2027", Consent
form "revised 5/28/2014"); noisy on ordinary pages, where the first term mentioned is
not the page's date (e.g. "Apply" -> "Fall 2027"). Known limitation.
