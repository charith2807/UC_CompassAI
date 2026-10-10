# Chunking and re-chunking

## Strategies

The project compares deterministic fixed windows with heading-aware section chunks. Both use a target of 500 tokens and 75-token overlap when a section exceeds the window. Heading-aware chunks carry the section heading path in metadata. Tables remain Markdown text and may cross window boundaries when large.

The reported lengths use `unicode-word-and-punctuation-proxy-v1`, a Unicode word/punctuation counter. These counts are not MiniLM WordPiece token counts. Before embedding, long chunk text is split using the model tokenizer and pooled so input is not silently truncated.

## Recorded chunk distributions

The checked-in `docs/chunking_counts.json` reports:

| Strategy | Chunks | Minimum | Median | 95th percentile | Maximum | Mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed | 668 | 41 | 500 | 500 | 500 | 438.29 |
| Heading-aware | 2,825 | 3 | 24 | 500 | 500 | 95.81 |

These are corpus-level chunk counts and proxy-token length summaries. The larger heading-aware count reflects section boundaries and many short sections. It is not evidence that either strategy retrieves better.

## Re-chunk migration

Chunk IDs are deterministic and include document ID, strategy, version, and position. Rebuilding reads normalized documents rather than crawling again. The migration path computes new vectors, removes the prior strategy/version, and records deletion and orphan checks in the index manifest. The Chroma persistence, filtering, deletion, and zero-stale behavior has been exercised with synthetic vectors. Real model downloads and both corpus indexes now completed: 668 fixed chunks and 2,825 structure chunks, each with zero orphan chunks. Batched WordPiece subwindow pooling passed alignment checks. This establishes successful indexing, not retrieval quality.

## Reproduction

```bash
.venv/bin/python -m indexing.chunking
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass_fixed
.venv/bin/python -m indexing.rechunk --strategy fixed --collection compass
.venv/bin/python -m indexing.rechunk --strategy structure --collection compass
```

The first command writes `data/chunks/` and refreshes `docs/chunking_counts.json`. Index commands require the private normalized corpus in `data/processed/` and cached model weights. See [../docs/REPRODUCE.md](../docs/REPRODUCE.md).

## Interpretation

No retrieval metric comparison has been run on these chunk sets. Chunking preference must be based on the same verified development questions and a controlled run; the reserved test split must remain untouched until the final configuration is frozen.
