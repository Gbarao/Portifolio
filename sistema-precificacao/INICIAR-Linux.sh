#!/bin/bash
# Execute este arquivo para instalar e abrir o sistema.
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    python3 instalador/instalar.py
else
    echo
    echo "  O Python não foi encontrado neste computador."
    echo "  Instale com o gerenciador de pacotes da sua distribuição, por exemplo:"
    echo "      sudo apt install python3 python3-venv"
    echo
    read -r -p "Pressione Enter para fechar. "
fi
