from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SOURCE_REGISTRY = ROOT / "data" / "PUBLIC_SOURCE_REGISTRY.json"
ANALYTE_REGISTRY = ROOT / "data" / "ANALYTE_REGISTRY.json"


def guarded_read_xpt(path: Path) -> pd.DataFrame:
    resolved = path.resolve()
    if "confirmatory_locked" in {part.lower() for part in resolved.parts}:
        raise PermissionError(f"Development code refused confirmatory file: {resolved}")
    if not resolved.is_relative_to(RAW.resolve()):
        raise PermissionError(f"Development input must be inside data/raw: {resolved}")
    return pd.read_sas(resolved, format="xport", encoding="latin1")


def main() -> int:
    sources = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))["cycles"]
    analytes = json.loads(ANALYTE_REGISTRY.read_text(encoding="utf-8"))["analytes"]
    rows, audit = [], []
    for source in sources:
        if source["partition"] == "confirmatory_locked":
            continue
        folder = RAW / source["partition"] / source["cycle"]
        lab = guarded_read_xpt(folder / f"{source['laboratory']}.XPT")
        demo = guarded_read_xpt(folder / f"{source['demographics']}.XPT")
        output = pd.DataFrame({"participant_id": lab["SEQN"].astype("Int64")})
        missing_columns = []
        for canonical, mapping in analytes.items():
            source_column = mapping.get(source["cycle"], mapping["default"])
            if source_column not in lab.columns:
                missing_columns.append(f"{canonical}:{source_column}")
                output[canonical] = pd.NA
            else:
                output[canonical] = pd.to_numeric(lab[source_column], errors="coerce")
        demo_keep = [column for column in ("SEQN", "RIDAGEYR", "RIAGENDR") if column in demo.columns]
        demo_small = demo[demo_keep].copy().rename(columns={"SEQN": "participant_id", "RIDAGEYR": "age_years", "RIAGENDR": "sex_code"})
        demo_small["participant_id"] = demo_small["participant_id"].astype("Int64")
        output = output.merge(demo_small, on="participant_id", how="left", validate="one_to_one")
        output.insert(1, "cycle", source["cycle"])
        output.insert(2, "partition", source["partition"])
        rows.append(output)
        audit.append({"cycle": source["cycle"], "partition": source["partition"], "rows": len(output),
                      "analytes": len(analytes), "missing_source_columns": missing_columns,
                      "complete_panel_rows": int(output[list(analytes)].notna().all(axis=1).sum())})
    combined = pd.concat(rows, ignore_index=True)
    if combined.duplicated(["cycle", "participant_id"]).any():
        raise RuntimeError("Duplicate participant within cycle")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    combined.to_csv(PROCESSED / "nhanes_harmonized_panel.csv.gz", index=False, compression="gzip")
    (PROCESSED / "HARMONIZATION_AUDIT.json").write_text(json.dumps({"cycles": audit,
        "total_rows": len(combined), "analytes": list(analytes),
        "confirmatory_read": False}, indent=2), encoding="utf-8")
    print(f"PASS: rows={len(combined)} analytes={len(analytes)} cycles={len(audit)}")
    for row in audit:
        print(f"{row['cycle']}: rows={row['rows']} complete={row['complete_panel_rows']} missing_columns={len(row['missing_source_columns'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
