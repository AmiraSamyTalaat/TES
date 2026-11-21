#!/usr/bin/env python3
"""OPHRP-2026-0654 post-hoc reviewer analyses; originals remain immutable.

Designed for user-owned NHANES public-use source package Q1_SOURCE_V1_2.
Outputs: cohort missingness, exact baselines vs original frozen AFT models,
paired participant bootstrap CIs, cohort-specific IPCW calibration summaries,
and horizon-specific Kaplan-Meier calibration curves.

IMPORTANT: New age-only/age+sex AFT models and analyses are POST-HOC.
Validation cohort is used for early stopping; validation differences are descriptive.
No frozen primary outcomes, protocols or models are changed.
"""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import norm
import statsmodels.api as sm
from numba import njit

EXCLUDE = {"participant_id", "cycle", "partition", "analysis_split", "eligstat", "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int", "permth_exm", "event", "time_months"}

@njit(cache=True)
def _fast_c_numba(time, event, ranks, n_rank):
    # Compare only deaths at strictly earlier follow-up times against longer survivors.
    order = np.argsort(-time)
    tree = np.zeros(n_rank + 2, dtype=np.int64)
    concordant_twice, comparable, seen = 0, 0, 0
    k = 0
    while k < len(order):
        end = k + 1
        t = time[order[k]]
        while end < len(order) and time[order[end]] == t:
            end += 1
        for j in range(k, end):
            idx = order[j]
            if event[idx] != 1:
                continue
            rank = ranks[idx]
            lower = 0
            a = rank
            while a > 0:
                lower += tree[a]
                a -= a & -a
            le = 0
            a = rank + 1
            while a > 0:
                le += tree[a]
                a -= a & -a
            comparable += seen
            concordant_twice += 2 * lower + (le - lower)
        for j in range(k, end):
            rank = ranks[order[j]]
            a = rank + 1
            while a < len(tree):
                tree[a] += 1
                a += a & -a
            seen += 1
        k = end
    if comparable == 0: return np.nan
    return concordant_twice / (2.0 * comparable)

def ranks_of_risk(risk):
    risk = np.asarray(risk, float)
    if not np.all(np.isfinite(risk)):
        raise RuntimeError('nonfinite risk score')
    unique = np.unique(risk)
    return np.searchsorted(unique,risk).astype(np.int64), len(unique)

def concordance(t,e,r):
    rank,n = ranks_of_risk(r)
    return float(_fast_c_numba(np.asarray(t,float),np.asarray(e,np.int64),rank,n))

def c_bstrap(t,e,model_risk,baseline_risk,n_boot=350,seed=20261120):
    t=np.asarray(t,float);e=np.asarray(e,np.int64)
    am,an=ranks_of_risk(model_risk);bm,bn=ranks_of_risk(baseline_risk)
    real=concordance(t,e,model_risk)-concordance(t,e,baseline_risk)
    rng=np.random.default_rng(seed); n=len(t);vals=np.empty(n_boot)
    for k in range(n_boot):
        idx=rng.integers(0,n,size=n)
        vals[k]=_fast_c_numba(t[idx],e[idx],am[idx],an)-_fast_c_numba(t[idx],e[idx],bm[idx],bn)
    ok=vals[np.isfinite(vals)]
    return dict(delta_c=float(real), ci_lower=float(np.quantile(ok,0.025)),ci_upper=float(np.quantile(ok,0.975)),n_bootstrap=len(ok),seed=seed)

def normalise(train,test,cols):
    a=train[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    b=test[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    med=np.nanmedian(a,axis=0)
    a=np.where(np.isfinite(a),a,med);b=np.where(np.isfinite(b),b,med)
    centre=np.median(a,axis=0);iqr=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
    iqr=np.where(iqr>1e-12,iqr,1)
    return (a-centre)/iqr, (b-centre)/iqr

def cox_fit(X, t, d, ridge=.05, iterations=35):
    order=np.argsort(-t,kind='mergesort');X=X[order];t=t[order];d=d[order]
    beta=np.zeros(X.shape[1])
    for i in range(iterations):
        eta=np.clip(X@beta,-30,30);w=np.exp(eta)
        s0=np.cumsum(w);s1=np.cumsum(w[:,None]*X,axis=0)
        s2=np.cumsum(w[:,None,None]*X[:,:,None]*X[:,None,:],axis=0)
        gradient=-ridge*beta;info=ridge*np.eye(X.shape[1])
        for j in np.flatnonzero(d==1):
            avg=s1[j]/s0[j];gradient+=X[j]-avg
            info+=s2[j]/s0[j]-np.outer(avg,avg)
        step=np.linalg.solve(info+1e-8*np.eye(X.shape[1]),gradient)
        factor=min(1.0,1.5/max(np.max(np.abs(step)),1e-12));beta+=factor*step
        if np.max(np.abs(step*factor))<1e-6:break
    return beta

def make_aft(frame,cols,labels=True):
    dm=xgb.DMatrix(frame[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float),feature_names=cols,missing=np.nan)
    if labels:
        t=frame['time_months'].to_numpy(float);ev=frame['event'].to_numpy(int)
        dm.set_float_info('label_lower_bound',t)
        dm.set_float_info('label_upper_bound',np.where(ev==1,t,np.inf))
    return dm

def load_booster(root,model,status):
    b=xgb.Booster();b.load_model(root/model)
    it=int(json.loads((root/status).read_text())['best_iteration'])
    return b,it

def pred(model,it,cohort,features,margin=False):
    return model.predict(make_aft(cohort,features,False),iteration_range=(0,it+1),output_margin=margin)

class CensorKM:
    def __init__(self,t,e):
        t=np.asarray(t,float);e=np.asarray(e,int)
        table=pd.DataFrame({'t':t,'censor':1-e}).groupby('t',sort=True).agg(n=('censor','size'),nc=('censor','sum'))
        ar=len(t)-table['n'].cumsum().shift(fill_value=0).to_numpy()
        s=np.cumprod(1-table['nc'].to_numpy()/ar)
        self.times=table.index.to_numpy(float);self.s=s
    def G(self,t,left=False):
        a=np.asarray(t,float);ix=np.searchsorted(self.times,a,side='left' if left else 'right')-1
        out=np.ones_like(a,float);use=ix>=0;out[use]=self.s[ix[use]]
        return out

def km_event(t,e,h):
    t=np.asarray(t,float);e=np.asarray(e,int)
    table=pd.DataFrame({'t':t,'d':e}).groupby('t',sort=True).agg(n=('d','size'),ne=('d','sum'))
    table=table.loc[table.index<=h]
    if table.empty:return 0.
    n_at=len(t)-table['n'].cumsum().shift(fill_value=0).to_numpy()
    return float(1-np.prod(1-table['ne'].to_numpy()/n_at))

def ipcw_calibration(t,e,p,h):
    t=np.asarray(t,float);e=np.asarray(e,int);p=np.clip(np.asarray(p,float),1e-6,1-1e-6)
    km=CensorKM(t,e)
    cases=(e==1)&(t<=h);controls=t>h;use=cases|controls
    x=np.log(p[use]/(1-p[use])); y=cases[use].astype(int)
    w=np.empty(len(y),float);cu=cases[use]
    w[cu]=1/np.maximum(km.G(t[use][cu],True),1e-8)
    w[~cu]=1/max(float(km.G(h)),1e-8)
    result={'slope':float('nan'),'intercept':float('nan'),'n_cases':int(cases.sum()),'at_risk_horizon':int(controls.sum()),'g_at_horizon':float(km.G(h)),'mean_predicted':float(p.mean()),'observed_km':km_event(t,e,h)}
    if len(y)>10 and len(np.unique(y))==2 and np.std(x)>1e-5:
        try:
            fit=sm.GLM(y,sm.add_constant(x),family=sm.families.Binomial(),freq_weights=w).fit()
            result.update(intercept=float(fit.params[0]),slope=float(fit.params[1]))
        except Exception as ex:result['fit_error']=str(ex)[:140]
    return result

def brier(t,e,s,h):
    t=np.asarray(t,float);e=np.asarray(e,int);s=np.asarray(s,float);km=CensorKM(t,e)
    cases=(e==1)&(t<=h);control=t>h
    if float(km.G(h))<=.01:return float('nan')
    w1=1/np.maximum(km.G(t[cases],True),1e-8)
    return float((np.sum(w1*s[cases]**2)+np.sum((1-s[control])**2)/float(km.G(h)))/len(t))

def curves(t,e,p,h,cohort_name,model):
    # KM observed risk per predicted risk decile (not outcome/censoring leakage in bin creation).
    try: bins=pd.qcut(pd.Series(p).rank(method='first'),10,labels=False)
    except ValueError: bins=pd.Series(np.zeros(len(p),int))
    rec=[]
    for dec in sorted(bins.unique()):
        ix=(bins.to_numpy()==dec)
        rec.append({'cohort':cohort_name,'model':model,'horizon_months':h,'decile':int(dec)+1,'n':int(ix.sum()),'predicted_mean':float(np.mean(p[ix])),'observed_km':km_event(t[ix],e[ix],h),'events_by_horizon':int(np.sum((e[ix]==1)&(t[ix]<=h)))})
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--n-boot',type=int,default=300);args=ap.parse_args()
    root=args.root;out=args.out;out.mkdir(parents=True,exist_ok=True)
    cohort=pd.read_csv(root/'data/processed/nhanes_survival_cohort.csv.gz')
    survey=pd.read_csv(root/'data/processed/nhanes_survival_cohort_survey.csv.gz')
    ext_f=pd.read_csv(root/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
    ext_m=pd.read_fwf(root/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
    ext=ext_f.merge(ext_m,on='participant_id',how='inner',validate='one_to_one')
    ext=ext.loc[ext.eligstat.eq(1)&ext.event.notna()&ext.time_months.notna()].reset_index(drop=True)
    train=cohort.loc[cohort.analysis_split.eq('train')].reset_index(drop=True)
    val=cohort.loc[cohort.analysis_split.eq('validation')].reset_index(drop=True)
    samples={'2009-2012 validation':val,'2013-2014 audit':cohort.loc[cohort.analysis_split.eq('calibration')].reset_index(drop=True),'2015-2016 frozen confirmation':cohort.loc[cohort.cycle.eq('2015-2016')].reset_index(drop=True),'2017-2018 short-follow-up stress':cohort.loc[cohort.cycle.eq('2017-2018')].reset_index(drop=True),'NHANES III external':ext}
    feat=[c for c in cohort.columns if c not in EXCLUDE]
    if len(feat)!=25:raise RuntimeError(f'expected 25 features, got {len(feat)}')
    print('Start missingness')
    missing=[]
    for name,d in {'1999-2008 development':train,**samples}.items():
        for c in feat:
            missing.append({'cohort':name,'predictor':c,'n':len(d),'n_missing':int(d[c].isna().sum()),'percent_missing':round(d[c].isna().mean()*100,3)})
    pd.DataFrame(missing).to_csv(out/'PREDICTOR_MISSINGNESS_BY_COHORT.csv',index=False)
    xgb_cox,xgb_it=load_booster(root,'outputs/xgboost_survival_pilot/xgboost_survival_model.ubj','outputs/xgboost_survival_pilot/XGBOOST_SURVIVAL_STATUS.json')
    tes,tes_it=load_booster(root,'outputs/tes_aft_pilot/tes_aft_model.ubj','outputs/tes_aft_pilot/TES_AFT_STATUS.json')
    full,full_it=load_booster(root,'outputs/aft_survival_pilot/xgboost_aft_model.ubj','outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json')
    tes_feats=json.loads((root/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())['selected_features']
    protocol=json.loads((root/'AFT_SURVIVAL_PROTOCOL_FREEZE.json').read_text())
    models={};t=train.time_months.to_numpy(float);ev=train.event.to_numpy(int)
    print('Train matched baselines')
    for model,cols in [('age_only',['age_years']),('age_sex',['age_years','sex_code'])]:
        ztrain,_=normalise(train,train,cols)
        beta=cox_fit(ztrain,t,ev)
        aft_params={**protocol['parameters'],'objective':'survival:aft','eval_metric':'aft-nloglik','aft_loss_distribution':protocol['distribution'],'aft_loss_distribution_scale':protocol['distribution_scale'],'tree_method':'hist','nthread':4}
        m=xgb.train(aft_params,make_aft(train,cols),num_boost_round=protocol['maximum_rounds'],evals=[(make_aft(val,cols),'validation')],early_stopping_rounds=protocol['early_stopping_rounds'],verbose_eval=False)
        model_dir=out/'POST_HOC_BASELINE_MODELS';model_dir.mkdir(exist_ok=True)
        m.save_model(model_dir/(model+'.ubj'))
        models[model]={'cols':cols,'cox_beta':beta,'aft_model':m,'aft_iteration':int(m.best_iteration)}
    stats=[]; cal=[];curve=[]
    print('Evaluate cohorts')
    for ix,(name,d) in enumerate(samples.items()):
        t=d.time_months.to_numpy(float);ev=d.event.to_numpy(int)
        risks={}
        p_by_model={}
        for model in models:
            spec=models[model]
            _,scaled=normalise(train,d,spec['cols'])
            risks[model+'_cox']=scaled@spec['cox_beta']
            aft_margin=pred(spec['aft_model'],spec['aft_iteration'],d,spec['cols'],True)
            risks[model+'_aft']=-np.exp(aft_margin)
            p_by_model[model+'_aft']=(aft_margin,protocol['distribution_scale'])
        risks['full_xgb_cox']=pred(xgb_cox,xgb_it,d,feat)
        full_margin=pred(full,full_it,d,feat,True)
        tes_margin=pred(tes,tes_it,d,tes_feats,True)
        risks['full_aft']=-np.exp(full_margin)
        risks['tes11_aft']=-np.exp(tes_margin)
        p_by_model['full_aft']=(full_margin,protocol['distribution_scale']);p_by_model['tes11_aft']=(tes_margin,protocol['distribution_scale'])
        values={n:concordance(t,ev,r) for n,r in risks.items()}
        for m,v in values.items():
            stats.append({'cohort':name,'model':m,'c_index':v,'delta_vs_age_sex_aft':v-values['age_sex_aft'],'n':len(d),'deaths':int(ev.sum()),'analysis_type':'post-hoc' if m.endswith('_aft') and m in ['age_only_aft','age_sex_aft'] else 'frozen_model_evaluation'})
        for target,baseline in [('tes11_aft','age_sex_aft'),('full_aft','age_sex_aft'),('age_sex_aft','age_only_aft'),('full_xgb_cox','age_sex_cox')]:
            res=c_bstrap(t,ev,risks[target],risks[baseline],args.n_boot,20261120+ix*10+len(target))
            res.update(cohort=name,comparison=target+' minus '+baseline)
            cal.append(res)
        for model,(margin,dist_scale) in p_by_model.items():
            for h in ([24] if name.startswith('2017') else [24,60]):
                prob=norm.cdf((np.log(h)-margin)/dist_scale)
                row=ipcw_calibration(t,ev,prob,h)
                row.update(cohort=name,model=model,horizon_months=h,ipcw_brier=brier(t,ev,1-prob,h))
                stats_key={'cohort':name,'model':model,'horizon_months':h}
                curve+=curves(t,ev,prob,h,name,model)
                # store in separate output
                if 'cal_rows' not in locals():cal_rows=[]
                cal_rows.append({**stats_key,**row})
        print(name,'N',len(d),'C[TES]',values['tes11_aft'],'C[age+sex AFT]',values['age_sex_aft'])
    pd.DataFrame(stats).to_csv(out/'AGE_BASELINE_C_INDEX_BY_ERA.csv',index=False)
    pd.DataFrame(cal).to_csv(out/'PAIRED_BOOTSTRAP_DELTAC_95CI.csv',index=False)
    pd.DataFrame(cal_rows).to_csv(out/'CALIBRATION_COHORT_SPECIFIC_CENSORING.csv',index=False)
    pd.DataFrame(curve).to_csv(out/'CALIBRATION_DECILE_KM_CURVES.csv',index=False)
    meta={'classification':'EXPLORATORY POST-HOC REVIEWER EXTENSION','original_frozen_files_modified':False,'source_sha256':hashlib.sha256((root/'AFT_SURVIVAL_PROTOCOL_FREEZE.json').read_bytes()).hexdigest(),'cohorts':{n:{'n':len(d),'deaths':int(d.event.sum())} for n,d in samples.items()},'new_age_only_aft_best_iteration':models['age_only']['aft_iteration'],'new_age_sex_aft_best_iteration':models['age_sex']['aft_iteration'],'paired_bootstrap_repetitions':args.n_boot,'censoring_distribution':'estimated within each evaluation cohort for all new calibration/IPCW Brier analyses','warning':'Do not treat reconstructed calibration as sufficient until validated against methodological assumptions and software-version sensitivity; no survey-design robust standard errors in this stage; NHANES III is backward-era transfer.'}
    (out/'STAGE1_STATUS.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,indent=2))

if __name__=='__main__':main()
