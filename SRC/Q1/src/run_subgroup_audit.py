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

from run_cox_baseline import COHORT, NON_FEATURES, prepare
from run_paired_bootstrap_validation import fast_c

OUT = ROOT / "outputs" / "subgroup_audit"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    protocol = json.loads((ROOT / "SUBGROUP_AUDIT_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    val = frame.loc[frame["analysis_split"].eq("validation")].copy().reset_index(drop=True)
    baseline_path = ROOT / "outputs" / "cox_baseline" / "COX_BASELINE_STATUS.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    cox = next(m for m in baseline["models"] if m["model"] == "full_panel_cox")
    _, x_val = prepare(train, val, cox["features"])
    cox_risk = x_val @ np.array([cox["coefficients_standardized"][c] for c in cox["features"]])
    features = [c for c in frame.columns if c not in NON_FEATURES]
    model_path = ROOT / "outputs" / "xgboost_survival_pilot" / "xgboost_survival_model.ubj"
    model_status_path = ROOT / "outputs" / "xgboost_survival_pilot" / "XGBOOST_SURVIVAL_STATUS.json"
    booster = xgb.Booster()
    booster.load_model(model_path)
    best = json.loads(model_status_path.read_text(encoding="utf-8"))["best_iteration"]
    matrix = xgb.DMatrix(val[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    xgb_risk = booster.predict(matrix, iteration_range=(0, best + 1))
    groups = {
        "female": val["sex_code"].eq(2).to_numpy(),
        "male": val["sex_code"].eq(1).to_numpy(),
        "age_20_39": val["age_years"].between(20, 39, inclusive="both").to_numpy(),
        "age_40_59": val["age_years"].between(40, 59, inclusive="both").to_numpy(),
        "age_60_plus": val["age_years"].ge(60).to_numpy(),
    }
    rng = np.random.default_rng(20260827)
    summaries, replicates = [], []
    for name, mask in groups.items():
        idx_all = np.flatnonzero(mask)
        subgroup = val.loc[idx_all].reset_index(drop=True)
        t = subgroup["time_months"].to_numpy(float)
        e = subgroup["event"].to_numpy(int)
        cr, xr = cox_risk[idx_all], xgb_risk[idx_all]
        c_cox, c_xgb = fast_c(t, e, cr), fast_c(t, e, xr)
        cycle_idx = [np.flatnonzero(subgroup["cycle"].eq(c).to_numpy()) for c in sorted(subgroup["cycle"].unique())]
        gains = []
        for rep in range(protocol["bootstrap_replicates"]):
            sample = np.concatenate([rng.choice(idx, len(idx), replace=True) for idx in cycle_idx])
            gain = fast_c(t[sample], e[sample], xr[sample]) - fast_c(t[sample], e[sample], cr[sample])
            gains.append(gain)
            replicates.append({"group": name, "replicate": rep + 1, "paired_gain": gain})
        lower, upper = np.quantile(gains, [0.025, 0.975])
        summaries.append({"group": name, "rows": len(subgroup), "events": int(e.sum()),
                          "cox_c": c_cox, "xgboost_c": c_xgb, "paired_gain": c_xgb - c_cox,
                          "gain_ci95_lower": lower, "gain_ci95_upper": upper,
                          "bootstrap_probability_gain_positive": float(np.mean(np.asarray(gains) > 0))})
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).to_csv(OUT / "subgroup_summary.csv", index=False)
    pd.DataFrame(replicates).to_csv(OUT / "subgroup_bootstrap_replicates.csv.gz", index=False, compression="gzip")
    status = {"status": "PASS", "confirmatory_rows_used": 0, "groups": summaries,
              "model_freeze": {"xgboost_model_sha256": sha256(model_path),
                               "xgboost_status_sha256": sha256(model_status_path),
                               "cox_status_sha256": sha256(baseline_path),
                               "subgroup_protocol_sha256": sha256(ROOT / "SUBGROUP_AUDIT_PROTOCOL_FREEZE.json")}}
    (OUT / "SUBGROUP_AUDIT_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

