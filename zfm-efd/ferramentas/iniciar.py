"""Inicializador do programa (chamado pelo iniciar.bat). Usa so a biblioteca padrao.

1a execucao: cria o ambiente virtual (.venv) na pasta do programa e instala os
pacotes do requirements.txt. Nas seguintes: so abre o programa no navegador.
Nada e instalado no sistema; nao precisa de administrador.
"""
from __future__ import annotations

import datetime as _dt
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VENV = RAIZ / ".venv"
REQ = RAIZ / "requirements.txt"
MARCA = VENV / "pacotes_instalados.txt"
LOGS = RAIZ / "data" / "logs"
PORTA_INICIAL = 8501
VERSAO_MINIMA = (3, 10)

SINAIS_REDE = ("SSL", "CERTIFICATE_VERIFY_FAILED", "ProxyError", "proxy", "407",
               "Max retries exceeded", "NewConnectionError", "getaddrinfo failed",
               "Temporary failure in name resolution", "timed out")


def python_venv() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def titulo(txt: str) -> None:
    print()
    print("=" * 70)
    print(txt)
    print("=" * 70)


def log_instalacao() -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    return LOGS / f"instalacao_{_dt.datetime.now():%Y%m%d_%H%M%S}.log"


def rodar_mostrando(cmd: list[str], log: Path) -> tuple[int, str]:
    """Executa mostrando a saida na janela e gravando no log."""
    saida: list[str] = []
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        p = subprocess.Popen(cmd, cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        assert p.stdout is not None
        for linha in p.stdout:
            print("   " + linha.rstrip())
            f.write(linha)
            saida.append(linha)
        p.wait()
    return p.returncode, "".join(saida)


def verificar_python() -> bool:
    v = sys.version_info
    if (v.major, v.minor) < VERSAO_MINIMA:
        titulo("Versao do Python muito antiga")
        print(f"Este computador tem o Python {v.major}.{v.minor}. O programa precisa do 3.10 ou superior.")
        print("O que fazer: pedir a TI a atualizacao do Python (texto pronto no MANUAL.md, secao 2).")
        return False
    return True


def preparar_ambiente() -> bool:
    req = REQ.read_text(encoding="utf-8")
    if python_venv().exists() and MARCA.exists() and MARCA.read_text(encoding="utf-8") == req:
        return True
    log = log_instalacao()
    if not python_venv().exists():
        titulo("Preparando o programa pela primeira vez (so acontece uma vez)")
        print("Criando a pasta .venv com as bibliotecas do programa...")
        cod, _ = rodar_mostrando([sys.executable, "-m", "venv", str(VENV)], log)
        if cod != 0 or not python_venv().exists():
            print()
            print("[FALHA] Nao foi possivel criar o ambiente do programa (.venv).")
            print(f"Detalhes em: {log}")
            print("O que fazer: envie esse arquivo de log ao Claude Code.")
            return False
    titulo("Baixando e instalando as bibliotecas (pode levar alguns minutos)")
    print("Esta e a unica etapa que usa a internet. Depois o programa funciona desligado da rede.")
    base = [str(python_venv()), "-m", "pip", "install", "--disable-pip-version-check",
            "--only-binary=:all:", "-r", str(REQ)]
    cod, saida = rodar_mostrando(base, log)
    if cod != 0 and any(s in saida for s in SINAIS_REDE):
        print()
        print("Primeira tentativa falhou por rede/certificado. Tentando de novo usando os")
        print("certificados do Windows (a verificacao de seguranca continua ligada)...")
        cod, saida = rodar_mostrando(base + ["--use-feature=truststore"], log)
    if cod != 0:
        titulo("[FALHA] As bibliotecas nao foram instaladas")
        if any(s in saida for s in SINAIS_REDE):
            print("Motivo provavel: a rede da empresa (proxy ou certificado) bloqueou o download.")
            print("O que fazer: pedir a TI, com o texto pronto do MANUAL.md (secao 2, passo 5),")
            print("a liberacao dos enderecos pypi.org e files.pythonhosted.org ou o endereco do proxy.")
        else:
            print("Motivo: veja o final do texto acima.")
        print(f"Detalhes gravados em: {log}")
        print("Envie esse arquivo ao Claude Code se precisar de ajuda.")
        return False
    MARCA.write_text(req, encoding="utf-8")
    print()
    print("Bibliotecas instaladas com sucesso.")
    return True


def porta_livre(inicio: int = PORTA_INICIAL, tentativas: int = 30) -> int | None:
    for porta in range(inicio, inicio + tentativas):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    return None


def esperar_porta(porta: int, segundos: float = 90) -> bool:
    fim = time.time() + segundos
    while time.time() < fim:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.5)
    return False


def abrir_programa(abrir_navegador: bool = True) -> int:
    porta = porta_livre()
    if porta is None:
        print("[FALHA] Nao encontrei uma porta livre entre 8501 e 8530.")
        print("A 'porta' e o endereco interno que o programa usa dentro do seu computador.")
        print("O que fazer: feche outras janelas do programa e tente de novo.")
        return 1
    url = f"http://127.0.0.1:{porta}"
    titulo("Abrindo o programa")
    print(f"Endereco (so funciona neste computador): {url}")
    print("Para FECHAR o programa, feche esta janela preta.")
    (RAIZ / "data").mkdir(exist_ok=True)
    cmd = [str(python_venv()), "-m", "streamlit", "run", str(RAIZ / "app.py"),
           "--server.port", str(porta), "--server.address", "127.0.0.1",
           "--server.headless", "true", "--browser.gatherUsageStats", "false"]
    proc = subprocess.Popen(cmd, cwd=RAIZ)
    try:
        if esperar_porta(porta):
            if abrir_navegador:
                webbrowser.open(url)
            print(f"Programa aberto no navegador. Se nao abriu sozinho, copie {url} no navegador.")
        else:
            print("O programa demorou para responder. Veja as mensagens acima.")
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 0


def main() -> int:
    if not verificar_python():
        return 1
    if not preparar_ambiente():
        return 1
    if "--so-preparar" in sys.argv:
        return 0
    return abrir_programa(abrir_navegador="--sem-navegador" not in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
