# CDC 2017–2018 assay-bridging post-hoc sensitivity (V9)

This folder includes a standalone **exploratory, non-prespecified** calculation using the existing frozen TES-11 model.

Source: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BIOPRO_J.htm

Requires local private `Q1` source files (not included in the public archive). Example:

`python cdc_2017_18_bridging_sensitivity.py --q1-root /local/Q1 --output /local/aggregate_results --bootstrap 300`

Published CDC backward (Cobas -> DxC) equations are applied to six TES-11 chemistry predictors; CDC recommends no adjustment for glucose/chloride/potassium in that particular bridge study. AFT model is frozen (no fitting, no retuning), and the historical test outcomes are reused only for a post-hoc sensitivity.

**Interpretation:** 2017–2018 -> 2015–2016 method differences only. This does NOT prove equivalence across 1999–2018 and NHANES III, nor does it establish TES superiority. The apparent 24-month Brier change is descriptive, and the paired bootstrap ignores stratified survey variance. No participant-level data are distributed.

The original archived `augment_survey_design.py` uses an incorrect all-cycle 2-year pooling rule for 1999–2002; use the corrected CDC pooling code provided separately in the V8/V9 public release when reconstructing long-period weighted estimates.
