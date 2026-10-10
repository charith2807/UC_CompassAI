"""Deterministic fixed/heading-aware chunking of saved normalized text."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

# A dependency-free token proxy. Reports explicitly name it; index uses the same chunks.
TOKENIZER = 'unicode-word-and-punctuation-proxy-v1'
TOKEN = re.compile(r'\w+|[^\w\s]', re.UNICODE)

def spans(text): return [(m.start(), m.end()) for m in TOKEN.finditer(text)]
def token_count(text): return len(spans(text))

def windows(text, size=500, overlap=75):
    if size <= 0 or overlap < 0 or overlap >= size: raise ValueError('Invalid size/overlap')
    positions = spans(text)
    start = 0
    while start < len(positions):
        end = min(start + size, len(positions))
        yield text[positions[start][0]:positions[end-1][1]], end-start
        if end == len(positions): break
        start = end-overlap

def chunk_document(document, strategy='fixed', version='v1', size=500, overlap=75):
    if strategy not in ('fixed','structure'): raise ValueError('Unknown chunk strategy')
    if strategy == 'structure':
        from crawler.normalize import sections
        groups = document.get('sections') or sections(document['text'], document['title'])
    else: groups = [{'text':document['text'], 'heading_path':[document['title']]}]
    chunks=[]
    for group in groups:
        for text, length in windows(group['text'], size, overlap):
            chunk_id=f"{document['doc_id']}_{strategy}_{version}_{len(chunks):04d}"
            path=group['heading_path']
            chunks.append({'chunk_id':chunk_id,'doc_id':document['doc_id'],
                'source_url':document.get('source_url',document.get('url')),'title':document['title'],
                'heading_path':path,'page_type':document['page_type'],
                'crawl_timestamp':document.get('crawl_timestamp',document['crawled_at']),
                'effective_date':document.get('effective_date'),'chunk_strategy':strategy,
                'chunk_version':version,'content_hash':hashlib.sha256(text.encode()).hexdigest(),
                'text':text,'token_count':length,'tokenizer':TOKENIZER})
    return chunks

def load_chunks(processed_dir, strategy, **kwargs):
    result=[]
    files=sorted(Path(processed_dir).glob('*.json'))
    if not files: raise ValueError('No processed documents found')
    for path in files:
        doc=json.loads(path.read_text())
        if doc.get('normalization_version') != 'v2': raise ValueError('Run crawler.normalize first')
        result.extend(chunk_document(doc,strategy,**kwargs))
    return result

def distribution(chunks):
    values=sorted(c['token_count'] for c in chunks)
    def percentile(q):
        if not values:return 0
        index=(len(values)-1)*q; a=math.floor(index); b=math.ceil(index)
        return values[a]+(values[b]-values[a])*(index-a)
    return {'chunks':len(values),'min':min(values,default=0),'p50':percentile(.5),
            'p95':percentile(.95),'max':max(values,default=0),
            'mean':sum(values)/len(values) if values else 0,'tokenizer':TOKENIZER}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--processed-dir',default='data/processed')
    args=parser.parse_args()
    summary={}
    target=Path('data/chunks');target.mkdir(parents=True,exist_ok=True)
    for strategy in ('fixed','structure'):
        chunks=load_chunks(args.processed_dir,strategy)
        (target/f'{strategy}_v1.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in chunks))
        summary[strategy]=distribution(chunks)
    Path('docs/chunking_counts.json').write_text(json.dumps(summary,indent=2))
    Path('docs/chunking_report.md').write_text('# Chunking\n\n'+
        'Both strategies use 500 proxy tokens with 75 overlap for long sections.\n'
        'Structure-aware chunks preserve heading paths. Tables remain Markdown; very\n'
        'large tables can span windows, so table boundaries remain a known limitation.\n'
        'Counts use a Unicode word/punctuation proxy, not MiniLM WordPiece tokens.\n'
        'Embedding separately splits by the actual model tokenizer to prevent truncation.\n\n'
        '```json\n'+json.dumps(summary,indent=2)+'\n```\n\n'
        'Reproduce: `.venv/bin/python -m indexing.chunking`.\n'
        'Retrieval quality has not yet selected a winning strategy.\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
