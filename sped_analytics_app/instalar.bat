@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Instalacao - Consolidacao Fiscal SPED
echo ============================================
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul || (
  echo [ERRO] Python nao encontrado. Instale o Python 3.11 ou superior em https://www.python.org/downloads/
  echo        marcando a opcao "Add python.exe to PATH" e execute este arquivo novamente.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual .venv ...
  %PY% -m venv .venv || (echo [ERRO] Falha ao criar o ambiente virtual & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo [ERRO] Falha ao instalar dependencias & pause & exit /b 1)
echo Instalando janela nativa (opcional)...
".venv\Scripts\python.exe" -m pip install pywebview || echo [AVISO] pywebview nao instalado: a interface abrira no navegador.
echo.
echo Instalacao concluida. Execute iniciar.bat para abrir o programa.
pause
