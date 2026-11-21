# TES / NHANES — reproducibility code and aggregate results

**Manuscript:** *Temporal Explanation-Stable Feature Selection Yields an 11-Predictor Mortality Risk Panel with Retained Discrimination Across NHANES Eras*  
**Journal submission:** OPHRP-2026-0654

This repository contains the original study scripts and recorded protocols, saved XGBoost models, code for the additional reviewer-requested analyses, checksums, aggregate numerical outputs, and verification utilities. It is a **code-and-results archive**, not an additional manuscript file. The eleven scientific tables and five figures appear in the main manuscript submission; historical reference figure assets retained here are not a replacement for the journal-ready TIFF figures.

## Start here

1. Run `python release_preflight.py` at the repository root. It verifies the package manifest and presence of the key scripts, model artifacts and configuration files. It also lists participant-level inputs absent by design. A successful exit does **not** mean the original study can be rerun from this ZIP alone.
2. Run `python test_metric_implementations.py` for small, data-free checks of unweighted/weighted concordance and censoring calculations.
3. Read `REPRODUCTION_COMMANDS.md` for analyst commands and `REPRODUCIBILITY_STATUS.md` for the scope of completed verification checks.
4. See `MANUSCRIPT_REVIEWER_EVIDENCE_INDEX.md` for a map from the final manuscript tables to aggregate evidence in this archive.

## Repository contents

- `SRC/Q1/` — preserved original programs, locked protocols, environment records, model objects, source registries and original aggregate results.
- `reviewer_stage1.py` to `reviewer_stage7_leakage_free_baselines.py` and `STAGE1_RESULTS/` to `STAGE7_RESULTS/` — reviewer-requested methods and outputs; corrected development-only age/sex reference-model results are in Stage 7 (which supersedes the earlier exploratory Stage 1 baseline comparisons).
- `STAGE8_MATCHED_MISSINGNESS/` and `POSTHOC_V14_MATCHED_NHANES_III/` — matched-preprocessing comparisons, including historical-era NHANES III; both are post-hoc analyses.
- `POSTHOC_V6_CALIBRATION_AUDIT/`, `POSTHOC_V8_INDEPENDENT_AUDIT/` and `POSTHOC_V9_CDC_2017_18_BRIDGING/` — calibration, source/weight and laboratory-assay sensitivity documentation.
- `REVIEWER_EVIDENCE_DATA/` — eleven aggregate CSV evidence tables linked to main manuscript tables by the evidence index.
- `RELEASE_SHA256SUMS.txt` and `RELEASE_SHA256_MANIFEST.json` — checksums for the **current** published file inventory (excluding the manifest files themselves).

## Data access and execution scope

The public archive intentionally excludes participant-level NHANES/NHANES III records, linked mortality files and person-level predictions. The required inputs must be obtained independently from the official CDC/NCHS sources and restored locally before the original pipeline or extensions can be rerun. See `PUBLIC_RELEASE_DATA_POLICY.md`, `DATA_ACCESS_AND_RELEASE_POLICY.md`, and the source registries. Never commit private, restricted or local participant-level data to this repository.

The preserved original full-AFT booster reproduced its recorded validation inference (Harrell C = 0.8620894048827847; best iteration 345). Local checks of the archived source inputs reproduced the reviewer-stage aggregate outputs. The archive includes original training programs, recorded configurations, verification reports, and saved model objects. Re-running data-dependent analyses requires obtaining the official CDC/NCHS source data separately; detailed computational audit records are retained in the corresponding JSON reports.

TES-11 used the frozen selection design. Exploratory post-hoc age/sex, selector, matched-preprocessing, survey-weight, perturbation, calibration and assay-bridging analyses are distinguished from the locked primary comparisons. Weighted estimates are descriptive and are not a substitute for fully design-based inference. Other limitations are described in `REPRODUCIBILITY_STATUS.md`.

## Re-running the analyses

See `REPRODUCTION_COMMANDS.md` for the ordered commands. Use the recorded software requirements for primary analyses, and document any changes made for secondary or post-hoc runs. An optional environment-comparison utility is in `EXACT_AFT_RETRAIN_WINDOWS/`.

## GitHub / Zenodo release

Extract the ZIP before adding its **contents** as a new local repository in GitHub Desktop. Commit, publish the public repository after an author file/rights review, and create a tagged GitHub release (e.g. `v1.0.0`). Link GitHub to Zenodo to archive the exact tagged version and retrieve the real DOI. Alternatively, deposit this versioned archive directly into Zenodo rather than generating a second independent record. Add only the confirmed repository URL and DOI to the manuscript's data/code availability statements and reviewer response. No URL or DOI is asserted by this archive before publication.
