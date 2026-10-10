"""Reciprocal Rank Fusion keeps lexical and semantic score scales separate."""
def rrf(*rankings,k=60,limit=20):
    if k<=0:raise ValueError('RRF constant must be positive')
    fused={}
    for ranking in rankings:
        seen=set()
        for rank,chunk in enumerate(ranking,1):
            cid=chunk['chunk_id']
            if cid in seen:continue
            seen.add(cid)
            if cid not in fused:fused[cid]={**chunk,'rrf_score':0.0}
            fused[cid]['rrf_score']+=1/(k+rank)
            for score in ('bm25_score','dense_score'):
                if score in chunk:fused[cid][score]=chunk[score]
    result=sorted(fused.values(),key=lambda c:(-c['rrf_score'],c['chunk_id']))[:limit]
    return [{**c,'initial_score':c['rrf_score']} for c in result]
