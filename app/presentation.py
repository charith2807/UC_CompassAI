"""Readable chat presentation; original evidence stays unchanged in results."""
import re

def readable_text(text):
    text=re.sub(r'!?\[([^\]]+)\]\([^)]*\)',r'\1',text)
    lines=[]
    for line in text.splitlines():
        if re.fullmatch(r'[\s|:\-]+',line):continue
        line=re.sub(r'#{1,6}(?=\s|$)', '', line)
        line=re.sub(r'^\s*[-*+]\s+', '', line)
        line=re.sub(r'(?:\[\d+\])+\s*$', '', line)
        line=line.replace('|',' ').replace('**','').replace('__','').replace('`','')
        line=re.sub(r'\s+',' ',line).strip()
        if line:lines.append(line)
    return '\n\n'.join(lines)

def message_text(result):
    if not result.get('refused') and result.get('mode','').startswith(('retrieval-only','UI mock')):
        excerpts=[]
        for citation in result.get('citations',[]):
            text=readable_text(citation['quote'])
            if text and text not in excerpts:excerpts.append(text)
        if excerpts:
            return 'Here is what I found in the university sources:\n\n'+'\n\n'.join(excerpts[:3])
    return readable_text(result['answer'])
