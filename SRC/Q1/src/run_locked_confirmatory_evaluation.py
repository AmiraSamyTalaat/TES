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

OUT = ROOT / "outputs" / "locked_confirmatory_evaluation"
FREEZE = ROOT / "CONFIRMATORY_EXECUTION_MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_freeze() -> dict:
    manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    mismatches = []
    for relative, expected in manifest["critical_sha256"].items():
        actual = sha256(ROOT / relative)
        if actual != expected:
            mismatches.append({"file": relative, "expected": expected, "actual": actual})
    if mismatches:
        raise RuntimeError(f"CONFIRMATORY FREEZE INVALID: {mismatches}")
    return manifest


def bootstrap_group(name, idx, data, cox_risk, xgb_risk, rng, replicates=1000):
    subset = data.loc[idx].reset_index(drop=True)
    t = subset["time_months"].to_numpy(float)
    e = subset["event"].to_numpy(int)
    cr, xr = cox_risk[idx], xgb_risk[idx]
    point_cox, point_xgb = fast_c(t, e, cr), fast_c(t, e, xr)
    gains = []
    for _ in range(replicates):
        sample = rng.choice(len(subset), len(subset), replace=True)
        gains.append(fast_c(t[sample], e[sample], xr[sample]) - fast_c(t[sample], e[sample], cr[sample]))
    lower, upper = np.quantile(gains, [0.025, 0.975])
    return {"group": name, "rows": len(subset), "events": int(e.sum()),
            "median_followup_months": float(np.median(t)), "cox_c": point_cox,
            "xgboost_c": point_xgb, "paired_gain": point_xgb - point_cox,
            "paired_gain_ci95": [float(lower), float(upper)],
            "bootstrap_probability_gain_positive": float(np.mean(np.asarray(gains) > 0))}, gains


def main() -> int:
    manifest = verify_freeze()
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    confirm = frame.loc[frame["analysis_split"].eq("confirmatory_locked")].copy().reset_index(drop=True)
    baseline_path = ROOT / "outputs" / "cox_baseline" / "COX_BASELINE_STATUS.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    cox = next(m for m in baseline["models"] if m["model"] == "full_panel_cox")
    _, x_confirm = prepare(train, confirm, cox["features"])
    cox_risk = x_confirm @ np.array([cox["coefficients_standardized"][c] for c in cox["features"]])
    features = [c for c in frame.columns if c not in NON_FEATURES]
    model_dir = ROOT / "outputs" / "xgboost_survival_pilot"
    booster = xgb.Booster()
    booster.load_model(model_dir / "xgboost_survival_model.ubj")
    best = json.loads((model_dir / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    matrix = xgb.DMatrix(confirm[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    xgb_risk = booster.predict(matrix, iteration_range=(0, best + 1))
    rng = np.random.default_rng(20260827)
    summaries, replicate_rows = [], []
    for cycle in ("2015-2016", "2017-2018"):
        idx = np.flatnonzero(confirm["cycle"].eq(cycle).to_numpy())
        summary, gains = bootstrap_group(cycle, idx, confirm, cox_risk, xgb_risk, rng)
        summaries.append(summary)
        replicate_rows.extend({"group": cycle, "replicate": i + 1, "paired_gain": g} for i, g in enumerate(gains))
    cycle_idx = [np.flatnonzero(confirm["cycle"].eq(c).to_numpy()) for c in ("2015-2016", "2017-2018")]
    pooled_gains = []
    t, e = confirm["time_months"].to_numpy(float), confirm["event"].to_numpy(int)
    for _ in range(1000):
        sample = np.concatenate([rng.choice(idx, len(idx), replace=True) for idx in cycle_idx])
        pooled_gains.append(fast_c(t[sample], e[sample], xgb_risk[sample]) - fast_c(t[sample], e[sample], cox_risk[sample]))
    pooled = {"group": "pooled_secondary", "rows": len(confirm), "events": int(e.sum()),
              "cox_c": fast_c(t, e, cox_risk), "xgboost_c": fast_c(t, e, xgb_risk)}
    pooled["paired_gain"] = pooled["xgboost_c"] - pooled["cox_c"]
    pooled["paired_gain_ci95"] = [float(x) for x in np.quantile(pooled_gains, [0.025, 0.975])]
    primary = summaries[0]
    status = {"status": "PASS" if primary["paired_gain_ci95"][0] > 0 else "STOP",
              "freeze_verified": True, "manifest_sha256": sha256(FREEZE),
              "no_refit_or_tuning": True, "cycles": summaries, "pooled_secondary": pooled,
              "primary_success_gate_pass": bool(primary["paired_gain_ci95"][0] > 0),
              "freeze_stage": manifest["stage"]}
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(replicate_rows).to_csv(OUT / "confirmatory_bootstrap_replicates.csv.gz", index=False, compression="gzip")
    (OUT / "LOCKED_CONFIRMATORY_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

