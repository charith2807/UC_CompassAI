"""Retrieval and human-grade summaries with deterministic bootstrap intervals."""
import math
import random


def ranking_metrics(ranked_ids, relevant_ids, answerable=True):
    relevant = set(relevant_ids)
    if not relevant:
        value = 0.0 if answerable else None
        return {'recall@5': value, 'recall@20': value, 'mrr': value, 'ndcg@10': value}
    ranked = list(dict.fromkeys(ranked_ids))
    def recall(k):
        return len(set(ranked[:k]) & relevant) / len(relevant)
    rank = next((i for i, cid in enumerate(ranked, 1) if cid in relevant), None)
    dcg = sum(1 / math.log2(i + 2) for i, cid in enumerate(ranked[:10]) if cid in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(10, len(relevant))))
    return {'recall@5': recall(5), 'recall@20': recall(20),
            'mrr': 1 / rank if rank else 0.0, 'ndcg@10': dcg / ideal if ideal else 0.0}


def bootstrap(values, iterations=2000, seed=633):
    values = [v for v in values if v is not None]
    if not values:
        return {'mean': None, 'ci95': None, 'n': 0}
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in values) / n for _ in range(iterations))
    return {'mean': sum(values) / n,
            'ci95': [means[int(.025 * iterations)], means[min(iterations - 1, int(.975 * iterations))]], 'n': n}


def paired_delta(before, after):
    if len(before) != len(after):
        raise ValueError('Paired arrays must have equal lengths')
    return bootstrap([b - a for a, b in zip(before, after)])


def percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def summarize(rows):
    keys = ['recall@5', 'recall@20', 'candidate_pool_recall@20', 'mrr', 'ndcg@10',
            'evidence_coverage@5', 'evidence_coverage@20', 'answer_correct',
            'citation_valid', 'correct_refusal', 'over_refusal',
            'expected_behavior_match', 'cost_usd']
    summary = {key: bootstrap([r.get(key) for r in rows]) for key in keys}
    times = [r['latency_ms'] for r in rows]
    summary['latency_ms'] = {'p50': percentile(times, .5), 'p95': percentile(times, .95),
                             'mean_ci95': bootstrap(times)}
    summary['overall_refusal_rate'] = bootstrap([int(r['refused']) for r in rows])
    summary['evidence_chunk_match'] = {
        'matched': sum(r.get('evidence_chunk_match_count', 0) for r in rows),
        'gold_units': sum(r.get('gold_evidence_count', 0) for r in rows)}
    return summary
