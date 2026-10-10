"""Calibrate the rerank sigmoid evidence gate from human-labelled dev records."""
import argparse
import json
import math
from pathlib import Path

import yaml
from generation.settings import ROOT, load_config
from .freeze import digest, load_golden, sha, validate_split


def calibrate(records, items, assignments):
    records = list(records)
    if not records:
        raise ValueError('Calibration needs manually labelled dev evidence records')
    by_id = {item['id']: item for item in items}
    if len(by_id) != len(items):
        raise ValueError('Duplicate golden IDs')
    seen = set()
    normalized = []
    for row in records:
        key = (row.get('item_id'), row.get('chunk_id'))
        if key in seen or not all(isinstance(part, str) and part for part in key):
            raise ValueError('Each item/chunk evidence record must be unique')
        seen.add(key)
        if key[0] not in by_id or assignments.get(key[0]) != 'dev' or by_id[key[0]].get('status') != 'VERIFIED':
            raise ValueError('Calibration may use verified dev records only')
        if type(row.get('evidence_sufficient')) is not int or row['evidence_sufficient'] not in (0, 1):
            raise ValueError('Human evidence_sufficient must be 0 or 1')
        logit = row.get('rerank_logit')
        if isinstance(logit, bool) or not isinstance(logit, (int, float)) or not math.isfinite(logit):
            raise ValueError('Finite rerank logit required')
        score = 1 / (1 + math.exp(-max(-60, min(60, logit))))
        normalized.append({'item_id': key[0], 'chunk_id': key[1],
                           'rerank_logit': float(logit), 'rerank_score': score,
                           'evidence_sufficient': row['evidence_sufficient']})
    if set(r['evidence_sufficient'] for r in normalized) != {0, 1}:
        raise ValueError('Both sufficient and insufficient evidence labels required')
    normalized.sort(key=lambda r: (r['item_id'], r['chunk_id']))
    scores = sorted({r['rerank_score'] for r in normalized})
    thresholds = [0.0] + scores + [math.nextafter(scores[-1], 1.0)]
    criteria = []
    for threshold in thresholds:
        tp = sum(r['evidence_sufficient'] == 1 and r['rerank_score'] >= threshold for r in normalized)
        tn = sum(r['evidence_sufficient'] == 0 and r['rerank_score'] < threshold for r in normalized)
        positive = sum(r['evidence_sufficient'] for r in normalized)
        negative = len(normalized) - positive
        criteria.append({'threshold': threshold, 'true_positive': tp, 'true_negative': tn,
                         'positive_count': positive, 'negative_count': negative,
                         'balanced_accuracy': (tp / positive + tn / negative) / 2})
    # On a tie, choose the higher threshold to avoid admitting unsupported evidence.
    best = max(criteria, key=lambda r: (r['balanced_accuracy'], r['threshold']))
    return {'criterion': 'balanced_accuracy', 'selection_rule': 'maximum balanced accuracy; higher threshold on tie',
            'selected_threshold': best['threshold'], 'selected_record': best,
            'records': normalized, 'criterion_records': criteria,
            'dev_item_ids': sorted({r['item_id'] for r in normalized})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('human_labels', type=Path, help='JSONL: item_id, chunk_id, rerank_logit, evidence_sufficient')
    parser.add_argument('--config', default='config/shared_config.yaml')
    args = parser.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    items = load_golden()
    assignments = validate_split(items)
    labels = [json.loads(line) for line in args.human_labels.read_text().splitlines() if line.strip()]
    artifact = calibrate(labels, items, assignments)
    artifact['reranker_model'] = config['reranker_model']
    artifact['reranker_revision'] = config['reranker_revision']
    artifact['dev_gold_hash'] = digest(sorted(
        (item for item in items if assignments[item['id']] == 'dev'),
        key=lambda item: item['id']))
    artifact['split_hash'] = sha(ROOT / 'eval/split_manifest.json')
    output = ROOT / 'eval/calibration_dev.json'
    if output.exists():
        raise SystemExit('Calibration artifact already exists; refusing overwrite')
    if config.get('threshold_status') == 'CALIBRATED_ON_DEV':
        raise SystemExit('Configuration already calibrated; refusing overwrite')
    output.write_text(json.dumps(artifact, indent=2) + '\n')
    settings = yaml.safe_load(config_path.read_text())
    settings['refusal_threshold'] = artifact['selected_threshold']
    settings['threshold_status'] = 'CALIBRATED_ON_DEV'
    settings['calibration'] = {'artifact_sha256': sha(output), 'criterion': 'balanced_accuracy',
                               'record_count': len(artifact['records']),
                               'dev_item_ids': artifact['dev_item_ids']}
    config_path.write_text(yaml.safe_dump(settings, sort_keys=False))
    print('Calibrated verified dev evidence:', len(artifact['records']), 'records')


if __name__ == '__main__':
    main()
