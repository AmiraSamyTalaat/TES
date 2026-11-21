from __future__ import annotations

"""Post-hoc strengthening analyses for the Strong-Q1 manuscript revision.

This script DOES NOT alter any frozen protocol, model, result, or confirmatory artifact.
It adds transparent, post-hoc technical analyses around the already frozen study:
1) formal TES component ablation under the original selection rule;
2) feature-selection baseline comparisons using fixed AFT hyperparameters;
3) censoring-aware survival evaluation (Uno C, cumulative/dynamic AUC, IPCW Brier,
   integrated Brier, and IPCW horizon calibration diagnostics).

All new outputs are written to outputs/strong_q1_extension/.
"""

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import norm
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "strong_q1_extension"
OUT.mkdir(parents=True, exist_ok=True)

COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort.csv.gz"
SURVEY_COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort_survey.csv.gz"
EXT_FEATURES = ROOT / "external_nhanes3" / "processed_features" / "nhanes3_feature_cohort_locked_outcome.csv.gz"
EXT_MORTALITY = ROOT / "external_nhanes3" / "locked_mortality" / "NHANES_III_MORT_2019_PUBLIC.dat"

NON_FEATURES = {
    "participant_id", "cycle", "partition", "analysis_split", "eligstat",
    "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int",
    "permth_exm", "event", "time_months",
}
SURVEY_VARS = {"exam_weight_2yr", "survey_stratum", "survey_psu", "pooled_exam_weight_20yr"}
FORCED = ["age_years", "sex_code"]
EPS = 1e-12


def fast_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray) -> float:
    """Harrell C with an O(n log n) Fenwick tree implementation."""
    ranks = np.searchsorted(np.unique(risk), risk)
    order = np.argsort(-time, kind="mergesort")
    tree = np.zeros(int(ranks.max()) + 2, dtype=np.int64)

    def add(index: int) -> None:
        index += 1
        while index < len(tree):
            tree[index] += 1
            index += index & -index

    def prefix(index: int) -> int:
        total = 0
        while index > 0:
            total += int(tree[index])
            index -= index & -index
        return total

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
            lower = prefix(rank)
            equal = prefix(rank + 1) - lower
            comparable += seen
            concordant_twice += 2 * lower + equal
        for idx in group:
            add(int(ranks[idx]))
            seen += 1
        position = end
    return concordant_twice / (2 * comparable) if comparable else float("nan")


class KMCensoring:
    """Kaplan-Meier estimator of the censoring survival distribution G(t)."""

    def __init__(self, time: np.ndarray, event: np.ndarray):
        time = np.asarray(time, float)
        event = np.asarray(event, int)
        order = np.argsort(time, kind="mergesort")
        time = time[order]
        censor_event = (1 - event[order]).astype(int)
        unique_times = np.unique(time)
        survival = []
        current = 1.0
        for value in unique_times:
            at_risk = int(np.sum(time >= value))
            d_censor = int(censor_event[time == value].sum())
            if at_risk:
                current *= (1.0 - d_censor / at_risk)
            survival.append(current)
        self.times = unique_times
        self.survival = np.asarray(survival, float)

    def g(self, values: np.ndarray | float, left: bool = False) -> np.ndarray:
        values = np.asarray(values, float)
        side = "left" if left else "right"
        idx = np.searchsorted(self.times, values, side=side) - 1
        out = np.ones_like(values, dtype=float)
        valid = idx >= 0
        out[valid] = self.survival[idx[valid]]
        return out


def uno_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray, censor_km: KMCensoring, tau: float) -> float:
    """IPCW Uno concordance truncated at tau, with G estimated in training data."""
    time = np.asarray(time, float)
    event = np.asarray(event, int)
    risk = np.asarray(risk, float)
    numerator = 0.0
    denominator = 0.0
    for i in np.flatnonzero((event == 1) & (time < tau)):
        g = float(censor_km.g(time[i], left=True))
        if g <= 1e-8:
            continue
        weight = 1.0 / (g * g)
        comparable = time > time[i]
        if not np.any(comparable):
            continue
        other = risk[comparable]
        denominator += weight * len(other)
        numerator += weight * (np.sum(risk[i] > other) + 0.5 * np.sum(risk[i] == other))
    return float(numerator / denominator) if denominator else float("nan")


def cumulative_dynamic_auc(time: np.ndarray, event: np.ndarray, risk: np.ndarray,
                           censor_km: KMCensoring, horizon: float) -> float:
    """Cumulative/dynamic time-dependent AUC with IPCW case/control weighting."""
    time = np.asarray(time, float)
    event = np.asarray(event, int)
    risk = np.asarray(risk, float)
    cases = np.flatnonzero((event == 1) & (time <= horizon))
    controls = np.flatnonzero(time > horizon)
    if not len(cases) or not len(controls):
        return float("nan")
    g_case = np.maximum(censor_km.g(time[cases], left=True), 1e-8)
    g_h = float(censor_km.g(horizon))
    if g_h <= 1e-8:
        return float("nan")
    w_case = 1.0 / g_case
    # All controls share 1/G(horizon), which cancels in the ratio.
    sorted_control_risk = np.sort(risk[controls])
    lower = np.searchsorted(sorted_control_risk, risk[cases], side="left")
    upper = np.searchsorted(sorted_control_risk, risk[cases], side="right")
    pair_score = lower + 0.5 * (upper - lower)
    return float(np.sum(w_case * pair_score) / (np.sum(w_case) * len(controls)))


def brier_ipcw(time: np.ndarray, event: np.ndarray, survival_probability: np.ndarray,
                censor_km: KMCensoring, horizon: float) -> float:
    """Graf/Gerds-style IPCW Brier score at a fixed horizon."""
    time = np.asarray(time, float)
    event = np.asarray(event, int)
    s = np.asarray(survival_probability, float)
    total = 0.0
    cases = (event == 1) & (time <= horizon)
    if np.any(cases):
        g_case = np.maximum(censor_km.g(time[cases], left=True), 1e-8)
        total += float(np.sum((s[cases] ** 2) / g_case))
    controls = time > horizon
    g_h = float(censor_km.g(horizon))
    if g_h <= 1e-8:
        return float("nan")
    total += float(np.sum(((1.0 - s[controls]) ** 2) / g_h))
    return total / len(time)


def km_event_risk(time: np.ndarray, event: np.ndarray, horizon: float) -> float:
    survival = 1.0
    for value in np.unique(time[time <= horizon]):
        at_risk = int(np.sum(time >= value))
        d_event = int(np.sum((time == value) & (event == 1)))
        if at_risk:
            survival *= 1.0 - d_event / at_risk
    return float(1.0 - survival)


def calibration_ipcw(time: np.ndarray, event: np.ndarray, event_probability: np.ndarray,
                     censor_km: KMCensoring, horizon: float) -> dict:
    """IPCW logistic calibration intercept/slope at a fixed horizon.

    These diagnostics are explicitly sensitivity analyses, not part of the frozen
    confirmatory success gates.
    """
    time = np.asarray(time, float)
    event = np.asarray(event, int)
    probability = np.clip(np.asarray(event_probability, float), 1e-6, 1 - 1e-6)
    cases = (event == 1) & (time <= horizon)
    controls = time > horizon
    use = cases | controls
    y = cases[use].astype(int)
    t_use = time[use]
    case_use = cases[use]
    weights = np.empty(len(y), dtype=float)
    weights[case_use] = 1.0 / np.maximum(censor_km.g(t_use[case_use], left=True), 1e-8)
    g_h = max(float(censor_km.g(horizon)), 1e-8)
    weights[~case_use] = 1.0 / g_h
    logit_p = np.log(probability[use] / (1.0 - probability[use]))
    try:
        fit = sm.GLM(y, sm.add_constant(logit_p), family=sm.families.Binomial(),
                     freq_weights=weights).fit()
        intercept, slope = [float(x) for x in fit.params]
    except Exception:
        intercept, slope = float("nan"), float("nan")
    return {
        "intercept": intercept,
        "slope": slope,
        "mean_predicted_event_risk": float(np.mean(probability)),
        "observed_km_event_risk": km_event_risk(time, event, horizon),
    }


def aft_matrix(frame: pd.DataFrame, features: list[str]) -> xgb.DMatrix:
    matrix = xgb.DMatrix(frame[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    time = frame["time_months"].to_numpy(float)
    event = frame["event"].to_numpy(int)
    matrix.set_float_info("label_lower_bound", time)
    matrix.set_float_info("label_upper_bound", np.where(event == 1, time, np.inf))
    return matrix


def predict_booster(model: xgb.Booster, best_iteration: int, frame: pd.DataFrame,
                    features: list[str], output_margin: bool = False) -> np.ndarray:
    matrix = xgb.DMatrix(frame[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
                         feature_names=features, missing=np.nan)
    return model.predict(matrix, iteration_range=(0, best_iteration + 1), output_margin=output_margin)


def load_model(model_path: Path, status_path: Path) -> tuple[xgb.Booster, int]:
    model = xgb.Booster()
    model.load_model(model_path)
    best = int(json.loads(status_path.read_text(encoding="utf-8"))["best_iteration"])
    return model, best


def fit_aft(train: pd.DataFrame, validation: pd.DataFrame, panel: list[str], protocol: dict) -> xgb.Booster:
    params = dict(protocol["parameters"])
    params.update({
        "objective": "survival:aft",
        "eval_metric": "aft-nloglik",
        "aft_loss_distribution": protocol["distribution"],
        "aft_loss_distribution_scale": protocol["distribution_scale"],
        "tree_method": "hist",
    })
    return xgb.train(params, aft_matrix(train, panel), num_boost_round=protocol["maximum_rounds"],
                     evals=[(aft_matrix(validation, panel), "validation")],
                     early_stopping_rounds=protocol["early_stopping_rounds"], verbose_eval=False)


def prepare_standardized(train: pd.DataFrame, test: pd.DataFrame, columns: list[str]):
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
            ridge: float = 0.05, iterations: int = 35) -> np.ndarray:
    order = np.argsort(-time, kind="mergesort")
    x, time, event = x[order], time[order], event[order]
    beta = np.zeros(x.shape[1])
    for _ in range(iterations):
        eta = np.clip(x @ beta, -30, 30)
        weights = np.exp(eta)
        s0 = np.cumsum(weights)
        s1 = np.cumsum(weights[:, None] * x, axis=0)
        s2 = np.cumsum(weights[:, None, None] * x[:, :, None] * x[:, None, :], axis=0)
        gradient = -(ridge * beta)
        information = ridge * np.eye(x.shape[1])
        for idx in np.flatnonzero(event == 1):
            mean = s1[idx] / s0[idx]
            gradient += x[idx] - mean
            information += s2[idx] / s0[idx] - np.outer(mean, mean)
        step = np.linalg.solve(information + 1e-8 * np.eye(x.shape[1]), gradient)
        step_scale = min(1.0, 1.5 / max(np.max(np.abs(step)), 1e-12))
        beta += step_scale * step
        if np.max(np.abs(step_scale * step)) < 1e-6:
            break
    return beta


def breslow_baseline(time: np.ndarray, event: np.ndarray, relative_risk: np.ndarray):
    event_times = np.sort(np.unique(time[event == 1]))
    cumulative = []
    current = 0.0
    for value in event_times:
        deaths = int(np.sum((time == value) & (event == 1)))
        risk_sum = float(np.sum(relative_risk[time >= value]))
        if risk_sum > 0:
            current += deaths / risk_sum
        cumulative.append(current)
    return event_times, np.asarray(cumulative, float)


def cumulative_hazard_at(event_times: np.ndarray, cumulative: np.ndarray, horizon: float) -> float:
    idx = np.searchsorted(event_times, horizon, side="right") - 1
    return 0.0 if idx < 0 else float(cumulative[idx])


def stable_score_table(profile: pd.DataFrame) -> pd.DataFrame:
    records = []
    for feature, group in profile.groupby("feature"):
        importance = group["normalized_importance"].to_numpy(float)
        directions = group["direction_spearman"].to_numpy(float)
        mean_importance = float(np.mean(importance))
        cv = float(np.std(importance) / max(mean_importance, EPS))
        reliable = directions[np.abs(directions) >= 0.10]
        agreement = float(abs(np.mean(np.sign(reliable)))) if len(reliable) else 0.5
        records.append({
            "feature": feature,
            "mean_importance": mean_importance,
            "importance_cv": cv,
            "direction_agreement": agreement,
            "score_importance_only": mean_importance,
            "score_no_direction": mean_importance / (1.0 + cv),
            "score_no_cv": mean_importance * agreement,
            "score_tes": mean_importance / (1.0 + cv) * agreement,
        })
    return pd.DataFrame(records)


def select_mass(score_table: pd.DataFrame, score_column: str, threshold: float = 0.90) -> list[str]:
    ranked = score_table.sort_values(score_column, ascending=False).reset_index(drop=True)
    mass = ranked[score_column].cumsum() / ranked[score_column].sum()
    count = max(8, int(np.searchsorted(mass.to_numpy(), threshold, side="left") + 1))
    count = min(count, 15)
    selected = ranked.head(count)["feature"].tolist()
    for feature in FORCED:
        if feature not in selected:
            selected.append(feature)
    return list(dict.fromkeys(selected))


def load_external() -> pd.DataFrame:
    feature_frame = pd.read_csv(EXT_FEATURES)
    mortality = pd.read_fwf(EXT_MORTALITY, colspecs=[(0, 6), (14, 15), (15, 16), (42, 45)],
                            names=["participant_id", "eligstat", "event", "time_months"])
    mortality = mortality.apply(pd.to_numeric, errors="coerce")
    cohort = feature_frame.merge(mortality, on="participant_id", how="inner", validate="one_to_one")
    return cohort.loc[cohort["eligstat"].eq(1) & cohort["event"].notna() & cohort["time_months"].notna()].reset_index(drop=True)


def main() -> int:
    frame = pd.read_csv(COHORT)
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    audit = frame.loc[frame["analysis_split"].eq("calibration")].copy().reset_index(drop=True)
    external = load_external()
    features = [c for c in frame.columns if c not in NON_FEATURES]

    # ------------------------------------------------------------------
    # 1) Formal TES component ablation under the ORIGINAL selection rule.
    # ------------------------------------------------------------------
    profiles = pd.read_csv(ROOT / "outputs" / "temporal_shap_stability" / "cycle_feature_shap_profiles.csv")
    selection_profiles = profiles.loc[profiles["cycle"].isin(["2009-2010", "2011-2012"])].copy()
    score_table = stable_score_table(selection_profiles)
    score_table.to_csv(OUT / "TES_COMPONENT_SCORES.csv", index=False)
    component_map = {
        "importance_only": "score_importance_only",
        "no_direction_term": "score_no_direction",
        "no_cv_penalty": "score_no_cv",
        "full_tes": "score_tes",
    }
    component_rows = []
    panels = {}
    for name, score_col in component_map.items():
        panel = select_mass(score_table, score_col)
        panels[name] = panel
        component_rows.append({
            "variant": name,
            "selected_feature_count": len(panel),
            "selected_features": "; ".join(panel),
            "reduction_vs_25": 1.0 - len(panel) / len(features),
        })
    component_table = pd.DataFrame(component_rows)
    component_table.to_csv(OUT / "TES_COMPONENT_ABLATION.csv", index=False)

    tes_status = json.loads((ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json").read_text(encoding="utf-8"))
    tes_features = tes_status["selected_features"]
    if panels["full_tes"] != tes_features:
        raise RuntimeError("Formal TES reconstruction does not reproduce the frozen TES-11 panel")

    # ---------------------------------------------------------------
    # 2) Feature-selection baselines, fixed model and training policy.
    # ---------------------------------------------------------------
    mean_importance = selection_profiles.groupby("feature")["normalized_importance"].mean()
    mean_shap_panel = select_mass(
        pd.DataFrame({"feature": mean_importance.index, "score": mean_importance.values}), "score"
    )
    latest = selection_profiles.loc[selection_profiles["cycle"].eq("2011-2012"), ["feature", "normalized_importance"]]
    latest_shap_panel = select_mass(latest.rename(columns={"normalized_importance": "score"}), "score")
    gain = pd.read_csv(ROOT / "outputs" / "xgboost_survival_pilot" / "feature_importance_gain.csv")
    gain_panel = gain.head(11)["feature"].tolist()

    univariate = []
    for feature in features:
        x_train, _ = prepare_standardized(train, train, [feature])
        beta = cox_fit(x_train, train["time_months"].to_numpy(float), train["event"].to_numpy(int))
        univariate.append({"feature": feature, "abs_standardized_beta": abs(float(beta[0])), "beta": float(beta[0])})
    univariate_table = pd.DataFrame(univariate).sort_values("abs_standardized_beta", ascending=False)
    univariate_table.to_csv(OUT / "UNIVARIATE_COX_FEATURE_RANKING.csv", index=False)
    analyte_ranking = [f for f in univariate_table["feature"] if f not in FORCED]
    univariate_panel = FORCED + analyte_ranking[:9]

    baseline_panels = {
        "TES-11": tes_features,
        "Mean-SHAP mass": mean_shap_panel,
        "Latest-cycle SHAP mass": latest_shap_panel,
        "XGBoost gain top-11": gain_panel,
        "Univariate Cox top-11": univariate_panel,
    }
    aft_protocol = json.loads((ROOT / "AFT_SURVIVAL_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    baseline_models: dict[str, tuple[xgb.Booster, int, list[str]]] = {}
    baseline_dir = OUT / "baseline_models"
    baseline_dir.mkdir(exist_ok=True)
    for name, panel in baseline_panels.items():
        if name == "TES-11":
            model, best = load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj",
                                     ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json")
        else:
            model = fit_aft(train, validation, panel, aft_protocol)
            best = int(model.best_iteration)
            safe_name = name.lower().replace(" ", "_").replace("-", "_")
            model.save_model(baseline_dir / f"{safe_name}.ubj")
        baseline_models[name] = (model, best, panel)

    baseline_rows = []
    for name, (model, best, panel) in baseline_models.items():
        for cohort_name, cohort in [("2013-2014 audit", audit), ("NHANES III external", external)]:
            predicted_time = predict_booster(model, best, cohort, panel)
            c_index = fast_c(cohort["time_months"].to_numpy(float), cohort["event"].to_numpy(int), -predicted_time)
            baseline_rows.append({
                "method": name,
                "features": len(panel),
                "cohort": cohort_name,
                "harrell_c": c_index,
                "selected_features": "; ".join(panel),
                "selection_or_tuning_used_external_outcomes": False,
            })
    baseline_table = pd.DataFrame(baseline_rows)
    baseline_table.to_csv(OUT / "FEATURE_SELECTION_BASELINES.csv", index=False)

    # ---------------------------------------------------------------
    # 3) Censoring-aware survival evaluation of the frozen main models.
    # ---------------------------------------------------------------
    xgb_cox, xgb_cox_best = load_model(ROOT / "outputs" / "xgboost_survival_pilot" / "xgboost_survival_model.ubj",
                                       ROOT / "outputs" / "xgboost_survival_pilot" / "XGBOOST_SURVIVAL_STATUS.json")
    full_aft, full_aft_best = load_model(ROOT / "outputs" / "aft_survival_pilot" / "xgboost_aft_model.ubj",
                                         ROOT / "outputs" / "aft_survival_pilot" / "AFT_SURVIVAL_STATUS.json")
    tes_aft, tes_aft_best = load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj",
                                       ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json")

    # XGBoost-Cox Breslow baseline hazard from development data only.
    train_xgb_risk = predict_booster(xgb_cox, xgb_cox_best, train, features)
    xgb_event_times, xgb_h0 = breslow_baseline(train["time_months"].to_numpy(float),
                                               train["event"].to_numpy(int), train_xgb_risk)

    # Frozen full-panel conventional Cox baseline.
    cox_status = json.loads((ROOT / "outputs" / "cox_baseline" / "COX_BASELINE_STATUS.json").read_text(encoding="utf-8"))
    full_cox = next(item for item in cox_status["models"] if item["model"] == "full_panel_cox")
    cox_features = full_cox["features"]
    beta = np.asarray([full_cox["coefficients_standardized"][c] for c in cox_features], float)
    x_train_std, _ = prepare_standardized(train, train, cox_features)
    train_linear_rr = np.exp(np.clip(x_train_std @ beta, -30, 30))
    linear_event_times, linear_h0 = breslow_baseline(train["time_months"].to_numpy(float),
                                                     train["event"].to_numpy(int), train_linear_rr)
    censor_km = KMCensoring(train["time_months"].to_numpy(float), train["event"].to_numpy(int))

    cohorts = {
        "2009-2012 validation": validation.reset_index(drop=True),
        "2013-2014 audit": audit,
        "2015-2016 frozen confirmation": frame.loc[frame["cycle"].eq("2015-2016")].reset_index(drop=True),
        "2017-2018 short-follow-up stress": frame.loc[frame["cycle"].eq("2017-2018")].reset_index(drop=True),
        "NHANES III external": external,
    }
    safe_integrated_end = {
        "2009-2012 validation": 60.0,
        "2013-2014 audit": 60.0,
        "2015-2016 frozen confirmation": 48.0,
        "2017-2018 short-follow-up stress": 24.0,
        "NHANES III external": 60.0,
    }

    metric_rows = []
    calibration_rows = []
    for cohort_name, cohort in cohorts.items():
        time = cohort["time_months"].to_numpy(float)
        event = cohort["event"].to_numpy(int)

        # Precompute frozen-model risks and survival probability functions.
        xgb_risk = predict_booster(xgb_cox, xgb_cox_best, cohort, features)
        full_aft_margin = predict_booster(full_aft, full_aft_best, cohort, features, output_margin=True)
        tes_margin = predict_booster(tes_aft, tes_aft_best, cohort, tes_features, output_margin=True)
        _, x_cox_std = prepare_standardized(train, cohort, cox_features)
        linear_lp = x_cox_std @ beta
        linear_rr = np.exp(np.clip(linear_lp, -30, 30))

        models = {
            "Full Cox": {
                "risk": linear_rr,
                "survival": lambda h, rr=linear_rr: np.exp(-cumulative_hazard_at(linear_event_times, linear_h0, h) * rr),
            },
            "XGBoost-Cox": {
                "risk": xgb_risk,
                "survival": lambda h, rr=xgb_risk: np.exp(-cumulative_hazard_at(xgb_event_times, xgb_h0, h) * rr),
            },
            "Full AFT": {
                "risk": -np.exp(full_aft_margin),
                "survival": lambda h, mu=full_aft_margin: norm.sf((np.log(h) - mu) / aft_protocol["distribution_scale"]),
            },
            "TES-11 AFT": {
                "risk": -np.exp(tes_margin),
                "survival": lambda h, mu=tes_margin: norm.sf((np.log(h) - mu) / aft_protocol["distribution_scale"]),
            },
        }

        horizons = [24.0]
        if float(np.max(time)) > 60.0:
            horizons.append(60.0)
        integrated_end = safe_integrated_end[cohort_name]
        grid = np.arange(6.0, integrated_end + 0.01, 6.0)

        for model_name, obj in models.items():
            risk = obj["risk"]
            # Uno C uses a truncation tau; 24 months is available in all stages.
            for horizon in horizons:
                s = obj["survival"](horizon)
                metric_rows.append({
                    "cohort": cohort_name,
                    "model": model_name,
                    "horizon_months": int(horizon),
                    "uno_c": uno_c(time, event, risk, censor_km, horizon),
                    "cumulative_dynamic_auc": cumulative_dynamic_auc(time, event, risk, censor_km, horizon),
                    "ipcw_brier": brier_ipcw(time, event, s, censor_km, horizon),
                })
                cal = calibration_ipcw(time, event, 1.0 - s, censor_km, horizon)
                calibration_rows.append({"cohort": cohort_name, "model": model_name,
                                         "horizon_months": int(horizon), **cal})
            brier_values = np.asarray([
                brier_ipcw(time, event, obj["survival"](h), censor_km, h) for h in grid
            ], float)
            integrated = float(np.trapezoid(brier_values, grid) / (grid[-1] - grid[0])) if len(grid) > 1 else float(brier_values[0])
            metric_rows.append({
                "cohort": cohort_name,
                "model": model_name,
                "horizon_months": f"IBS_6_{int(integrated_end)}",
                "uno_c": np.nan,
                "cumulative_dynamic_auc": np.nan,
                "ipcw_brier": integrated,
            })

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUT / "SURVIVAL_METRICS_CENSORING_AWARE.csv", index=False)
    calibration = pd.DataFrame(calibration_rows)
    calibration.to_csv(OUT / "CALIBRATION_SENSITIVITY.csv", index=False)

    # Concise JSON facts used to build the manuscript without transcription errors.
    baseline_pivot = baseline_table.pivot(index="method", columns="cohort", values="harrell_c")
    summary = {
        "status": "PASS",
        "analysis_classification": "post-hoc manuscript-strengthening extension",
        "frozen_confirmatory_artifacts_modified": False,
        "tes_formula_reproduces_frozen_panel": True,
        "component_ablation": component_rows,
        "feature_selection_baselines": {
            method: {
                "features": len(baseline_panels[method]),
                "audit_c": float(baseline_pivot.loc[method, "2013-2014 audit"]),
                "external_c": float(baseline_pivot.loc[method, "NHANES III external"]),
            }
            for method in baseline_panels
        },
        "key_survival_sensitivity": {},
        "claim_boundary": (
            "New ablation, baseline-selection, Uno-C, time-dependent AUC, Brier, and calibration analyses are post-hoc "
            "strengthening analyses. They do not replace or retroactively alter the frozen confirmatory success gates."
        ),
    }
    for cohort_name in ["2009-2012 validation", "2013-2014 audit", "2015-2016 frozen confirmation",
                        "2017-2018 short-follow-up stress", "NHANES III external"]:
        sub = metrics.loc[(metrics["cohort"] == cohort_name) & (metrics["horizon_months"].astype(str) == "24")]
        summary["key_survival_sensitivity"][cohort_name] = {
            row["model"]: {
                "uno_c_24": float(row["uno_c"]),
                "auc_24": float(row["cumulative_dynamic_auc"]),
                "brier_24": float(row["ipcw_brier"]),
            }
            for _, row in sub.iterrows()
        }
    (OUT / "STRONG_Q1_EXTENSION_STATUS.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Human-readable formal specification preserving exact code semantics.
    spec = "# Temporal Explanation-Stable (TES) selection: formal specification\n\n"
    spec += "This document formalizes the already frozen TES selection rule; it does not change the algorithm.\n\n"
    spec += "For feature j and selection cycle c, let I_jc be the normalized mean absolute SHAP importance. " \
            "Let d_jc be Spearman's rho between the feature value and its SHAP contribution within cycle c.\n\n"
    spec += "1. Mean importance: Ibar_j = (1/C) * sum_c I_jc.\n"
    spec += "2. Temporal variation: CV_j = sd(I_j1,...,I_jC) / max(Ibar_j, epsilon).\n"
    spec += "3. Direction agreement: using cycles with |d_jc| >= 0.10, A_j = |mean(sign(d_jc))|; " \
            "if none are reliable, A_j = 0.5.\n"
    spec += "4. TES score: TES_j = Ibar_j * A_j / (1 + CV_j).\n"
    spec += "5. Sort features by TES_j descending. Select the smallest K whose cumulative TES mass reaches 0.90, " \
            "subject to 8 <= K <= 15, and force age and sex if absent.\n\n"
    spec += "The reconstructed rule selects the same 11 features as the frozen TES artifact.\n"
    (OUT / "TES_FORMAL_SPECIFICATION.md").write_text(spec, encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
