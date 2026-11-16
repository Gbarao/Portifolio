"""Ponto de entrada: Sistema Local de Inteligência e Consolidação Fiscal (SPED Fiscal + EFD-Contribuições).

Uso:
    python -m app.main                 # abre a aplicação (janela nativa se pywebview estiver instalado)
    python -m app.main --browser       # força abertura no navegador local (127.0.0.1)
    python -m app.main --importar DIR  # importa uma pasta sem abrir a interface
    python -m app.main --reconsolidar  # reconstrói a tabela fato
    python -m app.main --demo          # gera arquivos SPED de exemplo e importa
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402


def _cli_import(paths: list[str]) -> None:
    from app.database.engine import get_db
    db = get_db()
    summary = db.import_paths(paths, progress=lambda m, f: print(f"[{f * 100:5.1f}%] {m}", flush=True))
    for r in summary.resultados:
        print(f"{r.acao:12s} {Path(r.arquivo).name} {r.tipo} {r.cnpj} {r.competencia} {r.mensagem}")
    print(f"Concluído em {summary.segundos:.1f}s; competências reconsolidadas: {summary.competencias_reconsolidadas}")


def _free_port(start: int) -> int:
    import socket
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
            try:
                sk.bind((config.UI_HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError("Nenhuma porta livre encontrada")


def run_app(native: bool) -> None:
    """Sobe a API + interface em 127.0.0.1 e abre a janela nativa (pywebview) ou o navegador."""
    import threading
    import time
    import webbrowser

    import uvicorn

    from app.api.server import create_app

    app = create_app(native=native)
    port = _free_port(config.UI_PORT)
    url = f"http://{config.UI_HOST}:{port}/"
    server = uvicorn.Server(uvicorn.Config(app, host=config.UI_HOST, port=port, log_level="warning",
                                           access_log=False, timeout_keep_alive=30))
    print(f"Consolidação Fiscal SPED em {url}  (dados: {config.DATA_DIR})", flush=True)
    if native:
        import webview  # type: ignore

        t = threading.Thread(target=server.run, daemon=True, name="api")
        t.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.05)
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True
        except Exception:  # noqa: BLE001
            pass
        webview.create_window("Consolidação Fiscal SPED", url, width=1600, height=960, min_size=(1100, 700))
        webview.start()
        server.should_exit = True
        t.join(timeout=5)
    else:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        server.run()
    try:
        from app.database.engine import get_db
        get_db().close()
    except Exception:  # noqa: BLE001
        pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Consolidação Fiscal SPED (local)")
    ap.add_argument("--browser", action="store_true", help="abrir no navegador em vez de janela nativa")
    ap.add_argument("--importar", nargs="+", metavar="CAMINHO", help="importar pastas/arquivos e sair")
    ap.add_argument("--reconsolidar", action="store_true", help="reconstruir a tabela fato e sair")
    ap.add_argument("--demo", action="store_true", help="gerar e importar arquivos de exemplo")
    args = ap.parse_args()
    config.ensure_dirs()

    if args.demo:
        from tests.sample_data import write_scenario
        dest = config.DATA_DIR / "exemplo_sped"
        write_scenario(dest)
        _cli_import([str(dest)])
    if args.importar:
        _cli_import(args.importar)
    if args.reconsolidar:
        from app.database.engine import get_db
        r = get_db().rebuild_fato(None)
        print(f"{r['linhas']} linhas consolidadas em {r['segundos']:.1f}s")
    if args.importar or args.reconsolidar:
        return

    native = False
    if not args.browser:
        try:
            import webview  # noqa: F401  # type: ignore
            native = True
        except ImportError:
            native = False
    run_app(native)


if __name__ == "__main__":
    main()
