@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call instalar.bat
".venv\Scripts\python.exe" -m app.main --demo
if errorlevel 1 pause
