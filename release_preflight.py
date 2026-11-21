#!/usr/bin/env python3
"""Offline release preflight, no network or participant data exposure.
Run from the extracted public release root: python release_preflight.py
"""
from pathlib import Path
import hashlib, json, sys
BASE=Path(__file__).resolve().parent
REQ_CODE=[
 'SRC/Q1/src/build_harmonized_panel.py',
 'SRC/Q1/src/build_survival_cohort.py',
 'SRC/Q1/src/run_tes_aft_pilot.py',
 'SRC/Q1/outputs/tes_aft_pilot/tes_aft_model.ubj',
 'SRC/Q1/outputs/tes_aft_pilot/TES_AFT_STATUS.json',
 'SRC/Q1/data/ANALYTE_REGISTRY.json',
 'SRC/Q1/external_nhanes3/EXTERNAL_SOURCE_REGISTRY.json',
 'reviewer_stage1.py','reviewer_stage2_selectors.py','reviewer_stage3_survival.py',
 'reviewer_stage4_survey.py','reviewer_stage5_shift.py','reviewer_stage6_participant_flow.py',
 'reviewer_stage7_leakage_free_baselines.py',
 'STAGE7_RESULTS/age_only_development_tuned.ubj','STAGE7_RESULTS/age_sex_development_tuned.ubj']
REQ_DATA=[
 'SRC/Q1/data/processed/nhanes_harmonized_panel.csv.gz',
 'SRC/Q1/data/processed/nhanes_survival_cohort.csv.gz',
 'SRC/Q1/data/processed/nhanes_survival_cohort_survey.csv.gz',
 'SRC/Q1/external_nhanes3/processed_features/nhanes3_feature_cohort_locked_outcome.csv.gz',
 'SRC/Q1/external_nhanes3/locked_mortality/NHANES_III_MORT_2019_PUBLIC.dat',
 *[f'SRC/Q1/data/raw_mortality/NHANES_{a}_{b}_MORT_2019_PUBLIC.dat' for a,b in [('1999','2000'),('2001','2002'),('2003','2004'),('2005','2006'),('2007','2008'),('2009','2010'),('2011','2012'),('2013','2014'),('2015','2016'),('2017','2018')]]]
missing_code=[q for q in REQ_CODE if not (BASE/q).is_file()]
missing_data=[q for q in REQ_DATA if not (BASE/q).is_file()]
manifest=BASE/'RELEASE_SHA256SUMS.txt'
checks=0;invalid=[];sha=None
if manifest.exists():
 for line in manifest.read_text().splitlines():
  if not line.strip(): continue
  try:h,p=line.split('  ',1)
  except ValueError: invalid.append('invalid manifest line');continue
  fp=BASE/p
  if not fp.is_file() or hashlib.sha256(fp.read_bytes()).hexdigest()!=h:invalid.append(p)
  else:checks+=1
report={'core_code_files_found':len(REQ_CODE)-len(missing_code),'core_code_files_required':len(REQ_CODE),
 'missing_core_code':missing_code,'required_individual_data_missing':missing_data,
 'manifest_files_verified':checks,'manifest_invalid':invalid,
 'ready_for_original_reanalysis':not(missing_code or missing_data or invalid),
 'ready_for_public_DOI':False,
 'note':'This tests package completeness, not successful reproduction, scientific validity, or author sign-off.'}
print(json.dumps(report,indent=2,ensure_ascii=False))
sys.exit(1 if missing_code or invalid else 0)
