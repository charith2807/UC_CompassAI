"""Verify batched subwindows stay assigned to their original chunks."""
import unittest
import numpy as np
from indexing.embed import Embedder

class Tokenizer:
    def num_special_tokens_to_add(self, pair=False):return 2
    def encode(self, text, add_special_tokens=False):return [int(v) for v in text.split()]
    def decode(self, tokens, skip_special_tokens=True):return ' '.join(map(str,tokens))

class Model:
    max_seq_length=4
    tokenizer=Tokenizer()
    def __init__(self):self.calls=0
    def encode(self, texts, **kwargs):
        self.calls+=1
        return np.array([[float(text.split()[0]),1.0] for text in texts])

class EmbeddingTests(unittest.TestCase):
    def test_batched_pooling_preserves_chunk_alignment_and_weights(self):
        embedder=Embedder.__new__(Embedder)
        embedder.np=np;embedder.model=Model()
        vectors=embedder.encode(['2 2 8','5 5'])
        expected=np.array([[4.,1.],[5.,1.]])
        expected/=np.linalg.norm(expected,axis=1,keepdims=True)
        np.testing.assert_allclose(vectors,expected,rtol=1e-6)
        self.assertEqual(embedder.model.calls,1)
        np.testing.assert_allclose(np.linalg.norm(vectors,axis=1),1,rtol=1e-6)
    def test_empty_chunk_rejected(self):
        embedder=Embedder.__new__(Embedder)
        embedder.np=np;embedder.model=Model()
        with self.assertRaises(ValueError):embedder.encode([''])

if __name__=='__main__':unittest.main()
