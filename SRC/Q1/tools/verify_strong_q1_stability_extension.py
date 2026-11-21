from __future__ import annotations
import json, math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "outputs" / "strong_q1_stability_extension"
REF = ROOT / "reference" / "strong_q1_stability_extension"
TOL = 1e-6
CSV_FILES = [
    "PANEL_SELECTION_STABILITY_SUMMARY.csv",
    "PANEL_SELECTION_FREQUENCIES.csv",
    "STABILITY_AWARE_BASELINE_COMPARISON.csv",
    "TES_HYPERPARAMETER_SENSITIVITY.csv",
]
MODEL_FILES = [
    "models/cox_stability_consensus.ubj",
    "models/sensitivity_k13_457562.ubj",
    "models/sensitivity_k15_366866.ubj",
    "models/shap_resampling_consensus.ubj",
]

def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)

def compare_csv(name: str) -> None:
    a = pd.read_csv(CUR / name)
    b = pd.read_csv(REF / name)
    if list(a.columns) != list(b.columns) or a.shape != b.shape:
        fail(f"{name}: schema/shape differs: current={a.shape}, reference={b.shape}")
    for col in a.columns:
        if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]) and not pd.api.types.is_bool_dtype(a[col]):
            av = pd.to_numeric(a[col], errors="coerce")
            bv = pd.to_numeric(b[col], errors="coerce")
            both_nan = av.isna() & bv.isna()
            if (av.isna() ^ bv.isna()).any():
                fail(f"{name}: NaN pattern differs in {col}")
            diff = (av[~both_nan] - bv[~both_nan]).abs()
            if len(diff) and float(diff.max()) > TOL:
                fail(f"{name}: numeric difference in {col}; max_abs_diff={float(diff.max())}")
        else:
            if not a[col].fillna("").astype(str).equals(b[col].fillna("").astype(str)):
                fail(f"{name}: text values differ in {col}")
    print(f"PASS CSV: {name}")

def compare_json(a, b, path="root"):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b): fail(f"JSON keys differ at {path}")
        for k in a: compare_json(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): fail(f"JSON list length differs at {path}")
        for i,(x,y) in enumerate(zip(a,b)): compare_json(x,y,f"{path}[{i}]")
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)) and not isinstance(a,bool) and not isinstance(b,bool):
        if math.isnan(float(a)) and math.isnan(float(b)): return
        if abs(float(a)-float(b)) > TOL: fail(f"JSON numeric difference at {path}: {a} vs {b}")
    elif a != b:
        fail(f"JSON value differs at {path}: {a!r} vs {b!r}")

def main() -> int:
    if not CUR.is_dir() or not REF.is_dir(): fail("Current or reference V1.2 extension directory is missing")
    for name in CSV_FILES:
        if not (CUR/name).is_file() or not (REF/name).is_file(): fail(f"Missing {name}")
        compare_csv(name)
    cur = json.loads((CUR/"STRONG_Q1_STABILITY_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    ref = json.loads((REF/"STRONG_Q1_STABILITY_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    compare_json(cur, ref)
    if cur.get("status") != "PASS": fail("status is not PASS")
    if cur.get("frozen_confirmatory_artifacts_modified") is not False: fail("frozen-artifact flag invalid")
    if cur.get("resampling",{}).get("replicates") != 200: fail("resampling replicate count != 200")
    if not cur.get("sensitivity",{}).get("primary_90pct_panel_invariant_across_direction_thresholds"): fail("primary panel invariance failed")
    if not cur.get("sensitivity",{}).get("primary_90pct_k_bounds_inactive"): fail("primary K-bounds inactivity failed")
    d = pd.read_csv(CUR/"PANEL_SELECTION_STABILITY_SUMMARY.csv")
    tes = d[d.selector.eq("TES 90%-mass")]
    if len(tes) != 1 or float(tes.iloc[0].nogueira_stability) < 0.90: fail("TES stability unexpectedly low/missing")
    sens = pd.read_csv(CUR/"TES_HYPERPARAMETER_SENSITIVITY.csv")
    if len(sens) != 9: fail("sensitivity grid must contain 9 rows")
    for m in MODEL_FILES:
        if not (CUR/m).is_file(): fail(f"Missing regenerated model: {m}")
    for p in [ROOT/"publication"/"strong_q1_v1_2"/"PROVLAB_STRONG_Q1_MANUSCRIPT_CLEAN_V1_2_0.docx", ROOT/"publication"/"strong_q1_v1_2"/"PROVLAB_STRONG_Q1_MANUSCRIPT_REVIEW_V1_2_0.docx"]:
        if not p.is_file(): fail(f"Missing manuscript: {p.name}")
    report = {
        "status":"PASS", "numeric_tolerance":TOL,
        "current":str(CUR.relative_to(ROOT)), "reference":str(REF.relative_to(ROOT)),
        "resamples":200,
        "note":"V1.2 stability/sensitivity numeric outputs agree with archived reference within tolerance; regenerated model bytes are required to exist but are not required to be byte-identical across runtimes."
    }
    (ROOT/"STRONG_Q1_V1_2_VERIFICATION_STATUS.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
