"""Explicit UI-only mock. No model scores or evaluation claims."""
from time import perf_counter
import re
from generation.grounding import REFUSAL,input_gate

class MockBackend:
    def __init__(self,documents):self.documents=documents
    def answer(self,query,**kwargs):
        start=perf_counter()
        result={'answer':REFUSAL,'citations':[],'refused':True,'referral':None,
                'mode':'UI mock — not a measured RAG system','trace':{'mock':True},'latency':0.0}
        gate=input_gate(query)
        if gate:
            result['referral']=gate['referral']
            if gate['referral']:result['answer']='Please contact '+gate['referral']['office']+'.'
        elif 'tuition' in query.lower():
            document=next((d for d in self.documents if d['source_url'].endswith('/tuition')),None)
            if document:
                matches=list(re.finditer(r'\S+',document['text']))
                excerpt=document['text'][:matches[min(24,len(matches)-1)].end()]
                result.update(answer='UI mock: source excerpt only.',refused=False,
                    citations=[{'url':document['source_url'],'title':document['title'],
                                'quote':excerpt,'crawled_at':document['crawled_at']}])
        result['latency']=(perf_counter()-start)*1000
        return result
