"""Live UI conversation smoke; uses API quota and saved data, never the golden split."""
import json,sys,os
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)
from streamlit.testing.v1 import AppTest
app=AppTest.from_file('app/streamlit_app.py',default_timeout=90).run()
assert not app.exception
app.sidebar.checkbox[0].set_value(True).run()
records=[]
scenarios=[
 ('tuition', ['what is the tuition fee for PhD student?','IT','Executive','how about masters?','and online?','what are the requirements?','how long does it take?']),
 ('subjects', ['executive PhD in IT tuition','what about business?','and masters?','actually AI','no PhD']),
 ('services', ['What are the library hours?','Where is it?','What are housing options?','What does it cost?','done']),
 ('admissions', ['What are undergraduate admissions requirements?','and international students?','What documents do they need?','What is the admissions deadline for fall 2025?','how about spring 2026?']),
 ('safeguards', ['What is the university Wi-Fi password?','Will I qualify for financial aid?','What is the capital of Atlantis?']),
]
for name,queries in scenarios:
 app.sidebar.button[0].click().run()
 for q in queries:
  import time
  time.sleep(float(os.getenv('COMPASS_SMOKE_PAUSE_SECONDS','3')))
  app.chat_input[0].set_value(q).run()
  assert not app.exception,(name,q,'UI exception')
  assert not app.error,(name,q,[x.value for x in app.error],[x.value for x in app.caption if 'error' in x.value.lower()])
  r=app.session_state['messages'][-1]['result'];state=r.get('conversation_state',{})
  item={'scenario':name,'query':q,'answer':r['answer'],'reason':r.get('reason'),'provider':r.get('provider'),'model':r.get('model'),'attempts':r.get('provider_attempts'),'refused':r['refused'],'citations':len(r['citations']),'citation_urls':[c['url'] for c in r['citations']],'slots':state.get('slots',{}),'resolved_query':r.get('trace',{}).get('search_query'),'candidate_count':r.get('trace',{}).get('candidate_count')}
  records.append(item);Path('data/runtime/conversation_live_smoke.json').write_text(json.dumps({'checks':records,'complete':False},indent=2));print(json.dumps(item),flush=True)
  assert r.get('reason') not in ('generation_or_grounding_error',),(q,r.get('reason'))
  if q=='how about masters?':
   assert state['slots']['degree']=='masters' and state['slots']['format']=='executive'
   assert not r['refused'] and r['provider']=='groq' and r['citations']
   assert '549' in r['answer'] and '749' not in r['answer']
  if q=='and online?':
   assert state['slots']['format']=='online' and state['slots']['degree']=='masters'
   assert not r['refused'] and '355' in r['answer'] and '749' not in r['answer']
  if q=='What documents do they need?':assert 'admissions' in item['resolved_query'].lower() and state['slots']['audience']=='international'
  if q=='how about spring 2026?':
   assert not any('/graduate/' in u or 'physician' in u for u in item['citation_urls'])
   assert state['slots']['year']=='2026' and state['slots']['term']=='spring' and 'deadline' in item['resolved_query']
  if name=='safeguards':assert r['refused']
# Verify that all retriever modes preserve the degree switch in the actual UI.
for mode in ('bm25','dense'):
 app.sidebar.button[0].click().run();app.sidebar.selectbox[1].set_value(mode).run()
 for q in ('executive PhD in IT tuition','how about masters?'):
  import time
  time.sleep(float(os.getenv('COMPASS_SMOKE_PAUSE_SECONDS','3')))
  app.chat_input[0].set_value(q).run();assert not app.exception
  r=app.session_state['messages'][-1]['result']
  assert not r['refused'] and r.get('provider')=='groq' and r['citations'],(mode,q,r.get('reason'))
  if 'masters' in q:assert '549' in r['answer'] and '749' not in r['answer']
  records.append({'scenario':mode,'query':q,'answer':r['answer'],'provider':r.get('provider'),'citations':len(r['citations'])})
p=Path('data/runtime/conversation_live_smoke.json');p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps({'verified_at':datetime.now(timezone.utc).isoformat(),'checks':records},indent=2))
print('LIVE UI CHECKS PASSED',len(records),flush=True)
