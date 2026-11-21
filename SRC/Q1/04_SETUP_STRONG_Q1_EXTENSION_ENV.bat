@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto :nopython
py -3.12 -c "import sys,platform; assert sys.version_info[:2]==(3,12); assert platform.architecture()[0]=='64bit'" 2>nul
if errorlevel 1 goto :wrongpython
if not exist .venv_strong_q1\Scripts\python.exe py -3.12 -m venv .venv_strong_q1
if errorlevel 1 goto :fail
".venv_strong_q1\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv_strong_q1\Scripts\python.exe" -m pip install -r requirements_strong_q1_extension_exact.txt
if errorlevel 1 goto :fail
".venv_strong_q1\Scripts\python.exe" -c "import numpy,pandas,scipy,statsmodels,xgboost,docx; print('Strong-Q1 environment ready'); print('numpy',numpy.__version__); print('pandas',pandas.__version__); print('scipy',scipy.__version__); print('statsmodels',statsmodels.__version__); print('xgboost',xgboost.__version__); print('python-docx',docx.__version__)"
if errorlevel 1 goto :fail
echo Strong-Q1 extension environment is ready.
pause
exit /b 0
:nopython
echo Python launcher not found. Install 64-bit Python 3.12 and rerun.
pause
exit /b 1
:wrongpython
echo 64-bit CPython 3.12 is required for the unified reviewer workflow.
pause
exit /b 1
:fail
echo Strong-Q1 environment setup failed. Keep this window and preserve its text.
pause
exit /b 1
