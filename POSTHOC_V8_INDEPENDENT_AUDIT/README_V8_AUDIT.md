# Independent code audit (2026-11-21)

These reports are based on the locally archived NHANES 1999–2018 source package and ORIGINAL saved XGBoost-AFT booster; they do not claim new CDC downloads or fully independent end-to-end training reproducibility.

## AFT inference
Original saved full AFT booster: validation Harrell C 0.8620894048827847; archived 0.8620894048827847; exact numerical match. best_iteration 345. Another-runtime 3.1.3 model refit: best_iteration 465, C 0.8633699925535997; the original required XGBoost 3.4.1. No same-environment matched refit is claimed.

## CDC weights
For a combined NHANES 1999–2018 MEC-weight descriptive analysis, use `(2/10)*WTMEC4YR` for 1999–2002 and `(1/10)*WTMEC2YR` for 2003–2018. Early-cycle WTMEC4YR exists in archived demographic XPT files. Corrected development 1999–2008 weighted mean age: 46.376338, rounded to 46.4 y. This is descriptive and does not alter the frozen unweighted model or any single-era evaluation. No analyte-weight eligibility, design-adjusted calibration or per-era assay equivalence is claimed.

## Official supporting documentation
- https://wwwn.cdc.gov/nchs/nhanes/tutorials/Weighting.aspx
- https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2003/DataFiles/L40_C.htm
- https://wwwn.cdc.gov/Nchs/Nhanes/nhanes3/Lab1UsageNotes.aspx
- https://wwwn.cdc.gov/nchs/nhanes/nhanes3/datafiles.aspx

All public audit outputs are aggregated and contain no participant-level source data. Original frozen artifacts remain unchanged.
