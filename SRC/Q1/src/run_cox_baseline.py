from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort.csv.gz"
OUT = ROOT / "outputs" / "cox_baseline"
NON_FEATURES = {"participant_id", "cycle", "partition", "analysis_split", "eligstat",
                "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int",
                "permth_exm", "event", "time_months"}


def prepare(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]):
    x_train = train[columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    x_test = test[columns].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    med = np.nanmedian(x_train, axis=0)
    x_train = np.where(np.isfinite(x_train), x_train, med)
    x_test = np.where(np.isfinite(x_test), x_test, med)
    center = np.median(x_train, axis=0)
    scale = np.quantile(x_train, .75, axis=0) - np.quantile(x_train, .25, axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (x_train - center) / scale, (x_test - center) / scale


def cox_fit(x: np.ndarray, time: np.ndarray, event: np.ndarray,
            ridge: float = 0.05, iterations: int = 35) -> tuple[np.ndarray, list[float]]:
    order = np.argsort(-time, kind="mergesort")
    x, time, event = x[order], time[order], event[order]
    beta = np.zeros(x.shape[1])
    history = []
    for _ in range(iterations):
        eta = np.clip(x @ beta, -30, 30)
        weights = np.exp(eta)
        s0 = np.cumsum(weights)
        s1 = np.cumsum(weights[:, None] * x, axis=0)
        s2 = np.cumsum(weights[:, None, None] * x[:, :, None] * x[:, None, :], axis=0)
        gradient = -(ridge * beta)
        information = ridge * np.eye(x.shape[1])
        loglik = -0.5 * ridge * float(beta @ beta)
        for idx in np.flatnonzero(event == 1):
            mean = s1[idx] / s0[idx]
            gradient += x[idx] - mean
            information += s2[idx] / s0[idx] - np.outer(mean, mean)
            loglik += eta[idx] - np.log(s0[idx])
        history.append(float(loglik))
        step = np.linalg.solve(information + 1e-8 * np.eye(x.shape[1]), gradient)
        # Conservative damping protects the baseline from separation/outliers.
        step_scale = min(1.0, 1.5 / max(np.max(np.abs(step)), 1e-12))
        beta += step_scale * step
        if np.max(np.abs(step_scale * step)) < 1e-6:
            break
    return beta, history


def harrell_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray) -> dict:
    concordant = tied = comparable = 0
    for i in np.flatnonzero(event == 1):
        mask = time > time[i]
        if not np.any(mask):
            continue
        other = risk[mask]
        comparable += len(other)
        concordant += int(np.sum(risk[i] > other))
        tied += int(np.sum(risk[i] == other))
    value = (concordant + 0.5 * tied) / comparable if comparable else float("nan")
    return {"harrell_c": float(value), "comparable_pairs": int(comparable)}


def run_model(name: str, columns: list[str], train: pd.DataFrame, validation: pd.DataFrame) -> dict:
    x_train, x_val = prepare(train, validation, columns)
    beta, history = cox_fit(x_train, train["time_months"].to_numpy(float),
                            train["event"].to_numpy(int))
    train_metric = harrell_c(train["time_months"].to_numpy(float),
                             train["event"].to_numpy(int), x_train @ beta)
    val_metric = harrell_c(validation["time_months"].to_numpy(float),
                           validation["event"].to_numpy(int), x_val @ beta)
    return {"model": name, "features": columns, "n_features": len(columns),
            "iterations": len(history), "final_partial_loglik": history[-1],
            "train": train_metric, "validation": val_metric,
            "coefficients_standardized": dict(zip(columns, beta.tolist()))}


def main() -> int:
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    if frame.loc[frame["analysis_split"].eq("confirmatory_locked")].empty:
        raise RuntimeError("Expected locked confirmatory rows are missing")
    analytes = [c for c in frame.columns if c not in NON_FEATURES | {"age_years", "sex_code"}]
    models = [run_model("age_sex_cox", ["age_years", "sex_code"], train, validation),
              run_model("full_panel_cox", ["age_years", "sex_code", *analytes], train, validation)]
    gain = models[1]["validation"]["harrell_c"] - models[0]["validation"]["harrell_c"]
    status = {"status": "PASS", "train_rows": len(train), "validation_rows": len(validation),
              "confirmatory_rows_read_for_fitting": 0, "models": models,
              "full_panel_validation_c_gain": float(gain)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "COX_BASELINE_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    pd.DataFrame([{"model": m["model"], "features": m["n_features"],
                   "train_harrell_c": m["train"]["harrell_c"],
                   "validation_harrell_c": m["validation"]["harrell_c"]} for m in models]).to_csv(
                       OUT / "cox_baseline_summary.csv", index=False)
    print(json.dumps({"status": status["status"], "train_rows": len(train),
                      "validation_rows": len(validation),
                      "age_sex_validation_c": models[0]["validation"]["harrell_c"],
                      "full_panel_validation_c": models[1]["validation"]["harrell_c"],
                      "gain": gain, "confirmatory_rows_read_for_fitting": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

