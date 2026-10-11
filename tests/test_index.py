"""Checks for stage 5 indexing.

Run:  python -m tests.test_index      (no network; uses a temporary Chroma folder)
"""
import json
import tempfile
from pathlib import Path

import numpy as np

from compass import config, s5_index
from compass.s5_index import tokenize


def test_tokenizer_matches_what_students_type_to_what_pages_say():
    # BM25 only matches identical tokens, so test PAIRS that must agree.
    # Bug caught this way: a first stemmer turned "courses" into "cours" (no match).
    for typed, on_page in [("PhD", "Ph.D."), ("courses", "course"), ("classes", "class"),
                           ("EdD", "Ed.D."), ("fees", "fee"), ("requirements", "requirement")]:
        assert tokenize(typed) == tokenize(on_page), (typed, on_page)
    for word in ("status", "analysis", "campus"):         # must not be stripped
        assert tokenize(word) == [word]


def test_reindex_deletes_old_chunks_and_leaves_no_stale_ones():
    # The re-chunk requirement: re-indexing a strategy must replace, never accumulate.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        config.CHROMA_DIR, config.CHUNKS_DIR, config.EMBEDDINGS_DIR, config.BM25_DIR, config.ROOT = (
            tmp / "chroma", tmp / "chunks", tmp / "emb", tmp / "bm25", tmp)
        for d in (config.CHUNKS_DIR, config.EMBEDDINGS_DIR):
            d.mkdir()

        def write(n):
            chunks = [{"chunk_id": f"doc_test_v1_{i:03d}", "doc_id": "doc", "url": "u", "title": "t",
                       "section": "s", "strategy": "test_v1", "page_type": "general",
                       "effective_date": "", "fetched_at": "", "text": f"chunk number {i}"} for i in range(n)]
            (config.CHUNKS_DIR / "test_v1.jsonl").write_text("".join(json.dumps(c) + "\n" for c in chunks))
            vecs = np.random.default_rng(0).normal(size=(n, 384)).astype(np.float32)
            np.save(config.EMBEDDINGS_DIR / "test_v1.npy", vecs / np.linalg.norm(vecs, axis=1, keepdims=True))
            (config.EMBEDDINGS_DIR / "test_v1.ids.json").write_text(json.dumps([c["chunk_id"] for c in chunks]))

        write(5)
        s5_index.run("test")
        write(3)                        # re-chunk produced fewer chunks
        s5_index.run("test")            # asserts internally: 0 stale, 0 missing
        stored = s5_index.get_collection().get(where={"strategy": "test_v1"}, include=[])["ids"]
        assert sorted(stored) == [f"doc_test_v1_{i:03d}" for i in range(3)]


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
