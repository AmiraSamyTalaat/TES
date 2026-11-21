#!/usr/bin/env python3
"""Independent fixed-model calibration audit for OPHRP-2026-0654.

Only public-use NHANES source data; no person-level outputs.
No training, tuning, editing of source files, or recalibration on test outcomes.
Log-normal AFT prediction with normal error scale from frozen protocol.
IPCW calibration regression is descriptive; participant bootstrap omits complex-survey design.
Usage: python v6_calibration_audit.py --root Q1 --out RESULTS --boot 200
"""
from __future__ import annotations
import argparse, json, hashlib, platform
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr,expit
import xgboost as xgb

def survival_km(t,events,h):
    """Return KM survival at h (right-continuous), using ties at same follow-up."""
    t=np.asarray(t,dtype=float); ev=np.asarray(events,int)
    tt,inv,cc=np.unique(t,return_inverse=True,return_counts=True)
    n_risk=len(t)-np.cumsum(cc)+cc
    nd=np.bincount(inv,weights=ev,minlength=len(tt))
    factors=1-nd/n_risk
    surv=np.cumprod(factors)
    i=np.searchsorted(tt,h,side='right')-1
    return float(surv[i]) if i>=0 else 1.0

def Gvalues(t,e,query,left=False):
    """Censoring KM based on censor=1-event, at query horizons or t-"""
    t=np.asarray(t,float); e=np.asarray(e,int); q=np.asarray(query,float)
    tt,inv,cc=np.unique(t,return_inverse=True,return_counts=True)
    nr=len(t)-np.cumsum(cc)+cc
    nc=np.bincount(inv,weights=1-e,minlength=len(tt))
    s=np.cumprod(1-nc/nr)
    ix=np.searchsorted(tt,q,side='left' if left else 'right')-1
    out=np.ones_like(q,float)
    good=ix>=0
    out[good]=s[ix[good]]
    return out

def weighted_logit(x,y,w):
    """Independent two-parameter IRLS, ridge-free; intercept and slope."""
    a,b=0.0,1.0
    for i in range(35):
        z=np.clip(a+b*x,-30,30)
        p=expit(z)
        ww=w*p*(1-p)
        g0=np.sum(w*(y-p)); g1=np.dot(w*(y-p),x)
        h00=ww.sum();h01=np.dot(ww,x);h11=np.dot(ww,x*x)
        det=h00*h11-h01*h01
        if det<1e-12: return np.nan,np.nan
        da=(h11*g0-h01*g1)/det
        db=(-h01*g0+h00*g1)/det
        scale=min(1.0,2.0/max(abs(da),abs(db),1e-12))
        a+=scale*da;b+=scale*db
        if max(abs(da*scale),abs(db*scale))<1e-9:break
    return float(a),float(b)

def audit_one(t,e,p,h):
    t=np.asarray(t,float); e=np.asarray(e,int); p=np.clip(np.asarray(p,float),1e-9,1-1e-9)
    cases=(e==1)&(t<=h);controls=t>h
    keep=cases|controls
    gh=float(Gvalues(t,e,[h])[0])
    gcase=Gvalues(t,e,t[cases],left=True)
    if gh<1e-6 or np.any(gcase<1e-6):return None
    x=np.log(p[keep]/(1-p[keep])); y=cases[keep].astype(float)
    w=np.ones(np.sum(keep)); wc=cases[keep]
    w[wc]=1/np.maximum(gcase,1e-8)
    w[~wc]=1/gh
    intercept,slope=weighted_logit(x,y,w)
    obs=1-survival_km(t,e,h)
    mu=float(p.mean())
    return {'calibration_intercept':intercept,'calibration_slope':slope,
            'mean_predicted':mu,'observed_km':float(obs),
            'expected_over_observed':mu/obs if obs>0 else np.nan,
            'n_deaths_by_horizon':int(cases.sum()),'n_followed_past_horizon':int(controls.sum()),
            'censor_km_horizon':gh}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--boot',type=int,default=200)
    ap.add_argument('--seed',type=int,default=20261121)
    ap.add_argument('--reference',type=Path)
    arg=ap.parse_args();arg.out.mkdir(parents=True,exist_ok=True)
    r=arg.root
    fr=pd.read_csv(r/'data/processed/nhanes_survival_cohort.csv.gz',low_memory=False)
    exf=pd.read_csv(r/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz',low_memory=False)
    exm=pd.read_fwf(r/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
    ex=exf.merge(exm,on='participant_id',validate='one_to_one')
    ex=ex.loc[ex.eligstat.eq(1)&ex.event.notna()&ex.time_months.notna()].reset_index(drop=True)
    cohorts={'2009-2012 validation':fr[fr.analysis_split.eq('validation')].reset_index(drop=True),
             '2013-2014 audit':fr[fr.analysis_split.eq('calibration')].reset_index(drop=True),
             '2015-2016 frozen confirmation':fr[fr.cycle.eq('2015-2016')].reset_index(drop=True),
             '2017-2018 short-follow-up stress':fr[fr.cycle.eq('2017-2018')].reset_index(drop=True),
             'NHANES III external':ex}
    protocol=json.loads((r/'AFT_SURVIVAL_PROTOCOL_FREEZE.json').read_text())
    if protocol['distribution']!='normal': raise RuntimeError('AFT distribution is not normal as expected')
    scale=float(protocol['distribution_scale'])
    status=json.loads((r/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())
    feats=status['selected_features'];it=int(status['best_iteration'])
    booster=xgb.Booster();booster.load_model(str(r/'outputs/tes_aft_pilot/tes_aft_model.ubj'))
    rng=np.random.default_rng(arg.seed)
    rows=[]
    for name,df in cohorts.items():
        dm=xgb.DMatrix(df[feats].apply(pd.to_numeric,errors='coerce').to_numpy(float),feature_names=feats,missing=np.nan)
        margin=booster.predict(dm,iteration_range=(0,it+1),output_margin=True)
        t=df.time_months.to_numpy(float);e=df.event.to_numpy(int)
        for h in ([24] if name.startswith('2017') else [24,60]):
            p=ndtr((np.log(h)-margin)/scale)
            point=audit_one(t,e,p,h)
            if point is None: raise RuntimeError(f'Censoring survival zero: {name} {h}')
            reps=[]
            for _ in range(arg.boot):
                ix=rng.integers(0,len(df),size=len(df))
                result=audit_one(t[ix],e[ix],p[ix],h)
                if result is not None and np.isfinite(result['calibration_slope']): reps.append(result)
            if len(reps)<max(20,int(arg.boot*.8)):
                raise RuntimeError(f'Too few bootstrap replicates for {name} {h}: {len(reps)}')
            row={'cohort':name,'model':'TES-11 AFT','horizon_months':h,'n':len(df),'events_total':int(e.sum()),**point,'n_bootstrap_valid':len(reps),'bootstrap_seed':arg.seed,'analysis':'post-hoc fixed-model participant-bootstrap, not survey-design-based'}
            for k in ['calibration_intercept','calibration_slope','mean_predicted','observed_km','expected_over_observed']:
                rvals=np.asarray([x[k] for x in reps],float)
                row[k+'_ci_lower'],row[k+'_ci_upper']=np.quantile(rvals,[.025,.975]).tolist()
            rows.append(row)
            print(f'{name:35s} {h:2d} mo slope={point["calibration_slope"]:.4f} E/O={point["expected_over_observed"]:.3f} G={point["censor_km_horizon"]:.3f}',flush=True)
    out=pd.DataFrame(rows)
    if arg.reference and arg.reference.exists():
        ref=pd.read_csv(arg.reference)
        ref=ref[ref.model.eq('tes11_aft')]
        v=out.merge(ref,on=['cohort','horizon_months'])
        for old,new in [('slope','calibration_slope'),('intercept','calibration_intercept'),('mean_predicted','mean_predicted'),('observed_km','observed_km')]:
            a=v[old] if old!=new else v[old+'_y']
            b=v[new] if old!=new else v[new+'_x']
            d=float(np.max(np.abs(a-b)))
            print('Reference difference',old,d)
            if d>1e-5: raise AssertionError(f'Calibration {old} mismatch: {d}')
    out.to_csv(arg.out/'V6_CALIBRATION_UNCERTAINTY_TES.csv',index=False)
    manifest={'analysis':'exploratory, fixed frozen TES AFT, original data never changed',
              'model_sha256':hashlib.sha256((r/'outputs/tes_aft_pilot/tes_aft_model.ubj').read_bytes()).hexdigest(),
              'protocol_sha256':hashlib.sha256((r/'AFT_SURVIVAL_PROTOCOL_FREEZE.json').read_bytes()).hexdigest(),
              'best_iteration':it,'distribution':protocol['distribution'],'distribution_scale':scale,
              'python':platform.python_version(),'xgboost':xgb.__version__,
              'bootstrap_replications':arg.boot,'seed':arg.seed,'n_rows':len(out),
              'limitations':['Bootstrap participant-level only, not complex-survey based',
                              'Censoring KM re-estimated within evaluation cohort and each bootstrap replicate',
                              'AFT frozen model predictions read under currently installed XGBoost version',
                              'No evidence of calibrated absolute risk for clinical use',
                              '24-month G under 2017-2018 is low; avoid long horizons there']}
    (arg.out/'V6_CALIBRATION_AUDIT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if __name__=='__main__':main()
