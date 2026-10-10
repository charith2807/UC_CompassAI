"""Rebuild embeddings from normalized text, never re-crawl."""
import argparse
import hashlib
import json
from pathlib import Path
from generation.settings import load_config, ROOT
from .chunking import load_chunks, distribution
from .embed import Embedder
from .store import Store

def build(config,strategy,collection='compass'):
    processed=ROOT/config['processed_dir']
    chunks=load_chunks(processed,strategy,version=config['chunk_version'],
                       size=config['chunk_size'],overlap=config['chunk_overlap'])
    embedder=Embedder(config)
    # Download/model failures happen BEFORE any existing vectors are deleted.
    vectors=embedder.encode([c['text'] for c in chunks])
    store=Store(ROOT/'data/index',collection)
    deleted=store.clear_old(strategy,config['chunk_version'])
    store.add(chunks,vectors)
    indexed={c['chunk_id'] for c in store.all()}
    expected={c['chunk_id'] for c in chunks}
    if indexed!=expected:raise AssertionError('Index contains missing or orphan chunks')
    record={**embedder.record,'strategy':strategy,'chunk_version':config['chunk_version'],
            'collection':collection,'chunk_counts':distribution(chunks),'deleted':deleted,
            'orphan_count':len(indexed-expected),'indexed_count':len(indexed),
            'corpus_hash':hashlib.sha256(''.join(c['content_hash'] for c in chunks).encode()).hexdigest()}
    store.directory.mkdir(parents=True,exist_ok=True)
    (store.directory/f'{collection}_manifest.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))
    return record

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--strategy',choices=['fixed','structure'],default='structure')
    parser.add_argument('--collection',default='compass')
    parser.add_argument('--config',default=None)
    args=parser.parse_args()
    build(load_config(args.config),args.strategy,args.collection)
if __name__=='__main__':main()
