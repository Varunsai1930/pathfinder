"""Search small TF-IDF parameter changes around the high-scoring V8 model."""
import ast
import gc
import re
import sys
import numpy as np
import pandas as pd
sys.path.insert(0,'/private/tmp/hcl_sklearn')
from sklearn.feature_extraction.text import TfidfVectorizer

def clean(x): return re.sub(r'\s+',' ',x.lower()).strip()
def run(params,tr_text,te_text,rows,positions,ids):
 defaults=dict(ngram_range=(1,3),min_df=2,max_df=.95,sublinear_tf=True,max_features=200000,strip_accents='unicode')
 defaults.update(params)
 v=TfidfVectorizer(**defaults)
 a=v.fit_transform(tr_text);b=v.transform(te_text);out=[None]*len(te_text)
 for c,rr in rows.items():
  p=positions[c];z=b[rr].dot(a[p].T).toarray();r=np.argsort(-z,axis=1)[:,:10]
  for j,i in enumerate(rr):out[i]=ids[p[r[j]]].astype(int).tolist()
 vocab=a.shape[1];del a,b,v;gc.collect();return out,vocab
def main():
 tr=pd.read_csv('train.csv');te=pd.read_csv('test.csv');ref=pd.read_csv('/Users/varun/Downloads/submission_v8.csv').Index_list.map(ast.literal_eval).tolist()
 course=tr.set_index('Index').Course;cs=[course.loc[x[0]] for x in ref];rows={}
 for i,c in enumerate(cs):rows.setdefault(c,[]).append(i)
 pos={c:np.flatnonzero(tr.Course.to_numpy()==c) for c in tr.Course.unique()};ids=tr.Index.to_numpy()
 tr_text=[clean(re.sub(re.escape(c.lower()),' course ',r.lower())) for r,c in zip(tr.Reviews,tr.Course)];te_text=te.Reviews.map(clean).tolist()
 variants={
  'english':{'stop_words':'english'}, 'none':{'stop_words':None}, 'smooth_false':{'stop_words':'english','smooth_idf':False},
  'norm_l1':{'stop_words':'english','norm':'l1'}, 'norm_none':{'stop_words':'english','norm':None},
  'binary':{'stop_words':'english','binary':True},'no_idf':{'stop_words':'english','use_idf':False},
  'idf_raw':{'stop_words':'english','smooth_idf':False,'sublinear_tf':False},
 }
 for name,p in variants.items():
  out,vocab=run(p,tr_text,te_text,rows,pos,ids)
  s=np.mean([len(set(x)&set(y)) for x,y in zip(out,ref)]);q=np.mean([sum(a==b for a,b in zip(x,y)) for x,y in zip(out,ref)])
  print(name,vocab,round(float(s),4),round(float(q),4),flush=True)
if __name__=='__main__':main()
