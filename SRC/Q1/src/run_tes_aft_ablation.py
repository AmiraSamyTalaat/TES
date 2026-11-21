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

OUT = ROOT / "outputs" / "tes_aft_ablation"


def fit_aft(train, validation, features, base_protocol):
    params = dict(base_protocol["parameters"])
    params.update({"objective": "survival:aft", "eval_metric": "aft-nloglik", "aft_loss_distribution": "normal",
                   "aft_loss_distribution_scale": 1.0, "tree_method": "hist"})
    return xgb.train(params, aft_matrix(train, features), num_boost_round=base_protocol["maximum_rounds"],
                     evals=[(aft_matrix(validation, features), "validation")],
                     early_stopping_rounds=base_protocol["early_stopping_rounds"], verbose_eval=False)


def main() -> int:
    protocol = json.loads((ROOT / "TES_AFT_ABLATION_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    audit = frame.loc[frame["analysis_split"].eq("calibration")].copy().reset_index(drop=True)
    tes_status = json.loads((ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json").read_text(encoding="utf-8"))
    tes_features = tes_status["selected_features"]
    profiles = pd.read_csv(ROOT / "outputs" / "temporal_shap_stability" / "cycle_feature_shap_profiles.csv")
    development_profiles = profiles.loc[profiles["cycle"].isin(["2009-2010", "2011-2012"])]
    mean_rank = development_profiles.groupby("feature")["normalized_importance"].mean().sort_values(ascending=False)
    mean_features = mean_rank.head(protocol["panel_size"]).index.tolist()
    latest_rank = development_profiles.loc[development_profiles["cycle"].eq("2011-2012")].sort_values("normalized_importance", ascending=False)
    latest_features = latest_rank.head(protocol["panel_size"])["feature"].tolist()
    base_protocol = json.loads((ROOT / "AFT_SURVIVAL_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    mean_model = fit_aft(train, validation, mean_features, base_protocol)
    latest_model = fit_aft(train, validation, latest_features, base_protocol)
    tes_model = xgb.Booster(); tes_model.load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj")
    full_model = xgb.Booster(); full_model.load_model(ROOT / "outputs" / "aft_survival_pilot" / "xgboost_aft_model.ubj")
    full_features = [c for c in frame.columns if c not in NON_FEATURES]
    full_best = json.loads((ROOT / "outputs" / "aft_survival_pilot" / "AFT_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    predictions = {
        "tes": tes_model.predict(aft_matrix(audit, tes_features), iteration_range=(0, tes_status["best_iteration"] + 1)),
        "full": full_model.predict(aft_matrix(audit, full_features), iteration_range=(0, full_best + 1)),
        "mean_top_shap": mean_model.predict(aft_matrix(audit, mean_features), iteration_range=(0, mean_model.best_iteration + 1)),
        "latest_top_shap": latest_model.predict(aft_matrix(audit, latest_features), iteration_range=(0, latest_model.best_iteration + 1)),
    }
    t, e = audit["time_months"].to_numpy(float), audit["event"].to_numpy(int)
    point = {name: fast_c(t, e, -value) for name, value in predictions.items()}
    rng = np.random.default_rng(protocol["seed"])
    replicate_rows, comparisons = [], {}
    for comparator in ("full", "mean_top_shap", "latest_top_shap"):
        gains = []
        for rep in range(protocol["bootstrap_replicates"]):
            sample = rng.choice(len(audit), len(audit), replace=True)
            gain = fast_c(t[sample], e[sample], -predictions["tes"][sample]) - fast_c(t[sample], e[sample], -predictions[comparator][sample])
            gains.append(gain); replicate_rows.append({"comparator": comparator, "replicate": rep + 1, "tes_gain": gain})
        lower, upper = np.quantile(gains, [0.025, 0.975])
        comparisons[comparator] = {"point_gain": point["tes"] - point[comparator],
                                   "mean_bootstrap_gain": float(np.mean(gains)),
                                   "gain_ci95": [float(lower), float(upper)]}
    gates = protocol["gates"]
    gate = comparisons["full"]["gain_ci95"][0] >= gates["paired_noninferiority_margin_vs_full"] and all(
        comparisons[name]["gain_ci95"][0] >= gates["paired_noninferiority_margin_vs_shap_ablations"] for name in ("mean_top_shap", "latest_top_shap"))
    status = {"status": "PASS" if gate else "STOP", "audit_rows": len(audit), "audit_events": int(e.sum()),
              "feature_panels": {"tes": tes_features, "mean_top_shap": mean_features, "latest_top_shap": latest_features},
              "audit_c": point, "paired_comparisons": comparisons, "ablation_gate_pass": bool(gate),
              "confirmatory_2015_2018_used": False, "nhanes_iii_read": False}
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(replicate_rows).to_csv(OUT / "tes_ablation_bootstrap.csv.gz", index=False, compression="gzip")
    (OUT / "TES_AFT_ABLATION_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

