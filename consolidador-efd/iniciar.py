#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abre o Consolidador EFD no navegador.

    python iniciar.py

A aplicação roda só neste computador (endereço localhost). Para encerrar,
feche esta janela ou pressione Ctrl+C.
"""

import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        import duckdb, pandas, pyarrow, streamlit, xlsxwriter  # noqa: F401
    except ImportError as e:
        print(f"Falta instalar uma dependência ({e.name}). Rode:\n"
              f"    {sys.executable} -m pip install -r \"{os.path.join(AQUI, 'requirements.txt')}\"")
        return 1
    comando = [sys.executable, "-m", "streamlit", "run", os.path.join(AQUI, "app.py"),
               "--server.address", "localhost"] + sys.argv[1:]
    return subprocess.call(comando, cwd=AQUI)


if __name__ == "__main__":
    sys.exit(main())
