@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente nao instalado. Executando instalar.bat ...
  call instalar.bat
)
".venv\Scripts\python.exe" -m app.main %*
if errorlevel 1 pause
