@echo off
setlocal
title MegaMix TUI - CD preparation
set "PYTHONUTF8=1"
where py.exe >nul 2>nul
if errorlevel 1 goto try_python
py -3 -c "import sys;sys.exit(sys.version_info < (3,11))" >nul 2>nul
if errorlevel 1 goto try_python
py -3 "%~dp0launcher.py" %*
goto finished
:try_python
where python.exe >nul 2>nul
if errorlevel 1 goto missing_python
python -c "import sys;sys.exit(sys.version_info < (3,11))" >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0launcher.py" %*
goto finished
:missing_python
echo Python 3.11 or later is required. Install Python and enable its launcher or PATH option.
pause
exit /b 1
:finished
set "megamix_exit=%errorlevel%"
if not "%megamix_exit%"=="0" pause
exit /b %megamix_exit%
