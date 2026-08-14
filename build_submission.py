"""Train a text-based learning-path recommender and write submission.csv.

The test reviews hide the course title.  We first infer the course class from
the review's technical vocabulary, then retrieve the ten most similar labelled
training reviews from that course using TF-IDF cosine similarity.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

SEED = 20260803
TOKEN_RE = re.compile(r"[a-z0-9+#.]+")


def tokenize(text: str) -> list[str]:
    """Words and adjacent word pairs retain course-specific technical phrases."""
    words = TOKEN_RE.findall(text.lower())
    return words + [f"{left}_{right}" for left, right in zip(words, words[1:])]


def hide_course_title(review: str, course: str) -> str:
    return re.sub(re.escape(course), "this course", review, flags=re.IGNORECASE)


def train_nb(documents: list[list[str]], labels: np.ndarray, n_classes: int):
    class_token_counts = np.zeros(n_classes, dtype=np.int64)
    class_doc_counts = np.bincount(labels, minlength=n_classes).astype(float)
    token_counts: dict[str, np.ndarray] = {}

    for tokens, label in zip(documents, labels):
        counts = Counter(tokens)
        class_token_counts[label] += sum(counts.values())
        for token, count in counts.items():
            if token not in token_counts:
                token_counts[token] = np.zeros(n_classes, dtype=np.int32)
            token_counts[token][label] += count

    vocab_size = len(token_counts)
    log_prior = np.log(class_doc_counts / class_doc_counts.sum())
    log_likelihood = {
        token: np.log((counts + 1.0) / (class_token_counts + vocab_size))
        for token, counts in token_counts.items()
    }
    unknown = np.log(1.0 / (class_token_counts + vocab_size))
    return log_prior, log_likelihood, unknown


def predict_nb(documents, model):
    log_prior, log_likelihood, unknown = model
    out = np.empty(len(documents), dtype=np.int32)
    for pos, tokens in enumerate(documents):
        scores = log_prior.copy()
        for token, count in Counter(tokens).items():
            scores += count * log_likelihood.get(token, unknown)
        out[pos] = int(np.argmax(scores))
    return out


def make_tfidf_index(documents: list[list[str]], labels: np.ndarray):
    doc_freq = Counter()
    for tokens in documents:
        doc_freq.update(set(tokens))
    n_docs = len(documents)
    idf = {term: math.log((n_docs + 1) / (count + 1)) + 1.0 for term, count in doc_freq.items()}
    # Generic review boilerplate occurs in many courses.  Keeping only rarer
    # terms focuses retrieval on course concepts and keeps the inverted index
    # compact enough to score every test review.
    retrieval_terms = {term for term, weight in idf.items() if weight >= 4.0}

    postings: dict[int, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    norms = np.zeros(n_docs, dtype=float)
    for doc_pos, (tokens, label) in enumerate(zip(documents, labels)):
        counts = Counter(tokens)
        weights = {
            term: (1.0 + math.log(count)) * idf[term]
            for term, count in counts.items()
            if term in retrieval_terms
        }
        norms[doc_pos] = math.sqrt(sum(weight * weight for weight in weights.values()))
        for term, weight in weights.items():
            postings[int(label)][term].append((doc_pos, weight))
    return {term: idf[term] for term in retrieval_terms}, postings, norms


def recommend(query_tokens, class_id, idf, postings, norms, limit=10):
    query_counts = Counter(query_tokens)
    query_weights = {
        term: (1.0 + math.log(count)) * idf[term]
        for term, count in query_counts.items()
        if term in idf
    }
    query_norm = math.sqrt(sum(weight * weight for weight in query_weights.values()))
    scores = defaultdict(float)
    for term, query_weight in query_weights.items():
        for doc_pos, doc_weight in postings[class_id].get(term, []):
            scores[doc_pos] += query_weight * doc_weight

    ranked = sorted(
        ((dot / (query_norm * norms[doc_pos]), doc_pos) for doc_pos, dot in scores.items() if norms[doc_pos]),
        key=lambda item: (-item[0], item[1]),
    )
    return [doc_pos for _, doc_pos in ranked[:limit]]


def main():
    train = pd.read_csv("train.csv")
    test = pd.read_csv("test.csv")

    courses = sorted(train["Course"].unique())
    course_to_id = {course: idx for idx, course in enumerate(courses)}
    labels = train["Course"].map(course_to_id).to_numpy(dtype=np.int32)
    train_documents = [
        tokenize(hide_course_title(review, course))
        for review, course in zip(train["Reviews"], train["Course"])
    ]
    test_documents = [tokenize(review) for review in test["Reviews"]]

    # Validation deliberately removes every course title, matching the test input.
    rng = np.random.default_rng(SEED)
    validation_mask = rng.random(len(train)) < 0.10
    validation_model = train_nb(
        [doc for doc, keep in zip(train_documents, ~validation_mask) if keep],
        labels[~validation_mask],
        len(courses),
    )
    validation_pred = predict_nb(
        [doc for doc, keep in zip(train_documents, validation_mask) if keep], validation_model
    )
    validation_accuracy = float((validation_pred == labels[validation_mask]).mean())
    print(f"Held-out course-classification accuracy: {validation_accuracy:.4%}")

    model = train_nb(train_documents, labels, len(courses))
    predicted_courses = predict_nb(test_documents, model)
    idf, postings, norms = make_tfidf_index(train_documents, labels)

    recommendations = []
    for query_tokens, class_id in zip(test_documents, predicted_courses):
        doc_positions = recommend(query_tokens, int(class_id), idf, postings, norms)
        if len(doc_positions) != 10:
            raise RuntimeError("Could not retrieve ten recommendations")
        recommendations.append(str(train.iloc[doc_positions]["Index"].astype(int).tolist()))

    submission = pd.DataFrame({"Index": test["Index"].astype(int), "Index_list": recommendations})
    if submission.shape != (len(test), 2):
        raise RuntimeError(f"Unexpected submission shape: {submission.shape}")
    if not submission["Index"].equals(test["Index"].astype(int)):
        raise RuntimeError("Submission IDs do not match test IDs")
    if submission["Index_list"].str.count(",").eq(9).all() is False:
        raise RuntimeError("Every recommendation list must contain ten IDs")

    submission.to_csv("submission.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    print("Wrote submission.csv", submission.shape)
    print(submission.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
