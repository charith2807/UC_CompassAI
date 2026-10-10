"""Normalize saved documents without network access; screen contact blocks."""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from .extract import effective_date, heading_paths, privacy_filter

CONTACT = re.compile(r'contact information|meet your|student success coordinators|campus ambassador|our team|faculty', re.I)
ROLE = re.compile(r'coordinator|director|ambassador|professor|advisor|counselor|dean|president|specialist|manager', re.I)
NAME_LINE = re.compile(r'^(?:Dr\.\s+)?[A-Z][a-zA-Z\x27-]+(?:\s+[A-Z][a-zA-Z\x27-]+){1,3}$')

def align_table_columns(text,tables):
    """Restore empty cells from saved pandas tables, using header AND row identity.

    HTML text extraction can collapse an empty bi-term cell and move a per-credit
    amount left. Never infer a column: replace only when the saved table agrees.
    """
    def label(value):return re.sub(r'\s+',' ',value.replace('#','')).strip().lower()
    rows={};ambiguous=set()
    for table in tables:
        header=None
        for line in table.splitlines():
            if not line.strip().startswith('|'):continue
            cells=[x.strip() for x in line.strip().strip('|').split('|')]
            if any('rate per' in cell.lower() or 'per credit hour' in cell.lower() for cell in cells[1:]):
                header=label(cells[0]);continue
            if not header or not any('$' in cell for cell in cells):continue
            key=(header,label(cells[0]));canonical='| '+' | '.join(cells)+' |'
            if key in rows and rows[key]!=canonical:ambiguous.add(key)
            rows[key]=canonical
    result=[];header=None
    for line in text.splitlines():
        if line.startswith('#'):
            header=label(line.lstrip('# ').split('|')[0])
        if line.strip().startswith('|') and header:
            key=(header,label(line.strip().strip('|').split('|')[0]))
            if key in rows and key not in ambiguous:line=rows[key]
        result.append(line)
    return '\n'.join(result)

def classify(url, kind):
    path = urlparse(url).path.lower()
    if kind == 'pdf': return 'pdf'
    if 'calendar' in path: return 'calendar'
    if 'cost-attendance' in path or path.endswith('/tuition'): return 'tuition'
    if any(t in path for t in ('financial','scholarship','applying-aid','types-financial-aid')): return 'financial_aid'
    if any(t in path for t in ('policy','policies','privacy','sap','title-ix')): return 'policy'
    if path.startswith(('/admission','/prospective')): return 'admissions'
    if path.startswith('/academics'): return 'academics'
    if path.startswith(('/student-life','/current-students')): return 'student_life'
    return 'general'

def contact_names(document):
    headings = document.get('headings', [])
    names = set()
    for i, heading in enumerate(headings):
        if re.search(r'contact information', heading['text'], re.I):
            for previous in headings[max(0,i-2):i]:
                candidate = previous['text'].strip()
                if NAME_LINE.fullmatch(candidate) and not ROLE.search(candidate): names.add(candidate)
    lines = document['text'].splitlines()
    for i, line in enumerate(lines):
        candidate = re.sub(r'^[#*\s]+|[*\s]+$', '', line)
        neighborhood = '\n'.join(lines[max(0,i-4):i+10])
        if NAME_LINE.fullmatch(candidate) and not ROLE.search(candidate) and CONTACT.search(neighborhood) and ROLE.search(neighborhood):
            names.add(candidate)
    return names

def normalize(document):
    d = dict(document)
    names = contact_names(d)
    def clean(value):
        # De-obfuscate email addresses before applying the existing privacy filter.
        value = re.sub(r'\s*(?:\[at\]|\(at\))\s*', '@', value, flags=re.I)
        value = re.sub(r'\s*(?:\[dot\]|\(dot\))\s*', '.', value, flags=re.I)
        for name in sorted(names, key=len, reverse=True): value = value.replace(name, '[REDACTED_PERSON]')
        filtered, _, why = privacy_filter(value)
        if filtered is None: raise ValueError(why)
        return filtered
    d['text'] = clean(d['text'])
    d['title'] = clean(d['title'])
    d['headings'] = [{**h, 'text': clean(h['text'])} for h in d.get('headings', [])]
    d['tables'] = [clean(t) for t in d.get('tables', [])]
    d['text'] = align_table_columns(d['text'],d['tables'])
    # Preserve every extracted table in chunkable text, not just a separate field.
    for table in d['tables']:
        if table not in d['text']: d['text'] += '\n\n## Extracted table\n\n' + table
    d['source_url'] = d.get('source_url', d['url'])
    d['page_type'] = classify(d['source_url'], d['source_type'])
    d['effective_date'] = effective_date(d['text'])
    d['heading_path'] = heading_paths(d['headings'])
    d['crawl_timestamp'] = d['crawled_at']
    d['normalized_content_hash'] = hashlib.sha256(d['text'].encode()).hexdigest()
    d['normalization_version'] = 'v2'
    d['pii'] = {**d.get('pii',{}), 'contact_names_redacted': d.get('pii', {}).get('contact_names_redacted', 0) + len(names)}
    d['sections'] = sections(d['text'], d['title'])
    return d

def sections(text, title):
    result, stack, lines = [], [], []
    def flush():
        if lines and '\n'.join(lines).strip():
            result.append({'heading_path': [x[1] for x in stack] or [title], 'text': '\n'.join(lines).strip()})
        lines.clear()
    for line in text.splitlines():
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            flush()
            level, label = len(m[1]), m[2]
            while stack and stack[-1][0] >= level: stack.pop()
            stack.append((level,label))
        lines.append(line)
    flush()
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir',type=Path,default=Path('data/processed'))
    args = parser.parse_args()
    files = sorted(args.input_dir.glob('*.json'))
    if not files: raise SystemExit('No normalized documents found')
    docs, errors = [], []
    for file in files:
        try:
            d = normalize(json.loads(file.read_text()))
            file.write_text(json.dumps(d, ensure_ascii=False, indent=2))
            docs.append(d)
        except ValueError as e:
            errors.append({'doc_id': file.stem, 'reason': str(e)})
            quarantine = args.input_dir.parent / 'excluded' / 'processed'
            quarantine.mkdir(parents=True, exist_ok=True)
            file.replace(quarantine / file.name)
    exclusion_path=Path('docs/normalization_exclusions.json')
    prior=json.loads(exclusion_path.read_text()) if exclusion_path.exists() else []
    exclusions={e['doc_id']:e for e in prior+errors}
    exclusion_path.write_text(json.dumps(list(exclusions.values()), indent=2))
    summary = {'documents':len(docs),'types':dict(Counter(d['source_type'] for d in docs)),
               'page_types':dict(Counter(d['page_type'] for d in docs)),
               'documents_with_tables':sum(bool(d['tables']) for d in docs),
               'contact_names_redacted':sum(d['pii']['contact_names_redacted'] for d in docs)}
    Path('docs').mkdir(exist_ok=True)
    Path('docs/corpus_counts.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__ == '__main__': main()
