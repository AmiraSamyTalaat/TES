from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".python_packages"))

import numpy as np
import pandas as pd
import xgboost as xgb

from run_cox_baseline import COHORT, NON_FEATURES, prepare

OUT = ROOT / "outputs" / "paired_bootstrap_validation"


class Fenwick:
    def __init__(self, size: int):
        self.tree = np.zeros(size + 1, dtype=np.int64)

    def add(self, index: int, value: int = 1):
        index += 1
        while index < len(self.tree):
            self.tree[index] += value
            index += index & -index

    def prefix(self, end_exclusive: int) -> int:
        total = 0
        index = end_exclusive
        while index > 0:
            total += int(self.tree[index])
            index -= index & -index
        return total


def fast_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray) -> float:
    ranks = np.searchsorted(np.unique(risk), risk)
    order = np.argsort(-time, kind="mergesort")
    tree = Fenwick(int(ranks.max()) + 1)
    comparable = 0
    concordant_twice = 0
    seen = 0
    position = 0
    while position < len(order):
        end = position + 1
        current_time = time[order[position]]
        while end < len(order) and time[order[end]] == current_time:
            end += 1
        group = order[position:end]
        for idx in group[event[group] == 1]:
            rank = int(ranks[idx])
            lower = tree.prefix(rank)
            equal = tree.prefix(rank + 1) - lower
            comparable += seen
            concordant_twice += 2 * lower + equal
        for idx in group:
            tree.add(int(ranks[idx]))
            seen += 1
        position = end
    return concordant_twice / (2 * comparable) if comparable else float("nan")


def main() -> int:
    protocol = json.loads((ROOT / "PAIRED_BOOTSTRAP_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy().reset_index(drop=True)
    baseline = json.loads((ROOT / "outputs" / "cox_baseline" / "COX_BASELINE_STATUS.json").read_text(encoding="utf-8"))
    cox = next(m for m in baseline["models"] if m["model"] == "full_panel_cox")
    columns = cox["features"]
    _, x_val = prepare(train, validation, columns)
    cox_risk = x_val @ np.array([cox["coefficients_standardized"][c] for c in columns])

    features = [c for c in frame.columns if c not in NON_FEATURES]
    booster = xgb.Booster()
    model_dir = ROOT / "outputs" / "xgboost_survival_pilot"
    booster.load_model(model_dir / "xgboost_survival_model.ubj")
    best = json.loads((model_dir / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"]
    matrix = xgb.DMatrix(validation[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    xgb_risk = booster.predict(matrix, iteration_range=(0, best + 1))
    time = validation["time_months"].to_numpy(float)
    event = validation["event"].to_numpy(int)
    rng = np.random.default_rng(protocol["seed"])
    cycle_indices = [np.flatnonzero(validation["cycle"].eq(c).to_numpy()) for c in sorted(validation["cycle"].unique())]
    rows = []
    for replicate in range(protocol["replicates"]):
        sample = np.concatenate([rng.choice(idx, size=len(idx), replace=True) for idx in cycle_indices])
        c_cox = fast_c(time[sample], event[sample], cox_risk[sample])
        c_xgb = fast_c(time[sample], event[sample], xgb_risk[sample])
        rows.append((replicate + 1, c_cox, c_xgb, c_xgb - c_cox))
    result = pd.DataFrame(rows, columns=["replicate", "cox_c", "xgboost_c", "paired_gain"])
    lower, upper = np.quantile(result["paired_gain"], [0.025, 0.975])
    status = {"status": "PASS" if lower > 0 else "STOP", "replicates": len(result),
              "confirmatory_rows_used": 0, "mean_cox_c": float(result["cox_c"].mean()),
              "mean_xgboost_c": float(result["xgboost_c"].mean()),
              "mean_paired_gain": float(result["paired_gain"].mean()),
              "paired_gain_ci95": [float(lower), float(upper)],
              "probability_gain_positive": float((result["paired_gain"] > 0).mean()),
              "success_gate_pass": bool(lower > 0)}
    OUT.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT / "paired_bootstrap_replicates.csv.gz", index=False, compression="gzip")
    (OUT / "PAIRED_BOOTSTRAP_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

