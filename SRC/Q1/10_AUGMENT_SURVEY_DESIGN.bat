@echo off
setlocal
cd /d "%~dp0"
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :pythonfail
"%PROVLAB_PYTHON%" "src\augment_survey_design.py" || goto :fail
echo Step completed successfully.
pause
exit /b 0
:pythonfail
echo Python 3.12 environment not found. Run 00_SETUP_ENVIRONMENT.bat first.
pause
exit /b 1
:fail
echo Step failed. Keep this window and send its text for review.
pause
exit /b 1
