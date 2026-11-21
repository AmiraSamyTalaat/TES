#!/usr/bin/env python3
"""Post-hoc paired bootstrap CIs for archived alternative selectors (Tables 6–8)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb
from reviewer_stage1 import c_bstrap, concordance,make_aft,pred
ROOT=Path(__file__).resolve().parent/'SRC'/'Q1'
OUT=Path(__file__).resolve().parent/'STAGE2_RESULTS'; OUT.mkdir(exist_ok=True)
frame=pd.read_csv(ROOT/'data/processed/nhanes_survival_cohort.csv.gz')
audit=frame.loc[frame.analysis_split.eq('calibration')].reset_index(drop=True)
features=pd.read_csv(ROOT/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
mort=pd.read_fwf(ROOT/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')
ext=features.merge(mort,on='participant_id',validate='one_to_one')
ext=ext.loc[ext.eligstat.eq(1)&ext.event.notna()&ext.time_months.notna()].reset_index(drop=True)
name_map={
 'TES-11':'outputs/tes_aft_pilot/tes_aft_model.ubj',
 'Mean-SHAP mass':'outputs/strong_q1_extension/baseline_models/mean_shap_mass.ubj',
 'Latest-cycle SHAP mass':'outputs/strong_q1_extension/baseline_models/latest_cycle_shap_mass.ubj',
 'XGBoost gain top-11':'outputs/strong_q1_extension/baseline_models/xgboost_gain_top_11.ubj',
 'Univariate Cox top-11':'outputs/strong_q1_extension/baseline_models/univariate_cox_top_11.ubj',
 'Cox stability-selection consensus top-11':'outputs/strong_q1_stability_extension/models/cox_stability_consensus.ubj',
 'Resampling-consensus SHAP top-11':'outputs/strong_q1_stability_extension/models/shap_resampling_consensus.ubj',
 'TES 92.5%-mass (13)':'outputs/strong_q1_stability_extension/models/sensitivity_k13_457562.ubj',
 'TES 95%-mass (15)':'outputs/strong_q1_stability_extension/models/sensitivity_k15_366866.ubj',
}
tes_panel=json.loads((ROOT/'outputs/tes_aft_pilot/TES_AFT_STATUS.json').read_text())['selected_features']
base=pd.read_csv(ROOT/'outputs/strong_q1_extension/FEATURE_SELECTION_BASELINES.csv')
stab=pd.read_csv(ROOT/'outputs/strong_q1_stability_extension/STABILITY_AWARE_BASELINE_COMPARISON.csv')
sens=pd.read_csv(ROOT/'outputs/strong_q1_stability_extension/TES_HYPERPARAMETER_SENSITIVITY.csv')
feats={'TES-11':tes_panel}
for tab in [base,stab]:
 for name,g in tab.groupby('method'):
  feats[name]=g.iloc[0]['selected_features'].split('; ')
for n,k in [('TES 92.5%-mass (13)',13),('TES 95%-mass (15)',15)]:
 feats[n]=sens.loc[sens.selected_feature_count.eq(k)].iloc[0]['selected_features'].split('; ')
models={}
for name,path in name_map.items():
 b=xgb.Booster();b.load_model(ROOT/path)
 it=int(b.attr('best_iteration'))
 models[name]=(b,it,feats[name])
rows=[]
for ci,(cohort_name,d) in enumerate([('2013-2014 audit',audit),('NHANES III external',ext)]):
 t=d.time_months.to_numpy(float);e=d.event.to_numpy(int)
 risk={n:-pred(m,it,d,p) for n,(m,it,p) in models.items()}
 for j,name in enumerate(models):
  if name=='TES-11':continue
  summary=c_bstrap(t,e,risk['TES-11'],risk[name],n_boot=300,seed=20261120+ci*100+j)
  summary.update({'cohort':cohort_name,'comparison':'TES-11 minus '+name,'tes_c_index':concordance(t,e,risk['TES-11']),'other_c_index':concordance(t,e,risk[name]),'analysis':'exploratory post-hoc paired bootstrap; identical participant resamples'})
  rows.append(summary)
  print(cohort_name,name,round(summary['delta_c'],6),'CI',round(summary['ci_lower'],6),round(summary['ci_upper'],6),flush=True)
pd.DataFrame(rows).to_csv(OUT/'SELECTOR_PAIRED_BOOTSTRAP_TABLES_6_8.csv',index=False)
(OUT/'STAGE2_STATUS.json').write_text(json.dumps({'status':'DONE','n_comparisons':len(rows),'source':'existing frozen and post-hoc saved models','bootstrap_repetitions':300,'note':'CIs describe sampling uncertainty for model-score differences on fixed cohorts and are not evidence of clinical relevance or prespecified superiority'},indent=2),encoding='utf-8')
