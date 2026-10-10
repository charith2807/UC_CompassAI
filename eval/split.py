"""Deterministic 24/16 split with stratified largest-remainder allocation."""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

def stratified_split(items,seed=633):
    groups=defaultdict(list)
    for item in items:groups[item['category']].append(item)
    exact={k:.6*len(v) for k,v in groups.items()}
    allocation={k:int(v) for k,v in exact.items()}
    target=round(.6*len(items))
    for key in sorted(groups,key=lambda k:(-(exact[k]-allocation[k]),k))[:target-sum(allocation.values())]:allocation[key]+=1
    result={};rng=random.Random(seed)
    for category in sorted(groups):
        rows=sorted(groups[category],key=lambda x:x['id']);rng.shuffle(rows)
        for i,row in enumerate(rows):result[row['id']]='dev' if i<allocation[category] else 'test'
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--golden',default='eval/golden_set.jsonl');args=parser.parse_args()
    path=Path(args.golden);items=[json.loads(line) for line in path.read_text().splitlines() if line]
    assignments=stratified_split(items)
    output=Path('eval/split_manifest.json')
    if output.exists():
        prior=json.loads(output.read_text())
        if prior['assignments']!=assignments:raise SystemExit('Existing split would change; preserve frozen item IDs')
        print('Existing split preserved');return
    output.write_text(json.dumps({'seed':633,'assignments':assignments,'initial_golden_sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2))
    print('dev:',sum(s=='dev' for s in assignments.values()),'test:',sum(s=='test' for s in assignments.values()))
if __name__=='__main__':main()
