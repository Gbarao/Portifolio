"""Aplicacao FastAPI do sistema de custeio e precificacao."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.erros import registrar_tratadores
from app.api.routers import cadastros, cotacoes, operacoes, painel, saude, tributario

# A interface compilada vive fora do pacote Python, na pasta do frontend.
INTERFACE = Path(__file__).resolve().parents[3] / "frontend" / "out"

# Todos os endpoints ficam sob /api. As telas ocupam a raiz, e nunca ha duvida
# sobre qual das duas responde a um caminho.
PREFIXO_API = "/api"

DESCRICAO = """
API do modelo de precificacao para operacoes de reciclagem.

Tres comportamentos valem para toda a API:

* **Nenhum preco sem rotulo.** A escada devolve os cinco degraus com a
  finalidade de cada um; o cliente escolhe qual apresentar.
* **Regra fiscal vencida bloqueia.** O calculo ainda e devolvido, mas
  `permite_cotacao_definitiva` fica falso e o alerta explica o motivo.
* **Memoria de calculo em toda saida relevante.** Cada resposta de custo ou
  preco carrega os passos, formulas e fontes que a produziram.
"""


def criar_app() -> FastAPI:
    app = FastAPI(
        title="Precificacao para reciclagem",
        version=__version__,
        description=DESCRICAO,
        # Documentacao tambem sob /api: a raiz pertence inteira as telas.
        docs_url=f"{PREFIXO_API}/docs",
        redoc_url=f"{PREFIXO_API}/redoc",
        openapi_url=f"{PREFIXO_API}/openapi.json",
        openapi_tags=[
            {"name": "saude", "description": "Disponibilidade da API e do banco."},
            {"name": "cadastros", "description": "Unidades, parametros, materiais e parceiros."},
            {"name": "operacoes", "description": "Lotes, eventos e resultado economico."},
            {"name": "motor tributario", "description": "Matriz de regras, deducoes e Simples."},
            {"name": "cotacoes e simulacoes", "description": "Escada de precos e cenarios."},
            {"name": "painel gerencial", "description": "Indicadores agregados do periodo."},
        ],
    )

    # O frontend do Passo 5 roda em outra origem durante o desenvolvimento.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registrar_tratadores(app)

    for roteador in (
        saude.router,
        cadastros.router,
        operacoes.router,
        tributario.router,
        cotacoes.router,
        painel.router,
    ):
        app.include_router(roteador, prefix=PREFIXO_API)

    _servir_interface(app)
    return app


def _servir_interface(app: FastAPI) -> None:
    """Serve as telas compiladas na raiz, se existirem.

    E o que torna o sistema um programa so: um unico processo entrega a API e
    a interface, no mesmo endereco. Sem a pasta compilada o servidor continua
    funcionando como API pura -- util em desenvolvimento, quando as telas
    rodam pelo `npm run dev`.
    """

    if not INTERFACE.is_dir():
        return

    app.mount(
        "/",
        StaticFiles(directory=INTERFACE, html=True),
        name="interface",
    )


app = criar_app()
