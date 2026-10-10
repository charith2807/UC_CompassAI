"""Prepare both local indexes from the private corpus, without re-crawling."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    if not any((ROOT / 'data/processed').glob('*.json')):
        raise SystemExit('Obtain the private corpus handoff in data/processed first. Do not commit it.')
    env = dict(os.environ)
    env.pop('HF_HUB_OFFLINE', None)
    subprocess.run([sys.executable, 'scripts/download_models.py'], cwd=ROOT, env=env, check=True)
    env['HF_HUB_OFFLINE'] = '1'
    for arguments in [
        ['-m', 'crawler.normalize'],
        ['-m', 'indexing.chunking'],
        ['-m', 'indexing.rechunk', '--strategy', 'fixed', '--collection', 'compass_fixed'],
        ['-m', 'indexing.rechunk', '--strategy', 'structure', '--collection', 'compass'],
        ['scripts/smoke.py'],
    ]:
        subprocess.run([sys.executable, *arguments], cwd=ROOT, env=env, check=True)
    print('Ready: .venv/bin/python -m streamlit run app/streamlit_app.py')

if __name__ == '__main__':
    main()
