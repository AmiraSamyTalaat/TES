from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "PUBLIC_SOURCE_REGISTRY.json"
RAW = ROOT / "data" / "raw"
COHORT = ROOT / "data" / "processed" / "nhanes_survival_cohort.csv.gz"
OUTPUT = ROOT / "data" / "processed" / "nhanes_survival_cohort_survey.csv.gz"
AUDIT = ROOT / "data" / "processed" / "SURVEY_AUGMENTATION_AUDIT.json"
REQUIRED = ["SEQN", "WTMEC2YR", "SDMVSTRA", "SDMVPSU"]


def main() -> int:
    cohort = pd.read_csv(COHORT)
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["cycles"]
    pieces, audit = [], []
    for source in registry:
        cycle = source["cycle"]
        if cycle not in set(cohort["cycle"]):
            continue
        path = RAW / source["partition"] / cycle / f"{source['demographics']}.XPT"
        demo = pd.read_sas(path, format="xport", encoding="latin1")
        missing = [column for column in REQUIRED if column not in demo.columns]
        if missing:
            raise RuntimeError(f"{cycle} missing survey variables: {missing}")
        design = demo[REQUIRED].rename(columns={"SEQN": "participant_id",
                                                "WTMEC2YR": "exam_weight_2yr",
                                                "SDMVSTRA": "survey_stratum",
                                                "SDMVPSU": "survey_psu"})
        design["participant_id"] = design["participant_id"].astype("Int64")
        part = cohort.loc[cohort["cycle"].eq(cycle)].merge(
            design, on="participant_id", how="left", validate="one_to_one")
        # For pooled estimates across ten two-year cycles, divide each cycle weight by ten.
        part["pooled_exam_weight_20yr"] = part["exam_weight_2yr"] / 10.0
        if part[["exam_weight_2yr", "survey_stratum", "survey_psu"]].isna().any().any():
            raise RuntimeError(f"{cycle} has unmatched survey design rows")
        pieces.append(part)
        audit.append({"cycle": cycle, "rows": len(part),
                      "positive_exam_weights": int((part["exam_weight_2yr"] > 0).sum()),
                      "strata": int(part["survey_stratum"].nunique()),
                      "psu": int(part[["survey_stratum", "survey_psu"]].drop_duplicates().shape[0])})
    combined = pd.concat(pieces, ignore_index=True)
    combined.to_csv(OUTPUT, index=False, compression="gzip")
    status = {"status": "PASS", "rows": len(combined), "cycles": audit,
              "survey_variables": ["exam_weight_2yr", "survey_stratum", "survey_psu", "pooled_exam_weight_20yr"]}
    AUDIT.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

