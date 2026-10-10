"""Join complete human grades without querying the model again."""
import argparse
import json
from pathlib import Path

from .metrics import paired_delta, summarize


def apply_grades(rows, grades):
    rows = [dict(row) for row in rows]
    grades = list(grades)
    row_keys = [(r['baseline'], r['item_id']) for r in rows]
    grade_keys = [(g['baseline'], g['item_id']) for g in grades]
    if len(set(row_keys)) != len(row_keys) or len(set(grade_keys)) != len(grade_keys):
        raise ValueError('Duplicate baseline/item in results or grades')
    if set(grade_keys) != set(row_keys):
        raise ValueError('Human grades must cover every result exactly once, with no extras')
    labels = dict(zip(grade_keys, grades))
    for row in rows:
        grade = labels[(row['baseline'], row['item_id'])]
        if grade.get('answer_correct') not in (0, 1) or type(grade.get('answer_correct')) is not int:
            raise ValueError('Every result needs a human answer_correct label of 0 or 1')
        citation = grade.get('citation_valid')
        if citation not in (0, 1, None) or isinstance(citation, bool):
            raise ValueError('citation_valid must be 0, 1, or null')
        if not row['refused'] and citation is None:
            raise ValueError('A non-refusal needs a citation validity label, including 0 for missing citations')
        if row['refused'] and citation is not None:
            raise ValueError('Citation validity is null for a refusal')
        behavior = grade.get('expected_behavior_match')
        if row['category'] == 'ambiguous_adversarial':
            if behavior not in (0, 1) or type(behavior) is not int:
                raise ValueError('Ambiguous/adversarial responses need a human behavior label')
        elif behavior is not None:
            raise ValueError('Behavior match applies only to ambiguous/adversarial items')
        row.update(answer_correct=grade['answer_correct'], citation_valid=citation,
                   expected_behavior_match=behavior, scoring_status='HUMAN_GRADED')
    return rows


def graded_summaries(rows):
    baselines = sorted({r['baseline'] for r in rows})
    summaries = {b: summarize([r for r in rows if r['baseline'] == b]) for b in baselines}
    incorrect = {r['item_id'] for r in rows if r['baseline'] == 'B0' and r['answer_correct'] == 0}
    summaries['B0_incorrect_subset'] = {
        b: summarize([r for r in rows if r['baseline'] == b and r['item_id'] in incorrect])
        for b in baselines}
    b0_subset = {r['item_id']: r['answer_correct'] for r in rows
                 if r['baseline'] == 'B0' and r['item_id'] in incorrect}
    summaries['B0_incorrect_paired_deltas'] = {}
    for baseline in baselines:
        if baseline == 'B0':
            continue
        other = {r['item_id']: r['answer_correct'] for r in rows
                 if r['baseline'] == baseline and r['item_id'] in incorrect}
        if b0_subset and other.keys() == b0_subset.keys():
            ids = sorted(b0_subset)
            summaries['B0_incorrect_paired_deltas']['B0 -> ' + baseline] = paired_delta(
                [b0_subset[i] for i in ids], [other[i] for i in ids])
    progression = ['B2', 'A1_structure_dense', 'A2_structure_hybrid', 'A3_structure_rerank', 'B3']
    pairs = {}
    for before, after in zip(progression, progression[1:]):
        left = {r['item_id']: r['answer_correct'] for r in rows if r['baseline'] == before}
        right = {r['item_id']: r['answer_correct'] for r in rows if r['baseline'] == after}
        if left.keys() == right.keys() and left:
            ids = sorted(left)
            pairs[before + ' -> ' + after] = paired_delta([left[i] for i in ids], [right[i] for i in ids])
    summaries['paired_answer_deltas'] = pairs
    return summaries


def main():
    p = argparse.ArgumentParser()
    p.add_argument('run_dir', type=Path)
    p.add_argument('grades', type=Path)
    args = p.parse_args()
    rows = [json.loads(l) for l in (args.run_dir / 'per_item.jsonl').read_text().splitlines() if l.strip()]
    labels = [json.loads(l) for l in args.grades.read_text().splitlines() if l.strip()]
    graded = apply_grades(rows, labels)
    output = args.run_dir / 'graded_summary.json'
    if output.exists():
        raise SystemExit('Graded summary already exists; refusing overwrite')
    (args.run_dir / 'graded_per_item.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in graded))
    output.write_text(json.dumps(graded_summaries(graded), indent=2) + '\n')
    print('Complete human grades summarized; no model re-run')


if __name__ == '__main__':
    main()
