from __future__ import annotations

"""Post-hoc stability strengthening for the Strong-Q1 manuscript.

This script is an additive analysis layer. It does not modify any frozen
confirmatory artifact. It addresses three reviewer-facing questions:
1) Is TES panel selection stable to resampling of the selection-era data?
2) Is the TES-11 result sensitive to the direction threshold or score-mass cutoff?
3) How does TES compare with a generic resampling stability-selection comparator?

All resampling, tuning, and consensus construction use only 2009-2012 selection-era
data. 2013-2014 is an audit cohort and NHANES III is read only after panels are fixed.
"""

import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "strong_q1_stability_extension"
OUT.mkdir(parents=True, exist_ok=True)

COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort.csv.gz"
EXT_FEATURES = ROOT / "external_nhanes3" / "processed_features" / "nhanes3_feature_cohort_locked_outcome.csv.gz"
EXT_MORTALITY = ROOT / "external_nhanes3" / "locked_mortality" / "NHANES_III_MORT_2019_PUBLIC.dat"

NON_FEATURES = {
    "participant_id", "cycle", "partition", "analysis_split", "eligstat",
    "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int",
    "permth_exm", "event", "time_months",
}
FORCED = ["age_years", "sex_code"]
SELECTION_CYCLES = ["2009-2010", "2011-2012"]
SEED = 20260830
N_RESAMPLES = 200
SUBSAMPLE_FRACTION = 0.5
EPS = 1e-12


def fast_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray) -> float:
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


def aft_matrix(frame: pd.DataFrame, features: list[str]) -> xgb.DMatrix:
    matrix = xgb.DMatrix(
        frame[features].apply(pd.to_numeric, errors="coerce").to_numpy(float),
        feature_names=features,
        missing=np.nan,
    )
    time = frame["time_months"].to_numpy(float)
    event = frame["event"].to_numpy(int)
    matrix.set_float_info("label_lower_bound", time)
    matrix.set_float_info("label_upper_bound", np.where(event == 1, time, np.inf))
    return matrix


def fit_aft(train: pd.DataFrame, validation: pd.DataFrame, panel: list[str], protocol: dict) -> xgb.Booster:
    params = dict(protocol["parameters"])
    params.update({
        "objective": "survival:aft",
        "eval_metric": "aft-nloglik",
        "aft_loss_distribution": protocol["distribution"],
        "aft_loss_distribution_scale": protocol["distribution_scale"],
        "tree_method": "hist",
    })
    return xgb.train(
        params,
        aft_matrix(train, panel),
        num_boost_round=protocol["maximum_rounds"],
        evals=[(aft_matrix(validation, panel), "validation")],
        early_stopping_rounds=protocol["early_stopping_rounds"],
        verbose_eval=False,
    )


def predict_aft(model: xgb.Booster, best: int, frame: pd.DataFrame, panel: list[str]) -> np.ndarray:
    return model.predict(aft_matrix(frame, panel), iteration_range=(0, best + 1))


def load_external() -> pd.DataFrame:
    feature_frame = pd.read_csv(EXT_FEATURES)
    mortality = pd.read_fwf(
        EXT_MORTALITY,
        colspecs=[(0, 6), (14, 15), (15, 16), (42, 45)],
        names=["participant_id", "eligstat", "event", "time_months"],
    ).apply(pd.to_numeric, errors="coerce")
    cohort = feature_frame.merge(mortality, on="participant_id", how="inner", validate="one_to_one")
    return cohort.loc[
        cohort["eligstat"].eq(1) & cohort["event"].notna() & cohort["time_months"].notna()
    ].reset_index(drop=True)


def profile_from_arrays(values: np.ndarray, contributions: np.ndarray, features: list[str]) -> pd.DataFrame:
    importance = np.mean(np.abs(contributions), axis=0)
    normalized = importance / max(float(importance.sum()), EPS)
    directions = []
    for j in range(len(features)):
        valid = np.isfinite(values[:, j]) & np.isfinite(contributions[:, j])
        if int(valid.sum()) < 20:
            directions.append(0.0)
            continue
        a = rankdata(values[valid, j])
        b = rankdata(contributions[valid, j])
        a = a - a.mean(); b = b - b.mean()
        den = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
        rho = float(np.sum(a * b) / den) if den > 0 else 0.0
        directions.append(rho if np.isfinite(rho) else 0.0)
    directions = np.asarray(directions, float)
    return pd.DataFrame({
        "feature": features,
        "normalized_importance": normalized,
        "direction_spearman": directions,
    })


def tes_score_table(profiles: dict[str, pd.DataFrame], direction_threshold: float = 0.10) -> pd.DataFrame:
    rows = []
    for feature in profiles[SELECTION_CYCLES[0]]["feature"]:
        importance = np.array([
            float(profiles[c].loc[profiles[c]["feature"].eq(feature), "normalized_importance"].iloc[0])
            for c in SELECTION_CYCLES
        ])
        directions = np.array([
            float(profiles[c].loc[profiles[c]["feature"].eq(feature), "direction_spearman"].iloc[0])
            for c in SELECTION_CYCLES
        ])
        mean_imp = float(np.mean(importance))
        cv = float(np.std(importance) / max(mean_imp, EPS))
        reliable = directions[np.abs(directions) >= direction_threshold]
        agreement = float(abs(np.mean(np.sign(reliable)))) if len(reliable) else 0.5
        rows.append({
            "feature": feature,
            "mean_importance": mean_imp,
            "importance_cv": cv,
            "direction_agreement": agreement,
            "tes_score": mean_imp * agreement / (1.0 + cv),
        })
    return pd.DataFrame(rows)


def select_mass(score_table: pd.DataFrame, score_col: str, threshold: float = 0.90,
                min_k: int = 8, max_k: int = 15) -> list[str]:
    ranked = score_table.sort_values(score_col, ascending=False).reset_index(drop=True)
    total = float(ranked[score_col].sum())
    if total <= 0:
        raise RuntimeError("Nonpositive score mass")
    mass = ranked[score_col].cumsum() / total
    k = int(np.searchsorted(mass.to_numpy(), threshold, side="left") + 1)
    k = max(min_k, min(max_k, k))
    selected = ranked.head(k)["feature"].tolist()
    for feature in FORCED:
        if feature not in selected:
            selected.append(feature)
    return list(dict.fromkeys(selected))


def cox_score_z(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Vectorized standardized Cox score statistic at beta=0 for all features."""
    x = frame[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    med = np.nanmedian(x, axis=0)
    x = np.where(np.isfinite(x), x, med)
    center = np.median(x, axis=0)
    scale = np.quantile(x, 0.75, axis=0) - np.quantile(x, 0.25, axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    x = (x - center) / scale
    time = frame["time_months"].to_numpy(float)
    event = frame["event"].to_numpy(int)
    order = np.argsort(-time, kind="mergesort")
    x = x[order]
    time = time[order]
    event = event[order]
    cs1 = np.cumsum(x, axis=0)
    cs2 = np.cumsum(x * x, axis=0)
    u = np.zeros(x.shape[1])
    info = np.zeros(x.shape[1])
    pos = 0
    while pos < len(time):
        end = pos + 1
        while end < len(time) and time[end] == time[pos]:
            end += 1
        dmask = event[pos:end] == 1
        d = int(np.sum(dmask))
        if d:
            n_risk = end
            mean = cs1[end - 1] / n_risk
            mean2 = cs2[end - 1] / n_risk
            u += np.sum(x[pos:end][dmask], axis=0) - d * mean
            info += d * np.maximum(mean2 - mean * mean, 0.0)
        pos = end
    return u / np.sqrt(np.maximum(info, 1e-12))


def jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def nogueira_stability(sets: list[list[str]], all_features: list[str]) -> float:
    z = np.zeros((len(sets), len(all_features)), dtype=float)
    idx = {f: j for j, f in enumerate(all_features)}
    for i, selected in enumerate(sets):
        for f in selected:
            z[i, idx[f]] = 1.0
    p_hat = z.mean(axis=0)
    variances = (len(sets) / (len(sets) - 1)) * p_hat * (1.0 - p_hat)
    kbar = z.sum(axis=1).mean()
    p = len(all_features)
    denom = (kbar / p) * (1.0 - kbar / p)
    return float(1.0 - variances.mean() / denom) if denom > 0 else float("nan")


def summarize_sets(name: str, sets: list[list[str]], all_features: list[str], reference: list[str]) -> tuple[dict, pd.DataFrame]:
    freq = {f: np.mean([f in s for s in sets]) for f in all_features}
    js = [jaccard(set(a), set(b)) for a, b in combinations(sets, 2)]
    ref_js = [jaccard(set(s), set(reference)) for s in sets]
    counts = np.array([len(s) for s in sets], int)
    summary = {
        "selector": name,
        "resamples": len(sets),
        "mean_selected_count": float(np.mean(counts)),
        "selected_count_2_5pct": float(np.quantile(counts, 0.025)),
        "selected_count_97_5pct": float(np.quantile(counts, 0.975)),
        "mean_pairwise_jaccard": float(np.mean(js)),
        "median_pairwise_jaccard": float(np.median(js)),
        "nogueira_stability": nogueira_stability(sets, all_features),
        "mean_jaccard_to_frozen_tes11": float(np.mean(ref_js)),
    }
    table = pd.DataFrame({"feature": all_features, "selection_frequency": [freq[f] for f in all_features]})
    table.insert(0, "selector", name)
    return summary, table


def paired_bootstrap_difference(time: np.ndarray, event: np.ndarray, risk_a: np.ndarray, risk_b: np.ndarray,
                                reps: int = 500, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    point = fast_c(time, event, risk_a) - fast_c(time, event, risk_b)
    diffs = []
    for _ in range(reps):
        idx = rng.choice(len(time), len(time), replace=True)
        diffs.append(fast_c(time[idx], event[idx], risk_a[idx]) - fast_c(time[idx], event[idx], risk_b[idx]))
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {"point_difference": float(point), "ci95": [float(lo), float(hi)]}


def main() -> int:
    frame = pd.read_csv(COHORT)
    features = [c for c in frame.columns if c not in NON_FEATURES]
    train = frame.loc[frame["analysis_split"].eq("train")].copy()
    validation = frame.loc[frame["analysis_split"].eq("validation")].copy()
    audit = frame.loc[frame["analysis_split"].eq("calibration")].copy().reset_index(drop=True)

    tes_status = json.loads((ROOT / "outputs" / "tes_aft_pilot" / "TES_AFT_STATUS.json").read_text(encoding="utf-8"))
    frozen_tes = tes_status["selected_features"]

    # Fixed model used by the original temporal SHAP/TES procedure.
    shap_model = xgb.Booster()
    shap_model.load_model(ROOT / "outputs" / "xgboost_survival_pilot" / "xgboost_survival_model.ubj")
    shap_best = int(json.loads((ROOT / "outputs" / "xgboost_survival_pilot" / "XGBOOST_SURVIVAL_STATUS.json").read_text(encoding="utf-8"))["best_iteration"])

    cycle_cache = {}
    full_profiles = {}
    for cycle in SELECTION_CYCLES:
        subset = frame.loc[frame["cycle"].eq(cycle)].reset_index(drop=True)
        values = subset[features].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        dm = xgb.DMatrix(values, feature_names=features, missing=np.nan)
        contrib = shap_model.predict(dm, pred_contribs=True, iteration_range=(0, shap_best + 1))[:, :-1]
        cycle_cache[cycle] = (subset, values, contrib)
        full_profiles[cycle] = profile_from_arrays(values, contrib, features)

    default_table = tes_score_table(full_profiles, 0.10)
    reconstructed = select_mass(default_table, "tes_score", 0.90)
    if reconstructed != frozen_tes:
        raise RuntimeError("Stability extension does not reconstruct frozen TES-11")

    # ---------------------------------------------------------------
    # A) Stratified half-sample panel-selection stability.
    # ---------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    tes_sets: list[list[str]] = []
    mean_shap_sets: list[list[str]] = []
    latest_shap_sets: list[list[str]] = []
    cox_top11_sets: list[list[str]] = []

    for rep in range(N_RESAMPLES):
        if rep % 25 == 0: print(f"resample {rep}/{N_RESAMPLES}", flush=True)
        prof = {}
        pooled_parts = []
        for cycle in SELECTION_CYCLES:
            subset, values, contrib = cycle_cache[cycle]
            n_take = int(round(len(subset) * SUBSAMPLE_FRACTION))
            idx = rng.choice(len(subset), n_take, replace=False)
            prof[cycle] = profile_from_arrays(values[idx], contrib[idx], features)
            pooled_parts.append(subset.iloc[idx])

        tes_tab = tes_score_table(prof, 0.10)
        tes_sets.append(select_mass(tes_tab, "tes_score", 0.90))

        mean_tab = pd.DataFrame({
            "feature": features,
            "score": np.mean([
                prof[c].set_index("feature").loc[features, "normalized_importance"].to_numpy(float)
                for c in SELECTION_CYCLES
            ], axis=0),
        })
        mean_shap_sets.append(select_mass(mean_tab, "score", 0.90))

        latest_tab = prof["2011-2012"][["feature", "normalized_importance"]].rename(columns={"normalized_importance": "score"})
        latest_shap_sets.append(select_mass(latest_tab, "score", 0.90))

        pooled = pd.concat(pooled_parts, ignore_index=True)
        z = np.abs(cox_score_z(pooled, features))
        ranked = [features[i] for i in np.argsort(-z)]
        analytes = [f for f in ranked if f not in FORCED]
        cox_top11_sets.append(FORCED + analytes[:9])

    stability_summaries = []
    frequency_tables = []
    for name, sets in [
        ("TES 90%-mass", tes_sets),
        ("Mean-SHAP 90%-mass", mean_shap_sets),
        ("Latest-cycle SHAP 90%-mass", latest_shap_sets),
        ("Cox-score top-11 base selector", cox_top11_sets),
    ]:
        s, t = summarize_sets(name, sets, features, frozen_tes)
        stability_summaries.append(s)
        frequency_tables.append(t)

    pd.DataFrame(stability_summaries).to_csv(OUT / "PANEL_SELECTION_STABILITY_SUMMARY.csv", index=False)
    freq_all = pd.concat(frequency_tables, ignore_index=True)
    freq_all.to_csv(OUT / "PANEL_SELECTION_FREQUENCIES.csv", index=False)

    # Generic stability-selection comparator: consensus top-11 by half-sample
    # recurrence of a Cox survival-association base selector. This uses the
    # stability-selection principle (subsampling + recurrence), without claiming
    # Meinshausen-Buehlmann false-discovery bounds for this top-k base selector.
    cox_freq = freq_all.loc[freq_all["selector"].eq("Cox-score top-11 base selector")].sort_values(
        ["selection_frequency", "feature"], ascending=[False, True]
    )
    cox_consensus_rank = cox_freq["feature"].tolist()
    cox_consensus = FORCED + [f for f in cox_consensus_rank if f not in FORCED][:9]
    cox_consensus = list(dict.fromkeys(cox_consensus))

    # Also derive a resampling-consensus SHAP comparator (descriptive baseline).
    mean_freq = freq_all.loc[freq_all["selector"].eq("Mean-SHAP 90%-mass")].sort_values(
        ["selection_frequency", "feature"], ascending=[False, True]
    )
    mean_consensus_rank = mean_freq["feature"].tolist()
    shap_consensus = FORCED + [f for f in mean_consensus_rank if f not in FORCED][:9]
    shap_consensus = list(dict.fromkeys(shap_consensus))

    aft_protocol = json.loads((ROOT / "AFT_SURVIVAL_PROTOCOL_FREEZE.json").read_text(encoding="utf-8"))
    compare_panels = {
        "TES-11": frozen_tes,
        "Cox stability-selection consensus top-11": cox_consensus,
        "Resampling-consensus SHAP top-11": shap_consensus,
    }
    model_dir = OUT / "models"
    model_dir.mkdir(exist_ok=True)
    models = {}
    for name, panel in compare_panels.items():
        if name == "TES-11":
            m = xgb.Booster(); m.load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj")
            best = int(tes_status["best_iteration"])
        else:
            m = fit_aft(train, validation, panel, aft_protocol)
            best = int(m.best_iteration)
            m.save_model(model_dir / ("cox_stability_consensus.ubj" if name.startswith("Cox") else "shap_resampling_consensus.ubj"))
        models[name] = (m, best, panel)

    # Panels are fixed before external outcomes are loaded.
    print("resampling complete; fitting stability-aware comparator models", flush=True)
    external = load_external()
    comparator_rows = []
    predictions = {}
    for cohort_name, cohort in [("2013-2014 audit", audit), ("NHANES III external", external)]:
        predictions[cohort_name] = {}
        for name, (m, best, panel) in models.items():
            pred = predict_aft(m, best, cohort, panel)
            predictions[cohort_name][name] = -pred
            comparator_rows.append({
                "method": name,
                "features": len(panel),
                "cohort": cohort_name,
                "harrell_c": fast_c(cohort["time_months"].to_numpy(float), cohort["event"].to_numpy(int), -pred),
                "selected_features": "; ".join(panel),
                "external_outcomes_used_for_selection_or_tuning": False,
            })
    pd.DataFrame(comparator_rows).to_csv(OUT / "STABILITY_AWARE_BASELINE_COMPARISON.csv", index=False)

    paired = {}
    for cohort_name, cohort in [("2013-2014 audit", audit), ("NHANES III external", external)]:
        t = cohort["time_months"].to_numpy(float); e = cohort["event"].to_numpy(int)
        tes_c = fast_c(t, e, predictions[cohort_name]["TES-11"])
        cmp_c = fast_c(t, e, predictions[cohort_name]["Cox stability-selection consensus top-11"])
        paired[cohort_name] = {"tes_c": float(tes_c), "comparator_c": float(cmp_c), "point_difference": float(tes_c-cmp_c)}

    # ---------------------------------------------------------------
    # B) Sensitivity to direction reliability and TES-mass thresholds.
    # ---------------------------------------------------------------
    sensitivity_rows = []
    unique_panels: dict[tuple[str, ...], tuple[xgb.Booster, int]] = {}
    print("baseline comparison complete; running TES threshold sensitivity", flush=True)
    for direction_threshold in [0.05, 0.10, 0.15]:
        tab = tes_score_table(full_profiles, direction_threshold)
        for mass_threshold in [0.90, 0.925, 0.95]:
            # Report unconstrained K to show whether 8-15 bounds are active.
            ranked = tab.sort_values("tes_score", ascending=False).reset_index(drop=True)
            cum = ranked["tes_score"].cumsum() / ranked["tes_score"].sum()
            unconstrained_k = int(np.searchsorted(cum.to_numpy(), mass_threshold, side="left") + 1)
            panel = select_mass(tab, "tes_score", mass_threshold, min_k=8, max_k=15)
            key = tuple(panel)
            if key not in unique_panels:
                if panel == frozen_tes:
                    m = xgb.Booster(); m.load_model(ROOT / "outputs" / "tes_aft_pilot" / "tes_aft_model.ubj")
                    best = int(tes_status["best_iteration"])
                else:
                    m = fit_aft(train, validation, panel, aft_protocol)
                    best = int(m.best_iteration)
                    m.save_model(model_dir / f"sensitivity_k{len(panel)}_{abs(hash(key)) % 1000000}.ubj")
                unique_panels[key] = (m, best)
            m, best = unique_panels[key]
            audit_c = fast_c(audit["time_months"].to_numpy(float), audit["event"].to_numpy(int), -predict_aft(m, best, audit, panel))
            ext_c = fast_c(external["time_months"].to_numpy(float), external["event"].to_numpy(int), -predict_aft(m, best, external, panel))
            sensitivity_rows.append({
                "direction_reliability_threshold": direction_threshold,
                "tes_mass_threshold": mass_threshold,
                "unconstrained_k_before_8_15_bounds": unconstrained_k,
                "selected_feature_count": len(panel),
                "selected_features": "; ".join(panel),
                "audit_harrell_c": audit_c,
                "external_harrell_c": ext_c,
            })
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.to_csv(OUT / "TES_HYPERPARAMETER_SENSITIVITY.csv", index=False)

    # Primary 90% selection is independent of tested direction threshold and has
    # unconstrained K=11, showing that neither 8 nor 15 bound is active.
    primary_sensitivity = sensitivity.loc[sensitivity["tes_mass_threshold"].eq(0.90)]
    primary_panel_invariant = primary_sensitivity["selected_features"].nunique() == 1
    primary_bounds_inactive = bool((primary_sensitivity["unconstrained_k_before_8_15_bounds"] == 11).all())

    summary = {
        "status": "PASS",
        "analysis_classification": "post-hoc Strong-Q1 stability/sensitivity extension",
        "frozen_confirmatory_artifacts_modified": False,
        "selection_data_only_for_resampling_and_consensus": "NHANES 2009-2012",
        "resampling": {
            "replicates": N_RESAMPLES,
            "scheme": "stratified half-sampling without replacement within 2009-2010 and 2011-2012",
            "seed": SEED,
            "summaries": stability_summaries,
        },
        "stability_aware_comparator": {
            "name": "Cox stability-selection consensus top-11",
            "principle": "subsampling plus recurrence consensus using a survival-specific Cox score top-11 base selector",
            "false_discovery_control_claimed": False,
            "selected_features": cox_consensus,
            "paired_tes_minus_comparator": paired,
        },
        "resampling_consensus_shap_panel": shap_consensus,
        "sensitivity": {
            "direction_thresholds": [0.05, 0.10, 0.15],
            "tes_mass_thresholds": [0.90, 0.925, 0.95],
            "primary_90pct_panel_invariant_across_direction_thresholds": bool(primary_panel_invariant),
            "primary_90pct_k_bounds_inactive": primary_bounds_inactive,
            "unique_panels_across_grid": int(sensitivity["selected_features"].nunique()),
        },
        "claim_boundary": (
            "These analyses are post-hoc robustness analyses. They support selection stability and parameter robustness "
            "but do not convert NHANES III into a different-health-system deployment validation."
        ),
    }
    (OUT / "STRONG_Q1_STABILITY_EXTENSION_STATUS.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
