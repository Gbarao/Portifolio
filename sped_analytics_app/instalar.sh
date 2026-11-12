#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3.11+ não encontrado"; exit 1; }
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install pywebview || echo "[AVISO] pywebview não instalado: a interface abrirá no navegador."
echo "Instalação concluída. Execute ./iniciar.sh"
