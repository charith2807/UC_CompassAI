"""MS MARCO cross-encoder logits with explicit sigmoid score scale."""
import math
from .query import ranked_text

class Reranker:
    def __init__(self,config):
        import torch
        from sentence_transformers import CrossEncoder
        self.model=CrossEncoder(config['reranker_model'],revision=config['reranker_revision'],
                                default_activation_function=torch.nn.Identity())
        self.revision=getattr(self.model.model.config,'_commit_hash',config['reranker_revision'])
    def rerank(self,query,candidates,top_k=5):
        if not 1<=top_k<=5:raise ValueError('Reranker cap must be <= 5')
        if not candidates:return []
        scores=self.model.predict([(query,ranked_text(c)) for c in candidates],show_progress_bar=False)
        ranked=[]
        for c,score in zip(candidates,scores):
            logit=float(score)
            probability=1/(1+math.exp(-max(-60,min(60,logit))))
            # Retain scores on all candidates for the pre/post trace, not just top five.
            c.update(rerank_logit=logit,rerank_score=probability)
            ranked.append(dict(c))
        return sorted(ranked,key=lambda c:(-c['rerank_score'],c['chunk_id']))[:top_k]
