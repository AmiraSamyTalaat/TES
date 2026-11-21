# Protocol amendment 001 — follow-up feasibility

Date: 2026-08-27. Applied before fitting any candidate method and before confirmatory model evaluation.

## Trigger

The official CDC directory currently exposes the NHANES 1999–2018 linked mortality files carrying the 2019 release name. The cohort audit showed that later survey cycles necessarily have shorter potential follow-up (median 48 months for 2015–2016 and 25 months for 2017–2018).

## Amendment

- The locked temporal cycles remain 2015–2018.
- Right-censored discrimination is the primary temporal endpoint; censoring must be handled explicitly.
- A fixed five-year risk score must **not** be reported for 2017–2018.
- Fixed-horizon calibration/Brier analyses are allowed only when the cycle has adequate support at that horizon, documented by the censoring distribution.
- Report 2015–2016 and 2017–2018 separately; do not hide short follow-up by pooling alone.
- Confirmatory uncertainty must use participant-level resampling and disclose event counts.

This amendment changes no predictors, model, threshold, or observed performance target. It prevents an invalid endpoint caused by administrative follow-up.

