# Local reproduction instructions (Windows PowerShell or shell)

1. Extract ZIP to a short path; for example `C:\\TES_OPHRP_RELEASE` or `/path/to/TES_OPHRP_RELEASE`.
2. Restore the original `Q1_SOURCE_V1_2.zip` **locally** if you have it, placing the participant-level data folders under `SRC/Q1` (the public ZIP omits these).
3. Create and activate a Python environment with the archived frozen requirements when recreating primary results. If unavailable, use a separately documented compatible environment and record all version deviations.
4. To rerun the original analysis in a complete local source tree, consult `SRC/Q1/README_REPRODUCE_AND_REVISE_AR.md` and `tools/verify_reproduction_results.py`.
5. Run post-hoc analyses from the release root. Stage 1 and 2 use saved model scores and process NHANES III source files; all need the locally restored data.

```shell
python reviewer_stage1.py --root SRC/Q1 --out STAGE1_RESULTS --n-boot 250
python reviewer_stage2_selectors.py
python reviewer_stage3_survival.py
python reviewer_stage4_survey.py
python reviewer_stage5_shift.py
```

**Interpretation:** Updated age-only and age+sex AFT baselines used 1999–2006 for fitting and 2007–2008 for development-only early stopping, followed by 1999–2008 refitting; see `STAGE7_RESULTS/BASELINE_TRAINING_PROVENANCE.json`. TES was originally selected partly using 2009–2012, so TES contrasts in that stage are partly selection-dependent. Stage 2 bootstrap uncertainty for selector C differences; Stage 3 fixes censoring estimation by cohort; Stage 4 weighted pair C with PSU jackknife (not a full complex survey model); Stage 5 synthetic covariate perturbation only (not clinical outcome response).

## Research data caution

The archived `pooled_exam_weight_20yr` variable was constructed by simply dividing 2-year MEC weights by ten; for datasets combining 1999-2000 with later NHANES cycles, CDC provides a different rule. Do not use that pooled field as-is in published survey-weighted inferences. Confirm analyte-specific subsample weight eligibility.

```shell
python reviewer_stage6_participant_flow.py
```


### V3 development-only tuned baseline

After restoring source participant-level files LOCALLY (not in public GitHub), run:

```shell
python reviewer_stage7_leakage_free_baselines.py --root SRC/Q1 --out STAGE7_RESULTS --n-boot 250
```

The new V3 manuscript/response uses these corrected age-baseline estimates; Stage 1 is retained only for earlier computational traceability. The 2009–2012 contrast is not strictly independent for frozen TES because the original TES algorithm used 2009–2012 for selection.


### V14 matched-preprocessing external sensitivity (NHANES III)
Restore the **private** Q1 source locally, then run:

```sh
python POSTHOC_V14_MATCHED_NHANES_III/run_matched_nhanes3_v14.py --q1-root /local/private/Q1 --out /local/aggregate_results
```
The archive includes the aggregate JSON only, never the required participant-level inputs. The experiment uses a 512-round XGBoost-Cox fit selected within development in Stage 8; it is not part of the locked original TES study.
