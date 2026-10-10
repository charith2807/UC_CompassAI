class Dense:
    def __init__(self,store,embedder): self.store,self.embedder=store,embedder
    def search(self,query,limit=20,page_type=None,chunk_ids=None):
        if chunk_ids is None:return self.store.query(self.embedder.encode([query])[0],limit,page_type)
        return self.store.query(self.embedder.encode([query])[0],limit,page_type,chunk_ids=chunk_ids)
