@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto :nopython
py -3.12 -c "import sys,platform; assert sys.version_info[:2]==(3,12); assert platform.architecture()[0]=='64bit'" 2>nul
if errorlevel 1 goto :wrongpython
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -r requirements_frozen_runtime_exact.txt
if errorlevel 1 goto :fail
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :fail
"%PROVLAB_PYTHON%" tools\check_environment.py
if errorlevel 1 goto :fail
echo Environment ready. Exact package versions have been recreated from requirements_frozen_runtime_exact.txt.
pause
exit /b 0
:nopython
echo Python launcher not found. Install 64-bit Python 3.12 and rerun.
pause
exit /b 1
:wrongpython
echo 64-bit CPython 3.12 is required to preserve the frozen workflow.
pause
exit /b 1
:fail
echo Environment setup failed. Keep this window and send its text for review.
pause
exit /b 1
