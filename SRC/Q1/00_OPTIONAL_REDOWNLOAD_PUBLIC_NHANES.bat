@echo off
setlocal
cd /d "%~dp0"
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :pythonfail
"%PROVLAB_PYTHON%" tools\download_public_nhanes.py
if errorlevel 1 goto :fail
echo Public NHANES source files verified/downloaded.
pause
exit /b 0
:pythonfail
echo Python 3.12 environment not found. Run 00_SETUP_ENVIRONMENT.bat first.
pause
exit /b 1
:fail
echo Public NHANES download failed.
pause
exit /b 1
