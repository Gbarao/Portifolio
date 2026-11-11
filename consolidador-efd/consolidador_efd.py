# -*- coding: utf-8 -*-
"""
Ponto de entrada do executável (ConsolidadorEFD.exe).

Sem argumentos, abre a interface no navegador. O executável também atende
os processos auxiliares que a interface cria:

    ConsolidadorEFD.exe --trabalhador <pasta>     lê um arquivo EFD
    ConsolidadorEFD.exe --seletor <modo>          janela de seleção de arquivos
    ConsolidadorEFD.exe --testar-carga <dados> <base>   teste automatizado
"""

import os
import sys


def _pasta_programa() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _porta_livre() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def testar_carga(pasta_dados: str, pasta_base: str) -> int:
    """Carrega os .txt de uma pasta usando os processos de leitura do próprio
    executável e confere a integridade. Usado no teste do executável."""
    import glob
    import json
    from efd import base
    con = base.abrir(os.path.join(pasta_base, "efd.duckdb"))
    plano = base.planejar(con, sorted(glob.glob(os.path.join(pasta_dados, "*.txt"))))
    res = base.carregar(con, plano, pasta_base)
    ok = [r for r in res if r["ok"]]
    verificacoes = base.ultimas_verificacoes(con)
    resumo = {"carregados": len(ok), "falhas": [r["mensagem"] for r in res if not r["ok"]],
              "modos_de_leitura": sorted({r.get("modo_leitura", "") for r in ok}),
              "verificacoes_ok": all(v["ok"] for v in verificacoes),
              "linhas": con.execute("SELECT count(*) FROM itens").fetchone()[0]}
    print(json.dumps(resumo, ensure_ascii=False))
    certo = (ok and not resumo["falhas"] and resumo["verificacoes_ok"]
             and resumo["modos_de_leitura"] == ["processo próprio"])
    return 0 if certo else 1


def abrir_interface() -> int:
    import threading
    import time
    import webbrowser
    from streamlit.web import cli as stcli

    porta = int(os.environ.get("EFD_PORTA") or 0) or _porta_livre()
    endereco = f"http://localhost:{porta}"
    print("Consolidador EFD")
    print(f"Abrindo no navegador: {endereco}")
    print("Mantenha esta janela aberta enquanto usa o programa. Para encerrar, feche-a.")
    if not os.environ.get("EFD_SEM_NAVEGADOR"):
        def abrir():
            time.sleep(4)
            try:
                webbrowser.open(endereco)
            except Exception:
                pass
        threading.Thread(target=abrir, daemon=True).start()
    sys.argv = [
        "streamlit", "run", os.path.join(_pasta_programa(), "app.py"),
        "--global.developmentMode=false",
        "--server.address", "localhost", "--server.port", str(porta),
        "--server.headless", "true", "--server.fileWatcherType", "none",
        "--server.maxUploadSize", "500",
        "--browser.gatherUsageStats", "false",
        "--client.toolbarMode", "minimal",
        "--theme.base", "light", "--theme.primaryColor", "#1F4E5F",
    ]
    return stcli.main()


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--trabalhador"]:
        from efd import trabalhador
        sys.argv = [sys.argv[0]] + args[1:]
        return trabalhador.main()
    if args[:1] == ["--seletor"]:
        from efd import seletor
        sys.argv = [sys.argv[0]] + args[1:]
        return seletor.main()
    if args[:1] == ["--testar-carga"] and len(args) == 3:
        return testar_carga(args[1], args[2])
    return abrir_interface()


if __name__ == "__main__":
    sys.exit(main() or 0)
