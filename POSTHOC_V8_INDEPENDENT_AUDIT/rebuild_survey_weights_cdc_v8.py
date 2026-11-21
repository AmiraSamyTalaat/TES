"""Add CDC-consistent pooled MEC examination weights without modifying source files.

This script requires the original downloaded NHANES XPT files; no person-level
records are included in the public GitHub archive. Its output is a *local*
individual-level intermediate and must not be committed to public version control.

Example:
  python rebuild_survey_weights_cdc_v8.py --q1-root /path/to/Q1 --output /private/output.csv.gz
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('--q1-root',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
root=a.q1_root
cohort=pd.read_csv(root/'data/processed/nhanes_survival_cohort.csv.gz')
reg=json.loads((root/'data/PUBLIC_SOURCE_REGISTRY.json').read_text())['cycles']
parts=[]
for s in reg:
 cycle=s['cycle']; path=root/'data/raw'/s['partition']/cycle/(s['demographics']+'.XPT')
 demo=pd.read_sas(path,format='xport',encoding='latin1')
 keys=['SEQN','WTMEC2YR','SDMVSTRA','SDMVPSU']
 if cycle in ('1999-2000','2001-2002'): keys.append('WTMEC4YR')
 if not all(x in demo.columns for x in keys):
  raise RuntimeError(f'{cycle}: required CDC weight/design fields are missing')
 data=(cohort.loc[cohort.cycle.eq(cycle)]
       .merge(demo[keys].rename(columns={'SEQN':'participant_id'}),on='participant_id',validate='one_to_one'))
 if cycle in ('1999-2000','2001-2002'):
  data['corrected_pooled_mec_weight_1999_2018']=0.2*data['WTMEC4YR']
  data['source_weight_rule']='1999-2002: 2/10 x WTMEC4YR'
 else:
  data['corrected_pooled_mec_weight_1999_2018']=0.1*data['WTMEC2YR']
  data['source_weight_rule']='2003-2018: 1/10 x WTMEC2YR'
 data=data.rename(columns={'WTMEC2YR':'exam_weight_2yr','SDMVSTRA':'survey_stratum','SDMVPSU':'survey_psu'})
 if data['corrected_pooled_mec_weight_1999_2018'].isna().any() or (data['corrected_pooled_mec_weight_1999_2018']<0).any():
  raise RuntimeError(f'{cycle}: invalid pooled weights')
 parts.append(data)
result=pd.concat(parts,ignore_index=True)
assert len(result)==len(cohort)
print('N',len(result))
train=result.loc[result.analysis_split.eq('train')]
print('Development 1999-2008 weighted mean age',np.average(train.age_years,weights=train.corrected_pooled_mec_weight_1999_2018))
a.output.parent.mkdir(parents=True,exist_ok=True)
result.to_csv(a.output,index=False,compression='gzip')
print('PRIVATE local output only; do not upload',a.output)
