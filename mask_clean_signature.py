"""Test the exact V7 preprocessing plus course-name masking against V8."""

import ast
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/private/tmp/hcl_sklearn")
from sklearn.feature_extraction.text import TfidfVectorizer


def clean(text):
    text = text.lower()
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,!?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    train=pd.read_csv('train.csv'); test=pd.read_csv('test.csv'); ref=pd.read_csv('/Users/varun/Downloads/submission_v8.csv')
    reference=ref.Index_list.map(ast.literal_eval).tolist()
    course_for_id=train.set_index('Index').Course
    courses=[course_for_id.loc[x[0]] for x in reference]
    rows_by_course={}
    for i,c in enumerate(courses): rows_by_course.setdefault(c,[]).append(i)
    candidate_by_course={c:np.flatnonzero(train.Course.to_numpy()==c) for c in train.Course.unique()}
    train_text=[clean(re.sub(re.escape(c), 'this course', r, flags=re.I)) for r,c in zip(train.Reviews,train.Course)]
    test_text=test.Reviews.map(clean).tolist()
    for name, params in {
      'exact_v7_masked':dict(ngram_range=(1,3),min_df=2,max_df=.95,sublinear_tf=True),
      'min_df_1':dict(ngram_range=(1,3),min_df=1,max_df=.95,sublinear_tf=True),
      'maxdf_1':dict(ngram_range=(1,3),min_df=2,max_df=1.0,sublinear_tf=True),
      'no_sublinear':dict(ngram_range=(1,3),min_df=2,max_df=.95,sublinear_tf=False),
      'bigram':dict(ngram_range=(1,2),min_df=2,max_df=.95,sublinear_tf=True),
      'ngram4':dict(ngram_range=(1,4),min_df=2,max_df=.95,sublinear_tf=True),
    }.items():
      vec=TfidfVectorizer(lowercase=True,stop_words='english',max_features=200000,strip_accents='unicode',**params)
      xtr=vec.fit_transform(train_text); xte=vec.transform(test_text); out=[None]*len(test)
      for course,rows in rows_by_course.items():
       cand=candidate_by_course[course]; score=xte[rows].dot(xtr[cand].T).toarray(); rank=np.argsort(-score,axis=1)[:,:10]; ids=train.Index.to_numpy()[cand[rank]]
       for j,row in enumerate(rows):out[row]=ids[j].astype(int).tolist()
      sets=np.mean([len(set(a)&set(b)) for a,b in zip(out,reference)]);pos=np.mean([sum(a==b for a,b in zip(x,y)) for x,y in zip(out,reference)])
      print(name,xtr.shape,round(float(sets),4),round(float(pos),4),flush=True)
      if name=='exact_v7_masked':pd.DataFrame({'Index':test.Index.astype(int),'Index_list':[str(x) for x in out]}).to_csv('mask_clean_candidate.csv',index=False)

if __name__=='__main__':main()
