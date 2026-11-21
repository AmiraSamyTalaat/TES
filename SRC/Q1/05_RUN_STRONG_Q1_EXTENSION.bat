@echo off
setlocal
cd /d "%~dp0"
if not exist .venv_strong_q1\Scripts\python.exe goto :noenv
set "PYTHONPATH="
".venv_strong_q1\Scripts\python.exe" src\run_strong_q1_extension.py
if errorlevel 1 goto :fail
echo Strong-Q1 extension completed. See outputs\strong_q1_extension\STRONG_Q1_EXTENSION_STATUS.json
pause
exit /b 0
:noenv
echo Strong-Q1 environment not found. Run 04_SETUP_STRONG_Q1_EXTENSION_ENV.bat first.
pause
exit /b 1
:fail
echo Strong-Q1 extension failed. Do not alter frozen protocol files to force PASS.
pause
exit /b 1
