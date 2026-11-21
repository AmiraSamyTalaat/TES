"""Audit CDC-correct pooled MEC weights. Requires original local Q1 raw files; never modifies them."""
import json, argparse
from pathlib import Path
import numpy as np, pandas as pd
P=argparse.ArgumentParser();P.add_argument('--q1-root',required=True);P.add_argument('--out',default='WEIGHT_AUDIT_OUTPUT.csv');a=P.parse_args()
r=Path(a.q1_root);c=pd.read_csv(r/'data/processed/nhanes_survival_cohort_survey.csv.gz')
reg=json.loads((r/'data/PUBLIC_SOURCE_REGISTRY.json').read_text())['cycles'];rows=[]
for s in reg:
 cy=s['cycle'];demo=pd.read_sas(r/'data/raw'/s['partition']/cy/(s['demographics']+'.XPT'),format='xport',encoding='latin1')
 subset=c.loc[c.cycle.eq(cy),['participant_id','age_years']].merge(demo[['SEQN','WTMEC2YR']+(['WTMEC4YR'] if 'WTMEC4YR' in demo else [])].rename(columns={'SEQN':'participant_id'}),on='participant_id',validate='one_to_one')
 if cy in ('1999-2000','2001-2002'):
  assert 'WTMEC4YR' in subset; w=(2/10)*subset.WTMEC4YR
 else:w=subset.WTMEC2YR/10
 assert (w>=0).all() and np.isfinite(w).all()
 rows.append({'cycle':cy,'N':len(subset),'corrected_weight_sum':w.sum(),'weighted_age':np.average(subset.age_years,weights=w)})
pd.DataFrame(rows).to_csv(a.out,index=False);print('Wrote',a.out)
