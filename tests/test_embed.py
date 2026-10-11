"""Checks for stage 4 embeddings. The first run downloads the model (~90 MB) into
./.cache/huggingface; later runs are offline and take a few seconds.

Run:  python -m tests.test_embed
"""
import numpy as np

from compass.s4_embed import EMBED_MODEL, embed, get_model


def test_vectors_have_384_dims_and_unit_length():
    # Unit length is what makes cosine similarity equal a plain dot product,
    # the metric Chroma is configured with in stage 5. A mismatch silently degrades ranking.
    v = embed(["Online undergraduate tuition is $220 per credit hour.", "Pets are not allowed."])
    assert v.shape == (2, 384) and v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


def test_paraphrase_is_closer_than_unrelated_text():
    # Dense search works on meaning: no shared keywords needed.
    q, para, other = embed(["When does the fall semester start?",
                            "Monday, August 24, 2026: Classes Begin",
                            "No pets are allowed in University housing."])
    assert q @ para > q @ other


def test_model_and_truncation_limit_are_what_we_report():
    model = get_model()
    assert EMBED_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
    assert model.max_seq_length == 256   # longer chunks are silently truncated
    # Words != tokens: table rows cost several tokens per "word".
    row = "| Kentucky Resident | $9,875 ^1 | $335 |"
    assert len(model.tokenizer.tokenize(row)) > len(row.split())


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"{len(tests)} passed")
