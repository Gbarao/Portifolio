"""Instalador e inicializador do sistema de precificacao.

Um arquivo so, sem dependencia externa alguma: usa apenas a biblioteca padrao
do Python. Ele descobre o que ja existe, faz o que falta e abre o navegador.

Rodar de novo depois de instalado nao reinstala nada -- apenas liga o sistema.
E por isso que o mesmo atalho serve para instalar e para usar todo dia.
"""

from __future__ import annotations

import os
import platform
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import venv
import webbrowser
from pathlib import Path

PORTA_PADRAO = 8000
PYTHON_MINIMO = (3, 11)

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
INTERFACE = RAIZ / "frontend" / "out"
AMBIENTE = BACKEND / ".venv"
MARCA_INSTALACAO = AMBIENTE / ".instalado"
BANCO = BACKEND / "precificacao.db"

VERDE = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
CINZA = "\033[90m"
NEGRITO = "\033[1m"
FIM = "\033[0m"


def _sem_cor() -> bool:
    """Terminais antigos do Windows nao entendem as sequencias de cor."""

    return platform.system() == "Windows" and not os.environ.get("WT_SESSION")


if _sem_cor():
    VERDE = AMARELO = VERMELHO = CINZA = NEGRITO = FIM = ""


def titulo(texto: str) -> None:
    print(f"\n{NEGRITO}{texto}{FIM}")


def passo(texto: str) -> None:
    print(f"  {CINZA}...{FIM} {texto}", flush=True)


def ok(texto: str) -> None:
    print(f"  {VERDE}OK{FIM}  {texto}")


def aviso(texto: str) -> None:
    print(f"  {AMARELO}!{FIM}   {texto}")


def erro(texto: str) -> None:
    print(f"\n  {VERMELHO}ERRO{FIM}  {texto}\n")


def encerrar(mensagem: str, codigo: int = 1) -> None:
    """Mostra o erro e espera o Enter, para a janela nao sumir no clique duplo."""

    erro(mensagem)
    try:
        input("Pressione Enter para fechar. ")
    except (EOFError, KeyboardInterrupt):
        pass
    sys.exit(codigo)


# --------------------------------------------------------------- ambiente
def executavel_do_ambiente(nome: str) -> Path:
    pasta = "Scripts" if platform.system() == "Windows" else "bin"
    sufixo = ".exe" if platform.system() == "Windows" else ""
    return AMBIENTE / pasta / f"{nome}{sufixo}"


def rodar(comando: list[str], descricao: str) -> None:
    """Executa um comando, mostrando a saida apenas quando algo der errado."""

    resultado = subprocess.run(
        comando, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8"
    )
    if resultado.returncode != 0:
        erro(f"Falhou: {descricao}")
        saida = (resultado.stderr or resultado.stdout or "").strip()
        print(saida[-2500:])
        encerrar(
            "O passo acima não pôde ser concluído. Se precisar de ajuda, envie "
            "estas últimas linhas para quem instalou o sistema."
        )


def conferir_python() -> None:
    if sys.version_info < PYTHON_MINIMO:
        encerrar(
            f"Este sistema precisa do Python {PYTHON_MINIMO[0]}.{PYTHON_MINIMO[1]} "
            f"ou mais novo. A versão encontrada foi "
            f"{sys.version_info.major}.{sys.version_info.minor}.\n"
            f"        Baixe a versão atual em https://www.python.org/downloads/ "
            f"e rode este instalador de novo."
        )
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor} encontrado")


def instalar() -> None:
    """Cria o ambiente, instala as bibliotecas e prepara o banco."""

    titulo("Instalando (isso acontece só na primeira vez)")

    if not AMBIENTE.exists():
        passo("Criando o ambiente do Python")
        venv.create(AMBIENTE, with_pip=True)
    ok("Ambiente pronto")

    passo("Baixando as bibliotecas — pode levar alguns minutos")
    rodar(
        [str(executavel_do_ambiente("python")), "-m", "pip", "install", "--quiet",
         "--upgrade", "pip"],
        "atualizar o pip",
    )
    rodar(
        [str(executavel_do_ambiente("python")), "-m", "pip", "install", "--quiet",
         "-e", "."],
        "instalar as bibliotecas",
    )
    ok("Bibliotecas instaladas")

    passo("Preparando o banco de dados")
    rodar([str(executavel_do_ambiente("alembic")), "upgrade", "head"],
          "criar as tabelas do banco")
    ok("Banco de dados pronto")

    MARCA_INSTALACAO.write_text("instalado\n", encoding="utf-8")


def precisa_instalar() -> bool:
    return not MARCA_INSTALACAO.exists() or not executavel_do_ambiente("python").exists()


def banco_tem_dados() -> bool:
    """Pergunta ao banco, nao ao tamanho do arquivo.

    Um banco recem-criado ja passa de 400 KB so com as tabelas vazias, entao
    tamanho de arquivo nao diz nada sobre haver conteudo.
    """

    if not BANCO.exists():
        return False
    try:
        with sqlite3.connect(BANCO) as conexao:
            existe = conexao.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='material'"
            ).fetchone()
            if existe is None:
                return False
            (quantidade,) = conexao.execute("SELECT COUNT(*) FROM material").fetchone()
            return quantidade > 0
    except sqlite3.Error:
        # Banco ilegivel conta como vazio: no maximo a pergunta aparece de novo.
        return False


def oferecer_dados_de_exemplo() -> None:
    """Pergunta uma vez, e so quando o banco esta vazio."""

    if banco_tem_dados():
        return

    titulo("Dados de demonstração")
    print(
        "  O sistema pode começar com dados de exemplo: materiais, parceiros,\n"
        "  um lote completo e uma matriz tributária de exemplo. Serve para\n"
        "  conhecer as telas antes de cadastrar os seus próprios dados."
    )
    try:
        resposta = input(f"\n  Carregar os dados de exemplo? [{NEGRITO}S{FIM}/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resposta = "n"

    if resposta in ("", "s", "sim", "y"):
        passo("Carregando os dados de exemplo")
        rodar([str(executavel_do_ambiente("python")), "-m", "app.seeds.demo"],
              "carregar os dados de exemplo")
        ok("Dados de exemplo carregados")
    else:
        aviso("Começando com a base vazia")


# ------------------------------------------------------------------ execucao
def porta_livre(inicial: int = PORTA_PADRAO) -> int:
    """Procura uma porta livre a partir da preferida.

    Outro programa pode estar ocupando a 8000. Em vez de falhar com uma
    mensagem tecnica, o sistema simplesmente usa a proxima livre.
    """

    for porta in range(inicial, inicial + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            teste.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                teste.bind(("127.0.0.1", porta))
                return porta
            except OSError:
                continue
    encerrar(
        "Não foi possível encontrar uma porta livre para o sistema. "
        "Reinicie o computador e tente de novo."
    )
    return inicial  # inalcançável; mantém o tipo de retorno


def esperar_e_abrir(endereco: str) -> None:
    """Abre o navegador assim que o servidor comecar a responder."""

    porta = int(endereco.rsplit(":", 1)[1])
    for _ in range(60):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            if teste.connect_ex(("127.0.0.1", porta)) == 0:
                webbrowser.open(endereco)
                return


def iniciar(porta: int) -> None:
    endereco = f"http://localhost:{porta}"

    titulo("Sistema em execução")
    print(f"  Endereço: {NEGRITO}{endereco}{FIM}")
    print(f"  {CINZA}O navegador abre sozinho em instantes.{FIM}")
    print(f"\n  {AMARELO}Para desligar o sistema, feche esta janela.{FIM}\n")

    threading.Thread(target=esperar_e_abrir, args=(endereco,), daemon=True).start()

    ambiente = os.environ.copy()
    ambiente.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{BANCO.name}")

    try:
        subprocess.run(
            [
                str(executavel_do_ambiente("python")),
                "-m", "uvicorn",
                "app.api.main:app",
                "--host", "127.0.0.1",
                "--port", str(porta),
                "--log-level", "warning",
            ],
            cwd=BACKEND,
            env=ambiente,
        )
    except KeyboardInterrupt:
        pass

    print(f"\n  {CINZA}Sistema desligado.{FIM}")


def conferir_interface() -> None:
    if INTERFACE.is_dir() and (INTERFACE / "index.html").exists():
        ok("Telas encontradas")
        return
    aviso(
        "As telas compiladas não foram encontradas. O sistema vai subir, mas "
        "só responderá como API."
    )


def main() -> None:
    print(f"\n{NEGRITO}Sistema de custeio e precificação para reciclagem{FIM}")
    print(f"{CINZA}Instalação e inicialização{FIM}")

    if not BACKEND.is_dir():
        encerrar(
            "A pasta do sistema não foi encontrada. Mantenha este instalador "
            "dentro da pasta do projeto, junto das pastas backend e frontend."
        )

    titulo("Verificando o computador")
    conferir_python()
    conferir_interface()

    if precisa_instalar():
        instalar()
        oferecer_dados_de_exemplo()
    else:
        ok("Já instalado — iniciando direto")

    iniciar(porta_livre())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)
