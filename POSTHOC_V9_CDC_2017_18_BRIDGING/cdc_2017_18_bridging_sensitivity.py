#!/usr/bin/env python3
"""Exploratory 2017–18 chemistry-method bridging sensitivity for saved TES-11 AFT.

Only aggregate outputs are generated. Requires authorized local NHANES cohort and saved booster.
CDC documentation: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.htm
Method: published backward 2017–18 Cobas-6000 to 2015–16 DxC-660i equations;
NOT a substitute for full 1999–2018 harmonization or an external validation.
"""
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb

def cindex(t, e, r):
    """Harrell C excluding tied times; original program definition."""
    concordant=tied=comparable=0
    for i in np.flatnonzero(e==1):
        m=t>t[i]
        y=r[m]
        comparable+=len(y)
        concordant+=int(np.sum(r[i]>y))
        tied+=int(np.sum(r[i]==y))
    return (concordant+0.5*tied)/comparable if comparable else float('nan')

def bridge(frame):
    data=frame.copy()
    # Equations are backward (Cobas 2017–18 -> DxC 2015–16).
    # Albumin source equation g/dL; harmonized feature is g/L.
    data['albumin_g_l']=1.044*data['albumin_g_l']+0.1128
    x=data['alp_u_l'].to_numpy(float)
    data['alp_u_l']=np.where(np.isfinite(x)&(x>0), 10**(1.001*np.log10(np.where(x>0,x,np.nan))-0.04294),x)
    data['alt_u_l']=1.013*data['alt_u_l']+2.688
    # BUN source equation is mg/dL; harmonized field mmol/L (x 0.357).
    data['bun_mmol_l']=1.001*data['bun_mmol_l']+(0.4488*0.357)
    data['ggt_u_l']=0.8042*data['ggt_u_l']+2.363
    data['ldh_u_l']=0.8568*data['ldh_u_l']+2.062
    return data

def survival_km_at(t,e,h, target_event=True):
    times=np.asarray(t,float);flag=np.asarray(e,int) if target_event else 1-np.asarray(e,int)
    tab=pd.DataFrame({'t':times,'f':flag}).groupby('t',sort=True).agg(n=('f','size'),events=('f','sum'))
    ar=len(t)-tab['n'].cumsum().shift(fill_value=0).to_numpy()
    s=np.cumprod(1-tab.events.to_numpy()/ar)
    ix=np.searchsorted(tab.index.to_numpy(float),h,side='right')-1
    return float(1.0 if ix<0 else s[ix])

def ipcw_brier(t,e,p,h):
    t=np.asarray(t,float);e=np.asarray(e,int);p=np.asarray(p,float)
    group=pd.DataFrame({'t':t,'f':1-e}).groupby('t',sort=True).agg(n=('f','size'),c=('f','sum'))
    times=group.index.to_numpy(float)
    ar=len(t)-group.n.cumsum().shift(fill_value=0).to_numpy()
    G=np.cumprod(1-group.c.to_numpy()/ar)
    def get_G(at,left=False):
        ix=np.searchsorted(times,np.asarray(at,float),side='left' if left else 'right')-1
        return np.where(ix>=0,G[np.maximum(ix,0)],1.0)
    Gh=float(get_G([h])[0]);
    if Gh<=.01:return float('nan'),Gh
    dead=(e==1)&(t<=h)
    alive=t>h
    brier=(np.sum((1-p[dead])**2/np.maximum(get_G(t[dead],left=True),1e-9)) + np.sum(p[alive]**2/Gh))/len(t)
    return float(brier),Gh

def run(root, out, nboot=300):
    frame=pd.read_csv(root/'data/processed/nhanes_survival_cohort.csv.gz')
    tst=frame.loc[frame.cycle.eq('2017-2018')].reset_index(drop=True)
    model_file=root/'outputs/tes_aft_pilot/tes_aft_model.ubj'
    booster=xgb.Booster(model_file=str(model_file))
    names=list(booster.feature_names)
    assert len(tst)==5231 and int(tst.event.sum())==129, 'unexpected cohort; stop rather than compare different populations'
    assert len(names)==11 and set(['age_years','sex_code','alt_u_l','ggt_u_l','glucose_mmol_l','alp_u_l','chloride_mmol_l','albumin_g_l','bun_mmol_l','potassium_mmol_l','ldh_u_l'])==set(names)
    corrected=bridge(tst)
    it=int(booster.attr('best_iteration'))
    def predict(df, output_margin=False):
        mat=xgb.DMatrix(df[names].apply(pd.to_numeric,errors='coerce').to_numpy(float),feature_names=names,missing=np.nan)
        return booster.predict(mat,iteration_range=(0,it+1),output_margin=output_margin)
    raw=predict(tst)
    adj=predict(corrected)
    t=tst.time_months.to_numpy(float);ev=tst.event.to_numpy(int)
    # negation agrees with the original AFT model's Harrell-C orientation.
    c_original=cindex(t,ev,-raw);c_corrected=cindex(t,ev,-adj)
    from scipy.stats import norm
    margin0=predict(tst,output_margin=True)
    margin1=predict(corrected,output_margin=True)
    risk0=norm.cdf((np.log(24)-margin0)/1.0)
    risk1=norm.cdf((np.log(24)-margin1)/1.0)
    brier0,g24=ipcw_brier(t,ev,risk0,24)
    brier1,_=ipcw_brier(t,ev,risk1,24)
    observed24=1-survival_km_at(t,ev,24)
    # C-index estimator matches original loop; bootstrap is participant-paired.
    rng=np.random.default_rng(20261121)
    delta=[]
    for j in range(nboot):
        idx=rng.integers(0,len(t),size=len(t))
        a=cindex(t[idx],ev[idx],-adj[idx]);b=cindex(t[idx],ev[idx],-raw[idx])
        if np.isfinite(a) and np.isfinite(b):delta.append(a-b)
    out.mkdir(parents=True,exist_ok=True)
    summary={
        'analysis':'post-hoc measurement-method bridging sensitivity; fixed frozen TES-11 AFT predictions only',
        'target_cohort':'NHANES 2017-2018', 'n':len(t),'deaths':int(ev.sum()),
        'source':'CDC BIOPRO_J 2017-2018 Data Documentation, bridging equations to 2015-2016 DxC',
        'source_url':'https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.htm',
        'adjusted_predictors':['albumin_g_l','alp_u_l','alt_u_l','bun_mmol_l','ggt_u_l','ldh_u_l'],
        'no_adjustment_recommended_predictors':['chloride_mmol_l','glucose_mmol_l','potassium_mmol_l'],
        'original_harrell_c':float(c_original),'bridged_harrell_c':float(c_corrected),
        'delta_c_bridged_minus_original':float(c_corrected-c_original),
        'paired_participant_bootstrap_95CI_delta_c':[float(np.quantile(delta,.025)),float(np.quantile(delta,.975))],
        'bootstrap_repetitions_valid':len(delta),
        'observed_kaplan_meier_risk_at_24m':float(observed24),
        'censoring_KM_survival_at_24m':float(g24),
        'original_ipcw_brier_at_24m':brier0,
        'bridged_ipcw_brier_at_24m':brier1,
        'original_mean_predicted_24month_risk':float(np.mean(risk0)),
        'bridged_mean_predicted_24month_risk':float(np.mean(risk1)),
        'mean_absolute_change_predicted_24month_risk':float(np.mean(np.abs(risk1-risk0))),
        'fraction_with_changed_prediction':float(np.mean(~np.isclose(raw,adj,rtol=0,atol=1e-10))),
        'caveats':['CDC published formulas compare only 2017-2018 and 2015-2016 chemistry platforms, not all 1999-2018 or NHANES III eras','post-hoc reuse of 2017-2018 test outcomes','C-index uncertainty uses participants, not survey design','no refitting or modification of original sealed models','cannot establish any method superiority or accurate absolute risk calibration']
    }
    (out/'CDC_2017_18_BRIDGING_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    pd.DataFrame([{k:v for k,v in summary.items() if k in ('target_cohort','n','deaths','original_harrell_c','bridged_harrell_c','delta_c_bridged_minus_original','original_mean_predicted_24month_risk','observed_kaplan_meier_risk_at_24m','original_ipcw_brier_at_24m','bridged_ipcw_brier_at_24m','bridged_mean_predicted_24month_risk','mean_absolute_change_predicted_24month_risk')}]).to_csv(out/'CDC_2017_18_BRIDGING_RESULT.csv',index=False)
    print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--q1-root',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--bootstrap',type=int,default=300)
    ar=a.parse_args();run(ar.q1_root,ar.output,ar.bootstrap)
