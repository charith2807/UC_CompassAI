"""Run: streamlit run app/streamlit_app.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import os
import streamlit as st
from generation.settings import ROOT,load_config
from generation.providers import provider_key_available
from app.presentation import message_text,readable_text

st.set_page_config(page_title='Cumberlands Compass AI',page_icon='🧭')
st.title('Cumberlands Compass AI')
st.caption('Information may be out of date; verify on the official site.')
demo_mode=os.getenv('COMPASS_DEMO','').lower() in ('1','true','yes')
backend=st.sidebar.selectbox('Backend',['University corpus','UI mock'],index=1 if demo_mode else 0)
mode=st.sidebar.selectbox('Retriever',['hybrid','bm25','dense'])
page_type=st.sidebar.selectbox('Source category',['all','admissions','tuition','financial_aid','academics','calendar','student_life','policy','pdf'])
show_trace=st.sidebar.checkbox('Show retrieval trace',False)
if backend=='UI mock':
    st.info('Demo interface: uses a saved tuition excerpt, without live AI or measured retrieval.')
    st.caption('Try “What is tuition?”, “What is the Wi-Fi password?”, or “Will I qualify for aid?”')
elif not provider_key_available(load_config()):
    st.info('Retrieval-only mode: no generated answer. Source excerpts remain available when the index is ready.')

@st.cache_resource
def real_service():
    from generation.answer import create_service
    return create_service()

@st.cache_resource
def mock_service():
    from app.mock_backend import MockBackend
    return MockBackend([json.loads(p.read_text()) for p in (ROOT/'data/processed').glob('*.json')])

if 'messages' not in st.session_state:st.session_state.messages=[]
if st.sidebar.button('Clear conversation'):st.session_state.messages=[];st.rerun()

def display_result(result):
    text=message_text(result)
    if result.get('reason')=='all_configured_providers_unavailable':
        limited=any(a.get('error_type')=='RateLimitError' for a in result.get('provider_attempts',[]))
        st.info('The AI provider is temporarily rate-limited. These are source excerpts; please try again shortly.' if limited else 'The AI provider is unavailable. These are source excerpts, not a generated answer.')
    if result.get('refused'):st.warning(text)
    else:st.write(text.replace('$',r'\$'))
    if not result.get('refused') and result.get('mode','').startswith(('retrieval-only','UI mock')):
        st.caption('These are source excerpts, not an AI-generated answer.')
    if result.get('referral'):
        referral=result['referral'];st.link_button('Contact '+referral['office'],referral['url'])
    for i,citation in enumerate(result.get('citations',[]),1):
        with st.expander(f"Source {i}: {citation['title']} — crawled {citation['crawled_at']}"):
            st.link_button('Open official source',citation['url'])
            st.write(readable_text(citation['quote']).replace('$',r'\$'))
    if show_trace:
        st.caption(f"{result.get('mode','')} · {result.get('provider','')} {result.get('model','')} · {result.get('latency',0):.0f} ms")
        with st.expander('Retrieved evidence and scores'):
            st.json(result.get('trace',{}))

for message in st.session_state.messages:
    with st.chat_message(message['role']):
        if message['role']=='assistant':display_result(message['result'])
        else:st.markdown(message['content'])
if query:=st.chat_input('Ask about admissions, costs, programs, or student services'):
    history=[{'role':m['role'],'content':m['content'],
              **({'conversation_state':m['result']['conversation_state']}
                 if m['role']=='assistant' and 'conversation_state' in m.get('result',{}) else {})}
             for m in st.session_state.messages]
    st.session_state.messages.append({'role':'user','content':query})
    with st.chat_message('user'):st.markdown(query)
    with st.chat_message('assistant'):
        try:
            service=mock_service() if backend=='UI mock' else real_service()
        except Exception as exc:
            st.error('The university sources could not be loaded. Prepare the local index using docs/REPRODUCE.md, or select UI mock to inspect the interface.')
            if show_trace:st.caption('Startup error type: '+type(exc).__name__)
            st.stop()
        try:
            with st.spinner('Finding university sources…'):
                result=service.answer(query,history=history,mode=mode,page_type=None if page_type=='all' else page_type)
            display_result(result)
            st.session_state.messages.append({'role':'assistant','content':result['answer'],'result':result})
        except Exception as exc:
            st.error('I could not complete that search. Please try rephrasing the question or clearing the source-category filter.')
            if show_trace:st.caption('Search error type: '+type(exc).__name__)
