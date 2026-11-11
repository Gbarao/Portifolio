#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abre o Consolidador EFD no navegador.

    python iniciar.py

A aplicação roda só neste computador (endereço localhost). Para encerrar,
feche esta janela ou pressione Ctrl+C.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))


def porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def abrir_navegador(endereco: str, espera: float = 3.0):
    def abrir():
        time.sleep(espera)
        try:
            webbrowser.open(endereco)
        except Exception:
            pass
    threading.Thread(target=abrir, daemon=True).start()


def main():
    try:
        import duckdb, pandas, pyarrow, streamlit, xlsxwriter  # noqa: F401
    except ImportError as e:
        print(f"Falta instalar uma dependência ({e.name}). Rode:\n"
              f"    {sys.executable} -m pip install -r \"{os.path.join(AQUI, 'requirements.txt')}\"")
        return 1
    porta = porta_livre()
    endereco = f"http://localhost:{porta}"
    print(f"Consolidador EFD em execução: {endereco}")
    print("Para encerrar, feche esta janela ou pressione Ctrl+C.")
    abrir_navegador(endereco)
    # --server.headless evita o pedido de e-mail que o Streamlit faz no primeiro uso
    comando = [sys.executable, "-m", "streamlit", "run", os.path.join(AQUI, "app.py"),
               "--server.address", "localhost", "--server.port", str(porta),
               "--server.headless", "true", "--browser.gatherUsageStats", "false"] + sys.argv[1:]
    return subprocess.call(comando, cwd=AQUI)


if __name__ == "__main__":
    sys.exit(main())
