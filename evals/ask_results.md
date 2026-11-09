# "Ask about my work": test results

## Decision: a list of checked questions, not a search box

The bar for shipping free typing was set before round 3: at least 17 of 20 answered and at least 8 of 10 refused. It
scored 14 and 9. A wrong answer about my own work is worse than a shorter list, so the page now offers a fixed set of
questions whose sources I read. The code for these rounds, including the evaluation script, is in commit `e211217`.

## Round 3 (matching on words and meaning)

30 new questions, scored once with every setting already frozen. The bar was set before scoring: at least
17 of 20 answered and at least 8 of 10 refused. **Result: not met.**

| Check | Result |
|---|---|
| Should answer: a right source is shown | 14/20 (70%; 95% interval 48% to 85%) |
| Should answer: the first source shown is right | 13/20 (65%; 95% interval 43% to 82%) |
| Should refuse: it refused | 9/10 (90%; 95% interval 60% to 98%) |

**Limits.** The questions were written by the same author as the page, so they are not independent of it. With 30
questions the intervals are wide, and a real visitor's phrasing may be harder.

## Does the meaning model earn its place?

**Why this test.** The model adds about 6 MB to the repo, so it should do measurably better than matching words alone.
Both versions answer the same 30 questions, which makes the outcomes paired, and McNemar's test uses only the questions
where the two disagree.

**What it says.** With the model: answered 14/20 (70%; 95% interval 48% to 85%), refused 9/10 (90%; 95% interval 60% to 98%). Words only: answered 7/20 (35%; 95% interval 18% to 57%),
refused 9/10 (90%; 95% interval 60% to 98%). Across all 30, only the model version was right on 7, only the words version was
right on 0, exact McNemar p = 0.016. 
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

- `W03` Tell me about a time his work made the company money (returned quotes: michelin-rag)
- `W06` Has he dealt with imbalanced classification? (returned decline: nothing)
- `W08` Has he worked at a large financial firm? (returned decline: nothing)
- `W12` Anything with named entity recognition? (returned decline: nothing)
- `W16` Has he deployed anything on Azure? (returned decline: nothing)
- `W18` How was the customer churn model explained to stakeholders? (returned decline: nothing)
- `W24` What's the weather in Charlotte? (returned quotes: park-crowd-forecast, grid-stress-simulator)
