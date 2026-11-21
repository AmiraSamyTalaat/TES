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

OUT = ROOT / "outputs" / "xgboost_survival_pilot"
PROTOCOL = ROOT / "XGBOOST_SURVIVAL_PROTOCOL_FREEZE.json"


def survival_label(frame: pd.DataFrame) -> np.ndarray:
    time = frame["time_months"].to_numpy(float)
    event = frame["event"].to_numpy(int)
    return np.where(event == 1, time, -time)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    features = [c for c in frame.columns if c not in NON_FEATURES]
    x_train = train[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    x_val = validation[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    dtrain = xgb.DMatrix(x_train, label=survival_label(train), feature_names=features, missing=np.nan)
    dval = xgb.DMatrix(x_val, label=survival_label(validation), feature_names=features, missing=np.nan)
    params = dict(protocol["parameters"])
    params.update({"objective": "survival:cox", "eval_metric": "cox-nloglik", "tree_method": "hist"})
    model = xgb.train(params, dtrain, num_boost_round=protocol["maximum_rounds"],
                      evals=[(dval, "validation")],
                      early_stopping_rounds=protocol["early_stopping_rounds"], verbose_eval=False)
    risk = model.predict(dval, iteration_range=(0, model.best_iteration + 1))
    metric = harrell_c(validation["time_months"].to_numpy(float),
                       validation["event"].to_numpy(int), risk)
    baseline = json.loads((ROOT / "outputs" / "cox_baseline" / "COX_BASELINE_STATUS.json").read_text(encoding="utf-8"))
    baseline_c = next(m for m in baseline["models"] if m["model"] == "full_panel_cox")["validation"]["harrell_c"]
    gain = metric["harrell_c"] - baseline_c
    gate = metric["harrell_c"] >= protocol["progression_gate"]["validation_harrell_c_minimum"] and gain >= protocol["progression_gate"]["gain_over_full_panel_cox_minimum"]
    OUT.mkdir(parents=True, exist_ok=True)
    model.save_model(OUT / "xgboost_survival_model.ubj")
    importance = pd.DataFrame(sorted(model.get_score(importance_type="gain").items(),
                                     key=lambda item: item[1], reverse=True), columns=["feature", "gain"])
    importance.to_csv(OUT / "feature_importance_gain.csv", index=False)
    status = {"status": "PASS" if gate else "STOP", "train_rows": len(train),
              "validation_rows": len(validation), "confirmatory_rows_used": 0,
              "best_iteration": int(model.best_iteration),
              "validation_harrell_c": metric["harrell_c"], "cox_baseline_harrell_c": baseline_c,
              "gain_over_cox": float(gain), "progression_gate_pass": bool(gate)}
    (OUT / "XGBOOST_SURVIVAL_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

