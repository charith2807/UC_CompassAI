import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from indexing.chunking import chunk_document,windows,token_count
from indexing.store import Store
from retrieval.hybrid import rrf
from retrieval.rerank import Reranker
from generation.answer import AnswerService
from generation.grounding import validate_claims
from eval.metrics import ranking_metrics,bootstrap,paired_delta
from eval.split import stratified_split
from eval.freeze import require_verified

DOC={'doc_id':'doc123','source_url':'https://www.ucumberlands.edu/tuition-aid/tuition',
     'url':'https://www.ucumberlands.edu/tuition-aid/tuition','title':'Tuition',
     'page_type':'tuition','crawled_at':'2026-10-10T00:00:00Z','text':'## Tuition\nAnnual tuition is $9,875.\n## Costs\nOther costs vary.',
     'sections':[{'heading_path':['Tuition'],'text':'Annual tuition is $9,875.'},{'heading_path':['Costs'],'text':'Other costs vary.'}]}
CHUNK={**chunk_document(DOC)[0],'rerank_score':.9,'initial_score':.5}
CONFIG={'candidate_pool':20,'rerank_top_k':5,'rrf_k':60,'refusal_threshold':.5,'threshold_status':'UNCALIBRATED','llm_model':'gpt-4o-mini'}

class PipelineTests(unittest.TestCase):
    def test_chunk_ids_deterministic(self):
        first=chunk_document(DOC,'structure');second=chunk_document(DOC,'structure')
        self.assertEqual(first,second);self.assertEqual(first[0]['chunk_id'],'doc123_structure_v1_0000')
        self.assertNotEqual(first[0]['chunk_id'],chunk_document(DOC,'fixed')[0]['chunk_id'])
    def test_heading_path(self):
        chunks=chunk_document(DOC,'structure');self.assertEqual(chunks[1]['heading_path'],['Costs'])
    def test_windows_overlap_and_cap(self):
        text=' '.join(f'token{i}' for i in range(1000));chunks=list(windows(text,500,75))
        self.assertEqual([n for _,n in chunks],[500,500,150])
        self.assertEqual(chunks[0][0].split()[-75:],chunks[1][0].split()[:75])
    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):list(windows('text',10,10))
    def test_rrf_union_score_and_tie(self):
        result=rrf([{'chunk_id':'b'},{'chunk_id':'a'}],[{'chunk_id':'a'},{'chunk_id':'c'}],limit=20)
        self.assertEqual(result[0]['chunk_id'],'a')
        self.assertAlmostEqual(result[0]['rrf_score'],1/62+1/61)
    def test_rrf_no_duplicates(self):
        result=rrf([{'chunk_id':'a'},{'chunk_id':'a'}],limit=20)
        self.assertAlmostEqual(result[0]['rrf_score'],1/61)
    def test_rrf_pool_twenty(self):
        self.assertEqual(len(rrf([{'chunk_id':str(i)} for i in range(30)],limit=20)),20)
    def test_rerank_top_five(self):
        class Model:
            def predict(self,pairs,**kwargs):return list(range(len(pairs)))
        ranker=Reranker.__new__(Reranker);ranker.model=Model()
        candidates=[{**CHUNK,'chunk_id':str(i)} for i in range(20)]
        result=ranker.rerank('tuition',candidates,5)
        self.assertEqual(len(result),5);self.assertEqual(result[0]['chunk_id'],'19')
        with self.assertRaises(ValueError):ranker.rerank('tuition',candidates,6)
    def test_stale_delete_filter_and_assertion(self):
        class Collection:
            def __init__(self):self.rows=[{'chunk_strategy':'fixed','chunk_version':'v1','id':'old'}]
            def delete(self,where):
                self.assertion=where;self.rows=[]
            def get(self,where,include):return {'ids':[r['id'] for r in self.rows]}
        store=Store.__new__(Store);store.collection=Collection()
        store.delete_strategy('fixed','v1');self.assertEqual(store.collection.assertion,Store.strategy_filter('fixed','v1'))
        store.collection.rows=[{'id':'orphan'}]
        with self.assertRaises(AssertionError):store.assert_zero_stale('fixed','v1')
    def test_citations_from_metadata(self):
        claims=[{'text':'The page lists annual tuition.','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'Annual tuition is $9,875.'}]}]
        result=validate_claims(claims,[CHUNK]);self.assertEqual(result[0]['citations'][0]['url'],DOC['url'])
    def test_unknown_citation_rejected(self):
        with self.assertRaises(ValueError):validate_claims([{'text':'Claim','evidence':[{'chunk_id':'invented','quote':'Annual tuition'}]}],[CHUNK])
    def test_fake_quote_rejected(self):
        with self.assertRaises(ValueError):validate_claims([{'text':'Claim','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'Not in source'}]}],[CHUNK])
    def test_model_url_rejected(self):
        with self.assertRaises(ValueError):validate_claims([{'text':'https://invented.example','evidence':[]}],[CHUNK])
    def test_ranking_known_values(self):
        m=ranking_metrics(['a','b','c'],['b','c']);self.assertEqual(m['recall@5'],1);self.assertEqual(m['mrr'],.5)
    def test_bootstrap_and_paired(self):
        self.assertEqual(bootstrap([1,1,1])['ci95'],[1,1]);self.assertEqual(paired_delta([0,1],[1,1])['mean'],.5)
    def test_split_stratified(self):
        items=[{'id':str(i),'category':str(i//10)} for i in range(40)]
        result=stratified_split(items);self.assertEqual(sum(x=='dev' for x in result.values()),24)
        self.assertEqual(result,stratified_split(items))
    def test_unverified_evaluation_blocked(self):
        with self.assertRaises(ValueError):require_verified([{'status':'DRAFT_NEEDS_HUMAN_VERIFICATION'}])
    def test_no_key_retrieval_only(self):
        class Retriever:
            def retrieve(self,*args):return [CHUNK],{'selected':[CHUNK],'candidates':[CHUNK]}
        with patch.dict('os.environ',{},clear=True):
            result=AnswerService(Retriever(),CONFIG).answer('What is tuition?')
        self.assertFalse(result['refused']);self.assertEqual(result['mode'],'retrieval-only');self.assertTrue(result['citations'])

if __name__=='__main__':unittest.main()
