# NHANES III matched preprocessing (reviewer-requested post-hoc analysis; V14)

This folder **extends** the Stage 8 matched-preprocessing comparison from four later eras to the historical-era NHANES III evaluation. The original protocol freeze and saved models are unchanged.

The development-fitted 25-feature median imputation and IQR standardization are applied identically to the saved Cox coefficients and a development-trained XGBoost-Cox model. XGBoost-Cox uses **512 rounds** as established in the Stage 8 development-only analysis, without selecting rounds using NHANES III outcomes. Both methods are evaluated on the same 16,519 NHANES III participants. The percentile 95% CI is based on 300 participant-paired bootstrap replicates (seed 20261121) and does not use stratified NHANES survey variance estimation.

## Reproduction, locally (do NOT upload participant records)

Unzip the author's original `Q1_SOURCE_V1_2.zip` privately to obtain `/some/path/Q1`. Then from the public release root, with the documented post-hoc dependencies installed:

```sh
python POSTHOC_V14_MATCHED_NHANES_III/run_matched_nhanes3_v14.py --q1-root /some/path/Q1 --out /some/local/aggregate_output
```

**Recorded reference environment:** XGBoost 3.1.3, 4 CPU threads. Other library versions and platform settings can affect exact reproduction. Original frozen TES/AFT results are independent of this additional post-hoc analysis.

**Expected aggregate result:** Cox C=0.826602116590147; XGBoost-Cox C=0.8501917003936214; paired delta C=0.023589583803474312; 95% CI [0.021440362159156443, 0.02549723346220919]. These are post-hoc, not a new frozen confirmatory endpoint; the outcome data were already inspected for the original external evaluation.

Only the aggregate JSON and source code are present in the release. Source microdata, person-level predictions and raw mortality linkage files are deliberately excluded. Do not claim results establish model calibration, survey design representativeness, or external model independence beyond the historical survey-era contrast.
