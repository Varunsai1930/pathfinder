# Judge round 2 — acceptance audit (2026-08-05)

## Verdict

**No replacement is accepted.**  The available local data proves that course
selection is saturated, but it contains no labels for the requested hidden
F1/ranking target.  Therefore a change to the ten returned train indexes
cannot be shown to improve the reported 78.71% score.  Under the stated rule,
the baseline must remain unchanged.

## Reproducible evidence

This command was run with the bundled Python runtime:

```sh
/Users/varun/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 - <<'PY'
import re
import pandas as pd
train = pd.read_csv('train.csv')
test = pd.read_csv('test.csv')
def sentence_two(text):
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return parts[1].lower().strip() if len(parts) > 1 else ''
train_topic = train.Reviews.map(sentence_two)
test_topic = test.Reviews.map(sentence_two)
topic_courses = train.assign(topic=train_topic).groupby('topic').Course.nunique()
print(len(train), len(test), train.Course.nunique())
print(train_topic.nunique(), test_topic.nunique())
print((topic_courses == 1).sum(), len(topic_courses))
print(test_topic.isin(topic_courses.index).sum(), len(test))
PY
```

Observed result:

| Check | Result |
| --- | ---: |
| Training rows / test rows / courses | 109,776 / 10,977 / 80 |
| Distinct second sentences in training / test | 240 / 240 |
| Training second sentences with exactly one course | 240 / 240 |
| Test second sentences seen exactly in training | 10,977 / 10,977 |
| Course-specific topic sentences per course | 3 |

The exact second sentence is thus an allowed, perfect course identifier in
this particular split.  This explains the 1.00000 course rank-1 and P@10
reported by `judge_validation.py`: no course-choice candidate can beat a
perfect score.  It does **not** prove an improvement in the hidden ranking
F1, because the dataset has no relevance labels or target ten-index lists for
test rows.

The stored candidate CSVs confirm why this matters.  Each of
`submission.csv`, `submission_v9.csv`, `submission_v10.csv`,
`mask_candidate.csv`, `mask_clean_candidate.csv`, `trail_submission.csv`, and
`submission_try_1.csv` returns ten distinct indexes from one course on all
10,977 rows.  Yet the rankings are materially different: relative to v10,
the mean ten-index set overlap ranges from 5.3931 (`submission.csv`) to 9.8844
(`mask_clean_candidate.csv`).  Course purity therefore cannot discriminate
between those rerankers; it would be false validation to call any of them a
winner using that proxy.

## Audit of the first judge harness

`judge_validation.py` is useful as a rejection screen, but its printed
paired-t lower bound must not be treated as formal statistical proof: its five
random body-group holdouts overlap, so they are not independent observations.
More importantly, its metrics are course recovery rather than the platform F1.
That distinction is material here because all candidate rerankers share the
same perfect course signal while returning different within-course documents.

The stricter decision rule for a future candidate is therefore:

1. Freeze `solution_v11.py` and record the exact generated baseline
   submission plus platform score.
2. Obtain an independently labelled holdout of the *same target* (ten-index
   relevance lists / F1), or run paired platform submissions under a permitted
   controlled evaluation protocol.
3. Use per-query paired F1 differences on that holdout, with a stratified
   paired bootstrap confidence interval.  Accept only if the 95% lower bound
   is above zero and the mean gain clears a predeclared practical threshold.
4. If candidates are statistically indistinguishable, retain the simpler
   baseline as required.

Until step 2 is available, an alternate TF-IDF setting, blend, or reranker
can only be an unvalidated change.  It is rejected rather than written as a
new baseline submission.
