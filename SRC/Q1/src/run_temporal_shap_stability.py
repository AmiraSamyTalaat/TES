from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import spearmanr

from run_cox_baseline import NON_FEATURES

COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort_survey.csv.gz"
OUT = ROOT / "outputs" / "temporal_shap_stability"
SURVEY = {"exam_weight_2yr", "survey_stratum", "survey_psu", "pooled_exam_weight_20yr"}


def js_divergence(p, q):
    p, q = p / p.sum(), q / q.sum()
    m = 0.5 * (p + q)
    kl_p = np.sum(np.where(p > 0, p * np.log2(p / m), 0))
    kl_q = np.sum(np.where(q > 0, q * np.log2(q / m), 0))
    return float(0.5 * (kl_p + kl_q))


def main() -> int:
    protocol = json.loads((ROOT / "TEMPORAL_SHAP_STABILITY_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    features = [c for c in frame.columns if c not in NON_FEATURES | SURVEY]
    model_dir = ROOT / "outputs" / "xgboost_survival_pilot"
    model = xgb.Booster(); model.load_model(model_dir / "xgboost_survival_model.ubj")
    best = json.loads((model_dir / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    profiles, feature_rows = {}, []
    for cycle in protocol["cycles"]:
        subset = frame.loc[frame["cycle"].eq(cycle)].copy()
        values = subset[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        matrix = xgb.DMatrix(values, feature_names=features, missing=np.nan)
        contributions = model.predict(matrix, pred_contribs=True, iteration_range=(0, best + 1))[:, :-1]
        importance = np.mean(np.abs(contributions), axis=0)
        directions = []
        for j in range(len(features)):
            valid = np.isfinite(values[:, j]) & np.isfinite(contributions[:, j])
            rho = float(spearmanr(values[valid, j], contributions[valid, j]).statistic) if valid.sum() >= 20 else 0.0
            directions.append(0.0 if not np.isfinite(rho) else rho)
            feature_rows.append({"cycle": cycle, "feature": features[j], "mean_abs_shap": importance[j],
                                 "normalized_importance": importance[j] / importance.sum(), "direction_spearman": directions[-1]})
        profiles[cycle] = {"importance": importance, "direction": np.asarray(directions)}
    pair_rows = []
    for first, second in itertools.combinations(protocol["cycles"], 2):
        a, b = profiles[first], profiles[second]
        rank_rho = float(spearmanr(a["importance"], b["importance"]).statistic)
        top_a = set(np.argsort(-a["importance"])[:10]); top_b = set(np.argsort(-b["importance"])[:10])
        reliable = (np.abs(a["direction"]) >= 0.10) & (np.abs(b["direction"]) >= 0.10)
        flips = np.sign(a["direction"][reliable]) != np.sign(b["direction"][reliable])
        pair_rows.append({"cycle_a": first, "cycle_b": second, "importance_spearman": rank_rho,
                          "importance_js_divergence": js_divergence(a["importance"], b["importance"]),
                          "top10_overlap": len(top_a & top_b) / 10,
                          "reliable_direction_features": int(reliable.sum()),
                          "direction_flip_fraction": float(flips.mean()) if reliable.any() else 0.0})
    gates = protocol["gates"]
    gate = (min(r["importance_spearman"] for r in pair_rows) >= gates["minimum_pairwise_importance_spearman"] and
            max(r["importance_js_divergence"] for r in pair_rows) <= gates["maximum_pairwise_js_divergence"] and
            min(r["top10_overlap"] for r in pair_rows) >= gates["minimum_top10_overlap"] and
            max(r["direction_flip_fraction"] for r in pair_rows) <= gates["maximum_direction_flip_fraction"])
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(feature_rows).to_csv(OUT / "cycle_feature_shap_profiles.csv", index=False)
    pd.DataFrame(pair_rows).to_csv(OUT / "pairwise_shap_stability.csv", index=False)
    status = {"status": "PASS" if gate else "STOP", "cycles": protocol["cycles"],
              "confirmatory_2015_2018_used": False, "nhanes_iii_read": False,
              "pairwise": pair_rows, "stability_gate_pass": bool(gate)}
    (OUT / "TEMPORAL_SHAP_STABILITY_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

