#!/usr/bin/env python3
"""Post-hoc external-era within-cohort IPCW metrics, subgroup and frozen C comparisons.
Original protocol and results remain unchanged; no survey-design inference here.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from numba import njit
import xgboost as xgb
from reviewer_stage1 import CensorKM,ranks_of_risk,concordance,c_bstrap,load_booster,pred,brier
R=Path(__file__).resolve().parent/'SRC'/'Q1'
OUT=Path(__file__).resolve().parent/'STAGE3_RESULTS';OUT.mkdir(exist_ok=True)
NON_FEATURES={"participant_id", "cycle", "partition", "analysis_split", "eligstat", "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int", "permth_exm", "event", "time_months"}
@njit(cache=True)
def fast_uno(t,ev,ranks,n_rank,g,tau):
 order=np.argsort(-t);tree=np.zeros(n_rank+2,np.int64)
 seen=0;num=0.;den=0.;pos=0
 while pos<len(order):
  end=pos+1;time=t[order[pos]]
  while end<len(order) and t[order[end]]==time:end+=1
  for j in range(pos,end):
   idx=order[j]
   if ev[idx]!=1 or time>=tau or g[idx]<=1e-8:continue
   a=ranks[idx];low=0;le=0;b=a
   while b>0:low+=tree[b];b-=b&-b
   b=a+1
   while b>0:le+=tree[b];b-=b&-b
   weight=1/(g[idx]*g[idx]);num+=weight*(low+.5*(le-low));den+=weight*seen
  for j in range(pos,end):
   b=ranks[order[j]]+1
   while b<len(tree):tree[b]+=1;b+=b&-b
   seen+=1
  pos=end
 return float(num/den) if den>0 else np.nan

def time_auc(t,e,risk,km,h):
 cases=(e==1)&(t<=h);controls=t>h
 if not np.any(cases) or not np.any(controls):return float('nan')
 risk_case=risk[cases];cr=np.sort(risk[controls]);w=1/np.maximum(km.G(t[cases],True),1e-8)
 less=np.searchsorted(cr,risk_case,'left');more=np.searchsorted(cr,risk_case,'right')
 return float(np.sum(w*(less+.5*(more-less)))/(len(cr)*np.sum(w)))

fr=pd.read_csv(R/'data/processed/nhanes_survival_cohort.csv.gz')
exf=pd.read_csv(R/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
exm=pd.read_fwf(R/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
ex=exf.merge(exm,on='participant_id',validate='one_to_one')
ex=ex.loc[ex.eligstat.eq(1)&ex.event.notna()&ex.time_months.notna()].reset_index(drop=True)
cohorts={'2009-2012 validation':fr[fr.analysis_split=='validation'].reset_index(drop=True),'2013-2014 audit':fr[fr.analysis_split=='calibration'].reset_index(drop=True),'2015-2016 frozen confirmation':fr[fr.cycle=='2015-2016'].reset_index(drop=True),'2017-2018 stress':fr[fr.cycle=='2017-2018'].reset_index(drop=True),'NHANES III earlier era':ex}
features=[c for c in fr if c not in NON_FEATURES]
tes_panel=json.loads((R/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())['selected_features']
mx,ix=load_booster(R,'outputs/xgboost_survival_pilot/xgboost_survival_model.ubj','outputs/xgboost_survival_pilot/XGBOOST_SURVIVAL_STATUS.json')
ma,ia=load_booster(R,'outputs/aft_survival_pilot/xgboost_aft_model.ubj','outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json')
mt,it=load_booster(R,'outputs/tes_aft_pilot/tes_aft_model.ubj','outputs/tes_aft_pilot/TES_AFT_STATUS.json')
metrics=[];groups=[];contrasts=[]
for k,(name,d) in enumerate(cohorts.items()):
 t=d.time_months.to_numpy(float);e=d.event.to_numpy(int);km=CensorKM(t,e)
 risk={'XGBoost-Cox':pred(mx,ix,d,features),'Full AFT':-pred(ma,ia,d,features),'TES-11 AFT':-pred(mt,it,d,tes_panel)}
 for label,r in risk.items():
  rr,nn=ranks_of_risk(r);g=km.G(t,True)
  for h in ([24] if '2017' in name else [24,60]):
   metrics.append({'cohort':name,'model':label,'horizon_months':h,'uno_c_cohort_km':fast_uno(t,e,rr,nn,g,float(h)),'cumulative_dynamic_auc_cohort_km':time_auc(t,e,r,km,float(h)),'G_at_horizon':float(km.G(h)),'N':len(d),'n_deaths':int(e.sum())})
  for group,sub in {'Male':d.sex_code.eq(1),'Female':d.sex_code.eq(2),'Age 20–39':d.age_years.between(20,39.999),'Age 40–59':d.age_years.between(40,59.999),'Age >=60':d.age_years.ge(60)}.items():
   ixsub=np.asarray(sub.to_numpy(),bool);t2=t[ixsub];e2=e[ixsub]
   groups.append({'cohort':name,'model':label,'subgroup':group,'N':len(t2),'deaths':int(e2.sum()),'harrell_c':concordance(t2,e2,r[ixsub]) if int(e2.sum())>=2 else np.nan,'interpretation_flag':'CAUTION: sparse deaths' if int(e2.sum())<20 else 'descriptive only'})
 if name in ['2015-2016 frozen confirmation','2017-2018 stress']:
  res=c_bstrap(t,e,risk['TES-11 AFT'],risk['Full AFT'],n_boot=400,seed=20261125+k)
  contrasts.append({'cohort':name,**res,'comparison':'TES-11 AFT minus Full AFT','classification':'exploratory post-hoc, unchanged frozen saved models'})
 print(name,'N',len(d),'G(24)',float(km.G(24)),'TES Uno C24',metrics[-1 if False else -2]['uno_c_cohort_km'] if len(metrics)>1 else '',flush=True)
pd.DataFrame(metrics).to_csv(OUT/'CENSORING_AWARE_COHORT_SPECIFIC_UNO_AUC.csv',index=False)
pd.DataFrame(groups).to_csv(OUT/'SUBGROUP_C_INDEX_BY_ERA.csv',index=False)
pd.DataFrame(contrasts).to_csv(OUT/'TES_VS_FULL_AFT_CONFIRMATION_STRESS.csv',index=False)
(OUT/'STAGE3_STATUS.json').write_text(json.dumps({'classification':'post-hoc supplemental analysis','missing':'survey-design variance, temporal drift experiment, linked mortality version/assay crosswalk, TRIPOD flow diagram','method':'Censor distribution fit separately per evaluation era (KM); fixed model predictions; Uno C pairs strictly time ordered, no same-time comparables; subgroup C descriptive; Bootstrap 400 pairs for 2015–2018 TES vs Full AFT','outcomes_used_for_refitting':'none'},indent=2))
