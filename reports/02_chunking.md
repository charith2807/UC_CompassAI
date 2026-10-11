# 02 · Chunking and re-chunk migration

Reproduce: `python -m compass.s3_chunk --strategy both`, `python -m compass.chunk_stats`,
`python -m compass.s5_index --strategy both`.

## Two strategies
| | fixed (naive, used by B2) | structure-aware (used by A1-B3) |
|---|---|---|
| Rule | 150-word sliding window, 30-word overlap | split on markdown headings, heading stack carried as `Title > Section > Subsection`, sections < 40 words merged forward, paragraphs packed to <= 150 words, tables never split mid-row |
| Context header | none | every chunk starts with `Title > Section path` |
| Chunk ID | `{doc_id}_fixed_v1_{pos:03d}` | `{doc_id}_structure_v1_{pos:03d}` |

## Counts and token-length distributions
Token counts use the embedding model's own tokenizer (all-MiniLM-L6-v2, max 256 tokens;
longer input is silently truncated).

| strategy | chunks | docs | p10 | p25 | p50 | p75 | p90 | p95 | max | > 256 tokens (truncated) |
|---|---|---|---|---|---|---|---|---|---|---|
| fixed | 3,846 | 273 | 169 | 178 | 189 | 203 | 226 | 240 | 499 | 86 (2.2%) |
| structure | 4,403 | 273 | 64 | 95 | 144 | 179 | 199 | 212 | 356 | 40 (0.9%) |

| tokens | 0-32 | 32-64 | 64-128 | 128-192 | 192-256 | 256-384 | 384+ |
|---|---|---|---|---|---|---|---|
| fixed | 0 | 36 | 124 | 1,938 | 1,661 | 85 | 2 |
| structure | 105 | 322 | 1,364 | 1,971 | 600 | 41 | 0 |

Fixed chunks cluster just under the limit (150 words ≈ 190 tokens); structure chunks
follow the page's own sections, so they are shorter and more varied, and truncate less
than half as often. Words ≠ tokens: table rows like `| $9,875 ^1 | $335 |` and TOC dot
leaders cost many tokens per word (one handbook chunk was 147 words / 4,337 tokens
before dot leaders were collapsed).

Example (Tuition page): the fixed chunk starts mid-sentence and flattens the tuition
table into one line; the structure chunk is `Tuition > Undergraduate Tuition` followed
by the table with its rows intact.

Bugs found by reading chunks (counts looked fine in both cases): a hard-split step
re-joined every piece with spaces and flattened all tables; merged tiny sections kept
the first heading (a price styled as a heading, `$19,175`) instead of the substantive
one.

## Re-chunk migration (no re-crawl)
Chunking reads `data/normalized/*.json` only; the crawl is never repeated. Both
strategies live in one Chroma collection, each chunk tagged `strategy="{name}_v1"`.
Re-indexing a strategy deletes by metadata first, then re-adds, then asserts that the
stored IDs equal the new IDs:

```
fixed_v1:     chroma had 3846, deleted them, added 3846 | stale: 0, missing: 0
structure_v1: chroma had 4403, deleted them, added 4403 | stale: 0, missing: 0
collection 'compass' total: 8249 chunks
```
Over the project the corpus went 32 -> 163 -> 273 documents; each migration logged
0 stale and 0 missing (e.g. 604 -> 3,717 -> 4,765 -> 8,249 chunks). The BM25 index is
rebuilt from the same chunk file, so it cannot drift from Chroma.

## Same evaluation, both strategies (B2 -> A1-structure: only chunking changes)
Dense retrieval, no reranker, no rewrite, no expansion in both.

| split | metric | fixed (B2) | structure (A1) | delta |
|---|---|---|---|---|
| dev | Recall@5 / Recall@20 | 0.86 / 0.86 | 0.86 / 0.90 | +0.00 / +0.05 |
| dev | MRR / nDCG@10 | 0.7460 / 0.7609 | 0.7917 / 0.8085 | +0.046 / +0.048 |
| dev | answer correct, all 33 items | 0.88 | 0.88 | +0.00 [95% CI -0.15, +0.15], McNemar p = 1.00 |
| test | Recall@5 / Recall@20 | 0.79 / 1.00 | 1.00 / 1.00 | +0.21 / +0.00 |
| test | MRR / nDCG@10 | 0.7036 / 0.7652 | 0.9286 / 0.9261 | +0.225 / +0.161 |
| test | answer correct, all 17 items | 0.59 | 0.82 | **+0.24 [95% CI +0.06, +0.47]**, McNemar p = 0.125 (4 vs 0 discordant) |

Structure-aware chunking improves ranking on both splits. On test the answer gain's
bootstrap CI excludes zero but McNemar's exact test (only 4 discordant items) does not
reach p < 0.05, so we report it as a consistent but not conclusively significant gain.
