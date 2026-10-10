import unittest
from indexing.chunking import chunk_document,windows
from tests.fixtures import DOC

class ChunkingTests(unittest.TestCase):
    def test_fixed_ids_repeat(self):
        a=chunk_document(DOC,'fixed');self.assertEqual(a,chunk_document(DOC,'fixed'))
        self.assertTrue(a[0]['chunk_id'].startswith('doc123_fixed_v1_'))
    def test_structure_path(self):
        self.assertEqual(chunk_document(DOC,'structure')[1]['heading_path'],['Costs'])
    def test_overlap(self):
        chunks=list(windows(' '.join(str(i) for i in range(700)),500,75))
        self.assertEqual(chunks[0][0].split()[-75:],chunks[1][0].split()[:75])
if __name__=='__main__':unittest.main()
