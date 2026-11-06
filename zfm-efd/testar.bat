@echo off
setlocal
cd /d "%~dp0"
title Testes automaticos - Programa ZFM
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo.
    echo O ambiente do programa ainda nao foi preparado.
    echo De duplo clique em iniciar.bat uma vez e depois rode este arquivo de novo.
    echo.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0ferramentas\testar.py"
pause
endlocal
