@echo off
set "PROVLAB_PYTHON="
set "PROVLAB_ROOT=%~dp0.."
if exist "%PROVLAB_ROOT%\.venv\Scripts\python.exe" set "PROVLAB_PYTHON=%PROVLAB_ROOT%\.venv\Scripts\python.exe"
if not defined PROVLAB_PYTHON (
  where py >nul 2>&1
  if not errorlevel 1 for /f "delims=" %%P in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do set "PROVLAB_PYTHON=%%P"
)
if not defined PROVLAB_PYTHON exit /b 1
set "PYTHONPATH=%PROVLAB_ROOT%\.python_packages;%PYTHONPATH%"
exit /b 0
