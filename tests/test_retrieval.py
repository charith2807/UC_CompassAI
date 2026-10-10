import unittest
from retrieval.hybrid import rrf
from retrieval.rerank import Reranker

class RetrievalTests(unittest.TestCase):
    def test_fusion_twenty(self):
        a=[{'chunk_id':str(i),'bm25_score':30-i} for i in range(30)]
        b=[{'chunk_id':str(i),'dense_score':i/30} for i in reversed(range(30))]
        self.assertEqual(len(rrf(a,b,limit=20)),20)
    def test_rerank_retains_trace_scores(self):
        class Model:
            def predict(self,pairs,**kwargs):return range(len(pairs))
        ranker=Reranker.__new__(Reranker);ranker.model=Model()
        pool=[{'chunk_id':str(i),'text':'text'} for i in range(20)]
        self.assertEqual(len(ranker.rerank('query',pool)),5)
        self.assertTrue(all('rerank_score' in c for c in pool))
if __name__=='__main__':unittest.main()
