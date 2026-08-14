"""Repeatable, title-masked validation for retrieval candidates.

This measures *course recovery*, the only supervised signal present in
``train.csv``.  It deliberately masks the title in both the fit and validation
documents, exactly as it is absent in the competition test set.  The reported
retrieval precision@10 is therefore a proxy, not a claim about the hidden
leaderboard metric.

Run with the temporary runtime used during investigation:
PYTHONPATH=/private/tmp/hcl_runtime python3 ml_engineer_validation.py
"""

from __future__ import annotations

import re
import time

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC


SEEDS = (17, 41, 83)
TEST_SIZE = 0.10


def clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def masked(review: str, course: str) -> str:
    return clean(re.sub(re.escape(course), "this course", review, flags=re.I))


def vectorizer() -> TfidfVectorizer:
    # Same sparse word space as v11, so this is a controlled comparison.
    return TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 3),
        max_features=200_000,
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
        strip_accents="unicode",
        dtype=np.float32,
    )


def global_retrieval_metrics(x_fit, x_valid, y_fit, y_valid) -> tuple[float, float]:
    """Metrics for solution_v11's ungated nearest-neighbor behavior."""
    correct_top1 = 0
    correct_at_10 = 0
    for start in range(0, x_valid.shape[0], 128):
        scores = x_valid[start : start + 128].dot(x_fit.T).toarray()
        ranks = np.argpartition(-scores, 10, axis=1)[:, :10]
        rows = np.arange(ranks.shape[0])[:, None]
        ranks = ranks[rows, np.argsort(-scores[rows, ranks], axis=1)]
        labels = y_fit[ranks]
        expected = y_valid[start : start + len(ranks), None]
        correct_top1 += int((labels[:, 0] == expected[:, 0]).sum())
        correct_at_10 += int((labels == expected).sum())
    n = len(y_valid)
    return correct_top1 / n, correct_at_10 / (10 * n)


def main() -> None:
    start = time.monotonic()
    train = pd.read_csv("train.csv")
    print(f"loaded rows={len(train)}", flush=True)
    labels = train["Course"].to_numpy()
    text = np.array([masked(review, course) for review, course in zip(train.Reviews, labels)])
    print("masked titles", flush=True)
    all_indices = np.arange(len(train))
    summary: dict[str, list[float]] = {
        "v11_global_top1": [],
        "v11_global_p10": [],
        "svc_c1_top1": [],
        "svc_c15_top1": [],
        "svc_c2_top1": [],
        "svc_c15_top5": [],
    }

    for seed in SEEDS:
        fit, valid = train_test_split(
            all_indices, test_size=TEST_SIZE, random_state=seed, stratify=labels
        )
        vec = vectorizer()
        x_fit = vec.fit_transform(text[fit])
        x_valid = vec.transform(text[valid])
        print(f"seed={seed} vectorized vocab={x_fit.shape[1]}", flush=True)
        top1, p10 = global_retrieval_metrics(x_fit, x_valid, labels[fit], labels[valid])
        print(f"seed={seed} global evaluated", flush=True)
        summary["v11_global_top1"].append(top1)
        summary["v11_global_p10"].append(p10)

        # Narrow C sweep around the workspace's existing C=1.0/1.5 models.
        models = {}
        for name, c in (("svc_c1_top1", 1.0), ("svc_c15_top1", 1.5), ("svc_c2_top1", 2.0)):
            model = LinearSVC(C=c, class_weight="balanced", max_iter=5_000)
            model.fit(x_fit, labels[fit])
            scores = model.decision_function(x_valid)
            summary[name].append(float((model.classes_[scores.argmax(axis=1)] == labels[valid]).mean()))
            models[c] = (model, scores)
        model, scores = models[1.5]
        top5 = model.classes_[np.argpartition(-scores, 5, axis=1)[:, :5]]
        summary["svc_c15_top5"].append(float(np.mean(np.any(top5 == labels[valid, None], axis=1))))
        print(
            f"seed={seed} vocab={x_fit.shape[1]} "
            + " ".join(f"{key}={summary[key][-1]:.5f}" for key in summary),
            flush=True,
        )

    print("\nRepeated stratified holdout summary (mean ± sample SD)")
    for name, values in summary.items():
        print(f"{name:20s} {np.mean(values):.5f} ± {np.std(values, ddof=1):.5f}  {values}")
    print(f"elapsed_seconds={time.monotonic() - start:.1f}")


if __name__ == "__main__":
    main()
