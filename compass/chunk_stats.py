"""Chunk statistics for report 02: counts and token-length distributions per strategy,
measured with the embedding model's own tokenizer (what actually gets truncated).

Reads:  data/chunks/{strategy}_v1.jsonl
Run:    python -m compass.chunk_stats
"""
import json

import numpy as np

from compass import config
from compass.s4_embed import get_model

BINS = [0, 32, 64, 128, 192, 256, 384, 10_000]


def main() -> None:
    tok = get_model().tokenizer
    limit = get_model().max_seq_length
    print(f"| strategy | chunks | docs | p10 | p25 | p50 | p75 | p90 | p95 | max | >{limit} tokens (truncated) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    hists = {}
    for strategy in ("fixed", "structure"):
        chunks = [json.loads(line) for line in open(config.CHUNKS_DIR / f"{strategy}_v1.jsonl")]
        n = np.array([len(tok.tokenize(c["text"])) for c in chunks])
        p = np.percentile(n, [10, 25, 50, 75, 90, 95]).astype(int)
        print(f"| {strategy} | {len(chunks):,} | {len({c['doc_id'] for c in chunks})} | " + " | ".join(map(str, p))
              + f" | {n.max()} | {(n > limit).sum()} ({(n > limit).mean():.1%}) |")
        hists[strategy] = np.histogram(n, bins=BINS)[0]
    print("\n| tokens | " + " | ".join(f"{a}-{b if b < 10_000 else 'max'}" for a, b in zip(BINS, BINS[1:])) + " |")
    print("|---|" + "---|" * (len(BINS) - 1))
    for strategy, h in hists.items():
        print(f"| {strategy} | " + " | ".join(str(x) for x in h) + " |")


if __name__ == "__main__":
    main()
