"""Shared settings, resolved relative to the repository rather than cwd."""
from pathlib import Path
import os
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('HF_HOME', str(ROOT / '.cache/huggingface'))

def load_config(path=None):
    import yaml
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    path = Path(path) if path else ROOT / 'config/shared_config.yaml'
    config = yaml.safe_load(path.read_text())
    config['_root'] = str(ROOT)
    return config
