"""Diagnostico do computador (chamado pelo diagnostico.bat). So biblioteca padrao.

Verifica: versao do Python, venv, pip, download de um pacote de teste, se a
pasta data/ pode ser gravada e, se o ambiente ja existir, os pacotes instalados.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iniciar import MARCA, RAIZ, REQ, SINAIS_REDE, VERSAO_MINIMA, python_venv  # noqa: E402

problemas: list[str] = []


def ok(txt: str) -> None:
    print(f"  [OK]    {txt}")


def falha(txt: str, oque_fazer: str) -> None:
    print(f"  [FALHA] {txt}")
    print(f"          O que fazer: {oque_fazer}")
    problemas.append(txt)


def rodar(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 1, "timed out"
    except OSError as e:
        return 1, str(e)


def main() -> int:
    print()
    print("DIAGNOSTICO DO COMPUTADOR - Programa ZFM x Reforma Tributaria")
    print("-" * 70)
    v = sys.version_info
    if (v.major, v.minor) >= VERSAO_MINIMA:
        ok(f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")
    else:
        falha(f"Python {v.major}.{v.minor} e antigo demais",
              "pedir a TI o Python 3.10 ou superior (MANUAL.md, secao 2).")

    cod, _ = rodar([sys.executable, "-m", "venv", "--help"])
    if cod == 0:
        ok("Modulo venv disponivel (cria o ambiente do programa sem administrador)")
    else:
        falha("Modulo venv indisponivel", "pedir a TI a instalacao completa do Python 3.")

    cod, out = rodar([sys.executable, "-m", "pip", "--version"])
    if cod == 0:
        ok(f"pip responde: {out.split(' from ')[0].strip()}")
    else:
        falha("pip nao responde", "pedir a TI a instalacao do Python com o pip incluido.")

    with tempfile.TemporaryDirectory() as tmp:
        cod, out = rodar([sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
                          "--no-deps", "--only-binary=:all:", "-d", tmp, "six"])
        if cod == 0:
            ok("Download de pacote de teste da internet (pypi.org) funcionou")
        elif any(s in out for s in SINAIS_REDE):
            falha("Download bloqueado pela rede (proxy ou certificado)",
                  "pedir a TI a liberacao de pypi.org e files.pythonhosted.org "
                  "(texto pronto no MANUAL.md, secao 2, passo 5).")
            print("          Mensagem original: " + out.strip().splitlines()[-1][:200])
        else:
            falha("Download de pacote de teste falhou",
                  "copie esta janela e envie ao Claude Code.")
            print("          Mensagem original: " + (out.strip().splitlines() or ["?"])[-1][:200])

    dados = RAIZ / "data"
    try:
        dados.mkdir(exist_ok=True)
        teste = dados / "_teste_gravacao.tmp"
        teste.write_text("ok", encoding="utf-8")
        teste.unlink()
        ok(f"Pasta de dados pode ser gravada ({dados})")
    except OSError:
        falha(f"Nao foi possivel gravar na pasta {dados}",
              "mova a pasta do programa para Documentos e tente de novo.")

    if python_venv().exists():
        if MARCA.exists() and MARCA.read_text(encoding="utf-8") == REQ.read_text(encoding="utf-8"):
            nomes = [l.split("==")[0].strip() for l in REQ.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            mods = {"pytest": "pytest", "openpyxl": "openpyxl"}
            cod, out = rodar([str(python_venv()), "-c",
                              "import importlib, sys; [importlib.import_module(m) for m in sys.argv[1:]]"]
                             + [mods.get(n, n) for n in nomes])
            if cod == 0:
                ok("Bibliotecas do programa instaladas: " + ", ".join(nomes))
            else:
                falha("Alguma biblioteca do programa nao carrega",
                      "apague a pasta .venv e de duplo clique em iniciar.bat de novo.")
        else:
            print("  [INFO]  O ambiente existe, mas a instalacao das bibliotecas nao terminou.")
            print("          De duplo clique em iniciar.bat para concluir.")
    else:
        print("  [INFO]  O ambiente do programa ainda nao foi criado (normal antes do 1o uso).")
        print("          Ele sera criado no primeiro duplo clique em iniciar.bat.")

    print("-" * 70)
    if problemas:
        print("RESULTADO: falta resolver:")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print("RESULTADO: Tudo certo. Pode dar duplo clique em iniciar.bat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
