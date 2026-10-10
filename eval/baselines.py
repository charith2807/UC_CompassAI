"""B0-B3 and one-factor progression. No key means no claimed answer evaluation."""
import os
from time import perf_counter

VARIANTS={
 'B1':{'collection':'compass_fixed','mode':'bm25','use_rerank':False,'use_grounding':True},
 'B2':{'collection':'compass_fixed','mode':'dense','use_rerank':False,'use_grounding':True},
 'A1_structure_dense':{'collection':'compass','mode':'dense','use_rerank':False,'use_grounding':True},
 'A2_structure_hybrid':{'collection':'compass','mode':'hybrid','use_rerank':False,'use_grounding':True},
 'A3_structure_rerank':{'collection':'compass','mode':'hybrid','use_rerank':True,'use_grounding':False},
 'B3':{'collection':'compass','mode':'hybrid','use_rerank':True,'use_grounding':True},
}
# A2 -> A3 enables reranking and its score selection; A3 -> B3 adds the threshold.
# B2 and A1 differ only by chunk strategy, A1/A2 only by retrieval mode.

class BaselineRunner:
    def __init__(self,name,config):
        self.name,self.config=name,config
        if name!='B0':
            from generation.answer import create_service
            self.options=dict(VARIANTS[name]);collection=self.options.pop('collection')
            self.service=create_service(config,collection)
    def answer(self,query):
        if self.name!='B0':return self.service.answer(query,**self.options)
        from generation.providers import ProviderRouter
        start=perf_counter()
        response=ProviderRouter(self.config).complete(
            [{'role':'system','content':'Answer the university question without retrieval. Say you do not know if uncertain.'},
             {'role':'user','content':query}])
        text=response['content']
        return {'answer':text,'citations':[],'refused':text.lower().startswith(('i do not know',"i don't know")),
                'trace':{},'latency':(perf_counter()-start)*1000,'mode':'closed-book',
                'usage':response['usage'],'cost_usd':response['cost_usd'],
                'provider':response['provider'],'model':response['model'],'provider_attempts':response['attempts']}
