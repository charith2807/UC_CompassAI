# Chunking

Both strategies use 500 proxy tokens with 75 overlap for long sections.
Structure-aware chunks preserve heading paths. Tables remain Markdown; very
large tables can span windows, so table boundaries remain a known limitation.
Counts use a Unicode word/punctuation proxy, not MiniLM WordPiece tokens.
Embedding separately splits by the actual model tokenizer to prevent truncation.

```json
{
  "fixed": {
    "chunks": 668,
    "min": 41,
    "p50": 500.0,
    "p95": 500.0,
    "max": 500,
    "mean": 438.29491017964074,
    "tokenizer": "unicode-word-and-punctuation-proxy-v1"
  },
  "structure": {
    "chunks": 2825,
    "min": 3,
    "p50": 24.0,
    "p95": 500.0,
    "max": 500,
    "mean": 95.80743362831858,
    "tokenizer": "unicode-word-and-punctuation-proxy-v1"
  }
}
```

Reproduce: `.venv/bin/python -m indexing.chunking`.
Retrieval quality has not yet selected a winning strategy.
