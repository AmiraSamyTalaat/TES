from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "external_nhanes3"
RAW = EXT / "raw_features"
SCHEMA = EXT / "NHANES3_SCHEMA_AUDIT.json"
OUT = EXT / "processed_features"

DECIMALS = {
    "sodium_mmol_l": 1, "potassium_mmol_l": 2, "chloride_mmol_l": 1,
    "bicarbonate_mmol_l": 0, "calcium_mmol_l": 3, "phosphorus_mmol_l": 3,
    "uric_acid_umol_l": 1, "glucose_mmol_l": 2, "bun_mmol_l": 2,
    "bilirubin_umol_l": 2, "creatinine_umol_l": 1, "iron_umol_l": 1,
    "cholesterol_mmol_l": 3, "triglycerides_mmol_l": 3,
    "ast_u_l": 0, "alt_u_l": 0, "ggt_u_l": 0, "ldh_u_l": 0, "alp_u_l": 0,
    "protein_g_l": 0, "albumin_g_l": 0, "globulin_g_l": 0, "osmolality_mmol_kg": 0,
}


def read_fixed(path: Path, mapping: dict) -> pd.DataFrame:
    names = list(mapping)
    colspecs = [(value[0] - 1, value[1]) for value in mapping.values()]
    frame = pd.read_fwf(path, colspecs=colspecs, names=names, dtype=str)
    for name in names:
        text = frame[name].str.strip()
        text = text.mask(text.str.fullmatch(r"8+|9+", na=False))
        frame[name] = pd.to_numeric(text, errors="coerce")
    return frame


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    adult = read_fixed(RAW / "adult.dat", schema["adult_fixed_width_1_based"])
    lab = read_fixed(RAW / "lab.dat", schema["lab_fixed_width_1_based"])
    # NHANES III ASCII values include explicit decimal points; SAS informat decimals
    # describe display precision and must not be applied as an additional scale.
    adult["participant_id"] = adult["participant_id"].astype("Int64")
    lab["participant_id"] = lab["participant_id"].astype("Int64")
    if adult["participant_id"].duplicated().any() or lab["participant_id"].duplicated().any():
        raise RuntimeError("Duplicate NHANES III participant identifier")
    cohort = adult.merge(lab, on="participant_id", how="inner", validate="one_to_one")
    cohort = cohort.loc[(cohort["age_years"] >= 20) & (cohort["exam_weight"] > 0)].copy()
    analytes = list(DECIMALS)
    plausible = {
        "sodium_mmol_l": (90, 190), "potassium_mmol_l": (1, 10),
        "chloride_mmol_l": (60, 150), "calcium_mmol_l": (1, 5),
        "glucose_mmol_l": (1, 50), "creatinine_umol_l": (10, 3000),
        "albumin_g_l": (5, 80)
    }
    plausibility = {}
    for column, (low, high) in plausible.items():
        valid = cohort[column].dropna()
        plausibility[column] = {"nonmissing": int(len(valid)), "median": float(valid.median()),
                                "within_plausible_fraction": float(valid.between(low, high).mean())}
        if len(valid) == 0 or plausibility[column]["within_plausible_fraction"] < 0.95:
            raise RuntimeError(f"Implausible scale detected for {column}: {plausibility[column]}")
    OUT.mkdir(parents=True, exist_ok=True)
    cohort.to_csv(OUT / "nhanes3_feature_cohort_locked_outcome.csv.gz", index=False, compression="gzip")
    status = {"status": "PASS", "adult_rows": len(adult), "lab_rows": len(lab),
              "adult_lab_rows_age20_weighted": len(cohort), "analytes": len(analytes),
              "complete_23_analyte_rows": int(cohort[analytes].notna().all(axis=1).sum()),
              "complete_tes11_rows": int(cohort[["age_years", "sex_code", "alt_u_l", "ggt_u_l", "glucose_mmol_l",
                                                   "alp_u_l", "chloride_mmol_l", "albumin_g_l", "bun_mmol_l",
                                                   "potassium_mmol_l", "ldh_u_l"]].notna().all(axis=1).sum()),
              "plausibility": plausibility, "mortality_file_read": False}
    (OUT / "NHANES3_FEATURE_COHORT_STATUS.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
