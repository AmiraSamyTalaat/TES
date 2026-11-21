from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "data" / "processed" / "nhanes_survival_cohort_survey.csv.gz"
NH3_FEATURES = ROOT / "external_nhanes3" / "processed_features" / "nhanes3_feature_cohort_locked_outcome.csv.gz"
NH3_MORT = ROOT / "external_nhanes3" / "locked_mortality" / "NHANES_III_MORT_2019_PUBLIC.dat"
OUT = ROOT / "publication"
TES_LABS = ["alt_u_l", "ggt_u_l", "glucose_mmol_l", "alp_u_l", "chloride_mmol_l",
            "albumin_g_l", "bun_mmol_l", "potassium_mmol_l", "ldh_u_l"]


def weighted_mean(values, weights):
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    return float(np.average(values[valid], weights=weights[valid]))


def weighted_median(values, weights):
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    values, weights = values[valid], weights[valid]
    order = np.argsort(values, kind="mergesort")
    values, weights = values[order], weights[order]
    return float(values[np.searchsorted(np.cumsum(weights), 0.5 * weights.sum(), side="left")])


def summarize(name, frame, weight_column):
    weight = frame[weight_column].to_numpy(float)
    row = {"cohort": name, "participants_n": len(frame), "deaths_n": int(frame["event"].sum()),
           "unweighted_death_fraction": float(frame["event"].mean()),
           "median_followup_months": float(frame["time_months"].median()),
           "survey_weighted_mean_age_years": weighted_mean(frame["age_years"].to_numpy(float), weight),
           "survey_weighted_female_fraction": weighted_mean(frame["sex_code"].eq(2).to_numpy(float), weight)}
    for lab in TES_LABS:
        row[f"survey_weighted_median_{lab}"] = weighted_median(frame[lab].to_numpy(float), weight)
    return row


def main() -> int:
    main = pd.read_csv(MAIN)
    groups = [
        ("NHANES 1999-2008 development", main["analysis_split"].eq("train")),
        ("NHANES 2009-2012 validation", main["analysis_split"].eq("validation")),
        ("NHANES 2013-2014 audit", main["analysis_split"].eq("calibration")),
        ("NHANES 2015-2016 temporal confirmation", main["cycle"].eq("2015-2016")),
        ("NHANES 2017-2018 short-follow-up stress test", main["cycle"].eq("2017-2018")),
    ]
    rows = [summarize(name, main.loc[mask].copy(), "exam_weight_2yr") for name, mask in groups]
    nh3 = pd.read_csv(NH3_FEATURES)
    mortality = pd.read_fwf(NH3_MORT, colspecs=[(0, 6), (14, 15), (15, 16), (42, 45)],
                            names=["participant_id", "eligstat", "event", "time_months"]).apply(pd.to_numeric, errors="coerce")
    nh3 = nh3.merge(mortality, on="participant_id", how="inner", validate="one_to_one")
    nh3 = nh3.loc[nh3["eligstat"].eq(1) & nh3["event"].notna() & nh3["time_months"].notna()].copy()
    rows.append(summarize("NHANES III external-era validation", nh3, "exam_weight"))
    table = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "TABLE1_COHORT_CHARACTERISTICS.csv", index=False)
    status = {"status": "PASS", "rows": len(table), "cohorts": table["cohort"].tolist(),
              "weighted_fields": [c for c in table.columns if c.startswith("survey_weighted_")],
              "note": "Death fractions are descriptive and not comparable across cohorts with unequal administrative follow-up."}
    (OUT / "TABLE1_BUILD_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

