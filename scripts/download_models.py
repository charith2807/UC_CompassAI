"""Run once in a network-enabled terminal; caches only the two fixed-stack models."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('HF_HOME',str(ROOT/'.cache/huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET','1')
from generation.settings import load_config

def main():
    from huggingface_hub import snapshot_download
    config=load_config()
    for kind in ('embedding','reranker'):
        path=snapshot_download(repo_id=config[kind+'_model'],revision=config[kind+'_revision'],
             allow_patterns=['*.json','*.txt','*.safetensors','*.model'])
        print(kind,'cached snapshot:',Path(path).name)
    print('Model downloads complete. The application can now run with HF_HUB_OFFLINE=1.')
if __name__=='__main__':main()
