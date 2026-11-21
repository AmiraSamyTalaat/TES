#!/usr/bin/env python3
"""Run the original frozen AFT train only inside a clean project copy; no original overwrites."""
import argparse, sys, platform, subprocess, shutil, json, hashlib, importlib.metadata as md
from pathlib import Path

def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def main():
 pa=argparse.ArgumentParser()
 pa.add_argument('--source-root',type=Path,required=True)
 pa.add_argument('--work-root',type=Path,required=True)
 args=pa.parse_args()
 src=args.source_root.resolve(); dst=args.work_root.resolve()
 report={'source_root':str(src),'work_root':str(dst),'python':sys.version,'platform':platform.platform()}
 requirements=src/'requirements_frozen_runtime_exact.txt'
 if not requirements.is_file():raise SystemExit('Missing exact runtime requirements in original source')
 expected={}
 for s in requirements.read_text(encoding='utf-8-sig').splitlines():
  if '==' in s and not s.strip().startswith('#'):
   a,b=s.split('==',1);expected[a.lower().strip()]=b.strip()
 versions={}
 for package in expected:
  try:versions[package]=md.version(package)
  except md.PackageNotFoundError:versions[package]='NOT_INSTALLED'
 report['expected_versions']=expected;report['actual_versions']=versions
 report['version_mismatches']={k:[v,versions.get(k)] for k,v in expected.items() if versions.get(k)!=v}
 if sys.version_info[:2]!=(3,12):report['python_mismatch']='CPython 3.12 required'
 if dst.exists():raise SystemExit(f'Work-root already exists: {dst} (protects previous runs)')
 if src==dst or src in dst.parents or dst in src.parents:
  raise SystemExit('Work root must be separate from source root')
 # A clean exact version check is necessary for the scientific comparison.
 if report['version_mismatches'] or report.get('python_mismatch'):
  output=src.parent/'EXACT_AFT_RUNTIME_PREFLIGHT_FAILED.json'
  output.write_text(json.dumps(report,indent=2),encoding='utf-8')
  print('Exact environment DOES NOT MATCH; no model training performed. Report:',output)
  return 2
 shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.python_packages'))
 original_status=json.loads((src/'outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json').read_text())
 original_model=src/'outputs/aft_survival_pilot/xgboost_aft_model.ubj'
 expected_hash=sha256(original_model)
 (dst/'outputs/aft_survival_pilot/xgboost_aft_model.ubj').unlink(missing_ok=True)
 (dst/'outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json').unlink(missing_ok=True)
 result=subprocess.run([sys.executable,str(dst/'src/run_aft_survival_pilot.py')],cwd=dst,capture_output=True,text=True)
 report['returncode']=result.returncode
 report['stdout_tail']=result.stdout[-6000:]
 report['stderr_tail']=result.stderr[-6000:]
 if result.returncode==0:
  new_status=json.loads((dst/'outputs/aft_survival_pilot/AFT_SURVIVAL_STATUS.json').read_text())
  new_model=dst/'outputs/aft_survival_pilot/xgboost_aft_model.ubj'
  report['archived_best_iteration']=original_status['best_iteration']
  report['refit_best_iteration']=new_status['best_iteration']
  report['archived_validation_c']=original_status['validation_harrell_c']
  report['refit_validation_c']=new_status['validation_harrell_c']
  report['archived_model_sha256']=expected_hash
  report['refit_model_sha256']=sha256(new_model)
  report['numeric_match_1e-10']=abs(new_status['validation_harrell_c']-original_status['validation_harrell_c'])<1e-10 and new_status['best_iteration']==original_status['best_iteration']
  report['binary_match']=report['archived_model_sha256']==report['refit_model_sha256']
 else:report['numeric_match_1e-10']=False
 output=dst/'EXACT_AFT_RETRAIN_COMPARISON.json'
 output.write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(json.dumps(report,indent=2))
 return 0 if result.returncode==0 else 3
if __name__=='__main__':raise SystemExit(main())
