"""Leakage-aware local validation for course-masked retrieval candidates.

The public training reviews contain the course name; held-out queries have that
token replaced with ``this course`` to reproduce the test-time observation.
Metrics are course agreement of the nearest retrieval result and the mean
fraction of same-course rows in the first ten results.
"""

from __future__ import annotations

import gc
import re
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedShuffleSplit


def clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def mask(review: str, course: str) -> str:
    return clean(re.sub(re.escape(course), "this course", review, flags=re.I))


def drop_opening(text: str) -> str:
    parts = text.split(". ", 1)
    return parts[1] if len(parts) == 2 else text


def topic_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[1] if len(parts) > 1 else text


def validate(name: str, corpus: np.ndarray, labels: np.ndarray, seed: int) -> tuple[float, float]:
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.10, random_state=seed)
    fit, query = next(splitter.split(corpus, labels))
    vec = TfidfVectorizer(
        lowercase=False, stop_words="english", ngram_range=(1, 3),
        min_df=2, max_df=0.95, sublinear_tf=True, strip_accents="unicode",
        max_features=200_000, dtype=np.float32,
    )
    x_fit = vec.fit_transform(corpus[fit])
    x_query = vec.transform(corpus[query])
    nearest = np.empty((len(query), 10), dtype=np.int32)
    for start in range(0, len(query), 128):
        scores = x_query[start:start + 128].dot(x_fit.T).toarray()
        nearest[start:start + len(scores)] = np.argpartition(-scores, 9, axis=1)[:, :10]
        row = np.arange(len(scores))[:, None]
        nearest[start:start + len(scores)] = nearest[start:start + len(scores)][row, np.argsort(-scores[row, nearest[start:start + len(scores)]], axis=1)]
    retrieved = labels[fit][nearest]
    top1 = float(np.mean(retrieved[:, 0] == labels[query]))
    purity10 = float(np.mean(retrieved == labels[query, None]))
    print(f"{name} seed={seed} vocab={x_fit.shape[1]} top1={top1:.5f} purity10={purity10:.5f}", flush=True)
    del vec, x_fit, x_query, nearest, retrieved
    gc.collect()
    return top1, purity10


def main() -> None:
    train = pd.read_csv("train.csv")
    labels = train["Course"].to_numpy()
    masked = np.asarray([mask(r, c) for r, c in zip(train.Reviews, labels)])
    representations = {
        "full_masked": masked,
        "without_opening": np.asarray([drop_opening(x) for x in masked]),
        "topic_sentence_only": np.asarray([topic_sentence(x) for x in masked]),
    }
    seeds = tuple(map(int, sys.argv[1].split(","))) if len(sys.argv) > 1 else (17, 41, 73)
    selected = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set(representations)
    for seed in seeds:
        for name, corpus in representations.items():
            if name in selected:
                validate(name, corpus, labels, seed)


if __name__ == "__main__":
    main()
