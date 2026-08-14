"""Audit hidden-course inference against the current 78.72% benchmark.

This is diagnostic only: it never writes a submission file.
"""

import ast
import re
import sys

import numpy as np
import pandas as pd

# Local desktop dependency installed for analysis.  Kaggle has sklearn normally.
sys.path.insert(0, "/private/tmp/hcl_sklearn")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC


def clean(text):
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def masked(review, course):
    return clean(re.sub(re.escape(course), "this course", review, flags=re.I))


def main():
    train = pd.read_csv("train.csv")
    test = pd.read_csv("test.csv")
    ref = pd.read_csv("/Users/varun/Downloads/submission_v8.csv")
    index_course = train.set_index("Index")["Course"]
    reference_course = np.array([index_course.loc[ast.literal_eval(x)[0]] for x in ref["Index_list"]])

    text = np.array([masked(x, y) for x, y in zip(train.Reviews, train.Course)])
    test_text = test.Reviews.map(clean).to_numpy()
    labels = train.Course.to_numpy()
    tr, va = train_test_split(np.arange(len(train)), test_size=0.15, random_state=41, stratify=labels)
    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 3), max_features=200_000,
        min_df=2, max_df=0.95, sublinear_tf=True, strip_accents="unicode",
        dtype=np.float32,
    )
    print("Vectorizing", flush=True)
    x_train = vectorizer.fit_transform(text[tr])
    x_valid = vectorizer.transform(text[va])
    x_test = vectorizer.transform(test_text)
    print("Fitting classifier", x_train.shape, flush=True)
    model = LinearSVC(class_weight="balanced", C=1.0, max_iter=3000)
    model.fit(x_train, labels[tr])
    print("holdout_accuracy", float((model.predict(x_valid) == labels[va]).mean()), flush=True)
    score = model.decision_function(x_test)
    pred = model.classes_[score.argmax(axis=1)]
    # The margin is a model-only signal; write a small inspection table only.
    ordered = np.sort(score, axis=1)
    audit = pd.DataFrame({
        "Index": test.Index,
        "reference_course": reference_course,
        "predicted_course": pred,
        "margin": ordered[:, -1] - ordered[:, -2],
    })
    audit[audit.reference_course != audit.predicted_course].sort_values("margin", ascending=False).to_csv(
        "course_disagreements_v8.csv", index=False
    )
    print("disagreements", int((pred != reference_course).sum()), flush=True)
    print("wrote course_disagreements_v8.csv", flush=True)


if __name__ == "__main__":
    main()
