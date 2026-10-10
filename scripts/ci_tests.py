"""Run only stage tests whose dependencies have merged; never claim omitted stages pass."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHECKS={
 'test_ingestion_monitoring.py':['crawler/config.py'],
 'test_normalization.py':['crawler/normalize.py'],
 'test_chunking.py':['indexing/chunking.py','crawler/normalize.py'],
 'test_embed.py':['indexing/embed.py'],
 'test_store_integration.py':['indexing/store.py','indexing/chunking.py'],
 'test_retrieval.py':['retrieval/hybrid.py','retrieval/rerank.py'],
 'test_program_scope.py':['retrieval/query.py','retrieval/trace.py'],
 'test_conversation.py':['retrieval/conversation.py','generation/answer.py'],
 'test_pipeline.py':['generation/answer.py','retrieval/hybrid.py','eval/freeze.py'],
 'test_ui.py':['app/streamlit_app.py'],
 'test_providers.py':['generation/providers.py','generation/answer.py'],
 'test_eval_protocol.py':['eval/calibrate.py','eval/test_guard.py','eval/run_eval.py'],
 'test_refusal.py':['generation/answer.py'],
 'test_injection.py':['generation/prompt.py'],
}

def main():
    count=0
    for test,dependencies in CHECKS.items():
        if not (ROOT/'tests'/test).exists():continue
        if not all((ROOT/p).exists() for p in dependencies):
            print('Deferred until dependent PR merges:',test,flush=True);continue
        subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',test,'-v'],cwd=ROOT,check=True)
        count+=1
    if not count:raise SystemExit('No tests were eligible')
if __name__=='__main__':main()
