# Reviewer evidence index — OPHRP-2026-0654

This is a code-and-results reproducibility archive, not a supplementary manuscript or a substitute for the main article's key results.

The final article contains 11 main tables and five figures; all reviewer-requested scientific results appear in that main article. The archived aggregate evidence files `REVIEWER_EVIDENCE_DATA/analysis_table_01.csv` to `analysis_table_11.csv` preserve the originally tabulated reviewer-extension numbers for independent inspection. They are not participant-level data.

| Reviewer concern | Location in final article | Archive evidence |
|---|---|---|
| All 25 predictors / missingness | Table 4 / Methods 2.1 | `REVIEWER_EVIDENCE_DATA/analysis_table_01.csv` and original data mapping registry |
| Participant flow and exclusions | Figure 5 / Table 1 | `STAGE6_RESULTS/PARTICIPANT_FLOW_1999_2018_VERIFIED.csv` |
| Survey weights with jackknife | Table 11 / Results 3.11 | `REVIEWER_EVIDENCE_DATA/analysis_table_02.csv` |
| Synthetic measurement shift | Table 7 / Results 3.12 | `STAGE5_RESULTS/SIMULATED_MEASUREMENT_SHIFT_TES_VS_SHAP.csv` |
| TES subgroup C across all eras | Table 5 / Results 3.3 | `REVIEWER_EVIDENCE_DATA/analysis_table_04.csv` |
| Selector paired bootstrap CIs | Table 6 / Results 3.5 and 3.10 | `REVIEWER_EVIDENCE_DATA/analysis_table_05.csv` |
| Demographic baselines and their CIs | Table 9 / Results 3.10 | `STAGE7_RESULTS/DEVELOPMENT_TUNED_BOOTSTRAP_DELTAC_95CI.csv` |
| Hyperparameters / selected rounds | Methods 2.3 | `SRC/Q1/*PROTOCOL_FREEZE.json` |
| Matched Cox vs XGBoost-Cox | Table 11 / Results 3.13 | `STAGE8_MATCHED_MISSINGNESS/MATCHED_MISSINGNESS_PAIRED_CI.csv` |
| Fixed-horizon calibration | Table 10 / Figure 4 | `REVIEWER_EVIDENCE_DATA/analysis_table_10.csv` |
| CDC assay bridging | Results 3.14 | `REVIEWER_EVIDENCE_DATA/analysis_table_11.csv` |

All post-hoc analyses are identified as exploratory. The saved full-AFT booster validation inference was verified, and its training scripts and environment requirements are archived. Data-dependent re-execution requires independently obtaining the public CDC/NCHS source inputs and using the recorded software configurations. The accompanying audit reports document the scope of each check.
