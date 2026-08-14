"""Reverse-engineer a ranked reference by comparing sparse retrieval ensembles."""

import ast
import gc
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/private/tmp/hcl_sklearn")
from sklearn.feature_extraction.text import TfidfVectorizer


def clean(text):
    return " ".join(text.lower().split())


def body(text):
    parts = text.lower().split(". ", 1)
    return parts[1] if len(parts) == 2 else parts[0]


def masked(text, course=None):
    value = text.lower()
    if course:
        value = re.sub(re.escape(course.lower()), " course ", value)
    return re.sub(r"\b(this course|this program|this learning path)\b", " course ", value)


def compare(prediction, reference):
    set_hits = np.mean([len(set(a) & set(b)) for a, b in zip(prediction, reference)])
    position_hits = np.mean([sum(x == y for x, y in zip(a, b)) for a, b in zip(prediction, reference)])
    return round(float(set_hits), 4), round(float(position_hits), 4)


def rrf(rankings, weights, offset=20):
    out = []
    for rows in zip(*rankings):
        score = {}
        first = {}
        for weight, row in zip(weights, rows):
            for rank, item in enumerate(row, start=1):
                score[item] = score.get(item, 0) + weight / (offset + rank)
                first[item] = min(first.get(item, rank), rank)
        out.append(sorted(score, key=lambda item: (-score[item], first[item], item))[:10])
    return out


def predict(vectorizer, train_text, test_text, groups, train_positions, train_ids):
    x_train = vectorizer.fit_transform(train_text)
    x_test = vectorizer.transform(test_text)
    output = [None] * len(test_text)
    for course, rows in groups.items():
        candidates = train_positions[course]
        scores = x_test[rows].dot(x_train[candidates].T).toarray()
        ranks = np.argsort(-scores, axis=1)[:, :10]
        for local, row in enumerate(rows):
            output[row] = train_ids[candidates[ranks[local]]].astype(int).tolist()
    print("matrix", x_train.shape)
    del x_train, x_test
    gc.collect()
    return output


def main():
    train = pd.read_csv("train.csv")
    test = pd.read_csv("test.csv")
    ref = pd.read_csv("/Users/varun/Downloads/submission_v8.csv")
    reference = ref.Index_list.map(ast.literal_eval).tolist()
    course_for_id = train.set_index("Index").Course
    course_per_test = [course_for_id.loc[row[0]] for row in reference]
    groups = {}
    for row, course in enumerate(course_per_test):
        groups.setdefault(course, []).append(row)
    train_positions = {course: np.flatnonzero(train.Course.to_numpy() == course) for course in train.Course.unique()}
    train_ids = train.Index.to_numpy()

    full_train = train.Reviews.map(clean).tolist()
    full_test = test.Reviews.map(clean).tolist()
    masked_train = [masked(review, course) for review, course in zip(train.Reviews, train.Course)]
    masked_test = [masked(review) for review in test.Reviews]
    body_train = train.Reviews.map(body).tolist()
    body_test = test.Reviews.map(body).tolist()

    configs = {
        "word_tri": (TfidfVectorizer(stop_words="english", ngram_range=(1,3), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000, strip_accents="unicode"), full_train, full_test),
        "word_masked": (TfidfVectorizer(stop_words="english", ngram_range=(1,3), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000, strip_accents="unicode"), masked_train, masked_test),
        "word_body": (TfidfVectorizer(stop_words="english", ngram_range=(1,3), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000, strip_accents="unicode"), body_train, body_test),
        "char_3_5": (TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000), full_train, full_test),
        "char_2_6": (TfidfVectorizer(analyzer="char_wb", ngram_range=(2,6), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000), full_train, full_test),
    }
    outputs = {}
    for name, (vectorizer, train_text, test_text) in configs.items():
        print("building", name, flush=True)
        outputs[name] = predict(vectorizer, train_text, test_text, groups, train_positions, train_ids)
        print(name, compare(outputs[name], reference), flush=True)

    baseline = outputs["word_tri"]
    for other in ["word_masked", "word_body", "char_3_5", "char_2_6"]:
        for weight in [.15,.25,.35,.5,.75,1.0,1.5,2.0]:
            fused = rrf([baseline, outputs[other]], [1.0, weight])
            print("rrf", other, weight, compare(fused, reference), flush=True)


if __name__ == "__main__":
    main()
