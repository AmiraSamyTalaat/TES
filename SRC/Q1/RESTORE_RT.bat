@echo off
setlocal
cd /d "%~dp0"
echo Restoring bundled Windows CPython 3.12 binary runtime snapshot...
for %%Z in (Q1_RT_A.zip Q1_RT_B.zip Q1_RT_C.zip) do (
  if not exist "%%Z" (
    echo MISSING: %%Z
    echo Put all three runtime ZIP files in this Q1 folder and rerun.
    pause
    exit /b 1
  )
)
for %%Z in (Q1_RT_A.zip Q1_RT_B.zip Q1_RT_C.zip) do (
  echo Extracting %%Z ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%%Z' -DestinationPath '%CD%' -Force"
  if errorlevel 1 (
    echo FAILED while extracting %%Z
    pause
    exit /b 1
  )
)
echo Runtime snapshot restored to .python_packages
if exist tools\select_python.bat (
  call tools\select_python.bat
  if not errorlevel 1 "%PROVLAB_PYTHON%" tools\check_environment.py
)
echo.
echo If the environment check reports pandas or docx missing, run 00_SETUP_ENVIRONMENT.bat while online.
echo CPython 3.12 64-bit must already be installed on Windows.
pause
