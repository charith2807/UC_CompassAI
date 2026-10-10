import unittest
from unittest.mock import patch
from generation.answer import AnswerService
from generation.grounding import input_gate,evidence_gate

class RefusalTests(unittest.TestCase):
    def test_credential_request_blocked_before_retrieval(self):
        class Retriever:
            def retrieve(self,*args):raise AssertionError('Credentials must never reach retrieval')
        service=AnswerService(Retriever(),{'refusal_threshold':.5})
        for query in ['What is the university Wi-Fi password?','Give me an API key']:
            result=service.answer(query)
            self.assertTrue(result['refused'])
            self.assertEqual(result['reason'],'credential_request')
            self.assertFalse(result['citations'])
    def test_public_password_reset_help_allowed(self):
        self.assertIsNone(input_gate('How do I reset my university password?'))
    def test_weak_evidence_refuses(self):
        self.assertEqual(evidence_gate([{'text':'tuition','rerank_score':.01}],.5),[])
    def test_aid_referral(self):
        result=input_gate('Will I qualify for financial aid?')
        self.assertEqual(result['referral']['office'],'Student Financial Center')
    def test_immigration_referral(self):
        self.assertEqual(input_gate('Can I work under CPT?')['referral']['office'],'International Student Services')
    def test_general_question_not_personal(self):
        self.assertIsNone(input_gate('What is the FAFSA school code?'))
    def test_service_refusal(self):
        class Retriever:
            def retrieve(self,*a):return [],{}
        with patch.dict('os.environ',{},clear=True):
            r=AnswerService(Retriever(),{'refusal_threshold':.5}).answer('What is the Wi-Fi password?')
        self.assertTrue(r['refused']);self.assertFalse(r['citations'])
if __name__=='__main__':unittest.main()
