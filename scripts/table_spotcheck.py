"""Repeatable saved-HTML numeric spot-check; does not substitute for human review."""
import json
from pathlib import Path
from bs4 import BeautifulSoup

CHECKS={'30cf093febdc':['$9,875','$335','$220','$355'],
        '1264ef1238b2':['$26,471','$31,648'],
        'da972d41960b':['December 15','10:00 am','12:30 pm']}

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--raw-dir',type=Path,default=Path('../data/raw'));a=p.parse_args()
    results=[]
    for did,anchors in CHECKS.items():
        doc=json.loads(Path(f'data/processed/{did}.json').read_text())
        soup=BeautifulSoup((a.raw_dir/f'{did}.html').read_bytes(),'lxml')
        for sup in soup.find_all('sup'):sup.decompose()
        source=soup.get_text(' ',strip=True);tables='\n'.join(doc['tables'])
        checks={anchor:anchor in source and anchor in tables for anchor in anchors}
        if not all(checks.values()):raise AssertionError('Saved HTML/table mismatch')
        results.append({'doc_id':did,'source_url':doc['source_url'],'checks':checks,'tables':len(doc['tables'])})
    Path('docs/table_spotchecks.json').write_text(json.dumps(results,indent=2))
    print('Three page spot-checks passed; human row/header and footnote review still required')
if __name__=='__main__':main()
