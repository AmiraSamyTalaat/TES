from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import numpy as np
import pandas as pd
import xgboost as xgb

from run_aft_survival_pilot import aft_matrix
from run_cox_baseline import COHORT, NON_FEATURES
from run_paired_bootstrap_validation import fast_c

OUT = ROOT / "outputs" / "aft_vs_cox_bootstrap"


def main() -> int:
    protocol = json.loads((ROOT / "AFT_VS_COX_BOOTSTRAP_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy().reset_index(drop=True)
    features = [c for c in frame.columns if c not in NON_FEATURES]
    aft_dir = ROOT / "outputs" / "aft_survival_pilot"
    aft = xgb.Booster(); aft.load_model(aft_dir / "xgboost_aft_model.ubj")
    aft_best = json.loads((aft_dir / "AFT_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    aft_risk = -aft.predict(aft_matrix(validation, features), iteration_range=(0, aft_best + 1))
    cox_dir = ROOT / "outputs" / "xgboost_survival_pilot"
    cox = xgb.Booster(); cox.load_model(cox_dir / "xgboost_survival_model.ubj")
    cox_best = json.loads((cox_dir / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    matrix = xgb.DMatrix(validation[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    cox_risk = cox.predict(matrix, iteration_range=(0, cox_best + 1))
    time, event = validation["time_months"].to_numpy(float), validation["event"].to_numpy(int)
    cycle_indices = [np.flatnonzero(validation["cycle"].eq(c).to_numpy()) for c in sorted(validation["cycle"].unique())]
    rng = np.random.default_rng(protocol["seed"])
    rows = []
    for replicate in range(protocol["replicates"]):
        sample = np.concatenate([rng.choice(idx, len(idx), replace=True) for idx in cycle_indices])
        c_aft = fast_c(time[sample], event[sample], aft_risk[sample])
        c_cox = fast_c(time[sample], event[sample], cox_risk[sample])
        rows.append((replicate + 1, c_aft, c_cox, c_aft - c_cox))
    result = pd.DataFrame(rows, columns=["replicate", "aft_c", "xgboost_cox_c", "paired_gain"])
    lower, upper = np.quantile(result["paired_gain"], [0.025, 0.975])
    status = {"status": "SUPERIOR" if lower > 0 else "NONINFERIOR_NO_SUPERIORITY",
              "replicates": len(result), "mean_aft_c": float(result["aft_c"].mean()),
              "mean_xgboost_cox_c": float(result["xgboost_cox_c"].mean()),
              "mean_paired_gain": float(result["paired_gain"].mean()),
              "paired_gain_ci95": [float(lower), float(upper)],
              "probability_gain_positive": float(np.mean(result["paired_gain"] > 0)),
              "superiority_gate_pass": bool(lower > 0),
              "confirmatory_2015_2018_used": False, "nhanes_iii_read": False}
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "aft_vs_cox_bootstrap_replicates.csv.gz", index=False, compression="gzip")
    (OUT / "AFT_VS_COX_BOOTSTRAP_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

