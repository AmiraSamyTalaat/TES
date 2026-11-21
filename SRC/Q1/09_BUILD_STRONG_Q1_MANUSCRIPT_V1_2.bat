@echo off
setlocal
cd /d "%~dp0"
if not exist .venv_strong_q1\Scripts\python.exe goto :noenv
set "PYTHONPATH="
".venv_strong_q1\Scripts\python.exe" tools\build_strong_q1_manuscript_v1_2.py
if errorlevel 1 goto :fail
echo Strong-Q1 V1.2 manuscripts rebuilt.
pause
exit /b 0
:noenv
echo Strong-Q1 environment not found. Run 04_SETUP_STRONG_Q1_EXTENSION_ENV.bat first.
pause
exit /b 1
:fail
echo Manuscript build failed.
pause
exit /b 1
