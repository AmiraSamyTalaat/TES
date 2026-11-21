#!/usr/bin/env python3
"""Post-hoc Cox vs XGBoost-Cox sensitivity with identical median/IQR preprocessing.
Development-only XGB round selection. Original archive and frozen models unchanged.
Read Q1_SOURCE_V1_2.zip locally; output only aggregate results and method metadata.
"""
import sys,io,gzip,json,zipfile,argparse
from pathlib import Path
import numpy as np,pandas as pd,xgboost as xgb
from numba import njit
NON={'participant_id','cycle','partition','analysis_split','eligstat','mortstat','ucod_leading','diabetes','hyperten','permth_int','permth_exm','event','time_months'}
@njit
def c_index(t,e,s):
    vals=np.unique(s); ranks=np.searchsorted(vals,s)
    o=np.argsort(-t);tree=np.zeros(len(vals)+2,np.int64);total=0.;num=0.;den=0.;i=0
    while i<len(o):
        j=i+1
        while j<len(o) and t[o[j]]==t[o[i]]:j+=1
        for k in range(i,j):
            idx=o[k]
            if e[idx]!=1:continue
            rk=ranks[idx]+1; a=rk-1;lo=0.
            while a>0:lo+=tree[a];a-=a&-a
            a=rk;le=0.
            while a>0:le+=tree[a];a-=a&-a
            num+=lo+0.5*(le-lo);den+=total
        for k in range(i,j):
            idx=o[k];a=ranks[idx]+1
            while a<len(tree):tree[a]+=1;a+=a&-a
            total+=1
        i=j
    return num/den if den else np.nan

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-zip',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.source_zip) as z:
        d=pd.read_csv(io.BytesIO(gzip.decompress(z.read('Q1/data/processed/nhanes_survival_cohort.csv.gz'))))
        frozen=json.loads(z.read('Q1/outputs/cox_baseline/COX_BASELINE_STATUS.json').decode())
        protocol=json.loads(z.read('Q1/XGBOOST_SURVIVAL_PROTOCOL_FREEZE.json').decode())
    features=frozen['models'][1]['features'];assert len(features)==25 and set(features)==set(c for c in d.columns if c not in NON)
    dev=d.loc[d.analysis_split.eq('train')]; early=dev[~dev.cycle.eq('2007-2008')];late=dev[dev.cycle.eq('2007-2008')]
    def raw(f):return f[features].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    xd=raw(dev);med=np.nanmedian(xd,axis=0);imp=np.where(np.isfinite(xd),xd,med)
    center=np.median(imp,axis=0);scale=np.quantile(imp,.75,axis=0)-np.quantile(imp,.25,axis=0)
    scale=np.where(scale>1e-12,scale,1.)
    def prep(frame):
        xx=raw(frame);return (np.where(np.isfinite(xx),xx,med)-center)/scale
    def label(frame):
        t=frame.time_months.to_numpy(float);e=frame.event.to_numpy(int)
        return np.where(e==1,t,-t)
    cox=frozen['models'][1]; assert cox['features']==features
    beta=np.array([cox['coefficients_standardized'][c] for c in features],float)
    params=dict(protocol['parameters']);params.update(objective='survival:cox',eval_metric='cox-nloglik',tree_method='hist',nthread=4)
    dt=xgb.DMatrix(prep(early),label=label(early),feature_names=features)
    dv=xgb.DMatrix(prep(late),label=label(late),feature_names=features)
    temp=xgb.train(params,dt, num_boost_round=protocol['maximum_rounds'],evals=[(dv,'development_holdout')],
                   early_stopping_rounds=protocol['early_stopping_rounds'],verbose_eval=False)
    rounds=temp.best_iteration+1
    fitted=xgb.train(params,xgb.DMatrix(prep(dev),label=label(dev),feature_names=features),num_boost_round=rounds,verbose_eval=False)
    res=[]; ci_rows=[]; rng=np.random.default_rng(20261121); B=300
    eras=[('2009-2012 selection/validation',['2009-2010','2011-2012']),('2013-2014 audit',['2013-2014']),
          ('2015-2016 confirmation',['2015-2016']),('2017-2018 stress',['2017-2018'])]
    for era,cycles in eras:
        test=d[d.cycle.isin(cycles)];xx=prep(test);t=test.time_months.to_numpy(float);e=test.event.to_numpy(int)
        cox_score=xx@beta;xb_score=fitted.predict(xgb.DMatrix(xx,feature_names=features))
        cc=float(c_index(t,e,cox_score));xb=float(c_index(t,e,xb_score))
        diffs=[]
        for _ in range(B):
            ix=rng.integers(0,len(test),len(test))
            if e[ix].sum()==0:continue
            v1=c_index(t[ix],e[ix],cox_score[ix]);v2=c_index(t[ix],e[ix],xb_score[ix])
            if np.isfinite(v1) and np.isfinite(v2):diffs.append(float(v2-v1))
        ci_rows.append({'era':era,'delta_C_point':xb-cc,'CI95_lower':float(np.percentile(diffs,2.5)),
                        'CI95_upper':float(np.percentile(diffs,97.5)),'bootstrap_replicates':len(diffs)})
        res.append({'era':era,'N':len(test),'deaths':int(sum(e)),'cox_C':cc,'xgb_cox_C':xb,'delta_C':xb-cc})
    pd.DataFrame(res).to_csv(out/'MATCHED_MISSINGNESS_SENSITIVITY.csv',index=False)
    pd.DataFrame(ci_rows).to_csv(out/'MATCHED_MISSINGNESS_PAIRED_CI.csv',index=False)
    metadata={'status':'exploratory_posthoc','source':Path(a.source_zip).name,'original_frozen_files_modified':False,
      'same_processing_for_both':'training-based median imputation; training IQR standardization; same 25 predictors',
      'cox':'frozen Cox beta, ridge 0.05, 1999-2008 training','xgb_tuning':'1999-2006 fit / 2007-2008 early stopping, then refit 1999-2008',
      'xgb_best_round_1_based':int(rounds),'xgboost_version':xgb.__version__,'python':sys.version,
      'limitations':'Bootstrap CI is naive participant-paired (not complex-survey design-based); no NHANES III; post-hoc; XGBoost runtime differs from archived original.'}
    (out/'MATCHED_MISSINGNESS_METADATA.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(pd.DataFrame(res).to_string(index=False));print('rounds',rounds)
if __name__=='__main__':main()
