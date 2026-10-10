"""Grounded answer service; no key gives clearly labelled retrieval-only output."""
import json
import os
import re
from pathlib import Path
from time import perf_counter
from .grounding import REFUSAL,input_gate,evidence_gate,validate_claims
from .prompt import messages,grounded_schema,expand_quotes
from .settings import ROOT,load_config
from .providers import ProviderRouter, ProviderUnavailable
from retrieval.query import resolve_query,program_matches,shared_tuition_matches,audience_matches,FEES,retrieval_question

class AnswerService:
    def __init__(self,retriever,config,client=None):
        self.retriever,self.config=retriever,config
        self.router=ProviderRouter(config,clients={'openai':client} if client else None)
    def answer(self,query,history=None,mode='hybrid',page_type=None,use_rerank=True,use_grounding=True):
        start=perf_counter()
        result={'answer':REFUSAL,'citations':[],'refused':True,'referral':None,
                'mode':'generated' if self.router.configured() else 'retrieval-only',
                'trace':{},'latency':0.0,'usage':{'input_tokens':0,'output_tokens':0},'cost_usd':0.0}
        def done():
            result['latency']=(perf_counter()-start)*1000
            return result
        gate=input_gate(query)
        if gate:
            result['reason']=gate['reason'];result['referral']=gate['referral']
            if gate['referral']:result['answer']='Please contact '+gate['referral']['office']+' for advice specific to your circumstances.'
            return done()
        prior=[m['content'] for m in (history or []) if m['role']=='user']
        intent=resolve_query(query,history)
        result['conversation_state']=intent['conversation_state']
        search_query=intent['query']
        if intent.get('action'):
            result.update(refused=False,mode='conversation',reason='conversation_'+intent['action'],
                          answer='You’re welcome. You can start a new question whenever you’re ready.' if intent['action']=='end' else 'Sure. What would you like to ask about?')
            return done()
        if intent['clarification']:
            result['answer']=intent['clarification'];result['reason']='clarification_needed'
            return done()
        if search_query!=query:
            followup_gate=input_gate(search_query)
            if followup_gate:
                result['reason']=followup_gate['reason'];result['referral']=followup_gate['referral']
                if followup_gate['referral']:result['answer']='Please contact '+followup_gate['referral']['office']+' for advice specific to your circumstances.'
                return done()
        if not prior and re.fullmatch(r'\s*(?:how much does it cost|what is the deadline|what are the requirements)[?!.\s]*',query,re.I):
            result['answer']='Please specify the program, student level, or deadline you mean.'
            result['reason']='clarification_needed'
            result['conversation_state']['pending']='context'
            return done()
        scope=intent['scope']
        extra={'program_scope':scope} if scope else {}
        slots=result['conversation_state'].get('slots',{})
        if slots.get('degree') in ('undergraduate','associate'):extra['context_scope']=slots
        retrieval_query=retrieval_question(search_query,scope)
        if scope and scope.get('tuition') and scope.get('format')=='executive':
            level='doctoral' if scope.get('degree')=='phd' else "master's"
            retrieval_query='Executive '+level+' programs tuition rate per credit hour'
        elif scope and scope.get('tuition') and scope.get('format')=='online':
            level='doctoral '+scope['subject'] if scope.get('degree')=='phd' else "master's"
            retrieval_query='Online '+level+' tuition rate per credit hour'
        chunks,trace=self.retriever.retrieve(retrieval_query,mode,page_type,use_rerank,**extra)
        result['trace']=trace
        trace['search_query']=search_query
        trace['retrieval_query']=retrieval_query
        evidence=evidence_gate(chunks,self.config['refusal_threshold'],use_rerank) if use_grounding else chunks
        evidence=[c for c in evidence if audience_matches(c,slots)]
        if scope:
            evidence=[c for c in evidence if program_matches(c,scope)]
            if FEES.search(search_query):
                evidence=[c for c in evidence if (FEES.search(c['text']) or shared_tuition_matches(c,scope))
                    and not re.search(r'career|salary|outcome',' '.join(c.get('heading_path',[])),re.I)]
        if not evidence:
            result['reason']='insufficient_matching_evidence'
            result['answer']="I couldn't find enough relevant information in the saved university sources to answer that question. Please check the official university site."
            if scope and scope.get('tuition'):
                level='PhD' if scope.get('degree')=='phd' else "master's"
                result['answer']='I understand you mean tuition for the '+str(scope.get('format') or '')+' '+level+' in '+scope['subject'].title()+'. I couldn’t verify a matching rate in the saved sources. Please check the official tuition page or contact the Student Financial Center.'
            if scope and not chunks and page_type and trace.get('program_chunk_count',0)>0:
                result['reason']='source_filter_excludes_program'
                result['answer']='The selected source category excludes the matching program information. Set Source category to all, then ask again.'
            return done()
        if result['mode']=='retrieval-only':
            # No synthesized factual answer: only exact, capped evidence excerpts.
            result['answer']='Retrieval-only mode: inspect these source excerpts; no generated answer is available.'
            result['citations']=[{'url':c['source_url'],'title':c['title'],
                 'quote':excerpt(c['text']),'crawled_at':c['crawl_timestamp'],
                 'chunk_id':c['chunk_id']} for c in evidence[:5]]
            result['refused']=False
            result['threshold_status']=self.config.get('threshold_status','UNCALIBRATED')
            return done()
        try:
            prompt=messages(search_query,evidence,history)
            schema=grounded_schema(evidence)
            for attempt in range(2):
                response=self.router.complete(prompt,schema)
                for key,value in response['usage'].items():result['usage'][key]=result['usage'].get(key,0)+value
                cost=response['cost_usd']
                result['cost_usd']=result['cost_usd']+cost if result['cost_usd'] is not None and cost is not None else None
                result['provider']=response['provider'];result['model']=response['model']
                result.setdefault('provider_attempts',[]).extend(response['attempts'])
                payload=expand_quotes(json.loads(response['content']),evidence)
                if payload.get('refused',True):
                    result['reason']='unsupported_by_retrieved_context'
                    result['answer']='I found related university sources, but they don’t support a reliable answer to this question. Please verify it on the official site or with the relevant university office.'
                    return done()
                try:
                    claims=validate_claims(payload['claims'],evidence)
                    break
                except ValueError as exc:
                    # A broad overview can contain independently supported claims.
                    # Omit invalid claims; never relax their citation validation.
                    supported=[]
                    for claim in payload['claims']:
                        try:supported.extend(validate_claims([claim],evidence))
                        except ValueError:pass
                    if supported:
                        result['omitted_unsupported_claims']=len(payload['claims'])-len(supported)
                        claims=supported
                        break
                    if attempt or str(exc) not in ('Citation must quote <=25 exact words from a retrieved chunk','Claim introduces unsupported numbers','Claim introduces unsupported table unit'):raise
                    result['citation_repair_attempts']=1
                    prompt=[*prompt,{'role':'system','content':'The previous output failed citation validation. Every course code, number, and unit must appear in the exact source spans selected for that particular claim. Add the correct source identifiers or remove unsupported details. Generate a fresh answer using SHORT verbatim contiguous quotes copied character-for-character from the same retrieved context, at most 25 words each. Preserve whitespace and punctuation. Do not paraphrase inside quotes. Remove unsupported claims; refuse if no valid evidence supports an answer.'}]
            # Reject excessive verbatim copying even if the model followed citation schema.
            for claim in claims:
                words=claim['text'].split()
                for i in range(max(0,len(words)-25)):
                    phrase=' '.join(words[i:i+26])
                    if any(phrase in c['text'] for c in evidence):raise ValueError('Excessive verbatim quote')
            citations=[];lines=[]
            for claim in claims:
                labels=[]
                for citation in claim['citations']:
                    if citation not in citations:citations.append(citation)
                    labels.append(str(citations.index(citation)+1))
                lines.append(claim['text']+' '+''.join(f'[{label}]' for label in labels))
            result.update(answer='\n\n'.join(lines),citations=citations,refused=False)
            if scope and any(shared_tuition_matches(c,scope) for c in evidence):
                result['answer']+='\n\nThis is the published rate for the tuition category, rather than a separately verified program-specific fee schedule. Verify current rates and any additional fees with the Student Financial Center.'
        except ProviderUnavailable as exc:
            result['reason']='all_configured_providers_unavailable'
            result.setdefault('provider_attempts',[]).extend(exc.attempts)
            result['mode']='retrieval-only (providers unavailable)'
            result['answer']='Generation providers are unavailable. Inspect these source excerpts; no generated answer is available.'
            result['citations']=[{'url':c['source_url'],'title':c['title'],'quote':excerpt(c['text']),
                'crawled_at':c['crawl_timestamp'],'chunk_id':c['chunk_id']} for c in evidence[:5]]
            result['refused']=False
            result['cost_usd']=None
        except Exception as exc:
            result['reason']='generation_or_grounding_error'
            result['error_type']=type(exc).__name__  # never persist exception text that may contain secrets
        return done()


def create_service(config=None,collection='compass'):
    from indexing.embed import Embedder
    from indexing.store import Store
    from retrieval.bm25 import BM25
    from retrieval.dense import Dense
    from retrieval.rerank import Reranker
    from retrieval.trace import Retriever
    config=config or load_config()
    path=ROOT/'data/index'/f'{collection}_manifest.json'
    if not path.exists():raise RuntimeError('Build the index with python -m indexing.rechunk first')
    manifest=json.loads(path.read_text())
    if manifest['model']!=config['embedding_model'] or manifest['revision']!=config['embedding_revision']:
        raise ValueError('Embedding model/revision differs from index')
    if collection=='compass' and manifest['strategy']!=config['strategy']:
        raise ValueError('Index strategy differs from configuration')
    store=Store(ROOT/'data/index',collection)
    chunks=store.all()
    if not chunks:raise ValueError('Index is empty')
    embedder=Embedder(config)
    return AnswerService(Retriever(BM25(chunks),Dense(store,embedder),Reranker(config),config),config)

def answer(query,**kwargs):
    return create_service().answer(query,**kwargs)


def excerpt(text,limit=25):
    words=list(re.finditer(r'\S+',text))
    return text[:words[min(limit,len(words))-1].end()] if words else ''
