"""Stage 4 - Embed: turn every chunk into a 384-dim vector.

Reads:  data/chunks/{strategy}_v1.jsonl
Writes: data/embeddings/{strategy}_v1.npy        float32 array, shape (n_chunks, 384)
        data/embeddings/{strategy}_v1.ids.json   chunk_ids in the same row order
Run:    python -m compass.s4_embed --strategy structure   (or: fixed, both)
"""
import argparse
import json

import numpy as np

from compass import config  # sets HF_HOME before sentence_transformers is imported
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_model = None


def get_model() -> SentenceTransformer:
    """Load once; stages 5 and 6 reuse this to embed queries with the SAME model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def embed(texts: list[str]) -> np.ndarray:
    # normalize_embeddings=True -> every vector has length 1, so
    # cosine similarity == dot product (what Chroma and stage 6 compute).
    return get_model().encode(texts, batch_size=32, normalize_embeddings=True,
                              show_progress_bar=len(texts) > 100).astype(np.float32)


def run(strategy: str) -> None:
    chunks = [json.loads(line) for line in open(config.CHUNKS_DIR / f"{strategy}_v1.jsonl")]
    texts = [c["text"] for c in chunks]

    model = get_model()
    limit = model.max_seq_length
    token_counts = [len(model.tokenizer.tokenize(t)) for t in texts]
    truncated = sum(n > limit for n in token_counts)

    vectors = embed(texts)
    config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    np.save(config.EMBEDDINGS_DIR / f"{strategy}_v1.npy", vectors)
    (config.EMBEDDINGS_DIR / f"{strategy}_v1.ids.json").write_text(json.dumps([c["chunk_id"] for c in chunks]))

    print(f"{strategy}: {vectors.shape[0]} vectors x {vectors.shape[1]} dims")
    print(f"  tokens per chunk: median {sorted(token_counts)[len(token_counts) // 2]}, max {max(token_counts)}"
          f" | over the {limit}-token limit (truncated): {truncated}")
    print(f"  vector norms: {np.linalg.norm(vectors, axis=1).min():.3f}..{np.linalg.norm(vectors, axis=1).max():.3f}")

    # Sanity check: a paraphrased question should land nearest the right chunk.
    query = "How much does an online undergraduate course cost per credit?"
    scores = vectors @ embed([query])[0]
    print(f"  sanity query: {query!r}")
    for i in np.argsort(-scores)[:3]:
        print(f"    {scores[i]:.3f}  {chunks[i]['chunk_id']}  {chunks[i]['title']} > {chunks[i]['section'][:40]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", choices=["fixed", "structure", "both"], default="both")
    args = parser.parse_args()
    for s in ["fixed", "structure"] if args.strategy == "both" else [args.strategy]:
        run(s)
