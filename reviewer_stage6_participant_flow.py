#!/usr/bin/env python3
"""Reconstruct transparent participant flow using archived NHANES data sources.

Produces only aggregated counts by cycle. Does not alter original source or data.
"""
import json,argparse
from pathlib import Path
import pandas as pd

def mortality_read(path):
  return pd.read_fwf(path,colspecs=[(0,6),(14,15),(15,16),(42,45)],names=['participant_id','eligstat','event','time_months']).apply(pd.to_numeric,errors='coerce')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'SRC/Q1');ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parent/'STAGE6_RESULTS');o=ap.parse_args();r=o.root;out=o.out;out.mkdir(parents=True,exist_ok=True)
 p=pd.read_csv(r/'data/processed/nhanes_harmonized_panel.csv.gz',low_memory=False)
 final=pd.read_csv(r/'data/processed/nhanes_survival_cohort.csv.gz',low_memory=False)
 rows=[]
 for cycle,g in p.groupby('cycle',sort=True):
  m=mortality_read(r/'data/raw_mortality'/f"NHANES_{cycle.replace('-','_')}_MORT_2019_PUBLIC.dat")
  after=g.merge(m,on='participant_id',validate='one_to_one',how='inner')
  n_raw=len(g);n_merged=len(after)
  adult=after[after.age_years.ge(20)];elig=adult[adult.eligstat.eq(1)];valid=elig[elig.event.notna()&elig.time_months.notna()&elig.time_months.ge(0)]
  assert len(valid)==len(final[final.cycle.eq(cycle)]),(cycle,len(valid),len(final[final.cycle.eq(cycle)]))
  rows.append({'cycle':cycle,'harmonized_laboratory_rows':n_raw,'matched_public_mortality_rows':n_merged,
  'excluded_no_mortality_match':n_raw-n_merged,'excluded_age_below_20_or_missing':n_merged-len(adult),
  'excluded_ineligible_linkage':len(adult)-len(elig),'excluded_invalid_or_missing_followup':len(elig)-len(valid),
  'final_analytic_rows':len(valid),'observed_deaths':int(valid.event.sum())})
 d=pd.DataFrame(rows)
 d.loc[len(d)]=dict(cycle='ALL_1999_2018',**{c:int(d[c].sum()) for c in d if c!='cycle'})
 d.to_csv(out/'PARTICIPANT_FLOW_1999_2018_VERIFIED.csv',index=False)
 # Earlier-era independent rebuild from adult/lab combined source; public registry file is already adult-lab age 20 & weight eligible.
 ext=pd.read_csv(r/'external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz')
 mort=mortality_read(r/'external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat')
 merged=ext.merge(mort,on='participant_id',how='inner',validate='one_to_one')
 elig=merged.loc[merged.eligstat.eq(1)]
 valid=elig.loc[elig.event.notna()&elig.time_months.notna()&elig.time_months.ge(0)]
 assert len(valid)==16519,(len(valid),'expected 16519')
 summary={'nhanesIII_adult_lab_age20_weight_eligible_features':len(ext),'nhanesIII_matched_mortality':len(merged),'nhanesIII_linkage_ineligible':len(merged)-len(elig),'nhanesIII_missing_followup_or_outcome':len(elig)-len(valid),'nhanesIII_analysis_n':len(valid),'nhanesIII_deaths':int(valid.event.sum()),'nhanesIII_raw_adult_rows':20050,'nhanesIII_raw_lab_rows':29314,
  'note':'adult/lab source counts come from the archived feature cohort status and must not be misrepresented as a single mutually exclusive participant eligibility funnel.'}
 (out/'NHANES3_PARTICIPANT_FLOW_VERIFIED.json').write_text(json.dumps(summary,indent=2))
 print(d.tail(1).to_string(index=False));print(summary)
if __name__=='__main__':main()
