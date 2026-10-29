@echo off
setlocal
cd /d "%~dp0"
py -3.12 --version
if errorlevel 1 (
  echo Instale Python 3.12 antes de continuar.
  exit /b 1
)
if not exist "..\.venv312\Scripts\python.exe" py -3.12 -m venv "..\.venv312"
if errorlevel 1 exit /b 1
"..\.venv312\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
"..\.venv312\Scripts\python.exe" -m pip check
exit /b %errorlevel%
