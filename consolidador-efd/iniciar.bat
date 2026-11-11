@echo off
rem Abre o Consolidador EFD no navegador (Windows).
cd /d "%~dp0"
python iniciar.py
if errorlevel 1 pause
