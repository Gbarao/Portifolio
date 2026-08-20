"""Aplicacao FastAPI do sistema de custeio e precificacao."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.erros import registrar_tratadores
from app.api.routers import cadastros, cotacoes, operacoes, painel, saude, tributario

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

    app.include_router(saude.router)
    app.include_router(cadastros.router)
    app.include_router(operacoes.router)
    app.include_router(tributario.router)
    app.include_router(cotacoes.router)
    app.include_router(painel.router)
    return app


app = criar_app()
