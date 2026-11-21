#!/usr/bin/env python3
"""Transparent post-review measurement-shift stress test for TES scoring.

Frozen XGBoost-Cox model, 2009-10 untouched, 2011-12 perturbed by explicitly
specified simulated laboratory measurement shifts. No mortality outcomes used
in feature selection, and no model retraining. This assesses TES ranking under
injected measurement shift, NOT predictive validity of competing selected panels.
"""
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd,xgboost as xgb
from scipy.stats import spearmanr

NON={'participant_id','cycle','partition','analysis_split','eligstat','mortstat','ucod_leading','diabetes','hyperten','permth_int','permth_exm','event','time_months'}

def feature_profile(model,it,df,cols):
    vals=df[cols].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    dm=xgb.DMatrix(vals,feature_names=cols,missing=np.nan)
    contrib=model.predict(dm,pred_contribs=True,iteration_range=(0,it+1))[:,:-1]
    magn=np.mean(np.abs(contrib),axis=0);norm=magn/max(float(magn.sum()),1e-12)
    rho=[]
    for j in range(len(cols)):
        idx=np.isfinite(vals[:,j])&np.isfinite(contrib[:,j])
        if idx.sum()<20 or np.std(vals[idx,j])<1e-9:rho.append(0.)
        else:
            r=spearmanr(vals[idx,j],contrib[idx,j]).statistic
            rho.append(float(r) if np.isfinite(r) else 0.)
    return pd.DataFrame({'feature':cols,'normalized_importance':norm,'direction_spearman':rho})

def selectors(a,b):
    p=a.merge(b,on='feature',suffixes=('_old','_new'))
    vec=np.column_stack([p.normalized_importance_old,p.normalized_importance_new])
    mean=vec.mean(axis=1);cv=vec.std(axis=1)/np.maximum(mean,1e-12)
    direction=np.column_stack([p.direction_spearman_old,p.direction_spearman_new])
    agreement=[]
    for d in direction:
        nz=d[np.abs(d)>=.10]
        agreement.append(abs(np.sign(nz).mean()) if len(nz) else .5)
    tes=mean/(1+cv)*np.array(agreement)
    def choose(score):
        ix=np.argsort(-score,kind='stable')
        v=score[ix];total=sum(v)
        if total<=0:raise RuntimeError('TES zero score mass; requires inspection')
        cnt=min(15,max(8,int(np.searchsorted(np.cumsum(v)/total,.90)+1)))
        panel=[p.feature.iloc[k] for k in ix[:cnt]]
        for s in ['age_years','sex_code']:
            if s not in panel:panel.append(s)
        return panel
    return choose(tes),choose(mean),p,tes,mean

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'SRC/Q1');ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'STAGE5_RESULTS');opt=ap.parse_args()
    r=opt.root;out=opt.out;out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(r/'data/processed/nhanes_survival_cohort.csv.gz')
    cols=[x for x in df if x not in NON]
    m=xgb.Booster();m.load_model(r/'outputs/xgboost_survival_pilot/xgboost_survival_model.ubj')
    it=int(json.loads((r/'outputs/xgboost_survival_pilot/XGBOOST_SURVIVAL_STATUS.json').read_text())['best_iteration'])
    old=df[df.cycle.eq('2009-2010')].copy().reset_index(drop=True)
    new=df[df.cycle.eq('2011-2012')].copy().reset_index(drop=True)
    original_old=feature_profile(m,it,old,cols)
    original_new=feature_profile(m,it,new,cols)
    initial_tes,initial_shap,*_=selectors(original_old,original_new)
    def shift_data(mult,missing,seed):
        x=new.copy()
        for var,val in mult.items():
            x[var]=pd.to_numeric(x[var],errors='coerce')*val
        rng=np.random.default_rng(seed)
        for var,proportion in missing.items():
            idx=rng.random(len(x))<proportion
            x.loc[idx,var]=np.nan
        return x
    scenarios=[
      ('observed_unaltered',{},{}),
      ('glucose_assay_plus_25pct',{'glucose_mmol_l':1.25},{}),
      ('ggt_assay_plus_50pct',{'ggt_u_l':1.5},{}),
      ('lab_shift_multiple',{'glucose_mmol_l':1.25,'ggt_u_l':1.5,'creatinine_umol_l':1.6,'albumin_g_l':0.85},{}),
      ('lab_shift_missingness',{'glucose_mmol_l':1.25,'ggt_u_l':1.5,'creatinine_umol_l':1.6,'albumin_g_l':0.85},{'creatinine_umol_l':.25,'ggt_u_l':.20}),
    ]
    rows=[];all_profiles=[]
    for i,(name,mult,missing) in enumerate(scenarios):
        changed=shift_data(mult,missing,20261120+i)
        curr=feature_profile(m,it,changed,cols)
        tes,shap,joined,*_=selectors(original_old,curr)
        rank=float(spearmanr(original_old.normalized_importance,curr.normalized_importance).statistic)
        top1=set(original_old.sort_values('normalized_importance',ascending=False).feature.head(10))
        top2=set(curr.sort_values('normalized_importance',ascending=False).feature.head(10))
        rows.append({'scenario':name,'simulated_multiplier_json':json.dumps(mult,sort_keys=True),'extra_missingness_json':json.dumps(missing,sort_keys=True),
          'shap_rank_spearman_2009_vs_2011':rank,'top10_overlap':len(top1&top2)/10,'TES_panel_size':len(tes),'MeanSHAP_panel_size':len(shap),
          'TES_panel':'; '.join(tes),'MeanSHAP_panel':'; '.join(shap),'Jaccard_TES_vs_baseline':len(set(tes)&set(initial_tes))/len(set(tes)|set(initial_tes)),
          'Jaccard_SHAP_vs_baseline':len(set(shap)&set(initial_shap))/len(set(shap)|set(initial_shap))})
        curr['scenario']=name;all_profiles.append(curr)
        print(name,'rho',round(rank,3),'TES',len(tes),'MeanSHAP',len(shap),'TES_vs_orig',rows[-1]['Jaccard_TES_vs_baseline'],flush=True)
    pd.DataFrame(rows).to_csv(out/'SIMULATED_MEASUREMENT_SHIFT_TES_VS_SHAP.csv',index=False)
    pd.concat(all_profiles,ignore_index=True).to_csv(out/'SIMULATED_SHIFT_SHAP_PROFILES.csv',index=False)
    (out/'STAGE5_STATUS.json').write_text(json.dumps({'status':'EXPLORATORY_ONLY','model':'archived frozen XGBoost-Cox trained 1999-2008','selection_cycles':['2009-2010','2011-2012'],'perturbation_target':'2011-2012 predictors only','original_unshifted_sample':'2009-2010','outcomes_used':'none','does_not_prove':'TES superiority, country transfer, lab assay historical differences, clinical validity, or end-to-end outcome robustness','scenario_count':len(rows)},indent=2))
    (out/'METHODS_AND_LIMITATIONS.md').write_text('''# Synthetic measurement-shift demonstration (exploratory)

A fixed archived XGBoost-Cox model supplies TreeSHAP explanations on the 2009–2010 and 2011–2012 selection cycles. In the latter cycle only, prespecified variables are multiplied by 1.25/1.5/1.6/0.85 in separate scenarios; a fifth scenario also artificially masks 20% of GGT and 25% of creatinine observations. These values are **illustrative injections** and are not observed historical laboratory assay corrections. The original TES and 90% mass rule and an importance-only 90% mass rule are applied to the two SHAP profiles. No outcome data are used for selecting panels.

Outputs report importance-rank Spearman, top-10 overlap, selected feature lists and Jaccard against unperturbed panel. This is a limited **measurement-distribution sensitivity** only. It does NOT prove TES predictive superiority under genuine data drift. A paper claim of improvement under transport requires retraining comparator panels under a controlled development-only design and evaluating subsequent held-out perturbed outcomes; such evidence is not furnished by this script alone.
''',encoding='utf-8')
if __name__=='__main__':main()
