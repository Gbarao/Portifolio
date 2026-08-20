#!/bin/bash
# Clique duas vezes neste arquivo para instalar e abrir o sistema.
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    python3 instalador/instalar.py
else
    echo
    echo "  O Python não foi encontrado neste computador."
    echo
    echo "  1. Acesse https://www.python.org/downloads/"
    echo "  2. Baixe e instale a versão mais recente"
    echo "  3. Clique duas vezes neste arquivo de novo"
    echo
    read -r -p "Pressione Enter para fechar. "
fi
