"""Actual real retrieval-only smoke; no golden test items are used."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from generation.answer import create_service
from generation.settings import ROOT

def main():
    service=create_service()
    runs=[]
    for query in ['What is on-campus undergraduate tuition?','What is the university Wi-Fi password?','Will I qualify for financial aid?','What is the capital of Atlantis?']:
        r=service.answer(query);runs.append({'query':query,'result':r})
    if not runs[0]['result']['citations']:raise AssertionError('Grounded smoke question must have citations')
    if not runs[1]['result']['refused']:raise AssertionError('Unsupported smoke question must refuse')
    if not runs[2]['result']['referral']:raise AssertionError('Individualized aid question must refer')
    if not runs[3]['result']['refused']:raise AssertionError('Out-of-corpus factual question must refuse')
    trace=runs[0]['result']['trace']
    if trace['candidate_count']<20 or len(trace['selected'])>5:
        raise AssertionError('Candidate pool or rerank cap failed')
    filtered=service.answer('What is on-campus undergraduate tuition?',page_type='tuition')
    if not filtered['citations'] or any(c['page_type']!='tuition' for c in filtered['trace']['selected']):
        raise AssertionError('Tuition metadata filter failed')
    runs.append({'query':'What is on-campus undergraduate tuition?','page_type':'tuition','result':filtered})
    target=ROOT/'data/runtime';target.mkdir(parents=True,exist_ok=True)
    (target/'smoke.json').write_text(json.dumps(runs,indent=2))
    print('Real smoke passed: cited evidence, credential and weak-evidence refusal, referral, metadata filter, 20 candidates and top-five cap')
if __name__=='__main__':main()
