"""MiniLM embeddings with explicit normalization and no silent truncation."""
from importlib.metadata import version

class Embedder:
    def __init__(self, config):
        import numpy as np
        from sentence_transformers import SentenceTransformer
        from huggingface_hub import snapshot_download
        self.np=np
        self.config=config
        snapshot=snapshot_download(config['embedding_model'],revision=config['embedding_revision'],
            allow_patterns=['*.json','*.txt','*.safetensors','*.model'])
        # Never let SentenceTransformer silently substitute an auto-created model.
        from pathlib import Path
        if not (Path(snapshot)/'modules.json').exists():raise ValueError('Incomplete MiniLM snapshot; run scripts/download_models.py')
        self.model=SentenceTransformer(snapshot,local_files_only=True)
        if self.model.get_sentence_embedding_dimension()!=384: raise ValueError('Expected 384 dimensions')
        self.record={'model':config['embedding_model'],'revision':config['embedding_revision'],
                     'sentence_transformers_version':version('sentence-transformers'),
                     'dimension':384,'distance_metric':'cosine','l2_normalized':True,
                     'long_chunk_policy':'WordPiece subwindows, weighted mean, L2 normalize',
                     'max_sequence_length':self.model.max_seq_length}
    def encode(self, texts):
        np=self.np; vectors=[]; strings=[]; groups=[]
        tokenizer=self.model.tokenizer
        width=self.model.max_seq_length-tokenizer.num_special_tokens_to_add(pair=False)
        for text in texts:
            tokens=tokenizer.encode(text,add_special_tokens=False)
            if not tokens: raise ValueError('Cannot embed empty text')
            parts=[tokens[i:i+width] for i in range(0,len(tokens),width)]
            start=len(strings)
            strings.extend(tokenizer.decode(p,skip_special_tokens=True) for p in parts)
            groups.append((start,len(strings),[len(p) for p in parts]))
        if not strings:return np.empty((0,384),dtype=np.float32)
        embedded=self.model.encode(strings,batch_size=32,normalize_embeddings=True,show_progress_bar=len(texts)>32)
        for start,end,weights in groups:
            vector=np.average(embedded[start:end],axis=0,weights=weights)
            norm=np.linalg.norm(vector)
            if norm<1e-12: raise ValueError('Zero embedding')
            vectors.append(vector/norm)
        return np.asarray(vectors,dtype=np.float32)
