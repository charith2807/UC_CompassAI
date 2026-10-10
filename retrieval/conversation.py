"""Resolve follow-ups from explicit user-selected slots, never assistant facts."""
import re

END=re.compile(r"(?:thanks(?: a lot)?|thank you|done|all done|that'?s all|goodbye|bye|end conversation)[.!\s]*",re.I)
RESET=re.compile(r'^(?:new topic|new question|another topic|start over|clear conversation|forget that)\b[\s:,.\-]*',re.I)
QUESTION=re.compile(r'^(?:what|when|where|why|how|who|which|can|could|do|does|is|are|will|tell me|give me|explain)\b',re.I)
REFERENCE=re.compile(r'\b(?:this|that|those|these|they|their|its|what about|how about|i mean|also|and|more|continue|same|else|elaborate|instead|rather|actually|no)\b',re.I)
ELLIPTICAL=re.compile(r'(?:why|when|where|how|can you explain|could you explain)[?!.\s]*',re.I)
FACET=re.compile(r'\b(?:contact|email|phone|telephone|office|courses?|curriculum|classes|subjects|study|learn|fees?|tuition|cost|price|deadline|requirements?|apply|application|duration|long|credits?|eligib|documents?|hours|location|how much)\b',re.I)
TOPICS=(
    ('DSO',r'\b(?:DSO|designated school official)\b'),
    ('tuition',r'\b(?:tuition|fees?|cost|price)\b'),
    ('library',r'\blibrary\b'),('housing',r'\b(?:housing|dorms?|residence halls?)\b'),
    ('dining',r'\b(?:dining|meal plans?|cafeteria)\b'),
    ('calendar',r'\b(?:academic calendar|semester dates|holidays?)\b'),
    ('financial aid',r'\b(?:financial aid|fafsa|scholarships?)\b'),
    ('admissions',r'\b(?:admissions?|enrollment)\b'),
    ('IT support',r'\b(?:wifi|wi-fi|helpdesk|IT support)\b'),
    ('parking',r'\b(?:parking|parking permits?)\b'),
    ('commencement',r'\b(?:commencement|graduation ceremony)\b'),
)
DEGREES=(('phd',r'\b(?:ph\.?\s*d\.?|doctorate|doctoral|doctor of philosophy)\b'),
         ('masters',r"\b(?:master'?s?|mba|ms|msc)\b"),
         ('undergraduate',r"\b(?:undergrad(?:uate)?|bachelor'?s?)\b"),
         ('associate',r"\bassociate'?s?\b"))
SUBJECTS=('information technology','artificial intelligence','business','leadership',
          'computer science','education','counseling','nursing','psychology',
          'criminal justice','accounting','public health','occupational therapy','physical therapy')
FORMATS=(('executive',r'\b(?:executive|hybrid)\b'),('online',r'\bonline\b'),('on-campus',r'\b(?:on-campus|on campus|in person)\b'))
QUALIFIERS=(('term',r'\b(?:spring|summer|fall|autumn|winter)\b'),('year',r'\b20\d{2}\b'))


def topic(query):
    for name,pattern in sorted(TOPICS,key=lambda pair:pair[0]=='tuition'):
        if re.search(pattern,query,re.I):return name
    return None


def selections(query):
    result={}
    for key,choices in (('degree',DEGREES),('format',FORMATS)):
        for value,pattern in choices:
            if re.search(pattern,query,re.I):result[key]=value;break
    for name in SUBJECTS:
        if re.search(r'\b'+re.escape(name)+r'\b',query,re.I):result['subject']=name;break
    if 'subject' not in result:
        if re.search(r'\bIT\b',query) or re.fullmatch(r'\s*it[?!.\s]*',query) or re.search(r'\b(?:phd in it|it field|it program)\b',query,re.I):result['subject']='information technology'
        elif re.search(r'\bAI\b',query):result['subject']='artificial intelligence'
    if re.search(r'\binternational\b',query,re.I):result['audience']='international'
    elif re.search(r'\b(?:domestic|resident)\b',query,re.I):result['audience']='domestic'
    for key,pattern in QUALIFIERS:
        value=re.search(pattern,query,re.I)
        if value:result[key]=value.group(0).lower()
    return result


def anchor(query):
    current=topic(query)
    if current:
        level=re.search(r"\b(?:undergraduate|graduate|international|master'?s|bachelor'?s)\b",query,re.I)
        return (level.group(0)+' ' if level else '')+current
    return query


def program_anchor(slots):
    label={'phd':'Ph.D.','masters':"Master's",'undergraduate':'Undergraduate','associate':'Associate'}.get(slots.get('degree'),'')
    if slots.get('subject'):label+=(' in ' if label else '')+slots['subject'].title()
    if slots.get('format'):label+=' '+slots['format']
    if slots.get('audience'):label+=' '+slots['audience']+' students'
    for key in ('term','year'):
        if slots.get(key):label+=' '+slots[key]
    return label.strip()


def replace_selections(text,updates):
    """Replace each selector in place, adding only selectors not already present."""
    labels={'degree':{'phd':'Ph.D.','masters':"Master's",'undergraduate':'Undergraduate','associate':'Associate'}}
    patterns={'degree':'|'.join('(?:'+p+')' for _,p in DEGREES),
              'format':'|'.join('(?:'+p+')' for _,p in FORMATS),
              'subject':'|'.join(re.escape(name) for name in SUBJECTS)+r'|\bIT\b|\bAI\b',
              'audience':r'\b(?:international|domestic|resident)\b',
              **dict(QUALIFIERS)}
    for key,value in updates.items():
        replacement=labels.get(key,{}).get(value,value.title() if key=='subject' else value)
        pattern=patterns[key]
        if re.search(pattern,text,re.I):
            count=[0]
            def substitute(match):
                count[0]+=1
                return replacement if count[0]==1 else ''
            text=re.sub(pattern,substitute,text,flags=re.I)
        else:text+=' '+replacement
    return text


def advance(query,previous=None):
    previous=previous or {};query=query.strip()
    if END.fullmatch(query):return {'query':query,'state':{},'action':'end'}
    reset=RESET.match(query)
    if reset:
        query=query[reset.end():].strip();previous={}
        if not query:return {'query':query,'state':{},'action':'reset'}
    old=previous.get('context_query','');old_slots=previous.get('slots') or selections(old)
    updates=selections(query);current_topic=topic(query);old_topic=previous.get('topic')
    reference=bool(REFERENCE.search(query)) or bool(re.search(r'\bit\b',query))
    elliptical=bool(ELLIPTICAL.fullmatch(query))
    short=(len(query.split())<=10 and not QUESTION.match(query)) or elliptical
    pending=bool(previous.get('pending'))
    explicit_program=bool(updates.get('degree') and updates.get('subject'))
    new_level=bool(updates.get('degree') and updates.get('degree')!=old_slots.get('degree'))
    # A named new program is standalone; comparisons and clarification replies inherit intent.
    standalone=explicit_program and not reference and not (pending and short)
    if new_level and not reference and not pending:standalone=True
    program_facet=bool(old_slots.get('degree') and current_topic in ('tuition','admissions','financial aid'))
    if reference and current_topic=='tuition' and old_topic and not re.search(r'\btuition\b',query,re.I):current_topic=old_topic
    topic_change=bool(current_topic and current_topic!=old_topic and not program_facet)
    if reference and FACET.search(query) and current_topic=='tuition' and not re.search(r'\btuition\b',query,re.I):topic_change=False
    if pending and short:topic_change=False
    unknown_comparison=bool(re.match(r'^(?:what about|how about|and)\b',query,re.I) and not re.search(r'\b(?:it|that|same|more)\b',query,re.I))
    unclear=bool(old and not pending and not elliptical and not updates and not FACET.search(query) and not current_topic and ((short and not reference) or unknown_comparison))
    if unclear:
        return {'query':query,'state':dict(previous),'action':None,'clarification':'Could you clarify what you want to change or know more about? You can name the program, study format, or information you need.'}
    inherit=bool(old and not standalone and not topic_change and
                 (reference or short or FACET.search(query) or updates))
    slots=dict(old_slots) if inherit else {};slots.update(updates)
    if slots.get('degree') in ('undergraduate','associate') and slots.get('format')=='executive':slots.pop('format')
    if inherit:
        # Slot-only replies keep the last question. New facets replace its intent while retaining selectors.
        selector_reply=bool(updates and not FACET.search(query))
        comparison=bool(re.match(r'^(?:what about|how about|and)\b',query,re.I) and not FACET.search(query))
        if (pending and not FACET.search(query)) or selector_reply or elliptical or comparison:
            effective=replace_selections(old,updates)
            if pending and current_topic and not FACET.search(query):effective+=' '+query
            if not updates:effective=old+' '+query
        elif FACET.search(query) or reference or current_topic in ('admissions','financial aid'):
            root=program_anchor(slots) if slots.get('degree') in ('phd','masters') or slots.get('subject') else previous.get('anchor',anchor(old))
            if slots.get('audience') and slots['audience'] not in root:root+=' '+slots['audience']+' students'
            effective=root+' '+query
        else:effective=old+' '+query
    else:effective=query
    effective=re.sub(r'[ \t]+',' ',effective).strip()
    state={'context_query':effective,'anchor':program_anchor(slots) if slots.get('degree') in ('phd','masters') or slots.get('subject') else anchor(effective),
           'topic':current_topic or (old_topic if inherit else topic(effective)),
           'slots':slots,'pending':None,'program_context':bool(slots.get('degree'))}
    return {'query':effective,'state':state,'action':None}


def context(query,history=None):
    history=history or [];previous=None
    if history and history[-1].get('role')=='assistant':
        value=history[-1].get('conversation_state')
        if isinstance(value,dict):previous=value
    if previous is None:
        previous={}
        for item in history:
            if item.get('role')=='user':previous=advance(item['content'],previous)['state']
    return advance(query,previous)
