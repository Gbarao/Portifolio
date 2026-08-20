@echo off
chcp 65001 >nul
title Sistema de precificacao para reciclagem
cd /d "%~dp0"

rem O lancador do Windows (py) e a forma mais confiavel de achar o Python.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "instalador\instalar.py"
    goto fim
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "instalador\instalar.py"
    goto fim
)

echo.
echo   O Python nao foi encontrado neste computador.
echo.
echo   1. Acesse https://www.python.org/downloads/
echo   2. Baixe e instale a versao mais recente
echo   3. IMPORTANTE: marque "Add Python to PATH" durante a instalacao
echo   4. Clique duas vezes neste arquivo de novo
echo.
pause

:fim
