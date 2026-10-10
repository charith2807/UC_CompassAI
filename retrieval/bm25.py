"""Lexical retrieval using the required rank_bm25 implementation."""
import re
from .query import ranked_text

def tokenize(text): return re.findall(r'\w+',text.lower())

class BM25:
    def __init__(self,chunks):
        from rank_bm25 import BM25Okapi
        self.chunks=sorted(chunks,key=lambda c:c['chunk_id'])
        self.model=BM25Okapi([tokenize(ranked_text(c)) for c in self.chunks]) if self.chunks else None
    def search(self,query,limit=20,page_type=None,chunk_ids=None):
        if self.model is None:return []
        scores=self.model.get_scores(tokenize(query))
        order=sorted(range(len(scores)),key=lambda i:(-float(scores[i]),self.chunks[i]['chunk_id']))
        return [{**self.chunks[i],'bm25_score':float(scores[i]),'initial_score':float(scores[i])}
                for i in order if (page_type is None or self.chunks[i]['page_type']==page_type)
                and (chunk_ids is None or self.chunks[i]['chunk_id'] in chunk_ids)][:limit]
