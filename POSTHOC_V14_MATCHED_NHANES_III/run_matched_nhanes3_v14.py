"""Supplementary post-hoc NHANES III matched-missingness comparison, no existing frozen model altered."""
import json, sys, argparse
from pathlib import Path
import numpy as np,pandas as pd,xgboost as xgb
from numba import njit
p = argparse.ArgumentParser(description='Post-hoc matched-preprocessing Cox vs XGBoost-Cox in NHANES III (aggregate results only).')
p.add_argument('--q1-root', type=Path, required=True, help='Private local copy of Q1 from the original Q1_SOURCE_V1_2.zip; never upload it')
p.add_argument('--out', type=Path, required=True, help='Output directory for aggregate summary only')
a=p.parse_args()
ROOT = a.q1_root.resolve()
OUT = a.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)
required = [ROOT/'data/processed/nhanes_survival_cohort.csv.gz', ROOT/'outputs/cox_baseline/COX_BASELINE_STATUS.json',
ROOT/'XGBOOST_SURVIVAL_PROTOCOL_FREEZE.json',ROOT/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz',
ROOT/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat']
missing = [str(f) for f in required if not f.is_file()]
if missing: p.error('Local private input(s) not found: ' + '; '.join(missing))

@njit
def c_index(t,e,s):
    vals=np.unique(s);ranks=np.searchsorted(vals,s)
    o=np.argsort(-t);tree=np.zeros(len(vals)+2,np.int64);total=0.;num=0.;den=0.;i=0
    while i<len(o):
        j=i+1
        while j<len(o) and t[o[j]]==t[o[i]]:j+=1
        for k in range(i,j):
            idx=o[k]
            if e[idx]!=1:continue
            rk=ranks[idx]+1;a=rk-1;lo=0.
            while a>0:lo+=tree[a];a-=a&-a
            a=rk;le=0.
            while a>0:le+=tree[a];a-=a&-a
            num+=lo+0.5*(le-lo);den+=total
        for k in range(i,j):
            idx=o[k];a=ranks[idx]+1
            while a<len(tree):tree[a]+=1;a+=a&-a
            total+=1
        i=j
    return num/den if den>0 else np.nan

coh=pd.read_csv(ROOT/'data/processed/nhanes_survival_cohort.csv.gz')
status=json.load(open(ROOT/'outputs/cox_baseline/COX_BASELINE_STATUS.json'));cox=status['models'][1];feat=cox['features']
protocol=json.load(open(ROOT/'XGBOOST_SURVIVAL_PROTOCOL_FREEZE.json'))
train=coh.loc[coh.analysis_split.eq('train')]
features=pd.read_csv(ROOT/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
mort=pd.read_fwf(ROOT/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months'])
mort=mort.apply(pd.to_numeric,errors='coerce')
ext=features.merge(mort,on='participant_id',how='inner',validate='one_to_one')
ext=ext.loc[ext.eligstat.eq(1)&ext.event.notna()&ext.time_months.notna()].reset_index(drop=True)
assert len(ext)==16519 and int(ext.event.sum())==7081,(len(ext),int(ext.event.sum()))
def raw(x):return x[feat].apply(pd.to_numeric,errors='coerce').to_numpy(float)
xt=raw(train);med=np.nanmedian(xt,axis=0);imp=np.where(np.isfinite(xt),xt,med)
center=np.median(imp,axis=0);scale=np.quantile(imp,.75,axis=0)-np.quantile(imp,.25,axis=0)
scale=np.where(scale>1e-12,scale,1.)
def prep(x):
 y=raw(x);return (np.where(np.isfinite(y),y,med)-center)/scale
xx=prep(ext);bet=np.array([cox['coefficients_standardized'][f] for f in feat]);cs=xx@bet
params=dict(protocol['parameters']);params.update(objective='survival:cox',eval_metric='cox-nloglik',tree_method='hist',nthread=4)
def labels(x):
 t=x.time_months.to_numpy(float);e=x.event.to_numpy(int);return np.where(e==1,t,-t)
model=xgb.train(params,xgb.DMatrix(prep(train),label=labels(train),feature_names=feat),num_boost_round=512,verbose_eval=False)
xs=model.predict(xgb.DMatrix(xx,feature_names=feat))
t=ext.time_months.to_numpy(float); e=ext.event.to_numpy(int)
cc=float(c_index(t,e,cs));xc=float(c_index(t,e,xs))
B=300;rng=np.random.default_rng(20261121);pairs=[]
for i in range(B):
 ix=rng.integers(0,len(ext),len(ext));c1=c_index(t[ix],e[ix],cs[ix]);c2=c_index(t[ix],e[ix],xs[ix]);
 if np.isfinite(c1) and np.isfinite(c2):pairs.append(float(c2-c1))
record={'era':'NHANES III historical-era external','N':len(ext),'deaths':int(e.sum()),'cox_C':cc,'xgb_cox_C':xc,'delta_C':xc-cc,'CI95_lower':float(np.percentile(pairs,2.5)),'CI95_upper':float(np.percentile(pairs,97.5)),'bootstrap_replicates':len(pairs),'xgb_rounds':512,'xgboost_version':xgb.__version__,'random_seed':20261121,'design':'posthoc, development median/IQR and same 25 predictors; unweighted participant bootstrap', 'original_frozen_models_modified':False}
(OUT/'MATCHED_MISSINGNESS_NHANES3_V14.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2))
print('Output contains aggregate results only. No participant-level files written.')
