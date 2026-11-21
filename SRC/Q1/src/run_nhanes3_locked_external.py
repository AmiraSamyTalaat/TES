from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import numpy as np
import pandas as pd
import xgboost as xgb

from run_paired_bootstrap_validation import fast_c

EXT = ROOT / "external_nhanes3"
FEATURES = EXT / "processed_features" / "nhanes3_feature_cohort_locked_outcome.csv.gz"
MORTALITY = EXT / "locked_mortality" / "NHANES_III_MORT_2019_PUBLIC.dat"
MANIFEST = ROOT / "NHANES3_PRE_OUTCOME_EXECUTION_MANIFEST.json"
OUT = ROOT / "outputs" / "nhanes3_locked_external"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in manifest["critical_sha256"].items():
        actual = sha256(ROOT / relative)
        if actual != expected:
            mismatches.append({"file": relative, "expected": expected, "actual": actual})
    if mismatches:
        raise RuntimeError(f"EXTERNAL FREEZE INVALID: {mismatches}")
    return manifest


def load_model(model_path, status_path):
    model = xgb.Booster(); model.load_model(model_path)
    best = json.loads(status_path.read_text(encoding="utf-8"))["best_iteration"]
    return model, best


def predict(model, best, frame):
    names = model.feature_names
    matrix = xgb.DMatrix(frame[names].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=names, missing=np.nan)
    return model.predict(matrix, iteration_range=(0, best + 1))


def main() -> int:
    manifest = verify_manifest()
    protocol = json.loads((ROOT / "NHANES3_EXTERNAL_EVALUATION_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    feature_frame = pd.read_csv(FEATURES)
    mortality = pd.read_fwf(MORTALITY, colspecs=[(0, 6), (14, 15), (15, 16), (42, 45)],
                            names=["participant_id", "eligstat", "event", "time_months"])
    mortality = mortality.apply(pd.to_numeric, errors="coerce")
    cohort = feature_frame.merge(mortality, on="participant_id", how="inner", validate="one_to_one")
    cohort = cohort.loc[cohort["eligstat"].eq(1) & cohort["event"].notna() & cohort["time_months"].notna()].reset_index(drop=True)
    full_aft, full_best = load_model(ROOT / "outputs" / "aft_survival_pilot" / "xgboost_aft_model.ubj",
                                     ROOT / "outputs" / "aft_survival_pilot" / "AFT_SURVIVAL_STATUS.json")
    tes, tes_best = load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj",
                               ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json")
    cox, cox_best = load_model(ROOT / "outputs" / "xgboost_survival_pilot" / "xgboost_survival_model.ubj",
                               ROOT / "outputs" / "xgboost_survival_pilot" / "XGBOOST_SURVIVAL_STATUS.json")
    risks = {"full_aft": -predict(full_aft, full_best, cohort),
             "tes11_aft": -predict(tes, tes_best, cohort),
             "xgboost_cox": predict(cox, cox_best, cohort)}
    time, event = cohort["time_months"].to_numpy(float), cohort["event"].to_numpy(int)
    point = {name: fast_c(time, event, risk) for name, risk in risks.items()}
    rng = np.random.default_rng(protocol["seed"])
    comparisons = {"full_aft_minus_xgboost_cox": [], "tes11_minus_full_aft": []}
    rows = []
    for replicate in range(protocol["bootstrap_replicates"]):
        sample = rng.choice(len(cohort), len(cohort), replace=True)
        values = {name: fast_c(time[sample], event[sample], risk[sample]) for name, risk in risks.items()}
        comparisons["full_aft_minus_xgboost_cox"].append(values["full_aft"] - values["xgboost_cox"])
        comparisons["tes11_minus_full_aft"].append(values["tes11_aft"] - values["full_aft"])
        rows.append({"replicate": replicate + 1, **values,
                     "full_aft_minus_xgboost_cox": comparisons["full_aft_minus_xgboost_cox"][-1],
                     "tes11_minus_full_aft": comparisons["tes11_minus_full_aft"][-1]})
    summary = {}
    for name, values in comparisons.items():
        summary[name] = {"point": point["full_aft"] - point["xgboost_cox"] if name.startswith("full") else point["tes11_aft"] - point["full_aft"],
                         "mean_bootstrap": float(np.mean(values)),
                         "ci95": [float(x) for x in np.quantile(values, [0.025, 0.975])]}
    gates = protocol["success_gates"]
    gate = (point["full_aft"] >= gates["full_aft_c_minimum"] and
            summary["full_aft_minus_xgboost_cox"]["ci95"][0] >= gates["full_aft_vs_xgboost_cox_ci_lower_minimum"] and
            summary["tes11_minus_full_aft"]["ci95"][0] >= gates["tes11_vs_full_aft_ci_lower_minimum"])
    status = {"status": "PASS" if gate else "STOP", "freeze_verified": True,
              "manifest_sha256": sha256(MANIFEST), "rows": len(cohort), "events": int(event.sum()),
              "median_followup_months": float(np.median(time)), "point_c": point,
              "paired_comparisons": summary, "external_gate_pass": bool(gate),
              "no_fit_tuning_or_selection": True, "freeze_stage": manifest["stage"]}
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "nhanes3_external_bootstrap.csv.gz", index=False, compression="gzip")
    (OUT / "NHANES3_LOCKED_EXTERNAL_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

