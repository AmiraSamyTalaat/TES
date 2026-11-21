# Verification scope

The archived source checks verified 33 XPT files and 10 linked-mortality input files against recorded checksums. The locally reconstructed 1999–2018 analytic cohort matched 52,287 participants and 8,311 deaths. Reviewer-extension calculations were checked from previously archived local data; these records are not presented as fresh CDC downloads.

The preserved full-AFT model reproduced its archived validation inference (Harrell C = 0.8620894048827847, best iteration 345). The original training scripts, runtime requirements, saved models and supporting aggregate results are included for independent inspection. See the audit JSON records for the specific checks and their outputs.

Public distribution excludes participant-level input data. To execute data-dependent stages, download the official public-use CDC/NCHS input files and follow `REPRODUCTION_COMMANDS.md`. Individual assay harmonization, analyte-specific survey weights and design-based variance estimation have distinct limitations described in their respective stage notes. No independently collected external geographic cohort is claimed.
