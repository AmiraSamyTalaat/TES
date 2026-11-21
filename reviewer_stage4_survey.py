#!/usr/bin/env python3
"""Exploratory survey-design sensitivity for OPHRP-2026-0654.

Weighted Harrell concordance is computed using pair weights w_i*w_j, with
stratified delete-1-PSU jackknife standard errors. These are DESCRIPTIVE
sensitivity results; no calibration, complex-survey survival model refit or
population-based clinical validity is claimed.

For 2009-2012 (two 2-year cycles, both after 2001-2002) MEC 2-year weights
are divided by 2. For single cycles, original 2-year MEC weights are used.
Development 1999-2008 is not analyzed here; pooled 20-year weights in the
source archive should NOT be used because NHANES 1999-2000 requires an
additional special weighting convention. NHANES III analysis uses its
provided exam weights and pseudo-design variables (separate survey).
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from numba import njit
from reviewer_stage1 import load_booster, pred

@njit(cache=True)
def weighted_c_core(t, event, ranks, n_rank, weights):
    order=np.argsort(-t)
    tree=np.zeros(n_rank+2, dtype=np.float64)
    sum_w=0.0; numerator=0.0; denominator=0.0
    k=0
    while k<len(order):
        j=k+1
        while j<len(order) and t[order[j]]==t[order[k]]:j+=1
        for z in range(k,j):
            ix=order[z]
            if event[ix]!=1 or weights[ix]<=0:continue
            r=ranks[ix]
            less=0.0;a=r
            while a>0:
                less+=tree[a];a-=a&-a
            at_most=0.0;a=r+1
            while a>0:
                at_most+=tree[a];a-=a&-a
            wi=weights[ix]
            numerator+=wi*(less+0.5*(at_most-less))
            denominator+=wi*sum_w
        for z in range(k,j):
            ix=order[z]
            wi=weights[ix]
            if wi<=0:continue
            a=ranks[ix]+1
            while a<len(tree):tree[a]+=wi;a+=a&-a
            sum_w+=wi
        k=j
    return numerator/denominator if denominator>0 else np.nan

def weighted_harrell_jackknife(d,t,e,score,weight,design_stratum,design_psu):
    w=np.asarray(weight,float)
    if not np.all(np.isfinite(w)) or np.any(w<0):raise ValueError('Invalid sampling weights')
    if not np.all(np.isfinite(score)):raise ValueError('Invalid risk scores')
    # Overall scale of weights does not affect the ratio, but normalization
    # helps floating-point stability.
    w=w/(np.mean(w[w>0]))
    vals, ranks=np.unique(np.asarray(score,float),return_inverse=True)
    ranks=ranks.astype(np.int64)
    tt=np.asarray(t,float);ee=np.asarray(e,np.int64)
    estimate=weighted_c_core(tt,ee,ranks,len(vals),w)
    strata=np.asarray(design_stratum).astype(str)
    psu=np.asarray(design_psu).astype(str)
    variance=0.;n_reps=0;singles=0;strata_used=0
    for s in np.unique(strata):
        indices=np.where(strata==s)[0]
        groups=np.unique(psu[indices]);m=len(groups)
        if m<2:
            singles+=1;continue
        replicates=[]
        for g in groups:
            ww=w.copy()
            rem=indices[psu[indices]==g]
            keep=indices[psu[indices]!=g]
            ww[rem]=0
            ww[keep]*=m/(m-1)
            replicates.append(weighted_c_core(tt,ee,ranks,len(vals),ww))
            n_reps+=1
        reps=np.asarray(replicates,float)
        if np.all(np.isfinite(reps)):
            variance+=((m-1)/m)*np.sum((reps-np.mean(reps))**2)
            strata_used+=1
    se=np.sqrt(variance) if strata_used else np.nan
    return {'weighted_harrell_c':float(estimate),'jackknife_design_se':float(se),
     'ci_lower_normal':float(estimate-1.96*se) if np.isfinite(se) else None,
     'ci_upper_normal':float(estimate+1.96*se) if np.isfinite(se) else None,
     'n_strata':len(np.unique(strata)),'n_strata_usable':strata_used,
     'n_lonely_strata':singles,'n_jackknife_replicates':n_reps}

def main():
    pa=argparse.ArgumentParser();pa.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'SRC/Q1');pa.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'STAGE4_RESULTS')
    opt=pa.parse_args();r=opt.root;out=opt.out;out.mkdir(parents=True,exist_ok=True)
    ds=pd.read_csv(r/'data/processed/nhanes_survival_cohort_survey.csv.gz',low_memory=False)
    early=ds[ds.cycle.isin(['2009-2010','2011-2012'])].copy()
    eras=[('2009-2012 validation',early),('2013-2014 audit',ds[ds.cycle.eq('2013-2014')].copy()),('2015-2016 confirmation',ds[ds.cycle.eq('2015-2016')].copy()),('2017-2018 stress',ds[ds.cycle.eq('2017-2018')].copy())]
    ex=pd.read_csv(r/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
    mort=pd.read_fwf(r/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
    ex=ex.merge(mort,on='participant_id',validate='one_to_one');ex=ex.loc[ex.eligstat.eq(1)&ex.event.notna()&ex.time_months.notna()].copy()
    eras.append(('NHANES III earlier era',ex))
    nonfeatures={'participant_id','cycle','partition','analysis_split','eligstat','mortstat','ucod_leading','diabetes','hyperten','permth_int','permth_exm','event','time_months','exam_weight_2yr','survey_stratum','survey_psu','pooled_exam_weight_20yr'}
    features=[c for c in ds if c not in nonfeatures]
    panel=json.loads((r/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())['selected_features']
    models={}
    for name,mp,sp,cols in [
      ('XGBoost-Cox','outputs/xgboost_survival_pilot/xgboost_survival_model.ubj','outputs/xgboost_survival_pilot/XGBOOST_SURVIVAL_STATUS.json',features),
      ('Full AFT','outputs/aft_survival_pilot/xgboost_aft_model.ubj','outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json',features),
      ('TES-11 AFT','outputs/tes_aft_pilot/tes_aft_model.ubj','outputs/tes_aft_pilot/TES_AFT_STATUS.json',panel)]:
        models[name]=(*load_booster(r,mp,sp),cols)
    results=[]
    for en,d in eras:
        d=d.reset_index(drop=True)
        if en.startswith('NHANES III'):
            wei=d.exam_weight.to_numpy(float)
            stra='III:'+d.survey_stratum.astype(str)
            psu=d.survey_psu
            weighting='NHANES III examination weight; NCHS pseudo-design, separate era'
        else:
            wei=d.exam_weight_2yr.to_numpy(float)
            if en.startswith('2009'):
                wei=wei/2.
                weighting='2009-2012 4-year combined 2-cycle weight, MEC 2-year weight / 2'
            else:weighting='Single 2-year MEC examination weight'
            stra=d.cycle.astype(str)+':'+d.survey_stratum.astype(str)
            psu=d.survey_psu
        t=d.time_months.to_numpy(float);e=d.event.to_numpy(int)
        for name,(model,it,cols) in models.items():
            score=pred(model,it,d,cols)
            if name!='XGBoost-Cox':score=-score
            result=weighted_harrell_jackknife(d,t,e,score,wei,stra,psu)
            results.append({'cohort':en,'model':name,'N':len(d),'events':int(e.sum()),'weighting_rule':weighting,**result})
            print(en,name,'C',round(result['weighted_harrell_c'],5),'SE',round(result['jackknife_design_se'],5),flush=True)
    pd.DataFrame(results).to_csv(out/'SURVEY_DESIGN_WEIGHTED_HARRELL_JACKKNIFE.csv',index=False)
    (out/'METHODS_AND_WARNINGS.md').write_text('''# Exploratory survey-design sensitivity

Weighted Harrell's C is calculated using products of examination sampling weights for each comparable pair; ties in time excluded and tied risks receive half credit. Stratum-specific delete-one-PSU jackknife estimates sampling uncertainty using remaining PSU weight inflation m/(m−1), and the sum over strata of (m−1)/m × sum (replicate−replicate_mean)^2. The normal-approximation CI is indicative only. No refitting was done.

**Scope**: 2009–2012 validation (2009/2011 two-cycle weights /2), 2013–14, 2015–16, 2017–18 (each 2-year MEC weights), and earlier NHANES III (separate design and exam weights). Cycle names are prepended to pseudo-stratum identifiers. 1999–2008 pooled development is excluded because 1999–2000 requires special treatment: do NOT use the 20-year archived `pooled_exam_weight_20yr` column as-is. Consult NCHS rules for any analysis that pools 1999–2000.

**Limitations**: weighted pairwise Harrell's concordance is a descriptive sensitivity, NOT a design-based survival probability calibration analysis, survival regression coefficient variance, or statistically rigorous confidence interval for a clinically deployable model. Cluster design is approximated using public-use masked design variables. NCHS weight appropriateness should be independently reviewed for individual laboratory analytes, fasting subsamples, and NHANES III. No adjustments for multiple testing.

Official guidance: https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx and https://wwwn.cdc.gov/nchs/nhanes/analyticguidelines.aspx
''',encoding='utf8')
    (out/'STAGE4_STATUS.json').write_text(json.dumps({'status':'COMPLETE_EXPLORATORY','n_rows':len(results),'claim':'survey-design-sensitive weighted Harrell concordance, fixed models; not causal/clinical inference','development_1999_2008_excluded':True,'survey_weight_caveats':'original archive pooled_exam_weight_20yr is NOT compliant for combining 1999–2000 with later eras. Laboratory subsample-specific weights need evaluation.'},indent=2))
if __name__=='__main__':main()
