"""Provider compatibility tests use synthetic responses, never live keys."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from generation.providers import ProviderRouter,ProviderUnavailable,provider_key_available
from generation.prompt import SCHEMA
from generation.answer import AnswerService
from tests.test_pipeline import CHUNK,CONFIG

def fake_client(content='{"refused":true,"claims":[]}',error=None):
    class Completions:
        def create(self,**kwargs):
            self.parameters=kwargs
            if error:raise error
            return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10,completion_tokens=5),
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

class ProviderTests(unittest.TestCase):
    def test_quote_schema_covers_source_and_rejects_invented_quotes(self):
        from generation.prompt import grounded_schema,quote_bank
        import jsonschema
        text=' '.join('word'+str(i) for i in range(67))+'\n| Doctoral | | $749 |'
        bank=quote_bank(text)
        self.assertTrue(all(q in text and len(q.split())<=25 for q in bank))
        self.assertEqual(' '.join(' '.join(bank).split()),' '.join(text.split()))
        schema=grounded_schema([CHUNK])
        bad={'refused':False,'claims':[{'text':'Unsupported','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'invented quote'}]}]}
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(bad,schema)
    def test_whitespace_quote_returns_exact_source_span(self):
        from generation.grounding import validate_claims
        chunk={**CHUNK,'text':'Annual tuition\n  is $9,875.'}
        claim={'text':'Annual tuition is $9,875.','evidence':[{'chunk_id':chunk['chunk_id'],'quote':'Annual tuition is $9,875.'}]}
        result=validate_claims([claim],[chunk])
        self.assertEqual(result[0]['citations'][0]['quote'],chunk['text'])
        claim['evidence'][0]['quote']='Annual tuition is $1.'
        with self.assertRaises(ValueError):validate_claims([claim],[chunk])
    def test_wrong_tuition_unit_is_rejected_even_when_amount_matches(self):
        from generation.grounding import validate_table_units
        chunks=[{'text':'## Executive Programs | Rate Per Bi-Term | Per Credit Hour |\n| Doctoral Programs | | $749 |'}]
        validate_table_units('The rate is $749 per credit hour.',chunks)
        with self.assertRaises(ValueError):validate_table_units('The rate is $749 per bi-term.',chunks)
    def test_quote_repair_is_bounded_and_accounts_for_both_requests(self):
        from unittest.mock import Mock
        bad={'refused':False,'claims':[{'text':'Annual tuition is $9,875.','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'a paraphrase'}]}]}
        good={'refused':False,'claims':[{'text':'Annual tuition is $9,875.','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'Annual tuition is $9,875.'}]}]}
        class Retriever:
            def retrieve(self,*args,**kwargs):return [CHUNK],{}
        service=AnswerService(Retriever(),CONFIG);service.router=Mock();service.router.configured.return_value=['groq']
        def response(payload):return {'content':json.dumps(payload),'usage':{'input_tokens':10,'output_tokens':5},'cost_usd':None,'provider':'groq','model':'synthetic','attempts':[]}
        service.router.complete.side_effect=[response(bad),response(good)]
        r=service.answer('What is tuition?')
        self.assertFalse(r['refused']);self.assertEqual(service.router.complete.call_count,2)
        self.assertEqual(r['usage'],{'input_tokens':20,'output_tokens':10})
        service.router.complete.reset_mock();service.router.complete.side_effect=[response(bad),response(bad)]
        r=service.answer('What is tuition?')
        self.assertTrue(r['refused']);self.assertEqual(service.router.complete.call_count,2)
    def test_no_key(self):
        with patch.dict('os.environ',{},clear=True):self.assertFalse(provider_key_available({'llm_provider':'auto'}))
    def test_groq_preferred(self):
        a,b=fake_client(),fake_client()
        router=ProviderRouter({'llm_provider':'auto'},clients={'groq':a,'openai':b})
        result=router.complete([{'role':'user','content':'JSON'}],SCHEMA)
        self.assertEqual(result['provider'],'groq');self.assertEqual(result['model'],'openai/gpt-oss-20b')
        self.assertEqual(a.chat.completions.parameters['response_format']['type'],'json_schema')
    def test_fallback_on_inaccessible_provider(self):
        a=fake_client(error=RuntimeError('synthetic private error text'));b=fake_client()
        result=ProviderRouter({'llm_provider':'auto'},clients={'groq':a,'openai':b}).complete([],SCHEMA)
        self.assertEqual(result['provider'],'openai');self.assertEqual(len(result['attempts']),2)
        self.assertNotIn('private error text',str(result))
    def test_invalid_json_falls_back(self):
        result=ProviderRouter({'llm_provider':'auto'},clients={'groq':fake_client('not json'),'gemini':fake_client()}).complete([],SCHEMA)
        self.assertEqual(result['provider'],'gemini')
    def test_pinned_provider_no_fallback(self):
        router=ProviderRouter({'llm_provider':'groq'},clients={'groq':fake_client(error=RuntimeError()),'openai':fake_client()})
        with self.assertRaises(ProviderUnavailable) as ctx:router.complete([],SCHEMA)
        self.assertEqual(len(ctx.exception.attempts),1)
    def test_each_provider_uses_model_map(self):
        for provider in ('groq','openai','gemini'):
            result=ProviderRouter({'llm_provider':provider,'provider_models':{provider:'explicit-model'}},clients={provider:fake_client()}).complete([],SCHEMA)
            self.assertEqual(result['model'],'explicit-model')
    def test_grounded_generated_answer(self):
        payload={'refused':False,'claims':[{'text':'Annual tuition is $9,875.','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'q0_1'}]}]}
        class Retriever:
            def retrieve(self,*args):return [CHUNK],{'selected':[CHUNK],'candidates':[CHUNK]}
        service=AnswerService(Retriever(),{**CONFIG,'llm_provider':'openai'},client=fake_client(json.dumps(payload)))
        result=service.answer('What is tuition?')
        self.assertFalse(result['refused']);self.assertEqual(result['citations'][0]['url'],CHUNK['source_url'])
        self.assertEqual(result['provider'],'openai')
    def test_fabricated_numeric_claim_refused(self):
        payload={'refused':False,'claims':[{'text':'Annual tuition is $1.','evidence':[{'chunk_id':CHUNK['chunk_id'],'quote':'q0_1'}]}]}
        class Retriever:
            def retrieve(self,*args):return [CHUNK],{}
        result=AnswerService(Retriever(),{**CONFIG,'llm_provider':'openai'},client=fake_client(json.dumps(payload))).answer('What is tuition?')
        self.assertTrue(result['refused']);self.assertFalse(result['citations'])
if __name__=='__main__':unittest.main()
