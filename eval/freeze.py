"""Freeze verified evidence and reproducible runtime state before a final test."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from generation.settings import ROOT, load_config


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def code_hash(root=ROOT):
    paths = []
    for folder in ('crawler', 'indexing', 'retrieval', 'generation', 'app', 'eval'):
        paths.extend((Path(root) / folder).glob('*.py'))
    return digest([(str(p.relative_to(root)), sha(p)) for p in sorted(paths)])


def require_verified(items):
    items = list(items)
    if not items:
        raise ValueError('No verified items supplied')
    for item in items:
        if item.get('status') != 'VERIFIED':
            raise ValueError('Every item must be human VERIFIED before graded evaluation')
        if item.get('category') in ('unanswerable', 'ambiguous_adversarial'):
            if item.get('expected_behavior') not in ('refuse', 'refer', 'clarify'):
                raise ValueError('Label expected behavior')
        elif not item.get('gold_answer') or not item.get('evidence'):
            raise ValueError('Answerable item lacks verified gold/evidence')
    return items


def load_golden(root=ROOT):
    return [json.loads(line) for line in (Path(root) / 'eval/golden_set.jsonl').read_text().splitlines() if line.strip()]


def validate_split(items, root=ROOT):
    manifest = json.loads((Path(root) / 'eval/split_manifest.json').read_text())
    assignments = manifest['assignments']
    ids = [item['id'] for item in items]
    if len(ids) != 40 or len(set(ids)) != 40 or set(assignments) != set(ids):
        raise ValueError('Golden set and split must contain exactly the same 40 unique IDs')
    if sum(s == 'dev' for s in assignments.values()) != 24 or sum(s == 'test' for s in assignments.values()) != 16:
        raise ValueError('Expected immutable 24/16 dev/test split')
    if set(assignments.values()) != {'dev', 'test'}:
        raise ValueError('Unknown split assignment')
    return assignments


def _chunks(config, root, strategy):
    from indexing.chunking import load_chunks
    return load_chunks(Path(root) / config['processed_dir'], strategy,
                       version=config['chunk_version'], size=config['chunk_size'],
                       overlap=config['chunk_overlap'])


def index_snapshot(config, root=ROOT):
    """Hash expected chunks and actual stored documents, metadata, and vectors."""
    from indexing.store import Store
    result = {}
    for name, strategy in (('compass_fixed', 'fixed'), ('compass', 'structure')):
        manifest_path = Path(root) / 'data/index' / (name + '_manifest.json')
        if not manifest_path.exists():
            raise ValueError('Both real index manifests are required')
        manifest = json.loads(manifest_path.read_text())
        if (manifest.get('collection'), manifest.get('strategy'), manifest.get('model'), manifest.get('revision')) != (
                name, strategy, config['embedding_model'], config['embedding_revision']):
            raise ValueError('Index manifest model, revision, collection, or strategy mismatch')
        expected = _chunks(config, root, strategy)
        if not expected:
            raise ValueError('Index has no expected chunks')
        expected_by_id = {c['chunk_id']: c for c in expected}
        if len(expected_by_id) != len(expected):
            raise ValueError('Duplicate deterministic chunk IDs')
        store = Store(Path(root) / 'data/index', name)
        actual = store.collection.get(include=['documents', 'metadatas', 'embeddings'])
        ids = actual['ids']
        if len(ids) != len(expected_by_id) or set(ids) != set(expected_by_id):
            raise ValueError('Stored index differs from deterministic chunks')
        records = []
        for cid, text, meta, vector in zip(ids, actual['documents'], actual['metadatas'], actual['embeddings']):
            expected_chunk = expected_by_id[cid]
            if text != expected_chunk['text'] or meta.get('content_hash') != expected_chunk['content_hash']:
                raise ValueError('Stored index text differs from deterministic chunks')
            records.append((cid, text, meta, [float(x) for x in vector]))
        result[name] = {'manifest_hash': sha(manifest_path),
                        'chunks_hash': digest(sorted(expected, key=lambda c: c['chunk_id'])),
                        'index_data_hash': digest(sorted(records, key=lambda r: r[0])),
                        'count': len(records)}
    return result


def snapshot(config, root=ROOT):
    root = Path(root)
    processed = root / config['processed_dir']
    files = sorted(processed.glob('*.json'))
    if not files:
        raise ValueError('Normalized corpus is missing')
    return {'code_hash': code_hash(root),
            'golden_hash': sha(root / 'eval/golden_set.jsonl'),
            'split_hash': sha(root / 'eval/split_manifest.json'),
            'processed_hash': digest([(p.name, sha(p)) for p in files]),
            'model_revisions': {'embedding': config['embedding_revision'],
                                'reranker': config['reranker_revision'],
                                'llm_provider': config['llm_provider'],
                                'llm': config['provider_models'][config['llm_provider']]},
            'indexes': index_snapshot(config, root)}


def require_eval_provider(config):
    provider = config.get('llm_provider')
    models = config.get('provider_models') or {}
    if provider not in ('groq', 'openai', 'gemini') or not models.get(provider):
        raise ValueError('Graded evaluation requires one explicit provider and model; auto is forbidden')
    return provider


def check_calibration(config, root=ROOT):
    if config.get('threshold_status') != 'CALIBRATED_ON_DEV':
        raise ValueError('Refusal threshold must be calibrated on verified dev evidence')
    record = config.get('calibration') or {}
    path = Path(root) / 'eval/calibration_dev.json'
    if not path.exists() or record.get('artifact_sha256') != sha(path):
        raise ValueError('Calibration artifact is missing or changed')
    artifact = json.loads(path.read_text())
    if artifact.get('selected_threshold') != config.get('refusal_threshold') or artifact.get('criterion') != 'balanced_accuracy':
        raise ValueError('Calibration threshold or criterion mismatch')
    if not artifact.get('records') or not artifact.get('criterion_records'):
        raise ValueError('Calibration evidence and criterion records required')
    items = {i['id']: i for i in load_golden(root)}
    assignment = validate_split(list(items.values()), root)
    dev_gold_hash = digest(sorted(
        (item for item in items.values() if assignment[item['id']] == 'dev'),
        key=lambda item: item['id']))
    if (artifact.get('dev_gold_hash') != dev_gold_hash or
            artifact.get('split_hash') != sha(Path(root) / 'eval/split_manifest.json') or
            artifact.get('reranker_model') != config.get('reranker_model') or
            artifact.get('reranker_revision') != config.get('reranker_revision')):
        raise ValueError('Calibration dev gold, split, or reranker changed')
    for row in artifact['records']:
        if row['item_id'] not in items or assignment[row['item_id']] != 'dev' or items[row['item_id']]['status'] != 'VERIFIED':
            raise ValueError('Calibration includes an unverified or test item')
    from .calibrate import calibrate
    recalculated = calibrate(artifact['records'], list(items.values()), assignment)
    for key in ('selected_threshold', 'selected_record', 'criterion_records', 'records', 'dev_item_ids'):
        if artifact.get(key) != recalculated[key]:
            raise ValueError('Calibration criterion records do not match labelled evidence')
    return artifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/shared_config.yaml')
    args = parser.parse_args()
    import yaml
    config = load_config(args.config)
    config.pop('_root', None)
    require_eval_provider(config)
    target = ROOT / 'config/frozen_config.yaml'
    if target.exists():
        raise SystemExit('Frozen configuration already exists; refusing overwrite')
    items = require_verified(load_golden())
    validate_split(items)
    check_calibration(config)
    if not re.fullmatch(r'[0-9a-f]{40}', str(config.get('reranker_revision', ''))):
        raise SystemExit('Pin a resolved 40-character reranker commit before freezing')
    config['freeze'] = snapshot(config)
    with target.open('x') as handle:
        yaml.safe_dump(config, handle, sort_keys=True)
    print('Frozen config written; test has NOT been run')


if __name__ == '__main__':
    main()
