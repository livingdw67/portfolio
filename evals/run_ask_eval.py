"""Score the "Ask about my work" page on questions it should answer and should refuse.

    python evals/run_ask_eval.py tune     # sweep settings on the tuning questions
    python evals/run_ask_eval.py test     # score the held-out questions; writes evals/ask_results.md

Tuning uses the dev questions and the round 1 test questions. Round 1's were scored once
and then retired, because reading their misses made them unusable as a test. A hit means a
right source is among the sources shown. The check at the start stops the run if a "should
refuse" topic turns out to be in the write-ups, because that would make its label wrong.
"""
from __future__ import annotations

import itertools
import json
import math
import re
import sys
from pathlib import Path

from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ask_my_work import MIN_ANCHOR_IDF, MIN_COVERAGE, Index, answer  # noqa: E402

REFUSALS = {"decline", "personal", "blocked", "empty"}
MUST_BE_ABSENT = {
    "D21": "kubernetes", "D26": r"\brust\b", "D27": "quantum", "T21": "terraform", "T24": "tableau",
    "T28": "medical imaging", "T30": "cobol", "V21": r"\b(angular|react)\b", "V25": r"\b(sap|erp)\b",
    "V26": r"\bjava\b|microservice", "V28": "chili", "V29": "golf", "V30": "salesforce",
}


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float, float]:
    if not total:
        return 0.0, 0.0
    p, denominator = successes / total, 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def score(rows: list[dict], index: Index, min_coverage: float, min_anchor: float) -> list[dict]:
    results = []
    for row in rows:
        reply = answer(row["question"], index, min_coverage=min_coverage, min_anchor=min_anchor)
        if row["type"] == "decline":
            correct = top1 = reply.kind in REFUSALS
        else:
            shown = reply.keys[:3] if reply.kind == "quotes" else reply.keys
            correct = reply.kind in ("quotes", "listing") and bool(set(shown) & set(row["gold"]))
            top1 = bool(reply.keys) and reply.keys[0] in row["gold"]
        results.append({**row, "kind": reply.kind, "keys": reply.keys[:3], "correct": correct, "top1": top1})
    return results


def tally(results: list[dict], kind: str, field: str = "correct") -> tuple[int, int]:
    subset = [row for row in results if row["type"] == kind]
    return sum(row[field] for row in subset), len(subset)


def mcnemar(first: list[bool], second: list[bool]) -> tuple[int, int, float]:
    only_first = sum(a and not b for a, b in zip(first, second))
    only_second = sum(b and not a for a, b in zip(first, second))
    if only_first + only_second == 0:
        return only_first, only_second, 1.0
    return only_first, only_second, float(binomtest(only_first, only_first + only_second, 0.5).pvalue)


def percent(pair: tuple[int, int]) -> str:
    low, high = wilson(*pair)
    return f"{pair[0]}/{pair[1]} ({pair[0] / pair[1]:.0%}; 95% interval {low:.0%} to {high:.0%})"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "tune"
    passages = json.loads((ROOT / "ask_corpus.json").read_text(encoding="utf-8"))["passages"]
    corpus_text = " ".join(f"{p['source']} {p['section']} {p['text']}" for p in passages).lower()
    questions = [json.loads(line) for line in (ROOT / "evals" / "ask_questions.jsonl").read_text(encoding="utf-8").splitlines()]
    for question_id, pattern in MUST_BE_ABSENT.items():
        if re.search(pattern, corpus_text):
            sys.exit(f"{question_id}: '{pattern}' appears in the write-ups, so 'should refuse' is the wrong label")

    full, plain = Index(passages), Index(passages, normalize=False)
    if mode == "tune":
        rows = [row for row in questions if row["split"] in ("dev", "round1")]
        print("coverage anchor  answered   refused   wrong-source")
        for coverage, anchor in itertools.product((0.4, 0.5, 0.55, 0.6, 0.7), (0.5, 1.0, 1.5, 2.0, 2.5)):
            current = score(rows, full, coverage, anchor)
            answered, refused = tally(current, "answer"), tally(current, "decline")
            print(f"  {coverage:.2f}   {anchor:.1f}    {answered[0]:2d}/{answered[1]}     {refused[0]:2d}/{refused[1]}")
        current = score(rows, full, MIN_COVERAGE, MIN_ANCHOR_IDF)
        print(f"\nchosen {MIN_COVERAGE}/{MIN_ANCHOR_IDF}: answered {tally(current, 'answer')}, refused {tally(current, 'decline')}")
        for row in current:
            if not row["correct"]:
                print(f"  MISS {row['id']} [{row['kind']}] {row['question']} -> {row['keys']}")
        return

    rows = [row for row in questions if row["split"] == "test"]
    current = score(rows, full, MIN_COVERAGE, MIN_ANCHOR_IDF)
    baseline = score(rows, plain, MIN_COVERAGE, MIN_ANCHOR_IDF)
    answerable = [i for i, row in enumerate(rows) if row["type"] == "answer"]
    only_full, only_base, p_value = mcnemar(
        [current[i]["correct"] for i in answerable], [baseline[i]["correct"] for i in answerable]
    )
    ans, ref, top = tally(current, "answer"), tally(current, "decline"), tally(current, "answer", "top1")
    base = tally(baseline, "answer")
    print("answered:", percent(ans), "\ntop source:", percent(top), "\nrefused:", percent(ref))
    for row in current:
        if not row["correct"]:
            print(f"  MISS {row['id']} [{row['kind']}] {row['question']} -> {row['keys']}")
    print(f"normalized vs plain: {only_full} vs {only_base}, McNemar p = {p_value:.3f}")
    misses = "\n".join(
        f"- `{row['id']}` {row['question']} (returned {row['kind']}: {', '.join(row['keys']) or 'nothing'})"
        for row in current if not row["correct"]
    ) or "- None"
    few = "With so few disagreements this can't show much either way.\n" if only_full + only_base < 6 else ""
    report = f"""# "Ask about my work": test results

## Round 2 (current version)

{len(rows)} new questions, scored once with every setting already frozen.

| Check | Result |
|---|---|
| Should answer: a right source is shown | {percent(ans)} |
| Should answer: the first source shown is right | {percent(top)} |
| Should refuse: it refused | {percent(ref)} |

**Limits.** The questions were written by the same author as the page, after seeing round 1's misses, so they are not
independent of it. With 30 questions the intervals are wide. A real visitor's phrasing will be harder than this.

## Round 1, kept for the record

The first version scored 20/20 on its tuning questions and then **15/20 (75%) answered and 10/10 refused** on held-out
questions. All five misses were wrong refusals: a word the write-ups never use, such as "comfortable", counted heavily
against the match. Those questions then joined the tuning set, so they don't count toward round 2.

## Do word normalization and synonyms help?

**Why this test.** Normalization (forecast/forecasting, LLM/GenAI) is extra code that has to earn its place, and two
percentages on 20 questions can't separate a real gain from luck. Both versions answer the same questions, so the paired
test is McNemar's, which looks only at the questions where the two disagree.

**What it says.** With normalization {percent(ans)}; without it {percent(base)}. Only the normalized version got
{only_full} right, only the plain version got {only_base}, exact McNemar p = {p_value:.3f}. {few}
**Assumption check.** McNemar needs paired outcomes on independent questions. The pairing holds by design. Independence
is approximate, since several questions touch the same project. The exact binomial form is used because the number of
disagreements is small, which is where the chi-square approximation breaks down.

## Misses in round 2

{misses}
"""
    (ROOT / "evals" / "ask_results.md").write_bytes(report.encode("utf-8"))
    print("wrote evals/ask_results.md")


if __name__ == "__main__":
    main()
