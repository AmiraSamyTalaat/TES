# Exploratory survey-design sensitivity

Weighted Harrell's C is calculated using products of examination sampling weights for each comparable pair; ties in time excluded and tied risks receive half credit. Stratum-specific delete-one-PSU jackknife estimates sampling uncertainty using remaining PSU weight inflation m/(m−1), and the sum over strata of (m−1)/m × sum (replicate−replicate_mean)^2. The normal-approximation CI is indicative only. No refitting was done.

**Scope**: 2009–2012 validation (2009/2011 two-cycle weights /2), 2013–14, 2015–16, 2017–18 (each 2-year MEC weights), and earlier NHANES III (separate design and exam weights). Cycle names are prepended to pseudo-stratum identifiers. 1999–2008 pooled development is excluded because 1999–2000 requires special treatment: do NOT use the 20-year archived `pooled_exam_weight_20yr` column as-is. Consult NCHS rules for any analysis that pools 1999–2000.

**Limitations**: weighted pairwise Harrell's concordance is a descriptive sensitivity, NOT a design-based survival probability calibration analysis, survival regression coefficient variance, or statistically rigorous confidence interval for a clinically deployable model. Cluster design is approximated using public-use masked design variables. NCHS weight appropriateness should be independently reviewed for individual laboratory analytes, fasting subsamples, and NHANES III. No adjustments for multiple testing.

Official guidance: https://wwwn.cdc.gov/nchs/nhanes/tutorials/weighting.aspx and https://wwwn.cdc.gov/nchs/nhanes/analyticguidelines.aspx
