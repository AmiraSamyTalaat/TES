@echo off
setlocal
cd /d "%~dp0"
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :pythonfail
"%PROVLAB_PYTHON%" tools\check_environment.py || goto :fail
"%PROVLAB_PYTHON%" tools\verify_reviewer_package.py || goto :fail
echo PRISTINE PACKAGE VERIFICATION PASS.
pause
exit /b 0
:pythonfail
echo Python 3.12 environment not found. Run 00_SETUP_ENVIRONMENT.bat first.
pause
exit /b 1
:fail
echo Package verification failed. Keep this window and send its text for review.
pause
exit /b 1
