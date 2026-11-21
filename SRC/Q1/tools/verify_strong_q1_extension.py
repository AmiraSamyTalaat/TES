from __future__ import annotations

import json
import math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CUR = ROOT / "outputs" / "strong_q1_extension"
REF = ROOT / "reference" / "strong_q1_extension"
TOL = 1e-6
CSV_FILES = [
    "TES_COMPONENT_ABLATION.csv",
    "TES_COMPONENT_SCORES.csv",
    "FEATURE_SELECTION_BASELINES.csv",
    "UNIVARIATE_COX_FEATURE_RANKING.csv",
    "SURVIVAL_METRICS_CENSORING_AWARE.csv",
    "CALIBRATION_SENSITIVITY.csv",
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
        if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]) and not pd.api.types.is_bool_dtype(a[col]) and not pd.api.types.is_bool_dtype(b[col]):
            av = pd.to_numeric(a[col], errors="coerce")
            bv = pd.to_numeric(b[col], errors="coerce")
            both_nan = av.isna() & bv.isna()
            mismatch_nan = av.isna() ^ bv.isna()
            if mismatch_nan.any():
                fail(f"{name}: NaN pattern differs in {col}")
            diff = (av[~both_nan] - bv[~both_nan]).abs()
            if len(diff) and float(diff.max()) > TOL:
                fail(f"{name}: numeric difference in {col}; max_abs_diff={float(diff.max())}")
        else:
            aa = a[col].fillna("").astype(str)
            bb = b[col].fillna("").astype(str)
            if not aa.equals(bb):
                fail(f"{name}: text values differ in {col}")
    print(f"PASS CSV: {name}")


def compare_json_values(a, b, path="root"):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            fail(f"JSON keys differ at {path}")
        for k in a:
            compare_json_values(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            fail(f"JSON list length differs at {path}")
        for i, (x, y) in enumerate(zip(a, b)):
            compare_json_values(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if math.isnan(float(a)) and math.isnan(float(b)):
            return
        if abs(float(a) - float(b)) > TOL:
            fail(f"JSON numeric difference at {path}: {a} vs {b}")
    else:
        if a != b:
            fail(f"JSON value differs at {path}: {a!r} vs {b!r}")


def main() -> int:
    if not CUR.exists() or not REF.exists():
        fail("Current or reference Strong-Q1 output directory is missing")
    for name in CSV_FILES:
        if not (CUR / name).exists() or not (REF / name).exists():
            fail(f"Missing {name}")
        compare_csv(name)
    for name in ["TES_FORMAL_SPECIFICATION.md"]:
        if (CUR / name).read_bytes() != (REF / name).read_bytes():
            fail(f"{name}: exact text differs")
        print(f"PASS exact text: {name}")
    cur_status = json.loads((CUR / "STRONG_Q1_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    ref_status = json.loads((REF / "STRONG_Q1_EXTENSION_STATUS.json").read_text(encoding="utf-8"))
    compare_json_values(cur_status, ref_status)
    for model in [
        "baseline_models/latest_cycle_shap_mass.ubj",
        "baseline_models/mean_shap_mass.ubj",
        "baseline_models/univariate_cox_top_11.ubj",
        "baseline_models/xgboost_gain_top_11.ubj",
    ]:
        if not (CUR / model).exists():
            fail(f"Missing regenerated model: {model}")
    report = {
        "status": "PASS",
        "numeric_tolerance": TOL,
        "reference": str(REF.relative_to(ROOT)),
        "current": str(CUR.relative_to(ROOT)),
        "note": "Numeric outputs agree with the archived Strong-Q1 reference within tolerance; model bytes are required to exist but are not required to be byte-identical across runtimes."
    }
    (ROOT / "STRONG_Q1_EXTENSION_VERIFICATION_STATUS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
