"""Score the "Ask about my work" page on questions it should answer and should refuse.

    python evals/run_ask_eval.py tune     # sweep settings on the tuning questions
    python evals/run_ask_eval.py test     # score the held-out questions; writes evals/ask_results.md

Tuning uses the dev questions and the test questions from rounds 1 and 2. Those were each
scored once and then retired, because reading their misses made them unusable as a test.
The bar for round 3 was set before any of its questions were scored: at least 17 of 20
answered and at least 8 of 10 refused. A hit means a right source is among those shown.
The check at the start stops the run if a "should refuse" topic is in the write-ups,
because that would make its label wrong.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ask_my_work import MIN_ANCHOR_IDF, MIN_COSINE, MIN_COVERAGE, Index, Meaning, answer  # noqa: E402

REFUSALS = {"decline", "personal", "blocked", "empty"}
BAR_ANSWERED, BAR_REFUSED = 17, 8
MUST_BE_ABSENT = {
    "D21": "kubernetes", "D26": r"\brust\b", "D27": "quantum", "T21": "terraform", "T24": "tableau",
    "T28": "medical imaging", "T30": "cobol", "V21": r"\b(angular|react)\b", "V25": r"\b(sap|erp)\b",
    "V26": r"\bjava\b|microservice", "V28": "chili", "V29": "golf", "V30": "salesforce",
    "W21": "ruby", "W24": "charlotte", "W25": "blockchain", "W26": "restaurant", "W27": "circuit board", "W30": "panthers",
}


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float, float]:
    if not total:
        return 0.0, 0.0
    p, denominator = successes / total, 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def score(rows: list[dict], index: Index, meaning: Meaning | None, min_cosine: float = MIN_COSINE) -> list[dict]:
    results = []
    for row in rows:
        reply = answer(row["question"], index, meaning=meaning, min_cosine=min_cosine)
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

    index = Index(passages)
    meaning = Meaning(ROOT / "ask_model.npz", passages)
    if mode == "tune":
        rows = [row for row in questions if row["split"] in ("dev", "round1", "round2")]
        keyword = score(rows, index, None)
        print(f"words only: answered {tally(keyword, 'answer')}, refused {tally(keyword, 'decline')}")
        print("min cosine  answered  refused  sum")
        for cosine in (0.25, 0.3, 0.325, 0.35, 0.375, 0.4, 0.425, 0.45, 0.5, 0.55, 0.6):
            current = score(rows, index, meaning, cosine)
            answered, refused = tally(current, "answer"), tally(current, "decline")
            print(f"   {cosine:.3f}     {answered[0]:2d}/{answered[1]}    {refused[0]:2d}/{refused[1]}   {answered[0] + refused[0]}")
        current = score(rows, index, meaning)
        print(f"\nchosen {MIN_COSINE}: answered {tally(current, 'answer')}, refused {tally(current, 'decline')}")
        for row in current:
            if not row["correct"]:
                print(f"  MISS {row['id']} [{row['kind']}] {row['question']} -> {row['keys']}")
        return

    rows = [row for row in questions if row["split"] == "test"]
    current, baseline = score(rows, index, meaning), score(rows, index, None)
    every = list(range(len(rows)))
    only_meaning, only_words, p_value = mcnemar(
        [current[i]["correct"] for i in every], [baseline[i]["correct"] for i in every]
    )
    ans, ref, top = tally(current, "answer"), tally(current, "decline"), tally(current, "answer", "top1")
    base_ans, base_ref = tally(baseline, "answer"), tally(baseline, "decline")
    passed = ans[0] >= BAR_ANSWERED and ref[0] >= BAR_REFUSED
    print("answered:", percent(ans), "\ntop source:", percent(top), "\nrefused:", percent(ref))
    print("words only: answered", base_ans, "refused", base_ref)
    print("BAR", "PASSED" if passed else "NOT MET", f"(needed {BAR_ANSWERED}/20 answered and {BAR_REFUSED}/10 refused)")
    for row in current:
        if not row["correct"]:
            print(f"  MISS {row['id']} [{row['kind']}] {row['question']} -> {row['keys']}")
    print(f"meaning vs words: {only_meaning} vs {only_words}, McNemar p = {p_value:.3f}")
    misses = "\n".join(
        f"- `{row['id']}` {row['question']} (returned {row['kind']}: {', '.join(row['keys']) or 'nothing'})"
        for row in current if not row["correct"]
    ) or "- None"
    few = "With so few disagreements this can't show much either way.\n" if only_meaning + only_words < 6 else ""
    report = f"""# "Ask about my work": test results

## Round 3 (matching on words and meaning)

{len(rows)} new questions, scored once with every setting already frozen. The bar was set before scoring: at least
{BAR_ANSWERED} of 20 answered and at least {BAR_REFUSED} of 10 refused. **Result: {"met" if passed else "not met"}.**

| Check | Result |
|---|---|
| Should answer: a right source is shown | {percent(ans)} |
| Should answer: the first source shown is right | {percent(top)} |
| Should refuse: it refused | {percent(ref)} |

**Limits.** The questions were written by the same author as the page, so they are not independent of it. With 30
questions the intervals are wide, and a real visitor's phrasing may be harder.

## Does the meaning model earn its place?

**Why this test.** The model adds about 6 MB to the repo, so it should do measurably better than matching words alone.
Both versions answer the same 30 questions, which makes the outcomes paired, and McNemar's test uses only the questions
where the two disagree.

**What it says.** With the model: answered {percent(ans)}, refused {percent(ref)}. Words only: answered {percent(base_ans)},
refused {percent(base_ref)}. Across all 30, only the model version was right on {only_meaning}, only the words version was
right on {only_words}, exact McNemar p = {p_value:.3f}. {few}
**Assumption check.** McNemar needs paired outcomes on independent questions. The pairing holds by design. Independence
is approximate, since several questions touch the same project. The exact binomial form is used because the number of
disagreements is small, which is where the chi-square approximation breaks down.

## Earlier rounds, kept for the record

| Round | What changed | Answered | Refused |
|---|---|---:|---:|
| 1 | Word matching | 15/20 | 10/10 |
| 2 | New, more natural questions; stricter settings | 13/20 | 8/10 |

Each round used new questions, and once a round's misses had been read, its questions moved to the tuning set.

## Misses in round 3

{misses}
"""
    (ROOT / "evals" / "ask_results.md").write_bytes(report.encode("utf-8"))
    print("wrote evals/ask_results.md")


if __name__ == "__main__":
    main()
