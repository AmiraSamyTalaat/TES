@echo off
setlocal
cd /d "%~dp0"
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :pythonfail
"%PROVLAB_PYTHON%" tools\check_environment.py || goto :fail
"%PROVLAB_PYTHON%" tools\verify_reviewer_package.py || goto :fail

echo [1/5] Rebuild package-local source cohorts.
"%PROVLAB_PYTHON%" src\build_harmonized_panel.py || goto :fail
"%PROVLAB_PYTHON%" src\build_survival_cohort.py || goto :fail
"%PROVLAB_PYTHON%" src\augment_survey_design.py || goto :fail

echo [2/5] Re-run locked evaluations while original frozen model bytes are still pristine.
"%PROVLAB_PYTHON%" src\run_locked_confirmatory_evaluation.py || goto :fail
"%PROVLAB_PYTHON%" src\run_nhanes3_locked_external.py || goto :fail

echo [3/5] Re-run successful pre-confirmatory analyses from the rebuilt cohort.
for %%S in (
  src\run_cox_baseline.py
  src\run_xgboost_survival_pilot.py
  src\run_paired_bootstrap_validation.py
  src\run_subgroup_audit.py
  src\run_temporal_shap_stability.py
  src\run_aft_survival_pilot.py
  src\run_aft_vs_cox_bootstrap.py
  src\run_tes_aft_pilot.py
  src\run_tes_aft_ablation.py
) do (
  echo Running %%S
  "%PROVLAB_PYTHON%" "%%S" || goto :fail
)

echo [4/5] Rebuild the NHANES III feature cohort after its locked evaluation.
"%PROVLAB_PYTHON%" src\build_nhanes3_feature_cohort.py || goto :fail

echo [5/5] Rebuild publication artifacts and compare with the frozen reference results.
"%PROVLAB_PYTHON%" src\build_publication_table1.py || goto :fail
"%PROVLAB_PYTHON%" src\build_publication_figures.py || goto :fail
"%PROVLAB_PYTHON%" tools\build_complete_manuscript_docx.py || goto :fail
"%PROVLAB_PYTHON%" tools\verify_reproduction_results.py || goto :fail

echo REPRODUCTION PASS. See REPRODUCTION_VERIFICATION_STATUS.json.
echo NOTE: this working copy has intentionally regenerated frozen artifacts; use a fresh extraction for pristine freeze verification.
pause
exit /b 0
:pythonfail
echo Python 3.12 environment not found. Run 00_SETUP_ENVIRONMENT.bat first.
pause
exit /b 1
:fail
echo Reproduction stopped at the failed step shown above. Do not tune frozen settings.
pause
exit /b 1
