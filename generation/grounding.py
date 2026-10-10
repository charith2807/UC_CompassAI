"""Conservative input/evidence checks and citation validation."""
import re
from urllib.parse import urlparse

REFUSAL="I don't have enough information in the indexed university sources to answer that."
INJECTION=re.compile(r'ignore (?:all |previous |the )?(?:instructions|rules)|system prompt|reveal.{0,20}(?:key|secret)|<\/?(?:system|context|untrusted)|BEGIN_SYSTEM',re.I)
PERSONAL=re.compile(r'\b(i|me|my|mine|am i|can i|will i)\b',re.I)
AID=re.compile(r'\b(aid|scholarship|loan|pell|fafsa)\b',re.I)
IMMIGRATION=re.compile(r'\b(cpt|opt|visa|immigration|f-?1|work authorization)\b',re.I)
HEALTH=re.compile(r'\b(diagnos|medication|suicid|symptom|treatment)',re.I)
CREDENTIALS=re.compile(r'\b(password|passcode|api key|access token|secret key)\b',re.I)
PASSWORD_HELP=re.compile(r'\b(reset|change|forgot|recover)\b',re.I)

def input_gate(query):
    if INJECTION.search(query):return {'reason':'prompt_injection','referral':None}
    if CREDENTIALS.search(query) and not PASSWORD_HELP.search(query):
        return {'reason':'credential_request','referral':None}
    if PERSONAL.search(query) and IMMIGRATION.search(query):
        return {'reason':'individualized_high_stakes','referral':{'office':'International Student Services','url':'https://www.ucumberlands.edu/admissions/international-students'}}
    if PERSONAL.search(query) and AID.search(query) and re.search(r'eligible|eligibility|qualify|will|guarantee|approve|how much',query,re.I):
        return {'reason':'individualized_high_stakes','referral':{'office':'Student Financial Center','url':'https://www.ucumberlands.edu/student-life/student-services/sfc'}}
    if PERSONAL.search(query) and HEALTH.search(query):
        return {'reason':'individualized_high_stakes','referral':{'office':'Health and Wellness','url':'https://www.ucumberlands.edu/student-life/student-services'}}
    return None

def context_safe(chunk):return not INJECTION.search(chunk['text'])

def evidence_gate(chunks,threshold=.5,use_rerank=True):
    chunks=[c for c in chunks if context_safe(c)]
    if not chunks:return []
    if use_rerank:return [c for c in chunks if c.get('rerank_score',0)>=threshold]
    # Baselines/ablation use only positive retriever scores, explicitly no calibration claim.
    return [c for c in chunks if c.get('initial_score',0)>0]

def valid_url(url):
    parsed=urlparse(url)
    host=parsed.hostname or ''
    return parsed.scheme=='https' and (host=='ucumberlands.edu' or host.endswith('.ucumberlands.edu'))

def validate_claims(claims,chunks):
    lookup={c['chunk_id']:c for c in chunks}
    if not claims:raise ValueError('No supported claims')
    validated=[]
    for claim in claims:
        text=claim['text'].strip()
        if not text or re.search(r'https?://|\[[^]]+\]\(',text):raise ValueError('Model-provided URL is forbidden')
        evidence=claim.get('evidence',[])
        if not evidence:raise ValueError('Every claim needs evidence')
        citations=[]
        for item in evidence:
            chunk=lookup.get(item['chunk_id'])
            quote=item['quote'].strip()
            if chunk is not None and quote and quote not in chunk['text']:
                # Only whitespace may vary in the model's quote. Return the actual
                # source span; never accept changed words, punctuation, or numbers.
                match=re.search(r'\s+'.join(re.escape(word) for word in quote.split()),chunk['text'])
                if match:quote=match.group(0)
            if chunk is None or not quote or len(quote.split())>25 or quote not in chunk['text']:
                raise ValueError('Citation must quote <=25 exact words from a retrieved chunk')
            if not valid_url(chunk['source_url']):raise ValueError('Off-domain source')
            citations.append({'url':chunk['source_url'],'title':chunk['title'],'quote':quote,
                'crawled_at':chunk['crawl_timestamp'],'chunk_id':chunk['chunk_id']})
        numbers=re.findall(r'\d+(?:[,.:]\d+)*',text)
        supported_numbers=set(re.findall(r'\d+(?:[,.:]\d+)*',' '.join(c['quote'] for c in citations)))
        if any(n not in supported_numbers for n in numbers):raise ValueError('Claim introduces unsupported numbers')
        validate_table_units(text,[lookup[c['chunk_id']] for c in citations])
        validated.append({'text':text,'citations':citations})
    return validated

def validate_table_units(text,chunks):
    """An exact dollar amount cannot justify attaching the wrong table-column unit."""
    pairs=re.findall(r'(\$[\d,]+(?:\.\d+)?)\s+(?:per|a|each)\s+(credit hour|bi[ -]?term|semester|year)',text,re.I)
    for amount,unit in pairs:
        units=set()
        for chunk in chunks:
            header=None
            for line in chunk['text'].splitlines():
                if '|' not in line:continue
                cells=[c.replace('#','').strip().lower() for c in line.strip().strip('|').split('|')]
                if any('per credit hour' in c or 'rate per' in c or 'per year' in c for c in cells):
                    header=cells;continue
                if header:
                    for i,cell in enumerate(cells):
                        if amount.lower()==cell and i<len(header):units.add(header[i])
        if units:
            canonical=unit.lower().replace('bi term','bi-term').replace('biterm','bi-term')
            if not any(canonical in value for value in units):raise ValueError('Claim introduces unsupported table unit')
