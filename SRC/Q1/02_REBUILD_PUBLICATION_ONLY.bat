@echo off
setlocal
cd /d "%~dp0"
call "%~dp0tools\select_python.bat"
if errorlevel 1 goto :pythonfail
"%PROVLAB_PYTHON%" "src\build_publication_table1.py" || goto :fail
"%PROVLAB_PYTHON%" "src\build_publication_figures.py" || goto :fail
"%PROVLAB_PYTHON%" "tools\build_complete_manuscript_docx.py" || goto :fail
echo Publication files rebuilt successfully.
pause
exit /b 0
:pythonfail
echo Python 3.12 environment not found. Run 00_SETUP_ENVIRONMENT.bat first.
pause
exit /b 1
:fail
echo Publication rebuild failed. Keep this window and send its text for review.
pause
exit /b 1
