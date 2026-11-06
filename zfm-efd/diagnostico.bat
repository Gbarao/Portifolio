@echo off
setlocal
cd /d "%~dp0"
title Diagnostico - Programa ZFM
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
    python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
    echo.
    echo [FALHA] Python nao encontrado neste computador.
    echo O que fazer: pedir a TI a instalacao do Python 3.10 ou superior.
    echo Veja o arquivo MANUAL.md, secao 2 - Primeiro uso.
    echo.
    pause
    exit /b 1
)
%PYCMD% "%~dp0ferramentas\diagnostico.py"
pause
endlocal
