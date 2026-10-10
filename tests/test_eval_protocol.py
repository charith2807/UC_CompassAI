"""Protocol checks use synthetic records only; no held-out questions are run."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.calibrate import calibrate
from eval.freeze import check_calibration, digest, index_snapshot, require_verified, sha
from eval.grade import apply_grades
from eval.metrics import ranking_metrics
from eval.run_eval import require_generated_response, score_row
from eval.test_guard import assert_unused, finish, require_full_test, reserve


class ProtocolTests(unittest.TestCase):
    def test_one_test_receipt_survives_failure_and_rejects_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'test_receipt.json'
            require_full_test(['B3', 'B0', 'B2', 'B1'])
            reserve(receipt, {'config_hash': 'mock', 'baselines': ['B0', 'B1', 'B2', 'B3']})
            with self.assertRaises(FileExistsError):
                reserve(receipt, {'config_hash': 'other'})
            finish(receipt, 'FAILED', completed_rows=1)
            self.assertEqual(json.loads(receipt.read_text())['status'], 'FAILED')
            with self.assertRaises(FileExistsError):
                assert_unused(receipt)
            with self.assertRaises(ValueError):
                require_full_test(['B1', 'B2', 'B3'])
            with self.assertRaises(ValueError):
                require_full_test(['B0', 'B1', 'B2', 'B2'])

    def test_draft_gold_and_test_calibration_rejected(self):
        with self.assertRaises(ValueError):
            require_verified([{'id': 'a', 'status': 'DRAFT_NEEDS_HUMAN_VERIFICATION'}])
        items = [{'id': 'dev', 'status': 'VERIFIED'}, {'id': 'test', 'status': 'VERIFIED'}]
        assignments = {'dev': 'dev', 'test': 'test'}
        records = [{'item_id': 'dev', 'chunk_id': 'a', 'rerank_logit': 2,
                    'evidence_sufficient': 1},
                   {'item_id': 'test', 'chunk_id': 'b', 'rerank_logit': -2,
                    'evidence_sufficient': 0}]
        with self.assertRaises(ValueError):
            calibrate(records, items, assignments)
        records[1]['item_id'] = 'dev'
        result = calibrate(records, items, assignments)
        self.assertEqual(result['criterion'], 'balanced_accuracy')
        self.assertEqual(len(result['criterion_records']), 4)
        self.assertEqual(result['selected_record']['balanced_accuracy'], 1)

    def test_freeze_recomputes_calibration_criterion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'eval').mkdir()
            items = [{'id': f'mock{i:02}', 'status': 'VERIFIED'} for i in range(40)]
            assignments = {item['id']: ('dev' if i < 24 else 'test')
                           for i, item in enumerate(items)}
            (root / 'eval/golden_set.jsonl').write_text(''.join(json.dumps(i) + '\n' for i in items))
            (root / 'eval/split_manifest.json').write_text(json.dumps({'assignments': assignments}))
            records = [{'item_id': 'mock00', 'chunk_id': 'a', 'rerank_logit': 1,
                        'evidence_sufficient': 1},
                       {'item_id': 'mock01', 'chunk_id': 'b', 'rerank_logit': -1,
                        'evidence_sufficient': 0}]
            artifact = calibrate(records, items, assignments)
            artifact.update(reranker_model='reranker', reranker_revision='a' * 40,
                            dev_gold_hash=digest(items[:24]),
                            split_hash=sha(root / 'eval/split_manifest.json'))
            path = root / 'eval/calibration_dev.json'
            path.write_text(json.dumps(artifact))
            config = {'threshold_status': 'CALIBRATED_ON_DEV',
                      'refusal_threshold': artifact['selected_threshold'],
                      'reranker_model': 'reranker', 'reranker_revision': 'a' * 40,
                      'calibration': {'artifact_sha256': sha(path)}}
            check_calibration(config, root)
            artifact['criterion_records'][0]['balanced_accuracy'] = 0.123
            path.write_text(json.dumps(artifact))
            config['calibration']['artifact_sha256'] = sha(path)
            with self.assertRaisesRegex(ValueError, 'criterion records'):
                check_calibration(config, root)

    def test_index_snapshot_detects_stored_text_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data/index').mkdir(parents=True)
            chunks = []
            for name, strategy in (('compass_fixed', 'fixed'), ('compass', 'structure')):
                (root / 'data/index' / (name + '_manifest.json')).write_text(json.dumps({
                    'collection': name, 'strategy': strategy, 'model': 'model', 'revision': 'revision'}))
                chunks.append({'chunk_id': strategy, 'text': 'real', 'content_hash': 'hash'})
            config = {'embedding_model': 'model', 'embedding_revision': 'revision',
                      'processed_dir': 'data/processed', 'chunk_version': 'v1',
                      'chunk_size': 10, 'chunk_overlap': 2}
            class Collection:
                def get(self, include):
                    return {'ids': ['fixed'] if self.strategy == 'fixed' else ['structure'],
                            'documents': ['mutated'], 'metadatas': [{'content_hash': 'hash'}],
                            'embeddings': [[0.1]]}
            class Store:
                def __init__(self, directory, name):
                    self.collection = Collection()
                    self.collection.strategy = 'fixed' if name == 'compass_fixed' else 'structure'
            with patch('indexing.store.Store', Store), patch('eval.freeze._chunks', side_effect=lambda c, r, s: [
                    {'chunk_id': s, 'text': 'real', 'content_hash': 'hash'}]):
                with self.assertRaisesRegex(ValueError, 'text differs'):
                    index_snapshot(config, root)

    def test_index_snapshot_hash_changes_with_vector(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data/index').mkdir(parents=True)
            for name, strategy in (('compass_fixed', 'fixed'), ('compass', 'structure')):
                (root / 'data/index' / (name + '_manifest.json')).write_text(json.dumps({
                    'collection': name, 'strategy': strategy, 'model': 'model', 'revision': 'revision'}))
            vector = [0.1]
            class Collection:
                def __init__(self, strategy):
                    self.strategy = strategy
                def get(self, include):
                    return {'ids': [self.strategy], 'documents': ['real'],
                            'metadatas': [{'content_hash': 'hash'}], 'embeddings': [vector]}
            class Store:
                def __init__(self, directory, name):
                    self.collection = Collection('fixed' if name == 'compass_fixed' else 'structure')
            config = {'embedding_model': 'model', 'embedding_revision': 'revision',
                      'processed_dir': 'data/processed', 'chunk_version': 'v1',
                      'chunk_size': 10, 'chunk_overlap': 2}
            with patch('indexing.store.Store', Store), patch('eval.freeze._chunks', side_effect=lambda c, r, s: [
                    {'chunk_id': s, 'text': 'real', 'content_hash': 'hash'}]):
                before = index_snapshot(config, root)
                vector[0] = 0.2
                after = index_snapshot(config, root)
            self.assertNotEqual(before['compass']['index_data_hash'], after['compass']['index_data_hash'])

    def test_rerank_order_and_missing_chunk_coverage(self):
        item = {'id': 'mock', 'category': 'single_hop', 'evidence': [
            {'source_url': 'https://example.org', 'evidence_quote': 'fragmented phrase'}]}
        first = {'chunk_id': 'a', 'source_url': 'https://example.org', 'text': 'fragmented',
                 'rerank_score': 0.1}
        second = {'chunk_id': 'b', 'source_url': 'https://example.org', 'text': 'other',
                  'rerank_score': 0.9}
        result = {'answer': 'mock', 'citations': [], 'refused': False, 'latency': 1,
                  'trace': {'candidates': [first, second], 'selected': [second, first]}}
        row = score_row(item, 'B3', result, [first, second])
        self.assertEqual(row['recall@20'], 0)
        self.assertEqual(row['candidate_pool_recall@20'], 0)
        self.assertEqual(row['evidence_coverage@5'], 0)
        self.assertEqual(row['evidence_chunk_match_count'], 0)
        self.assertIsNone(ranking_metrics([], [], answerable=False)['recall@5'])
        second['text'] = 'fragmented phrase'
        row = score_row(item, 'B3', result, [first, second])
        self.assertEqual(row['mrr'], 1)
        self.assertEqual(row['candidate_pool_recall@20'], 1)

    def test_complete_human_grades_required(self):
        row = {'baseline': 'B0', 'item_id': 'mock', 'category': 'single_hop',
               'refused': False, 'answer_correct': None, 'citation_valid': None}
        with self.assertRaises(ValueError):
            apply_grades([row], [])
        with self.assertRaises(ValueError):
            apply_grades([row], [{'baseline': 'B0', 'item_id': 'mock',
                                  'answer_correct': 1, 'citation_valid': None}])
        graded = apply_grades([row], [{'baseline': 'B0', 'item_id': 'mock',
                                       'answer_correct': 0, 'citation_valid': 0}])
        self.assertEqual(graded[0]['scoring_status'], 'HUMAN_GRADED')

    def test_provider_outage_cannot_be_scored_as_refusal(self):
        with self.assertRaisesRegex(RuntimeError, 'provider unavailable'):
            require_generated_response({'mode': 'retrieval-only (providers unavailable)',
                                        'reason': 'all_configured_providers_unavailable',
                                        'refused': True})
        with self.assertRaisesRegex(RuntimeError, 'provider unavailable'):
            require_generated_response({'mode': 'generated',
                                        'reason': 'all_configured_providers_unavailable',
                                        'refused': True})
        require_generated_response({'mode': 'generated',
                                    'reason': 'generation_or_grounding_error',
                                    'refused': True})


if __name__ == '__main__':
    unittest.main()
