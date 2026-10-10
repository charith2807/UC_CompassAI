"""Run verified baselines; held-out test is reserved once before any question."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from generation.settings import ROOT, load_config
from .baselines import BaselineRunner, VARIANTS
from .freeze import (check_calibration, load_golden, require_eval_provider,
                     require_verified, sha, snapshot, validate_split)
from .metrics import ranking_metrics, summarize
from .test_guard import assert_unused, finish, require_full_test, reserve


def require_generated_response(result):
    """An unavailable provider is a failed run, never an evaluated refusal."""
    if (str(result.get('mode', '')).startswith('retrieval-only') or
            result.get('reason') == 'all_configured_providers_unavailable'):
        raise RuntimeError('Generation provider unavailable during graded evaluation')


def score_row(item, name, result, chunks):
    trace = result.get('trace', {})
    candidates = trace.get('candidates', [])
    reranked = name in ('A3_structure_rerank', 'B3')
    ranked = sorted(candidates, key=lambda c: (-c['rerank_score'], c['chunk_id'])) if reranked else candidates
    evidence = item.get('evidence', [])
    relevant = [c['chunk_id'] for c in chunks if any(
        e['source_url'] == c['source_url'] and e['evidence_quote'] in c['text'] for e in evidence)]
    answerable = item['category'] not in ('unanswerable', 'ambiguous_adversarial')
    metric = ranking_metrics([c['chunk_id'] for c in ranked], relevant, answerable=answerable)
    pool_metric = ranking_metrics([c['chunk_id'] for c in candidates], relevant, answerable=answerable)
    if name == 'B0':
        metric = {key: None for key in metric}
        pool_metric = {key: None for key in pool_metric}
    coverage = {}
    for k in (5, 20):
        coverage[f'evidence_coverage@{k}'] = (
            sum(any(e['source_url'] == c['source_url'] and e['evidence_quote'] in c['text']
                    for c in ranked[:k]) for e in evidence) / len(evidence)
            if evidence and name != 'B0' else (0.0 if answerable and name != 'B0' else None))
    citations = result.get('citations', [])
    allowed = {c['source_url'] for c in trace.get('selected', [])}
    category = item['category']
    return {'item_id': item['id'], 'baseline': name, 'category': category,
            **metric, 'candidate_pool_recall@20': pool_metric['recall@20'],
            **coverage, 'answer': result['answer'], 'citations': citations,
            'refused': result['refused'], 'latency_ms': result['latency'],
            'cost_usd': result.get('cost_usd'), 'answer_correct': None,
            'citation_valid': None, 'expected_behavior_match': None,
            'citation_url_integrity': bool(citations) and all(c['url'] in allowed for c in citations),
            'correct_refusal': int(result['refused']) if category == 'unanswerable' and
                item.get('expected_behavior') == 'refuse' else None,
            'over_refusal': int(result['refused']) if answerable else None,
            'expected_behavior': item.get('expected_behavior'),
            'relevant_chunk_count': len(relevant), 'gold_evidence_count': len(evidence),
            'evidence_chunk_match_count': sum(any(e['source_url'] == c['source_url'] and
                 e['evidence_quote'] in c['text'] for c in chunks) for e in evidence),
            'trace': trace, 'scoring_status': 'NEEDS_HUMAN_ANSWER_AND_CITATION_GRADING'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=['dev', 'test'], default='dev')
    parser.add_argument('--baselines', nargs='+', default=['B0', 'B1', 'B2', 'B3'])
    parser.add_argument('--config', default=None)
    args = parser.parse_args()
    if len(args.baselines) != len(set(args.baselines)) or any(
            name not in set(VARIANTS) | {'B0'} for name in args.baselines):
        raise SystemExit('Unknown or duplicate baseline')
    receipt_path = ROOT / 'eval/test_run_receipt.json'
    if args.split == 'test':
        require_full_test(args.baselines)
        assert_unused(receipt_path)
    items = load_golden()
    assignments = validate_split(items)
    selected = require_verified([item for item in items if assignments[item['id']] == args.split])
    config_path = Path(args.config) if args.config else ROOT / (
        'config/frozen_config.yaml' if args.split == 'test' else 'config/shared_config.yaml')
    config = load_config(config_path)
    provider = require_eval_provider(config)
    from generation.providers import provider_key_available
    key_name = {'groq': 'GROQ_API_KEY', 'openai': 'OPENAI_API_KEY',
                'gemini': 'GEMINI_API_KEY'}[provider]
    if not provider_key_available(config):
        raise SystemExit('Answer evaluation requires ' + key_name)
    if args.split == 'test':
        if config_path.resolve() != (ROOT / 'config/frozen_config.yaml').resolve():
            raise SystemExit('Test requires frozen config')
        require_verified(items)
        check_calibration(config)
        if config.get('freeze') != snapshot(config):
            raise SystemExit('Code, gold, split, corpus, chunks, model, or index changed after freeze')
    from indexing.chunking import load_chunks
    corpora = {
        strategy: load_chunks(ROOT / config['processed_dir'], strategy,
                              version=config['chunk_version'], size=config['chunk_size'],
                              overlap=config['chunk_overlap'])
        for strategy in ('fixed', 'structure')}
    # Construct all runners before reservation; no selected question is evaluated here.
    runners = {name: BaselineRunner(name, config) for name in args.baselines}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = ROOT / 'data/runtime' / f'{args.split}_{stamp}'
    if args.split == 'test':
        reserve(receipt_path, {'started_at': stamp, 'config_hash': sha(config_path),
                               'baselines': args.baselines, 'output': str(output.relative_to(ROOT))})
    rows = []
    try:
        output.mkdir(parents=True, exist_ok=False)
        for name, runner in runners.items():
            chunks = corpora['fixed' if name in ('B1', 'B2') else 'structure']
            for item in selected:
                result = runner.answer(item['question'])
                require_generated_response(result)
                row = score_row(item, name, result, chunks)
                rows.append(row)
                with (output / 'per_item.jsonl').open('a') as handle:
                    handle.write(json.dumps(row) + '\n')
        summary = {name: summarize([r for r in rows if r['baseline'] == name]) for name in runners}
        (output / 'summary.json').write_text(json.dumps(summary, indent=2))
        (output / 'run_metadata.json').write_text(json.dumps({
            'timestamp': stamp, 'split': args.split, 'config_hash': sha(config_path),
            'golden_hash': sha(ROOT / 'eval/golden_set.jsonl'), 'baselines': args.baselines}, indent=2))
    except BaseException as exc:
        if args.split == 'test':
            finish(receipt_path, 'FAILED', completed_rows=len(rows), error_type=type(exc).__name__)
        raise
    if args.split == 'test':
        finish(receipt_path, 'COMPLETED', completed_rows=len(rows))
    print('Raw results:', output, 'Human grading still required')


if __name__ == '__main__':
    main()
