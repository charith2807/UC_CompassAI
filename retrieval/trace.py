"""JSON-serializable evidence traces; no user-query persistence by default."""
from time import perf_counter
from .hybrid import rrf
from .query import program_matches,audience_matches

class Retriever:
    def __init__(self,bm25,dense,reranker,config):
        self.bm25,self.dense,self.reranker,self.config=bm25,dense,reranker,config
    def retrieve(self,query,mode='hybrid',page_type=None,use_rerank=True,program_scope=None,context_scope=None):
        start=perf_counter();pool=self.config['candidate_pool']
        if pool<20:raise ValueError('Candidate pool must be >= 20')
        scoped_ids=None
        if program_scope:
            scoped_ids={c['chunk_id'] for c in self.bm25.chunks if program_matches(c,program_scope)}
        if context_scope:
            allowed={c['chunk_id'] for c in self.bm25.chunks if audience_matches(c,context_scope)}
            scoped_ids=allowed if scoped_ids is None else scoped_ids & allowed
        extra={'chunk_ids':scoped_ids} if scoped_ids is not None else {}
        lexical=self.bm25.search(query,pool,page_type,**extra) if mode in ('bm25','hybrid') else []
        semantic=self.dense.search(query,pool,page_type,**extra) if mode in ('dense','hybrid') else []
        if mode=='hybrid':candidates=rrf(lexical,semantic,k=self.config['rrf_k'],limit=pool)
        elif mode=='bm25':candidates=lexical
        elif mode=='dense':candidates=semantic
        else:raise ValueError('Unknown retriever mode')
        retrieval_ms=(perf_counter()-start)*1000
        start=perf_counter()
        selected=self.reranker.rerank(query,candidates,self.config['rerank_top_k']) if use_rerank else candidates[:5]
        rerank_ms=(perf_counter()-start)*1000
        trace={'mode':mode,'page_type':page_type,'candidate_count':len(candidates),
               'program_scope':program_scope,'program_chunk_count':len(scoped_ids) if scoped_ids is not None else None,
               'context_scope':context_scope,
               'insufficient_pool':len(candidates)<20,'retrieval_ms':retrieval_ms,
               'rerank_ms':rerank_ms,'candidates':candidates,'selected':selected,
               'top_chunk_ids':[c['chunk_id'] for c in selected],
               'reranker_revision':getattr(self.reranker,'revision',None) if use_rerank else None}
        return selected,trace
