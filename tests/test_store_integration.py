import importlib.util
import tempfile
import unittest
from pathlib import Path

@unittest.skipUnless(importlib.util.find_spec('chromadb'),'Chroma dependency unavailable — real integration not verified')
class ChromaTests(unittest.TestCase):
    def test_persistence_filter_and_delete(self):
        import numpy as np
        from indexing.store import Store
        from indexing.chunking import chunk_document
        from tests.fixtures import DOC
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory,'integration_test')
            fixed=chunk_document(DOC,'fixed');structure=chunk_document(DOC,'structure')
            vectors=np.zeros((len(fixed),384),dtype=np.float32);vectors[:,0]=1
            store.add(fixed,vectors)
            self.assertEqual(len(Store(directory,'integration_test').all('tuition')),len(fixed))
            self.assertEqual(store.all('admissions'),[])
            store.delete_strategy('fixed','v1');self.assertEqual(store.all(),[])
            new=np.zeros((len(structure),384),dtype=np.float32);new[:,1]=1
            store.add(structure,new);store.assert_zero_stale('fixed','v1')
            self.assertEqual({c['chunk_id'] for c in store.all()},{c['chunk_id'] for c in structure})
            selected={structure[-1]['chunk_id']}
            filtered=store.query(new[0],20,'tuition',chunk_ids=selected)
            self.assertEqual({c['chunk_id'] for c in filtered},selected)
            self.assertEqual(store.query(new[0],20,'admissions',chunk_ids=selected),[])
            self.assertEqual(store.query(new[0],20,chunk_ids=set()),[])
            from unittest.mock import patch
            with patch.object(type(store.collection),'query',side_effect=RuntimeError('Cannot return the results in a contigious 2D array')):
                fallback=store.query(new[0],20,'tuition',chunk_ids=selected)
            self.assertEqual({c['chunk_id'] for c in fallback},selected)
            self.assertAlmostEqual(fallback[0]['dense_score'],1.0)

if __name__=='__main__':unittest.main()
