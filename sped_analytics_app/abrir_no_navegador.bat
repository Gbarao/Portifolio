@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call instalar.bat
".venv\Scripts\python.exe" -m app.main --browser
if errorlevel 1 pause
