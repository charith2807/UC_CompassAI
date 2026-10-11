"""Paired statistics for "is config B really better than config A?"

On ~20-35 items a few points of accuracy is noise, so every improvement claim gets:
  - a 95% bootstrap confidence interval on the accuracy difference (resample items
    with replacement 10,000 times; the CI is the 2.5th-97.5th percentile), and
  - McNemar's exact test on the paired pass/fail table: only items where the two
    configs disagree carry information (b = A pass/B fail, c = A fail/B pass);
    p = two-sided binomial probability of a split this lopsided if both were equal.
Also reports B's accuracy on the B0-incorrect subset: items the bare LLM already
knew don't measure retrieval.

Reads:  eval/results/{config}.{split}.jsonl
Run:    python -m eval.compare B2 B3 --split test
        python -m eval.compare --chain B2 A1-structure A2-hybrid A3-rerank A4-expand B3 --split dev
"""
import argparse
import json
import random
from math import comb

from eval.run_eval import RESULTS


def load(config: str, split: str) -> dict[str, float]:
    """Per-item pass/fail on answer correctness (answerable and unanswerable items alike)."""
    rows = [json.loads(line) for line in open(RESULTS / f"{config}.{split}.jsonl")]
    return {r["id"]: r["scores"]["correct"] for r in rows if "correct" in r["scores"]}


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def bootstrap_ci(diffs: list[float], reps: int = 10_000, seed: int = 633) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(diffs, k=len(diffs))) / len(diffs) for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def compare(a: str, b: str, split: str) -> dict:
    A, B = load(a, split), load(b, split)
    ids = sorted(set(A) & set(B))
    diffs = [B[i] - A[i] for i in ids]
    b_only = sum(1 for i in ids if A[i] and not B[i])
    c_only = sum(1 for i in ids if B[i] and not A[i])
    lo, hi = bootstrap_ci(diffs)
    out = {"A": a, "B": b, "n": len(ids), "acc_A": sum(A[i] for i in ids) / len(ids),
           "acc_B": sum(B[i] for i in ids) / len(ids), "diff": sum(diffs) / len(ids),
           "ci95": (lo, hi), "A_only": b_only, "B_only": c_only, "mcnemar_p": mcnemar_exact(b_only, c_only)}
    try:
        B0 = load("B0", split)
        sub = [i for i in ids if i in B0 and not B0[i]]
        out["B_on_B0_incorrect"] = (sum(B[i] for i in sub) / len(sub), len(sub)) if sub else None
    except FileNotFoundError:
        out["B_on_B0_incorrect"] = None
    return out


def show(r: dict) -> str:
    sig = "significant" if r["mcnemar_p"] < 0.05 and not (r["ci95"][0] <= 0 <= r["ci95"][1]) else "not significant"
    b0 = f" | {r['B']} on B0-incorrect: {r['B_on_B0_incorrect'][0]:.2f} (n={r['B_on_B0_incorrect'][1]})" if r["B_on_B0_incorrect"] else ""
    return (f"{r['A']:>13} -> {r['B']:<13} n={r['n']:<3} {r['acc_A']:.2f} -> {r['acc_B']:.2f}  "
            f"diff {r['diff']:+.2f} [95% CI {r['ci95'][0]:+.2f}, {r['ci95'][1]:+.2f}]  "
            f"discordant {r['A_only']}/{r['B_only']}  McNemar p={r['mcnemar_p']:.3f}  ({sig}){b0}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("configs", nargs="*")
    parser.add_argument("--chain", nargs="+", help="compare each config with the previous one")
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()
    pairs = list(zip(args.chain, args.chain[1:])) if args.chain else [tuple(args.configs)]
    for a, b in pairs:
        print(show(compare(a, b, args.split)))
