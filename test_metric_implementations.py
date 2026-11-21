#!/usr/bin/env python3
"""Independent small-array metric unit tests. No original NHANES files required.
Run: python test_metric_implementations.py
"""
import numpy as np
from reviewer_stage1 import concordance, CensorKM
from reviewer_stage4_survey import weighted_harrell_jackknife, weighted_c_core

def brute(t,e,r,w=None):
 t=np.asarray(t);e=np.asarray(e);r=np.asarray(r)
 w=np.ones(len(t)) if w is None else np.asarray(w)
 num=den=0.0
 for i in range(len(t)):
  if e[i]!=1:continue
  for j in range(len(t)):
   if t[j]<=t[i]:continue
   p=w[i]*w[j];den+=p
   num+=p*(1. if r[i]>r[j] else 0.5 if r[i]==r[j] else 0.)
 return num/den

rng=np.random.default_rng(20261120)
for k in range(30):
 n=10+k%7
 t=rng.integers(1,10,size=n).astype(float)
 e=rng.integers(0,2,size=n)
 if not np.any(e):e[0]=1
 risk=rng.integers(0,5,size=n).astype(float)
 w=rng.uniform(.1,3,size=n)
 c=concordance(t,e,risk)
 expected=brute(t,e,risk)
 if not np.isnan(expected):assert abs(c-expected)<1e-12,(k,c,expected)
 ranks=np.unique(risk,return_inverse=True)[1].astype(np.int64)
 wc=weighted_c_core(t,e,ranks,len(np.unique(risk)),w)
 target=brute(t,e,risk,w)
 if not np.isnan(target):assert abs(wc-target)<1e-12,(k,wc,target)
km=CensorKM(np.array([1.,2.,3.]),np.array([1,0,1]))
assert abs(float(km.G(2.))-.5)<1e-12
print('PASS 30 random unweighted/weighted C-index reference comparisons; censor KM test')
