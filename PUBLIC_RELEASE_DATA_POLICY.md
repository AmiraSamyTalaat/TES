# Distribution statement

This public-safe code ZIP intentionally excludes NHANES microdata, per-person predictions, participant-level source assays, raw mortality data and raw NHANES III participant records. Only original scripts, configuration/freezes/hashes, saved model objects and aggregate analytic summary results are included. These exclusions are deliberate; a participant-level local dataset is needed to fully rerun the calculations.

Original public NHANES datasets: https://wwwn.cdc.gov/nchs/nhanes/ ; NCHS public linked mortality: https://www.cdc.gov/nchs/linked-data/mortality-files/index.html ; NHANES III resources: https://wwwn.cdc.gov/nchs/nhanes/nhanes3/default.aspx.

Verification note: some original source `.bat` scripts use local Python runtime assumptions, and the frozen exact requirements may not match the environment used for post-hoc experiments. No external public repository is asserted to exist until the author uploads/releases this archive.
