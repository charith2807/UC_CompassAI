"""Persistent Chroma cosine store, filtered lookup, and verified deletion."""
import json
from pathlib import Path

class Store:
    def __init__(self, directory, name='compass'):
        import chromadb
        from chromadb.config import Settings
        self.client=chromadb.PersistentClient(path=str(directory),settings=Settings(anonymized_telemetry=False))
        self.collection=self.client.get_or_create_collection(name=name,metadata={'hnsw:space':'cosine'},embedding_function=None)
        if self.collection.metadata.get('hnsw:space')!='cosine': raise ValueError('Index metric mismatch')
        self.directory=Path(directory)
    def add(self,chunks,vectors):
        for start in range(0,len(chunks),128):
            block=chunks[start:start+128]
            metadata=[]
            for c in block:
                m={k:v for k,v in c.items() if k not in ('text','heading_path') and v is not None}
                m['heading_path']=json.dumps(c['heading_path'])
                metadata.append(m)
            self.collection.upsert(ids=[c['chunk_id'] for c in block],
                documents=[c['text'] for c in block],metadatas=metadata,
                embeddings=vectors[start:start+128].tolist())
    def all(self,page_type=None):
        data=self.collection.get(where={'page_type':page_type} if page_type else None,
                                 include=['documents','metadatas'])
        result=[]
        for id,text,meta in zip(data['ids'],data['documents'],data['metadatas']):
            result.append({**meta,'chunk_id':id,'text':text,'heading_path':json.loads(meta['heading_path'])})
        return sorted(result,key=lambda c:c['chunk_id'])
    def query(self, vector, limit=20, page_type=None, chunk_ids=None):
        if chunk_ids is not None and not chunk_ids:return []
        filters=[]
        if page_type:filters.append({'page_type':page_type})
        if chunk_ids is not None:filters.append({'chunk_id':{'$in':sorted(chunk_ids)}})
        where={'$and':filters} if len(filters)>1 else filters[0] if filters else None
        count=len(self.collection.get(where=where,include=[])['ids'])
        if not count:return []
        try:
            data=self.collection.query(query_embeddings=[vector.tolist()],n_results=min(limit,count),
                where=where,include=['documents','metadatas','distances'])
        except RuntimeError as exc:
            if 'contigious 2D array' not in str(exc):raise
            # Narrow metadata filters can exhaust HNSW traversal. Compute exact
            # cosine distances over the same persisted, filtered Chroma vectors.
            import numpy as np
            saved=self.collection.get(where=where,include=['documents','metadatas','embeddings'])
            vectors=np.asarray(saved['embeddings']); query=np.asarray(vector)
            distances=1-(vectors @ query)/(np.linalg.norm(vectors,axis=1)*np.linalg.norm(query))
            order=np.argsort(distances)[:min(limit,count)]
            data={key:[[saved[key][i] for i in order]] for key in ('ids','documents','metadatas')}
            data['distances']=[[float(distances[i]) for i in order]]
        result=[]
        for id,text,meta,distance in zip(data['ids'][0],data['documents'][0],data['metadatas'][0],data['distances'][0]):
            result.append({**meta,'chunk_id':id,'text':text,'heading_path':json.loads(meta['heading_path']),
                           'dense_score':1-float(distance),'initial_score':1-float(distance)})
        return result
    @staticmethod
    def strategy_filter(strategy,version):
        return {'$and':[{'chunk_strategy':{'$eq':strategy}},{'chunk_version':{'$eq':version}}]}
    def delete_strategy(self,strategy,version):
        where=self.strategy_filter(strategy,version)
        self.collection.delete(where=where)
        self.assert_zero_stale(strategy,version)
    def assert_zero_stale(self,strategy,version):
        remaining=self.collection.get(where=self.strategy_filter(strategy,version),include=[])
        if remaining['ids']:raise AssertionError(f"Stale chunks remain: {len(remaining['ids'])}")
    def clear_old(self,new_strategy,new_version):
        old={(c['chunk_strategy'],c['chunk_version']) for c in self.all()}
        for strategy,version in old:
            self.delete_strategy(strategy,version)
        return [{'strategy':s,'version':v,'remaining':0} for s,v in sorted(old)]
