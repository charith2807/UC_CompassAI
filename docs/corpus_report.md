# Corpus and normalization

The extraction input has 175 documents: 170 HTML files and five PDFs. The fifth
PDF is the two-page Future Patriot Guide, linked from the university prospect site.
The manually downloaded PDF carries acquisition provenance; its effective date and
robots compliance were not independently verified. The 2015–2016 business learning
report is archived outside the active corpus.

The privacy normalization pass retained **171 documents: 166 HTML and five PDFs**.
Ten retained documents have extracted HTML tables. Four pages were quarantined after
email de-obfuscation revealed more than five distinct addresses: Contact Us, Clubs
and Organizations, Military Students, and Scholarships. This loses potentially
useful information; selective, human-reviewed contact removal is future work.
The seed log contains 2,122 URL decisions, of which 1,852 were excluded.
The log excludes directory/login sections and unrelated content before crawling.

Normalization adds source URL, URL-based page type, explicit ISO effective date
(or null), hierarchical heading paths, per-section text, crawl timestamp, normalized
hash, and normalization version. Institutional telephone lines are retained.
Contact-block heuristics redacted 336 candidate person-name lines. This is a
conservative heuristic: some organization/section names may be over-redacted, and
names embedded in prose may remain. Human privacy review is still required before
publishing artifacts or deploying the chatbot.

The Academic Calendar text is approximately 700 characters and contains introductory
material and semester headings, not usable deadline details. It must not support
specific deadline answers. Several existing PDFs are old. The UI shows crawl dates,
but a crawl date does not establish that a policy is current.

## Saved-table checks

`python scripts/table_spotcheck.py --raw-dir ../data/raw` compared these values in
saved HTML with normalized Markdown tables; every listed comparison passed:

| Page | Values checked | Extracted tables |
| --- | --- | ---: |
| Tuition | $9,875; $335; $220; $355 | 2 |
| Cost of Attendance | $26,471; $31,648 | 15 |
| Commencement | December 15; 10:00 am; 12:30 pm | 1 |

These are automated spot-checks, not human verification of headers, every row,
footnote meaning, or current applicability. HTML superscript footnote markers are
removed to prevent numbers such as $9,8751; a reviewer must check the footnote text.
PDF tables are currently plain text, not structured Markdown tables.

## Reproduce

```bash
python -m crawler.extract --raw-dir ../data/raw
python -m crawler.normalize
python scripts/table_spotcheck.py --raw-dir ../data/raw
```

Raw/processed documents, chunks, local indexes, and excluded documents stay outside
public commits and owner packages. Share the private normalized corpus separately
through the team's approved channel. See corpus_counts.json and
normalization_exclusions.json for actual normalization output.

Saved tuition table alignment was repaired using matching headers and row labels from the extracted pandas table. Empty bi-term cells now remain empty and per-credit amounts remain in the per-credit column. This normalization fix used saved data only; no recrawl occurred. Full manual table review remains pending.
