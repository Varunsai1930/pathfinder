# Improvement gate — 2026-08-05

## Baseline

`/Users/varun/Downloads/solution_v11.py` is the retained baseline.  Its
reported hidden-test score is **78.71%**.  That score cannot be recomputed
locally because test-course labels and the platform's exact F1 evaluator are
not in the dataset.

## Changes investigated

| Candidate | Reason | Measured result | Decision |
| --- | --- | --- | --- |
| Masked word TF-IDF + linear classifier | Recover course before retrieving; tune the v8/v10 course choice. | A deterministic 20,000-row balanced fit agreed with `submission_v10.csv` on **10,977 / 10,977** test course choices.  It also got **7,432 / 7,432** independently verifiable exact-body test rows correct. | Rejected: no different prediction to validate as an improvement. |
| Body-only character TF-IDF + linear classifier | Make matching robust to wording and punctuation variation. | A separately trained 4,960-row balanced character model again agreed with `submission_v10.csv` on **10,977 / 10,977** test course choices, including the exact-body subset. | Rejected: adds complexity without a measurable change. |
| Global retrieval versus classifier proxy | Test whether selecting a class, rather than v11's global nearest neighbour, increases relevance. | In the judge's leakage-aware first split (seed 11; 20,000 balanced fit rows; 8,812 body-disjoint validation rows), global retrieval had rank-1=1.00000 and P@10=1.00000. The class-only comparator had rank-1=1.00000, so it cannot clear the improvement threshold. | Rejected by the Judge. |

## Judge rule

`judge_validation.py` pre-declares the acceptance rule: a candidate must
improve rank-1 and P@10 in every one of five body-disjoint splits, gain at
least 0.25 percentage points in mean rank-1, and have a positive paired 95%
lower confidence bound.  A tie keeps the simpler v11 implementation.

## Submission-template audit

`sample_submission.csv` is a schema example, not labelled supervision: its
five ten-item lists each span 7–9 unrelated courses and do not match the
review topic. It must not be used to select features or claim a local F1 gain.

## Reproduction

The environment needs scikit-learn in `/private/tmp/hcl_sklearn`.

```sh
/Users/varun/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -u judge_validation.py
```

The harness uses bounded cosine batches and a deterministic 250-row-per-course
fit sample so the comparisons fit in the desktop runtime.  It is intentionally
a proxy: it cannot certify a higher hidden F1 without a held-out labelled test
set or an allowed platform submission.

## Outcome

No `solution_v12.py` or submission file was created.  Producing one would
violate the requested acceptance rule because none of the candidates has
demonstrated a statistically better result than the 78.71% baseline.
