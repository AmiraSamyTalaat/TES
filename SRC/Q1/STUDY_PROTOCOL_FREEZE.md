# Study protocol freeze — v1.0.0

Frozen before model fitting on 2026-08-27.

## Population and predictors

Adults aged 20 years or older in NHANES 1999–2018 with public-use linked mortality eligibility. Predictors are age, sex, and 23 harmonized routine-biochemistry analytes. Missingness is retained and handled inside each training fold.

## Outcome

Primary analysis uses right-censored all-cause survival time (`PERMTH_INT`) rather than an unequal-follow-up binary label. Five- and ten-year risk are secondary horizons only where observable.

## Temporal split

- Development/training: 1999–2008
- Model selection: 2009–2012
- Calibration only: 2013–2014
- Locked temporal confirmation: 2015–2018

No fit, feature selection, threshold selection, or hyperparameter selection may use 2015–2018 outcomes.

## Required baselines

1. Age/sex Cox proportional hazards.
2. Full-panel penalized Cox.
3. Random survival forest.
4. Gradient-boosted survival/AFT when the runtime supports it.

## Candidate contribution

Temporal-robust survival prediction with post-hoc time-specific calibration and conformal/selective uncertainty. It proceeds only if it improves temporal calibration or selective risk over the strongest baseline without materially degrading discrimination.

## Primary metrics

Harrell/Uno C-index, integrated Brier score, time-dependent AUC, calibration slope/intercept and observed-to-expected risk. Report bootstrap confidence intervals and subgroup results by sex and age band.

## Stop rules

Do not make a superiority claim if the confirmatory confidence interval includes no improvement. Do not tune after confirmatory unblinding. Negative results remain reportable but do not justify a Q1-strength claim.

