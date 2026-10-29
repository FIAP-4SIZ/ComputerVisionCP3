@echo off
setlocal
cd /d "%~dp0"
set "CP3_PYTHON=..\.venv312\Scripts\python.exe"
if not exist "%CP3_PYTHON%" set "CP3_PYTHON=..\.venv\Scripts\python.exe"
if not exist "%CP3_PYTHON%" (
  echo Execute install_libraries.bat para criar o ambiente Python 3.12.
  exit /b 1
)
"%CP3_PYTHON%" run.py %*
exit /b %errorlevel%
