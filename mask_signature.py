"""Find the text-normalization rule behind submission_v8.csv."""

import ast
import gc
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/private/tmp/hcl_sklearn")
from sklearn.feature_extraction.text import TfidfVectorizer


def compare(predicted, reference):
    return (
        round(float(np.mean([len(set(a) & set(b)) for a, b in zip(predicted, reference)])), 4),
        round(float(np.mean([sum(x == y for x, y in zip(a, b)) for a, b in zip(predicted, reference)])), 4),
    )


def rankings(train_text, test_text, train, groups, positions_by_course):
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 3), min_df=2, max_df=.95, sublinear_tf=True, max_features=200000, strip_accents="unicode")
    xtr = vec.fit_transform(train_text)
    xte = vec.transform(test_text)
    output = [None] * len(test_text)
    ids = train.Index.to_numpy()
    for course, rows in groups.items():
        cand = positions_by_course[course]
        scores = xte[rows].dot(xtr[cand].T).toarray()
        ranks = np.argsort(-scores, axis=1)[:, :10]
        for local, row in enumerate(rows): output[row] = ids[cand[ranks[local]]].astype(int).tolist()
    print('vocab',xtr.shape[1], flush=True)
    del xtr,xte,vec
    gc.collect()
    return output


def main():
    train=pd.read_csv('train.csv'); test=pd.read_csv('test.csv'); ref=pd.read_csv('/Users/varun/Downloads/submission_v8.csv')
    reference=ref.Index_list.map(ast.literal_eval).tolist()
    course_for_id=train.set_index('Index').Course
    courses=[course_for_id.loc[row[0]] for row in reference]
    groups={}
    for i,c in enumerate(courses): groups.setdefault(c,[]).append(i)
    positions={c:np.flatnonzero(train.Course.to_numpy()==c) for c in train.Course.unique()}
    pattern_terms=r'\b(this course|this program|this learning path)\b'
    raw_test=test.Reviews.str.lower().tolist()
    variants={
      'replace_this_course_raw_test': ([re.sub(re.escape(c.lower()), ' this course ', r.lower()) for r,c in zip(train.Reviews,train.Course)], raw_test),
      'replace_this_course_normalized_test': ([re.sub(re.escape(c.lower()), ' this course ', r.lower()) for r,c in zip(train.Reviews,train.Course)], [re.sub(pattern_terms,' this course ',r) for r in raw_test]),
      'remove_course_remove_reference': ([re.sub(re.escape(c.lower()),' ',r.lower()) for r,c in zip(train.Reviews,train.Course)], [re.sub(pattern_terms,' ',r) for r in raw_test]),
      'replace_course_token_normalized_test': ([re.sub(re.escape(c.lower()),' course ',r.lower()) for r,c in zip(train.Reviews,train.Course)], [re.sub(pattern_terms,' course ',r) for r in raw_test]),
      'replace_course_token_raw_test': ([re.sub(re.escape(c.lower()),' course ',r.lower()) for r,c in zip(train.Reviews,train.Course)], raw_test),
      'replace_this_program_normalized_test': ([re.sub(re.escape(c.lower()),' this program ',r.lower()) for r,c in zip(train.Reviews,train.Course)], [re.sub(pattern_terms,' this program ',r) for r in raw_test]),
    }
    for name,(tr,te) in variants.items():
        print('building',name,flush=True)
        out=rankings(tr,te,train,groups,positions)
        print(name,compare(out,reference),flush=True)
        if name=='replace_this_course_raw_test':
            pd.DataFrame({'Index':test.Index.astype(int),'Index_list':[str(x) for x in out]}).to_csv('mask_candidate.csv',index=False)


if __name__=='__main__': main()
