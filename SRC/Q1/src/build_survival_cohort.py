from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "nhanes_harmonized_panel.csv.gz"
RAW_MORT = ROOT / "data" / "raw_mortality"
OUT = ROOT / "data" / "processed"

SPLITS = {
    **{x: "train" for x in ("1999-2000", "2001-2002", "2003-2004", "2005-2006", "2007-2008")},
    **{x: "validation" for x in ("2009-2010", "2011-2012")},
    "2013-2014": "calibration",
    "2015-2016": "confirmatory_locked",
    "2017-2018": "confirmatory_locked",
}


def read_mortality(path: Path) -> pd.DataFrame:
    # Positions are defined by the CDC public-use linked mortality data dictionary.
    frame = pd.read_fwf(path, colspecs=[(0, 6), (14, 15), (15, 16), (16, 19),
                                        (19, 20), (20, 21), (42, 45), (45, 48)],
                        names=["participant_id", "eligstat", "mortstat", "ucod_leading",
                               "diabetes", "hyperten", "permth_int", "permth_exm"])
    return frame.apply(pd.to_numeric, errors="coerce")


def main() -> int:
    if not PANEL.exists():
        raise FileNotFoundError(f"Verified harmonized panel is missing: {PANEL}")
    panel = pd.read_csv(PANEL)
    merged_parts, audit = [], []
    for cycle, split in SPLITS.items():
        mortality_path = RAW_MORT / f"NHANES_{cycle.replace('-', '_')}_MORT_2019_PUBLIC.dat"
        mortality = read_mortality(mortality_path)
        cohort = panel.loc[panel["cycle"].eq(cycle)].merge(
            mortality, on="participant_id", how="inner", validate="one_to_one")
        cohort = cohort.loc[(cohort["age_years"] >= 20) & cohort["eligstat"].eq(1)].copy()
        cohort["analysis_split"] = split
        cohort["event"] = cohort["mortstat"].astype("Int64")
        cohort["time_months"] = cohort["permth_int"]
        bad = cohort["event"].isna() | cohort["time_months"].isna() | (cohort["time_months"] < 0)
        cohort = cohort.loc[~bad].copy()
        merged_parts.append(cohort)
        audit.append({"cycle": cycle, "split": split, "rows": len(cohort),
                      "events": int(cohort["event"].sum()),
                      "event_rate": float(cohort["event"].mean()),
                      "median_followup_months": float(cohort["time_months"].median())})
    combined = pd.concat(merged_parts, ignore_index=True)
    if combined.duplicated(["cycle", "participant_id"]).any():
        raise RuntimeError("Duplicate participant within cycle")
    OUT.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT / "nhanes_survival_cohort.csv.gz", index=False, compression="gzip")
    status = {"status": "PASS", "rows": len(combined), "events": int(combined["event"].sum()),
              "confirmatory_outcomes_used_for_fitting": False, "cycles": audit}
    (OUT / "SURVIVAL_COHORT_AUDIT.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

