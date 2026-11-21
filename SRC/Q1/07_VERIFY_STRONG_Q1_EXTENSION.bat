@echo off
setlocal
cd /d "%~dp0"
if not exist .venv_strong_q1\Scripts\python.exe goto :noenv
set "PYTHONPATH="
".venv_strong_q1\Scripts\python.exe" tools\verify_strong_q1_extension.py
if errorlevel 1 goto :fail
echo Strong-Q1 extension verification PASS.
pause
exit /b 0
:noenv
echo Strong-Q1 environment not found. Run 04_SETUP_STRONG_Q1_EXTENSION_ENV.bat first.
pause
exit /b 1
:fail
echo Verification FAILED. Preserve both current and reference outputs and inspect the difference.
pause
exit /b 1
