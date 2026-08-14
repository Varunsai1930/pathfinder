"""High-capacity TF-IDF/SVM learning-path recommender.

Requires: pandas, numpy, scikit-learn
Reads: train.csv, test.csv
Writes: trail_submission.csv
"""

import re
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC


def clean_text(text):
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    train = pd.read_csv("train.csv")
    test = pd.read_csv("test.csv")
    train_text = train["Reviews"].map(clean_text)
    test_text = test["Reviews"].map(clean_text)

    # Word trigrams retain technical phrases such as API names, algorithms,
    # cloud services, and frameworks that distinguish the learning paths.
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 3),
        max_features=200_000,
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
        strip_accents="unicode",
    )
    train_matrix = vectorizer.fit_transform(train_text)
    test_matrix = vectorizer.transform(test_text)

    classifier = LinearSVC(class_weight="balanced", C=1.0, max_iter=3000)
    classifier.fit(train_matrix, train["Course"])
    class_scores = classifier.decision_function(test_matrix)
    classes = classifier.classes_
    top_courses = classes[np.argsort(-class_scores, axis=1)[:, :5]]

    train_positions_by_course = {
        course: np.flatnonzero(train["Course"].to_numpy() == course)
        for course in train["Course"].unique()
    }
    grouped_rows = defaultdict(list)
    for row, courses in enumerate(top_courses):
        grouped_rows[tuple(sorted(courses))].append(row)

    recommendations = [None] * len(test)
    train_ids = train["Index"].to_numpy()
    for courses, rows in grouped_rows.items():
        candidate_positions = np.unique(np.concatenate([
            train_positions_by_course[course] for course in courses
        ]))
        similarities = test_matrix[rows].dot(train_matrix[candidate_positions].T).toarray()
        top_positions = np.argsort(-similarities, axis=1)[:, :10]
        for local_row, test_row in enumerate(rows):
            recommendations[test_row] = train_ids[candidate_positions[top_positions[local_row]]].tolist()

    output = pd.DataFrame({
        "Index": test["Index"].astype(int),
        "Index_list": [str(ids) for ids in recommendations],
    })
    if output.shape != (len(test), 2) or not output["Index"].equals(test["Index"].astype(int)):
        raise RuntimeError("Invalid output schema")
    output.to_csv("trail_submission.csv", index=False)
    print("Wrote trail_submission.csv", output.shape)


if __name__ == "__main__":
    main()
