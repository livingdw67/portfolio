# "Ask about my work": test results

## Round 2 (current version)

30 new questions, scored once with every setting already frozen.

| Check | Result |
|---|---|
| Should answer: a right source is shown | 13/20 (65%; 95% interval 43% to 82%) |
| Should answer: the first source shown is right | 13/20 (65%; 95% interval 43% to 82%) |
| Should refuse: it refused | 8/10 (80%; 95% interval 49% to 94%) |

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

**What it says.** With normalization 13/20 (65%; 95% interval 43% to 82%); without it 13/20 (65%; 95% interval 43% to 82%). Only the normalized version got
1 right, only the plain version got 1, exact McNemar p = 1.000. With so few disagreements this can't show much either way.

**Assumption check.** McNemar needs paired outcomes on independent questions. The pairing holds by design. Independence
is approximate, since several questions touch the same project. The exact binomial form is used because the number of
disagreements is small, which is where the chi-square approximation breaks down.

## Misses in round 2

- `V01` Does he have hands-on experience shipping LLM agents to production? (returned decline: nothing)
- `V03` Any background in time series forecasting? (returned decline: nothing)
- `V04` How does he handle model monitoring in production? (returned decline: nothing)
- `V07` What's the biggest business impact he's delivered? (returned decline: nothing)
- `V12` Has he worked in financial services? (returned decline: nothing)
- `V16` How did he evaluate text-to-SQL accuracy? (returned decline: nothing)
- `V17` Is there a live demo of the jet engine app? (returned decline: nothing)
- `V22` What's his notice period? (returned quotes: park-crowd-forecast, cmapss-predictive-maintenance)
- `V29` Does he play golf? (returned quotes: cmapss-predictive-maintenance)
