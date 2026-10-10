"""Regression checks for cross-program leakage and acronym follow-ups."""
import unittest
from retrieval.query import resolve_query,program_matches
from retrieval.bm25 import BM25
from retrieval.trace import Retriever

IT='https://www.ucumberlands.edu/academics/executive/phd-information-technology'

class ProgramScopeTests(unittest.TestCase):
    def test_curriculum_query_and_followup_preserve_program(self):
        from retrieval.query import retrieval_question
        first=resolve_query('executive PhD in IT tuition')
        result=resolve_query('what courses will I study?', [{'role':'assistant','content':'','conversation_state':first['conversation_state']}])
        self.assertEqual(result['scope']['subject'],'information technology')
        self.assertFalse(result['scope']['tuition'])
        self.assertIn('course requirements curriculum',retrieval_question(result['query'],result['scope']))
        exact=resolve_query('Give me course details for Phd IT')
        self.assertIn('information technology',retrieval_question(exact['query'],exact['scope']))

    def test_undergraduate_deadlines_exclude_graduate_sources(self):
        from retrieval.query import audience_matches
        slots={'degree':'undergraduate','audience':'international'}
        for title in ['Graduate Admissions',"Master's in Physician Assistant Studies",'Ph.D. in IT']:
            self.assertFalse(audience_matches({'title':title,'source_url':'https://www.ucumberlands.edu/admissions','heading_path':[]},slots))
        self.assertTrue(audience_matches({'title':'Undergraduate Admissions','heading_path':[]},slots))
        self.assertTrue(audience_matches({'title':'Apply to Cumberlands','heading_path':[]},slots))
    def test_comparative_masters_keeps_tuition_subject_and_format(self):
        previous=resolve_query('executive PhD in IT tuition')
        result=resolve_query('how about masters?',[{'role':'assistant','conversation_state':previous['conversation_state'],'content':''}])
        self.assertEqual(result['scope']['degree'],'masters')
        self.assertEqual(result['scope']['subject'],'information technology')
        self.assertEqual(result['scope']['format'],'executive')
        self.assertTrue(result['scope']['tuition'])
        self.assertNotIn('Ph.D.',result['conversation_state']['anchor'])
    def test_executive_tuition_allows_category_but_not_mixed_table(self):
        scope=resolve_query('executive PhD in IT tuition')['scope']
        c={'source_url':'https://www.ucumberlands.edu/tuition-aid/tuition','title':'Tuition','heading_path':['Executive Programs | Per Credit Hour'], 'text':'Doctoral Programs (inc. Certificate) | $749'}
        self.assertTrue(program_matches(c,scope))
        self.assertFalse(program_matches(dict(c,heading_path=['Extracted table']),scope))
        self.assertFalse(program_matches(c,resolve_query('executive PhD in IT requirements')['scope']))
        self.assertFalse(program_matches(c,resolve_query('online PhD in IT tuition')['scope']))
    def test_it_acronym_does_not_merge_previous_topic(self):
        result=resolve_query('Tell me about PhD in IT',[{'role':'user','content':'Occupational therapy fees'}])
        self.assertEqual(result['scope']['subject'],'information technology')
        self.assertNotIn('Occupational',result['query'])
    def test_lowercase_pronoun_keeps_program_context(self):
        result=resolve_query('What are its requirements?',[{'role':'user','content':'PhD in IT'}])
        self.assertEqual(result['scope']['subject'],'information technology')
    def test_it_correction_keeps_degree(self):
        result=resolve_query('I mean the IT field',[{'role':'user','content':'Give me general PhD details'}])
        self.assertEqual(result['scope']['degree'],'phd')
        self.assertIn('Information Technology',result['query'])
    def test_generic_phd_and_ambiguous_fees_clarify(self):
        for query in ['General PhD details','What are PhD fees?','How much is a PhD in IT?']:
            self.assertTrue(resolve_query(query)['clarification'])
    def test_new_masters_topic_does_not_inherit_phd(self):
        result=resolve_query('Masters in IT',[{'role':'user','content':'PhD in IT'}])
        self.assertEqual(result['scope']['degree'],'masters')
        self.assertFalse(result['scope']['tuition'])
        self.assertNotIn('PhD',result['query'])
    def test_online_request_cannot_use_executive_program(self):
        scope=resolve_query('online PhD in IT')['scope']
        self.assertFalse(program_matches({'title':'Ph.D. in Information Technology','source_url':IT},scope))
    def test_scope_applied_before_pool_truncation(self):
        chunks=[]
        for i in range(30):
            for prefix,title,url,text in [('other','Occupational Therapy Doctorate','https://www.ucumberlands.edu/tuition','occupational therapy doctoral fees'),('it','Ph.D. in Information Technology',IT,'Research and program requirements')]:
                chunks.append({'chunk_id':prefix+str(i),'title':title,'source_url':url,'text':text,'heading_path':[],'page_type':'academics'})
        class Dense:
            def search(self,query,limit,page_type,chunk_ids=None):
                return [c for c in chunks if c['chunk_id'] in chunk_ids][:limit]
        class Reranker:
            def rerank(self,query,candidates,top_k):return candidates[:top_k]
        config={'candidate_pool':20,'rerank_top_k':5,'rrf_k':60}
        retriever=Retriever(BM25(chunks),Dense(),Reranker(),config)
        scope={'degree':'phd','subject':'information technology'}
        selected,trace=retriever.retrieve('occupational therapy doctoral fees',program_scope=scope)
        self.assertEqual(trace['candidate_count'],20)
        self.assertEqual(trace['program_chunk_count'],30)
        self.assertTrue(all(c['source_url']==IT for c in trace['candidates']))
        self.assertTrue(all(c['source_url']==IT for c in selected))

if __name__=='__main__':unittest.main()
