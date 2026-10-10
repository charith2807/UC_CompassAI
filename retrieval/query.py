"""Resolve degree/subject references without confusing the IT acronym with 'it'."""
import re
from .conversation import context,selections,program_anchor,SUBJECTS

PHD=re.compile(r'\b(?:ph\.?\s*d\.?|doctor(?:ate|al)|doctor of philosophy)\b',re.I)
FEES=re.compile(r'\b(?:fees?|tuition|cost|price|pricing|pay|how much)\b',re.I)
DSO=re.compile(r'\b(?:DSO|designated school official)\b',re.I)
# "who"/"where" signal contact only in contact phrasings; "Who is a DSO?" asks for the role.
CONTACT=re.compile(r'\b(?:contact|email|phone|telephone|reach|office|(?:who|where)\s+(?:do|can|should|would)\s+(?:i|we)|who\s+is\s+(?:my|our))\b',re.I)
DSO_DETAIL=re.compile(r'\b(?:contact|email|phone|telephone|reach|office|where|who|role|mean|stands?|definition|what is|what does|responsibilit|help|cpt|opt|visa|i-?20)\b',re.I)
COURSES=re.compile(r'\b(?:courses?|curriculum|classes|subjects|what (?:will|would|do) I (?:study|learn))\b',re.I)

def retrieval_question(query,scope):
    """Expand curriculum intent without changing program or evidence boundaries."""
    if DSO.search(query) and CONTACT.search(query):
        return 'If not sure which DSO to contact email the DSO listed on current I-20 document'
    if scope and not scope.get('tuition') and COURSES.search(query):
        degree='PhD' if scope.get('degree')=='phd' else "master's"
        return degree+' in '+scope['subject']+' course requirements curriculum professional research content specialty courses'
    return query

OTHER_LEVEL=re.compile(r"\b(?:undergrad(?:uate)?|bachelor(?:'?s)?|master(?:'?s)?|mba|associate(?:'?s)?)\b",re.I)

def subject(text):
    return selections(text).get('subject')

def resolve_query(query,history=None):
    turn=context(query,history)
    original=query
    query=turn['query']
    state=turn['state']
    slots=state.get('slots',{})
    def resolved(search,scope=None,clarification=None,pending=None):
        if not turn['action']:state['pending']=pending
        if slots.get('degree') in ('phd','masters'):
            state['program_context']=True
            state['anchor']=program_anchor(slots)
        if scope:
            state['anchor']=('Ph.D. in ' if scope['degree']=='phd' else "Master's in ")+scope['subject'].title()
            if scope.get('format'):state['anchor']+=' '+scope['format']
        return {'query':search,'scope':scope,'clarification':clarification,
                'conversation_state':state,'action':turn['action']}
    if turn['action']:return resolved(query)
    if turn.get('clarification'):return resolved(query,clarification=turn['clarification'])
    if DSO.search(query):
        if not DSO_DETAIL.search(original) and state.get('pending') != 'dso_detail':
            return resolved(query,clarification='Do you need contact information for your Designated School Official (DSO), or an explanation of what a DSO does?',pending='dso_detail')
        # DSO is a student-service request, independent of the previous program.
        return resolved(query)
    field=slots.get('subject');level=slots.get('degree');degree=level in ('phd','masters')
    label='PhD' if level=='phd' else "master's"
    if degree and field is None:
        prompt='Which '+label+' program is this tuition question about?' if FEES.search(query) else 'Which '+label+' subject are you interested in?'
        return resolved(query,clarification=prompt,pending='program')
    if degree and FEES.search(query) and not slots.get('format'):
        return resolved(query,clarification='For the '+label+' in '+field.title()+', which study format do you mean: online or executive/hybrid?',pending='format')
    if degree and field:
        expanded=re.sub(r'\bIT\b','Information Technology',query)
        expanded=re.sub(r'\bAI\b','Artificial Intelligence',expanded)
        state['context_query']=expanded
        return resolved(expanded,scope={'degree':level,'subject':field,
                         'format':slots.get('format'),
                         'tuition':bool(FEES.search(query))})
    return resolved(query)

def program_matches(chunk,scope):
    if not scope:return True
    if shared_tuition_matches(chunk,scope):return True
    identity=chunk.get('title','')+' '+chunk.get('source_url','').replace('-',' ')
    if scope.get('format')=='online' and '/executive/' in chunk.get('source_url',''):return False
    degree_match=bool(PHD.search(identity)) if scope.get('degree')=='phd' else bool(re.search(r"\b(?:master'?s|ms|msc)\b",identity,re.I))
    return degree_match and scope['subject'] in identity.lower()

def shared_tuition_matches(chunk,scope):
    """Allow only heading-scoped rates, never unrelated rows in mixed tables."""
    if not scope or not scope.get('tuition'):return False
    if not chunk.get('source_url','').rstrip('/').endswith('/tuition-aid/tuition'):return False
    heading=' '.join(chunk.get('heading_path',[])).lower()
    text=chunk.get('text','').lower()
    if scope.get('format')=='executive':
        row='doctoral programs' if scope.get('degree')=='phd' else "master's programs"
        return heading.startswith('executive programs') and row in text
    if scope.get('format')=='online':
        if scope.get('degree')=='phd':
            return heading.startswith('graduate - doctoral') and scope['subject']+' online' in text
        # Specialized programs publish separate rates; do not give them the general rate.
        return (scope.get('degree')=='masters' and scope['subject'] in ('information technology','artificial intelligence','business')
                and heading.startswith("graduate - master's |") and '| online |' in text)
    return False

def ranked_text(chunk):
    return chunk.get('title','')+'\n'+' > '.join(chunk.get('heading_path',[]))+'\n'+chunk['text']

def audience_matches(chunk,slots):
    """Exclude explicitly incompatible student-level sources, not general guidance."""
    if slots.get('degree') not in ('undergraduate','associate'):return True
    identity=' '.join([chunk.get('title',''),chunk.get('source_url','').replace('-',' '),*chunk.get('heading_path',[])])
    identity=re.sub(r'\bundergraduate\b','',identity,flags=re.I)
    return not re.search(r"\b(?:graduate|postgraduate|master'?s?|doctoral|doctorate|doctor|ph\.?\s*d|physician assistant|dpt|dba|edd)\b",identity,re.I)


def contact_evidence(query,chunks):
    """For DSO contact requests, retain exact contact sentences, not procedures."""
    if not (DSO.search(query) and CONTACT.search(query)):return chunks
    selected=[]
    for chunk in chunks:
        sentences=re.split(r'(?<=[.!?])\s+|\n+',chunk['text'])
        routes=[line for line in sentences if DSO.search(line) and
                re.search(r'email (?:the|your|a) (?:assigned )?DSO|contact (?:your )?assigned DSO by email',line,re.I)]
        if routes:selected.append({**chunk,'text':'\n'.join(routes)})
    return selected
