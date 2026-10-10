"""Conversation regressions: pending slots, references, topic changes and completion."""
import unittest
from retrieval.query import resolve_query
from retrieval.conversation import context
from generation.answer import AnswerService

def turn(query,history):
    result=resolve_query(query,history)
    history.extend([{'role':'user','content':query},
        {'role':'assistant','content':result['clarification'] or 'Reply',
         'conversation_state':result['conversation_state']}])
    return result

class ConversationTests(unittest.TestCase):
    def test_unknown_fragment_cannot_silently_reuse_previous_fee(self):
        for reply in ['biology','both','yes','what about biology?']:
            history=[];turn('executive PhD in IT tuition',history)
            result=turn(reply,history)
            self.assertTrue(result['clarification'])
            self.assertIsNone(result['scope'])
    def test_multi_topic_followup_matrix(self):
        cases=[
            (['executive PhD in IT tuition','how about masters?'],{'degree':'masters','subject':'information technology','format':'executive'},['tuition'],['PhD']),
            (['executive PhD in IT tuition','how about masters?','and PhD?'],{'degree':'phd','subject':'information technology'},['tuition'],["Master's"]),
            (['executive PhD in IT tuition','how about business?'],{'subject':'business','degree':'phd','format':'executive'},['tuition'],['Information Technology']),
            (['executive PhD in IT tuition','what about AI?'],{'subject':'artificial intelligence'},['tuition'],['Information Technology']),
            (['online PhD in IT tuition','No, executive'],{'format':'executive'},['tuition'],['online']),
            (['executive PhD in IT tuition','online instead'],{'format':'online'},['tuition'],['executive']),
            (['executive PhD in IT tuition','what are its requirements?'],{'degree':'phd','subject':'information technology'},['requirements'],['tuition']),
            (['executive PhD in IT tuition','scholarships'],{'degree':'phd','subject':'information technology'},['scholarships'],['tuition']),
            (['executive PhD in IT tuition','how long does it take?'],{'subject':'information technology'},['long'],['tuition']),
            (['PhD in IT requirements','how much?','executive'],{'format':'executive','subject':'information technology'},['how much'],['requirements']),
            (['PhD in IT','Masters in Business'],{'degree':'masters','subject':'business'},['Business'],['Information Technology']),
            (['PhD in IT','No, masters'],{'degree':'masters','subject':'information technology'},['Information Technology'],['PhD']),
            (['PhD tuition','IT','executive','how about masters?','what documents do I need?'],{'degree':'masters','format':'executive'},['documents'],['tuition']),
            (['What are undergraduate admissions requirements?','and international students?'],{'degree':'undergraduate','audience':'international'},['admissions','requirements'],[]),
            (['What are undergraduate admissions requirements?','and international students?','What documents do they need?'],{'degree':'undergraduate','audience':'international'},['admissions','documents'],['requirements']),
            (['What is the admissions deadline for fall 2025?','how about spring 2026?'],{'term':'spring','year':'2026'},['deadline'],['fall','2025']),
            (['What is the admissions deadline for fall 2025?','2026'],{'year':'2026','term':'fall'},['deadline'],['2025']),
            (['What are the library hours?','Where is it?'],{},['library','Where'],['hours']),
            (['What are the library hours?','Why?'],{},['library','hours','Why'],[]),
            (['What are housing options?','What does it cost?'],{},['housing','cost'],['library']),
            (['PhD in IT','tell me about the library','Where is it?'],{},['library'],['PhD','Information Technology']),
            (['library hours','new topic: What are housing options?'],{},['housing'],['library']),
            (['PhD in IT','done','IT'],{'subject':'information technology'},['IT'],['PhD']),
            (['PhD in IT','thank you','library hours'],{},['library'],['PhD']),
            (['PhD tuition','IT','executive','clear conversation','how about masters?'],{'degree':'masters'},['masters'],['tuition','IT','executive']),
        ]
        for questions,expected,include,exclude in cases:
            with self.subTest(questions=questions):
                history=[]
                for query in questions:result=turn(query,history)
                slots=result['conversation_state'].get('slots',{})
                for key,value in expected.items():self.assertEqual(slots.get(key),value)
                for word in include:self.assertIn(word.lower(),result['query'].lower())
                for word in exclude:self.assertNotIn(word.lower(),result['query'].lower())

    def test_repeated_comparisons_do_not_accumulate_query_text(self):
        history=[];turn('executive PhD in IT tuition',history)
        for _ in range(30):
            turn('how about masters?',history)
            result=turn('and PhD?',history)
        self.assertLess(len(result['query']),120)
        self.assertEqual(result['conversation_state']['slots']['degree'],'phd')

    def test_program_reply_keeps_tuition_question(self):
        history=[]
        self.assertEqual(turn('tuition fee for PhD',history)['conversation_state']['pending'],'program')
        result=turn('Information technology',history)
        self.assertIn('tuition',result['query'])
        self.assertIn('Information Technology',result['clarification'])
        self.assertEqual(result['conversation_state']['pending'],'format')
        result=turn('executive',history)
        self.assertIn('tuition',result['query'])
        self.assertEqual(result['scope']['subject'],'information technology')
        self.assertEqual(result['scope']['format'],'executive')
        self.assertIsNone(result['clarification'])
    def test_generic_clarification_reply_keeps_requirements(self):
        class Retriever:
            def retrieve(self,*args,**kwargs):return [],{}
        service=AnswerService(Retriever(),{'refusal_threshold':.5})
        first=service.answer('What are the requirements?')
        history=[{'role':'user','content':'What are the requirements?'},
                 {'role':'assistant','content':first['answer'],'conversation_state':first['conversation_state']}]
        result=resolve_query('Undergraduate admissions',history)
        self.assertIn('requirements',result['query'])
        self.assertIn('Undergraduate admissions',result['query'])
    def test_library_location_followup_keeps_library(self):
        history=[]
        turn('What are the library hours?',history)
        result=turn('Where is it?',history)
        self.assertIn('library',result['query'])
        self.assertIn('Where is it?',result['query'])
        self.assertNotIn('hours',result['query'])
    def test_program_requirements_followup_drops_previous_fee_intent(self):
        history=[]
        turn('executive PhD in IT tuition fees',history)
        result=turn('What are its requirements?',history)
        self.assertEqual(result['scope']['subject'],'information technology')
        self.assertNotIn('tuition',result['query'])
    def test_context_survives_many_turns_and_is_per_conversation(self):
        history=[]
        turn('PhD in IT',history)
        for _ in range(15):result=turn('Tell me more',history)
        self.assertEqual(result['scope']['subject'],'information technology')
        other=resolve_query('Information technology',[])
        self.assertIsNone(other['scope'])
    def test_done_and_new_topic_reset_previous_program(self):
        for end in ['done','thank you','new topic: What are the library hours?']:
            history=[]
            turn('PhD in IT',history)
            result=turn(end,history)
            self.assertIsNone(result['scope'])
            result=turn('Information technology',history)
            self.assertIsNone(result['scope'])
    def test_clear_action_skips_retrieval(self):
        class Retriever:
            def retrieve(self,*args,**kwargs):raise AssertionError('Conversation end must not retrieve')
        result=AnswerService(Retriever(),{'refusal_threshold':.5}).answer('done')
        self.assertEqual(result['reason'],'conversation_end')
        self.assertFalse(result['refused'])
        self.assertEqual(result['conversation_state'],{})
    def test_plain_user_history_also_retains_context(self):
        result=resolve_query('Information technology',[{'role':'user','content':'tuition fee for PhD'}])
        self.assertIn('tuition',result['query'])
        self.assertEqual(result['conversation_state']['pending'],'format')
    def test_one_word_why_keeps_previous_question(self):
        history=[]
        turn('What are the library hours?',history)
        result=turn('Why?',history)
        self.assertIn('library hours',result['query'])
        self.assertIn('Why?',result['query'])
    def test_full_program_name_can_answer_pending_slot(self):
        history=[]
        turn('PhD tuition fee',history)
        result=turn('PhD in Information Technology',history)
        self.assertIn('tuition fee',result['query'])
        self.assertEqual(result['conversation_state']['pending'],'format')
    def test_undergraduate_question_does_not_keep_doctoral_scope(self):
        history=[]
        turn('PhD in IT',history)
        result=turn('Undergraduate admissions',history)
        self.assertIsNone(result['scope'])
    def test_new_format_replaces_previous_format(self):
        history=[]
        turn('online PhD in IT tuition',history)
        result=turn('No, executive',history)
        self.assertEqual(result['scope']['format'],'executive')
        self.assertNotIn('online',result['query'])
    def test_generated_prompt_keeps_original_question_after_slot_replies(self):
        from unittest.mock import Mock
        import json
        class Retriever:
            def retrieve(self,*args,**kwargs):
                return [{'chunk_id':'it_fee','title':'Ph.D. in Information Technology',
                         'source_url':'https://www.ucumberlands.edu/academics/executive/phd-information-technology',
                         'text':'Tuition information for the executive PhD in Information Technology.',
                         'heading_path':['Tuition'],'rerank_score':1}],{}
        service=AnswerService(Retriever(),{'refusal_threshold':.5})
        service.router=Mock()
        service.router.configured.return_value=['groq']
        service.router.complete.return_value={'content':'{"refused": true,"claims": []}',
            'usage':{},'cost_usd':None,'provider':'groq','model':'model','attempts':[]}
        history=[]
        for query in ['tuition fee for PhD','Information technology','executive']:
            result=service.answer(query,history=history)
            history.extend([{'role':'user','content':query},
                {'role':'assistant','content':result['answer'],'conversation_state':result['conversation_state']}])
        prompt=json.loads(service.router.complete.call_args[0][0][-1]['content'])
        self.assertIn('tuition fee',prompt['question'])
        self.assertIn('Information Technology',prompt['question'])
        self.assertIn('executive',prompt['question'])
    def test_titles_and_honorifics_do_not_select_programs(self):
        for query,slot in [('Ms. Smith office hours?','degree'),('Ms Smith office hours?','degree'),
                           ('Who is the executive director of admissions?','format'),
                           ('Is the associate dean available?','degree'),('WHAT IS IT?','subject')]:
            result=resolve_query(query,[])
            self.assertNotIn(slot,result['conversation_state']['slots'],query)
            self.assertIsNone(result['clarification'],query)
    def test_program_words_still_select_programs(self):
        from retrieval.conversation import selections,replace_selections
        self.assertEqual(selections('What is the MS in nursing tuition?'),{'degree':'masters','subject':'nursing'})
        self.assertEqual(selections('associate degree in business'),{'degree':'associate','subject':'business'})
        self.assertEqual(selections('executive PhD in IT tuition'),{'degree':'phd','format':'executive','subject':'information technology'})
        self.assertEqual(selections('IT')['subject'],'information technology')
        self.assertEqual(selections('PHD IN IT')['subject'],'information technology')
        self.assertEqual(replace_selections('executive director of the executive PhD in IT',{'format':'online'}),
                         'executive director of the online PhD in IT')

if __name__=='__main__':unittest.main()
