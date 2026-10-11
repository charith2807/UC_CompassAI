"""Stage 5 - Index: load chunks + vectors into ChromaDB, and build a BM25 index.

Reads:  data/chunks/{strategy}_v1.jsonl, data/embeddings/{strategy}_v1.npy + .ids.json
Writes: chroma/                         one collection "compass"; every chunk is tagged
                                        with metadata strategy="{strategy}_v1"
        data/bm25/{strategy}_v1.pkl     BM25 keyword index + chunk ids
Run:    python -m compass.s5_index --strategy structure   (or: fixed, both)
"""
import argparse
import json
import pickle
import re

import chromadb
import numpy as np
from rank_bm25 import BM25Okapi

from compass import config

COLLECTION = "compass"


# Degree abbreviations: pages write "Ph.D.", students type "PhD". Without this,
# "Ph.D." became the tokens "ph" + "d" and never matched "phd".
DEGREES = re.compile(r"\b(ph|ed|m|b|d)\.\s?(d|s|a|b\.a|ed)\.?(?![a-z])")


def stem(word: str) -> str:
    """Very light stemming so "courses" matches "course" and "classes" matches "class"."""
    if len(word) > 4 and word.endswith(("sses", "ches", "shes", "xes", "zes")):
        return word[:-2]  # classes -> class, boxes -> box (but courses -> course, below)
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    """Shared by indexing and querying: BM25 only matches identical tokens."""
    text = DEGREES.sub(lambda m: (m.group(1) + m.group(2)).replace(".", ""), text.lower())
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text)]


def get_collection():
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    # We pass our own vectors, so no embedding function: Chroma must never
    # embed with a different model behind our back.
    return client.get_or_create_collection(
        COLLECTION, embedding_function=None, configuration={"hnsw": {"space": "cosine"}}
    )


def run(strategy: str) -> None:
    tag = f"{strategy}_v1"
    chunks = [json.loads(line) for line in open(config.CHUNKS_DIR / f"{tag}.jsonl")]
    vectors = np.load(config.EMBEDDINGS_DIR / f"{tag}.npy")
    ids = json.loads((config.EMBEDDINGS_DIR / f"{tag}.ids.json").read_text())
    # Embeddings must line up row-for-row with the chunks file.
    assert ids == [c["chunk_id"] for c in chunks], "chunks and embeddings are out of sync: re-run stage 4"

    collection = get_collection()
    before = len(collection.get(where={"strategy": tag}, include=[])["ids"])
    collection.delete(where={"strategy": tag})  # remove every old chunk of this strategy first

    for start in range(0, len(chunks), 500):  # Chroma limits batch size
        batch = chunks[start:start + 500]
        collection.add(
            ids=[c["chunk_id"] for c in batch],
            embeddings=vectors[start:start + 500].tolist(),
            documents=[c["text"] for c in batch],
            metadatas=[{k: c[k] for k in ("doc_id", "url", "title", "section", "strategy",
                                          "page_type", "effective_date", "fetched_at")} for c in batch],
        )

    # Stale check: what Chroma holds for this strategy must equal the new chunk set exactly.
    stored = set(collection.get(where={"strategy": tag}, include=[])["ids"])
    stale = stored - set(ids)
    missing = set(ids) - stored
    assert not stale and not missing, f"index mismatch: {len(stale)} stale, {len(missing)} missing"

    bm25 = BM25Okapi([tokenize(c["text"]) for c in chunks])
    config.BM25_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.BM25_DIR / f"{tag}.pkl", "wb") as f:
        pickle.dump({"bm25": bm25, "ids": ids}, f)

    print(f"{tag}: chroma had {before}, deleted them, added {len(stored)} | stale: 0, missing: 0")
    print(f"  bm25: {len(ids)} docs, vocabulary {len(bm25.idf):,} terms -> {(config.BM25_DIR / f'{tag}.pkl').relative_to(config.ROOT)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", choices=["fixed", "structure", "both"], default="both")
    args = parser.parse_args()
    for s in ["fixed", "structure"] if args.strategy == "both" else [args.strategy]:
        run(s)
    print(f"collection '{COLLECTION}' total: {get_collection().count()} chunks")
