@echo off
setlocal
cd /d "%~dp0"
if not exist .venv_strong_q1\Scripts\python.exe goto :noenv
set "PYTHONPATH="
".venv_strong_q1\Scripts\python.exe" tools\verify_strong_q1_stability_extension.py
if errorlevel 1 goto :fail
echo Strong-Q1 V1.2 stability/sensitivity verification PASS.
pause
exit /b 0
:noenv
echo Strong-Q1 environment not found. Run 04_SETUP_STRONG_Q1_EXTENSION_ENV.bat first.
pause
exit /b 1
:fail
echo V1.2 verification FAILED. Preserve current and reference outputs for comparison.
pause
exit /b 1
