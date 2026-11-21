from __future__ import annotations
import json, platform, sys, importlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/".python_packages"))
expected={"numpy":"2.5.2","scipy":"1.18.1","matplotlib":"3.11.1","xgboost":"3.4.1"}
problems=[]; versions={}
if sys.platform!="win32": problems.append(f"Frozen reviewer runtime is Windows-only; platform={sys.platform}")
if sys.version_info[:2]!=(3,12): problems.append(f"CPython 3.12 required; found {sys.version.split()[0]}")
if platform.architecture()[0]!="64bit": problems.append("64-bit Python required")
for name,want in expected.items():
    try:
        m=importlib.import_module(name); got=getattr(m,"__version__","unknown"); versions[name]=got
        if got!=want: problems.append(f"{name} version mismatch: expected {want}, found {got}")
    except Exception as exc: problems.append(f"{name} import failed: {exc}")
for name in ("pandas","docx"):
    try:
        m=importlib.import_module(name); versions[name]=getattr(m,"__version__","installed")
    except Exception as exc: problems.append(f"{name} import failed: {exc}")
report={"status":"PASS" if not problems else "FAIL","python":sys.version,"platform":platform.platform(),"packages":versions,"problems":problems}
print(json.dumps(report,indent=2))
raise SystemExit(0 if not problems else 1)
