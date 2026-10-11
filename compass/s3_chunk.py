"""Stage 3 - Chunk: split normalized documents into retrievable passages.

Reads:  data/normalized/{doc_id}.json
Writes: data/chunks/{strategy}_v1.jsonl, one chunk per line:
        {chunk_id, doc_id, url, title, section, strategy, page_type, effective_date,
         fetched_at, n_words, text}
        chunk_id = {doc_id}_{strategy}_v1_{position:03d}, e.g. 1a2b3c4d5e6f_structure_v1_004
Run:    python -m compass.s3_chunk --strategy structure   (or: fixed, both)
"""
import argparse
import json
import re

from compass import config

VERSION = "v1"
MAX_WORDS = 150     # all-MiniLM-L6-v2 reads at most 256 tokens; ~150 words fits
OVERLAP_WORDS = 30  # fixed strategy only
MIN_WORDS = 40      # structure strategy: merge sections smaller than this


def load_docs() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(config.NORMALIZED_DIR.glob("*.json"))]


def fixed_chunks(doc: dict) -> list[dict]:
    """Naive baseline (B2): sliding window of words, blind to structure."""
    words = doc["text"].split()
    step = MAX_WORDS - OVERLAP_WORDS
    return [
        {"section": "", "text": " ".join(words[start:start + MAX_WORDS])}
        for start in range(0, max(len(words) - OVERLAP_WORDS, 1), step)
    ]


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown on headings; return (section_path, body) pairs.
    A heading stack tracks nesting: "## Tuition" then "### Online" -> "Tuition > Online"."""
    sections, stack, body = [], [], []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if "".join(body).strip():
                sections.append((" > ".join(h for _, h in stack), "\n".join(body).strip()))
            body = []
            level, heading = len(m.group(1)), m.group(2).strip()
            stack = [(l, h) for l, h in stack if l < level] + [(level, heading)]
        else:
            body.append(line)
    if "".join(body).strip():
        sections.append((" > ".join(h for _, h in stack), "\n".join(body).strip()))
    return sections


def pack_paragraphs(body: str) -> list[str]:
    """Greedily pack paragraphs (blank-line separated) into pieces of <= MAX_WORDS.
    A table has no blank lines, so it stays one paragraph unless it alone is too
    long - then it is split by rows."""
    paragraphs = []
    for para in body.split("\n\n"):
        if len(para.split()) <= MAX_WORDS:
            paragraphs.append(para)
        else:
            paragraphs.extend(para.splitlines())
    pieces, current = [], []
    for para in paragraphs:
        if current and len(" ".join(current + [para]).split()) > MAX_WORDS:
            pieces.append("\n\n".join(current))
            current = []
        current.append(para)
    if current:
        pieces.append("\n\n".join(current))
    # A single over-long line (rare) still gets hard-split by words.
    out = []
    for piece in pieces:
        words = piece.split()
        if len(words) <= MAX_WORDS:
            out.append(piece)  # keep newlines: table rows stay rows
        else:
            out.extend(" ".join(words[i:i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS))
    return out


def structure_chunks(doc: dict) -> list[dict]:
    """Structure-aware (B3): split on headings, merge tiny sections, and prefix
    each chunk with "Title > Section path" so it carries its own context."""
    merged, buf_section, buf_body = [], None, ""
    for section, body in split_sections(doc["text"]):
        if buf_section is None:
            buf_section, buf_body = section, body
        else:
            # Tiny sections flow forward into the next one, which names the chunk.
            buf_body += f"\n\n{section.split(' > ')[-1]}\n{body}" if section else f"\n\n{body}"
            buf_section = section or buf_section
        if len(buf_body.split()) >= MIN_WORDS:
            merged.append((buf_section, buf_body))
            buf_section, buf_body = None, ""
    if buf_section is not None:
        merged.append((buf_section, buf_body))

    chunks = []
    for section, body in merged:
        header = " > ".join(p for p in (doc["title"], section) if p)
        for piece in pack_paragraphs(body):
            chunks.append({"section": section, "text": f"{header}\n\n{piece}"})
    return chunks


STRATEGIES = {"fixed": fixed_chunks, "structure": structure_chunks}


def run(strategy: str) -> None:
    config.CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.CHUNKS_DIR / f"{strategy}_{VERSION}.jsonl"
    all_chunks = []
    for doc in load_docs():
        for i, c in enumerate(STRATEGIES[strategy](doc)):
            all_chunks.append({
                "chunk_id": f"{doc['doc_id']}_{strategy}_{VERSION}_{i:03d}",
                "doc_id": doc["doc_id"], "url": doc["url"], "title": doc["title"],
                "section": c["section"], "strategy": f"{strategy}_{VERSION}",
                "page_type": doc.get("page_type", "general"), "effective_date": doc.get("effective_date") or "",
                "fetched_at": doc["fetched_at"],
                "n_words": len(c["text"].split()), "text": c["text"],
            })
    with open(out_path, "w") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    sizes = sorted(c["n_words"] for c in all_chunks)
    print(f"{strategy}: {len(all_chunks)} chunks -> {out_path.relative_to(config.ROOT)}")
    print(f"  words per chunk: min {sizes[0]}, median {sizes[len(sizes) // 2]}, max {sizes[-1]}")
    print(f"  chunks under 20 words: {sum(s < 20 for s in sizes)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", choices=[*STRATEGIES, "both"], default="both")
    args = parser.parse_args()
    for s in STRATEGIES if args.strategy == "both" else [args.strategy]:
        run(s)
