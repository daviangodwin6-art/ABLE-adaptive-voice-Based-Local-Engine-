@echo off
rem One-time setup: makes .venv in this folder and installs the Python packages
rem (offline from wheels\ if that folder exists, otherwise from the internet).
cd /d "%~dp0"
set PY=py -3.13
%PY% --version >nul 2>&1 || set PY=python
%PY% -c "import sys; sys.exit(sys.version_info < (3, 11))" || goto nopython
if exist .venv\Scripts\python.exe goto install
echo Creating .venv ...
%PY% -m venv .venv || goto fail
:install
set SRC=
if exist wheels set SRC=--no-index --find-links wheels
.venv\Scripts\python.exe -m pip install %SRC% -r requirements.txt || goto fail
echo.
echo Setup OK. Now double-click start.bat
pause
exit /b 0
:nopython
echo Python 3.13 (64-bit) was not found. Install it from https://www.python.org/downloads/ first (see FRIEND_README.md).
pause
exit /b 1
:fail
echo Setup FAILED. See the message above and the Troubleshooting part of FRIEND_README.md.
pause
exit /b 1
