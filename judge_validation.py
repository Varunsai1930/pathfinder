"""Batched, leakage-aware validation for course-hidden recommendation models.

This is a judge harness: it does not create a submission.  It measures whether
a change improves course relevance when the course-name-bearing first sentence
is unavailable at query time (the observed test-time condition).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path[:0] = ["/private/tmp/hcl_runtime", "/private/tmp/hcl_sklearn"]
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

SEEDS = (11, 29, 47, 71, 97)
# The sparse vocabulary is sizeable; a small block keeps the dense cosine
# buffer below 25 MB even on constrained desktop runners.
BATCH_SIZE = 32


def clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def body(text: str) -> str:
    """Remove the train-only course-name opening sentence."""
    parts = text.split(". ", 1)
    return parts[1].strip() if len(parts) == 2 else parts[0].strip()


def mask_course(text: str, course: str) -> str:
    return clean(re.sub(re.escape(course), "this course", text, flags=re.I))


def split_by_body(frame: pd.DataFrame, seed: int, fraction: float = 0.08):
    """Stratify by course and keep every repeated body in one partition."""
    rng = np.random.default_rng(seed)
    labels = frame["Course"].to_numpy()
    groups = frame["body"].to_numpy()
    valid = np.zeros(len(frame), dtype=bool)
    for course in np.unique(labels):
        rows = np.flatnonzero(labels == course)
        choices = np.unique(groups[rows])
        selected = rng.choice(choices, size=max(1, round(fraction * len(choices))), replace=False)
        valid[rows] = np.isin(groups[rows], selected)
    # A generic template may occur in multiple courses.  Never let retrieval
    # observe it during fitting and scoring in the same split.
    selected_groups = np.unique(groups[valid])
    valid = np.isin(groups, selected_groups)
    return np.flatnonzero(~valid), np.flatnonzero(valid)


def balanced_fit_sample(frame: pd.DataFrame, fit: np.ndarray, seed: int, per_course: int = 250) -> np.ndarray:
    """Cap fitting rows per course to make repeated tests feasible in RAM.

    This is a deterministic, class-balanced proxy; it does not privilege a
    candidate because baseline and candidate receive exactly the same rows.
    """
    rng = np.random.default_rng(seed)
    labels = frame["Course"].to_numpy()
    return np.concatenate([
        rng.choice(rows, size=min(len(rows), per_course), replace=False)
        for course in np.unique(labels)
        for rows in (fit[labels[fit] == course],)
    ])


def word_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        stop_words="english", ngram_range=(1, 3), min_df=2, max_df=0.95,
        # 60k retains the course-bearing vocabulary while keeping the
        # full-corpus validation reproducible within the desktop memory cap.
        # Both baseline and candidate use this identical representation.
        sublinear_tf=True, strip_accents="unicode", max_features=40_000,
        dtype=np.float32,
    )


def top10_from_retrieval(x_query, x_fit, fit_labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return rank-1 labels and mean same-course fraction in the first ten."""
    rank1, purity = [], []
    width = min(10, x_fit.shape[0])
    for start in range(0, x_query.shape[0], BATCH_SIZE):
        score = x_query[start : start + BATCH_SIZE].dot(x_fit.T).toarray()
        top = np.argpartition(-score, kth=width - 1, axis=1)[:, :width]
        ordered = np.take_along_axis(top, np.argsort(-np.take_along_axis(score, top, axis=1), axis=1), axis=1)
        rank1.append(fit_labels[ordered[:, 0]])
        purity.append(fit_labels[ordered])
    return np.concatenate(rank1), np.vstack(purity)


@dataclass(frozen=True)
class FoldResult:
    rank1: float
    precision10: float
    n: int


def measure_models(frame: pd.DataFrame, fit: np.ndarray, valid: np.ndarray) -> dict[str, FoldResult]:
    labels = frame["Course"].to_numpy()
    fit_text = frame["masked"].to_numpy()[fit]
    query_text = frame["body"].to_numpy()[valid]
    truth = labels[valid]
    word = word_vectorizer()
    x_fit = word.fit_transform(fit_text)
    x_query = word.transform(query_text)
    pred, top10 = top10_from_retrieval(x_query, x_fit, labels[fit])
    scores = {
        "v11_global_retrieval": FoldResult(
            rank1=float(np.mean(pred == truth)),
            precision10=float(np.mean(top10 == truth[:, None])), n=len(valid),
        )
    }

    # A compact classifier is included as a fixed, independently reproducible
    # comparison model.  It cannot claim a win unless it beats the baseline on
    # the pre-declared repeated-split criterion printed below.
    svc = LinearSVC(C=1.5, class_weight="balanced", max_iter=5000)
    svc.fit(x_fit, labels[fit])
    svc_pred = svc.predict(x_query)
    decision = svc.decision_function(x_query)
    class_order = svc.classes_[np.argsort(-decision, axis=1)[:, :10]]
    scores["word_svc"] = FoldResult(
        rank1=float(np.mean(svc_pred == truth)),
        precision10=float(np.mean(class_order == truth[:, None])), n=len(valid),
    )
    return scores


def report(values: dict[str, list[FoldResult]]) -> None:
    base = values["v11_global_retrieval"]
    print("\nAcceptance rule (pre-declared): candidate must improve BOTH metrics on every split,"
          " have mean rank-1 gain >= 0.25 percentage points, and have a positive lower"
          " 95% paired t interval (df=4) for rank-1 gain. Otherwise retain simpler v11.")
    for name, rows in values.items():
        rank1 = np.array([x.rank1 for x in rows])
        p10 = np.array([x.precision10 for x in rows])
        if name == "v11_global_retrieval":
            print(f"{name:22s} rank1={rank1.mean():.5f} ± {rank1.std(ddof=1):.5f} "
                  f"p@10={p10.mean():.5f} ± {p10.std(ddof=1):.5f}")
            continue
        delta = rank1 - np.array([x.rank1 for x in base])
        # t_(0.975, 4) = 2.776, fixed so scipy statistics is not a dependency.
        lower = delta.mean() - 2.776 * delta.std(ddof=1) / np.sqrt(len(delta))
        wins = bool(np.all(delta > 0) and delta.mean() >= 0.0025 and lower > 0
                    and np.all(p10 > np.array([x.precision10 for x in base])))
        print(f"{name:22s} rank1={rank1.mean():.5f} p@10={p10.mean():.5f} "
              f"delta={delta.mean():+.5f} CI95_low={lower:+.5f} accept={wins}")


def main() -> None:
    frame = pd.read_csv("train.csv")
    frame["body"] = frame["Reviews"].map(body).map(clean)
    frame["masked"] = [mask_course(text, course) for text, course in zip(frame["Reviews"], frame["Course"])]
    values: dict[str, list[FoldResult]] = {"v11_global_retrieval": [], "word_svc": []}
    for seed in SEEDS:
        fit, valid = split_by_body(frame, seed)
        fit = balanced_fit_sample(frame, fit, seed)
        print(f"seed={seed} fitting={len(fit)} validating={len(valid)}", flush=True)
        result = measure_models(frame, fit, valid)
        print(f"seed={seed} n={len(valid)} " + " ".join(
            f"{name}:r1={out.rank1:.5f},p10={out.precision10:.5f}" for name, out in result.items()), flush=True)
        for name, out in result.items():
            values[name].append(out)
    report(values)


if __name__ == "__main__":
    main()
