"""Checks for stage 3 chunking. Several pin down bugs that were invisible in the
chunk counts and only showed up when reading actual chunks.

Run:  python -m tests.test_chunk
"""
from compass.s3_chunk import MAX_WORDS, OVERLAP_WORDS, fixed_chunks, pack_paragraphs, split_sections, structure_chunks

TABLE = "| Program | Per Credit Hour |\n| Undergraduate | $220 |\n| Graduate | $355 |"


def test_fixed_windows_overlap():
    doc = {"text": " ".join(f"w{i}" for i in range(400))}
    chunks = fixed_chunks(doc)
    first, second = chunks[0]["text"].split(), chunks[1]["text"].split()
    assert len(first) == MAX_WORDS
    assert first[-OVERLAP_WORDS:] == second[:OVERLAP_WORDS]   # neighbours share 30 words


def test_heading_stack_builds_section_paths():
    text = "## Tuition\nintro\n### Online\nonline rates\n### On Campus\ncampus rates\n## Housing\nhalls"
    paths = [p for p, _ in split_sections(text)]
    assert paths == ["Tuition", "Tuition > Online", "Tuition > On Campus", "Housing"]


def test_table_rows_stay_on_their_own_lines():
    # Bug: a hard-split step re-joined every piece with spaces and flattened all tables.
    pieces = pack_paragraphs(f"Rates below.\n\n{TABLE}")
    assert any(TABLE in p for p in pieces)


def test_chunks_carry_title_and_substantive_heading():
    # Bug: merged tiny sections kept the first heading ("$19,175", a price styled as a heading).
    doc = {"title": "Tuition",
           "text": "## $19,175\nor less\n## Undergraduate Tuition\n" + TABLE + "\n" + " ".join(["word"] * 40)}
    chunk = structure_chunks(doc)[0]
    assert chunk["section"] == "Undergraduate Tuition"
    assert chunk["text"].startswith("Tuition > Undergraduate Tuition")


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
