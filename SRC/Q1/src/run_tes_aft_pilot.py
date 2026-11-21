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
from run_cox_baseline import COHORT, NON_FEATURES, harrell_c

OUT = ROOT / "outputs" / "tes_aft_pilot"


def c_index(frame, predicted_time):
    return harrell_c(frame["time_months"].to_numpy(float), frame["event"].to_numpy(int), -predicted_time)["harrell_c"]


def main() -> int:
    protocol = json.loads((ROOT / "TES_AFT_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    audit = frame.loc[frame["analysis_split"].eq("calibration")].copy()
    profile = pd.read_csv(ROOT / "outputs" / "temporal_shap_stability" / "cycle_feature_shap_profiles.csv")
    profile = profile.loc[profile["cycle"].isin(protocol["selection_cycles"])].copy()
    records = []
    for feature, group in profile.groupby("feature"):
        importance = group["normalized_importance"].to_numpy(float)
        directions = group["direction_spearman"].to_numpy(float)
        cv = float(np.std(importance) / max(np.mean(importance), 1e-12))
        nonzero = directions[np.abs(directions) >= 0.10]
        agreement = float(abs(np.mean(np.sign(nonzero)))) if len(nonzero) else 0.5
        records.append({"feature": feature, "mean_importance": float(np.mean(importance)),
                        "importance_cv": cv, "direction_agreement": agreement,
                        "stable_score": float(np.mean(importance) / (1 + cv) * agreement)})
    ranking = pd.DataFrame(records).sort_values("stable_score", ascending=False).reset_index(drop=True)
    mass = ranking["stable_score"].cumsum() / ranking["stable_score"].sum()
    count = max(8, int(np.searchsorted(mass.to_numpy(), 0.90, side="left") + 1))
    count = min(count, 15)
    selected = ranking.head(count)["feature"].tolist()
    for forced in ("age_years", "sex_code"):
        if forced not in selected:
            selected.append(forced)
    selected = list(dict.fromkeys(selected))

    base_protocol = json.loads((ROOT / "AFT_SURVIVAL_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    params = dict(base_protocol["parameters"])
    params.update({"objective": "survival:aft", "eval_metric": "aft-nloglik", "aft_loss_distribution": "normal",
                   "aft_loss_distribution_scale": 1.0, "tree_method": "hist"})
    model = xgb.train(params, aft_matrix(train, selected), num_boost_round=base_protocol["maximum_rounds"],
                      evals=[(aft_matrix(validation, selected), "validation")],
                      early_stopping_rounds=base_protocol["early_stopping_rounds"], verbose_eval=False)
    sparse_val = model.predict(aft_matrix(validation, selected), iteration_range=(0, model.best_iteration + 1))
    sparse_audit = model.predict(aft_matrix(audit, selected), iteration_range=(0, model.best_iteration + 1))
    full_features = [c for c in frame.columns if c not in NON_FEATURES]
    base_dir = ROOT / "outputs" / "aft_survival_pilot"
    base = xgb.Booster(); base.load_model(base_dir / "xgboost_aft_model.ubj")
    base_best = json.loads((base_dir / "AFT_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    base_val = base.predict(aft_matrix(validation, full_features), iteration_range=(0, base_best + 1))
    base_audit = base.predict(aft_matrix(audit, full_features), iteration_range=(0, base_best + 1))
    metrics = {"validation_full_c": c_index(validation, base_val), "validation_tes_c": c_index(validation, sparse_val),
               "audit_full_c": c_index(audit, base_audit), "audit_tes_c": c_index(audit, sparse_audit)}
    metrics["validation_gain"] = metrics["validation_tes_c"] - metrics["validation_full_c"]
    metrics["audit_gain"] = metrics["audit_tes_c"] - metrics["audit_full_c"]
    gates = protocol["gates"]
    gate = len(selected) <= gates["maximum_features"] and metrics["validation_gain"] >= gates["validation_noninferiority_margin"] and metrics["audit_gain"] >= gates["audit_noninferiority_margin"]
    OUT.mkdir(parents=True, exist_ok=True)
    ranking.assign(selected=ranking["feature"].isin(selected)).to_csv(OUT / "temporal_stability_feature_ranking.csv", index=False)
    model.save_model(OUT / "tes_aft_model.ubj")
    status = {"status": "PASS" if gate else "STOP", "selected_features": selected,
              "selected_feature_count": len(selected), "full_feature_count": len(full_features),
              "feature_reduction_fraction": 1 - len(selected) / len(full_features), "best_iteration": int(model.best_iteration),
              "metrics": metrics, "progression_gate_pass": bool(gate),
              "confirmatory_2015_2018_used": False, "nhanes_iii_read": False}
    (OUT / "TES_AFT_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

