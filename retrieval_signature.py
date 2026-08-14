"""Compare sparse-retrieval signatures against a scored reference submission."""

import ast
import gc
import sys

import numpy as np
import pandas as pd

# Keeps the workspace clean: scikit-learn is installed in a temporary directory.
sys.path.insert(0, "/private/tmp/hcl_sklearn")
from sklearn.feature_extraction.text import TfidfVectorizer


VARIANTS = {
    "v7_reproduction": dict(ngram_range=(1, 3), min_df=2, max_df=0.95, sublinear_tf=True),
    "unigram_sublinear": dict(ngram_range=(1, 1), min_df=2, max_df=0.95, sublinear_tf=True),
    "bigram_sublinear": dict(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=True),
    "trigram_raw_tf": dict(ngram_range=(1, 3), min_df=2, max_df=0.95, sublinear_tf=False),
    "bigram_raw_tf": dict(ngram_range=(1, 2), min_df=2, max_df=0.95, sublinear_tf=False),
    "unigram_raw_tf": dict(ngram_range=(1, 1), min_df=2, max_df=0.95, sublinear_tf=False),
    "fourgram_sublinear": dict(ngram_range=(1, 4), min_df=2, max_df=0.95, sublinear_tf=True),
}


def clean(text):
    return " ".join(text.lower().split())


def compare(predicted, reference):
    sets = [len(set(a) & set(b)) for a, b in zip(predicted, reference)]
    positions = [sum(x == y for x, y in zip(a, b)) for a, b in zip(predicted, reference)]
    reciprocal = []
    for predicted_row, reference_row in zip(predicted, reference):
        rank = {value: pos for pos, value in enumerate(predicted_row)}
        reciprocal.append(sum(1 / (1 + rank.get(value, 99)) for value in reference_row) / 10)
    return float(np.mean(sets)), float(np.mean(positions)), float(np.mean(reciprocal))


def main():
    train = pd.read_csv("train.csv")
    test = pd.read_csv("test.csv")
    reference = pd.read_csv("/Users/varun/Downloads/submission_v8.csv")
    ref_lists = reference["Index_list"].map(ast.literal_eval).tolist()
    course_by_index = train.set_index("Index")["Course"]
    inferred_course = [course_by_index.loc[values[0]] for values in ref_lists]
    train_positions = {
        course: np.flatnonzero(train["Course"].to_numpy() == course)
        for course in train["Course"].unique()
    }
    groups = {}
    for row, course in enumerate(inferred_course):
        groups.setdefault(course, []).append(row)

    train_text = train["Reviews"].map(clean)
    test_text = test["Reviews"].map(clean)
    for name, params in VARIANTS.items():
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            max_features=200_000,
            strip_accents="unicode",
            **params,
        )
        x_train = vectorizer.fit_transform(train_text)
        x_test = vectorizer.transform(test_text)
        predicted = [None] * len(test)
        for course, rows in groups.items():
            candidates = train_positions[course]
            similarity = x_test[rows].dot(x_train[candidates].T).toarray()
            ranks = np.argsort(-similarity, axis=1)[:, :10]
            ids = train["Index"].to_numpy()[candidates[ranks]]
            for local_row, row in enumerate(rows):
                predicted[row] = ids[local_row].astype(int).tolist()
        mean_set, mean_position, mean_reciprocal = compare(predicted, ref_lists)
        print(name, {"vocabulary": x_train.shape[1], "set": round(mean_set, 4), "position": round(mean_position, 4), "rr": round(mean_reciprocal, 6)})
        del vectorizer, x_train, x_test, predicted
        gc.collect()


if __name__ == "__main__":
    main()
