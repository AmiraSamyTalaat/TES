from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import numpy as np
import pandas as pd
import xgboost as xgb

from run_cox_baseline import COHORT, NON_FEATURES, harrell_c

OUT = ROOT / "outputs" / "aft_survival_pilot"


def aft_matrix(frame: pd.DataFrame, features: list[str]) -> xgb.DMatrix:
    matrix = xgb.DMatrix(frame[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    time = frame["time_months"].to_numpy(float)
    event = frame["event"].to_numpy(int)
    matrix.set_float_info("label_lower_bound", time)
    matrix.set_float_info("label_upper_bound", np.where(event == 1, time, np.inf))
    return matrix


def main() -> int:
    protocol = json.loads((ROOT / "AFT_SURVIVAL_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    features = [c for c in frame.columns if c not in NON_FEATURES]
    dtrain, dval = aft_matrix(train, features), aft_matrix(validation, features)
    params = dict(protocol["parameters"])
    params.update({"objective": "survival:aft", "eval_metric": "aft-nloglik",
                   "aft_loss_distribution": protocol["distribution"],
                   "aft_loss_distribution_scale": protocol["distribution_scale"], "tree_method": "hist"})
    model = xgb.train(params, dtrain, num_boost_round=protocol["maximum_rounds"], evals=[(dval, "validation")],
                      early_stopping_rounds=protocol["early_stopping_rounds"], verbose_eval=False)
    predicted_time = model.predict(dval, iteration_range=(0, model.best_iteration + 1))
    metric = harrell_c(validation["time_months"].to_numpy(float), validation["event"].to_numpy(int), -predicted_time)
    cox_status = json.loads((ROOT / "outputs" / "xgboost_survival_pilot" / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))
    difference = metric["harrell_c"] - cox_status["validation_harrell_c"]
    gate = metric["harrell_c"] >= protocol["progression_gate"]["validation_harrell_c_minimum"] and difference >= protocol["progression_gate"]["noninferiority_vs_xgboost_cox"]
    OUT.mkdir(parents=True, exist_ok=True)
    model.save_model(OUT / "xgboost_aft_model.ubj")
    status = {"status": "PASS" if gate else "STOP", "train_rows": len(train), "validation_rows": len(validation),
              "best_iteration": int(model.best_iteration), "validation_harrell_c": metric["harrell_c"],
              "xgboost_cox_harrell_c": cox_status["validation_harrell_c"], "difference_vs_xgboost_cox": difference,
              "median_predicted_time_months": float(np.median(predicted_time)),
              "confirmatory_2015_2018_used": False, "nhanes_iii_read": False,
              "progression_gate_pass": bool(gate)}
    (OUT / "AFT_SURVIVAL_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

