"""Traducao de erros de dominio para respostas HTTP.

Um bloqueio de regra de negocio nao e falha do servidor. Balanco de massa
fora da tolerancia, regra fiscal vencida ou dupla contagem sao respostas
legitimas do sistema, com causa identificada -- por isso viram 409 ou 422
com corpo explicativo, nunca 500.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# O nome da constante mudou entre versoes do Starlette; o codigo 422 nao.
# O acesso e condicional porque ler o nome antigo ja emite DeprecationWarning.
HTTP_422 = (
    status.HTTP_422_UNPROCESSABLE_CONTENT
    if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT")
    else 422
)

from app.dominio.excecoes import (
    DadoObrigatorioAusenteError,
    DenominadorZeroError,
    DuplaContagemError,
    ErroDominio,
    MassaInconsistenteError,
    ParametroInvalidoError,
    RegraFiscalIndisponivelError,
)

# 409 = conflito com o estado atual: o pedido faz sentido, mas o sistema nao
# pode atende-lo enquanto a condicao existir (regra vencida, massa aberta).
# 422 = a premissa enviada e invalida em si (denominador zero, r >= 100%).
MAPA_HTTP: dict[type[ErroDominio], int] = {
    # O erro base cai em 409: quase todo bloqueio nao mapeado e conflito com o
    # estado atual, nao premissa invalida.
    ErroDominio: status.HTTP_409_CONFLICT,
    MassaInconsistenteError: status.HTTP_409_CONFLICT,
    RegraFiscalIndisponivelError: status.HTTP_409_CONFLICT,
    DuplaContagemError: status.HTTP_409_CONFLICT,
    DenominadorZeroError: HTTP_422,
    ParametroInvalidoError: HTTP_422,
    DadoObrigatorioAusenteError: HTTP_422,
}


class RecursoNaoEncontrado(Exception):
    """Registro inexistente. Separado dos erros de dominio de proposito."""

    def __init__(self, entidade: str, identificador: object) -> None:
        self.entidade = entidade
        self.identificador = identificador
        super().__init__(f"{entidade} {identificador} não encontrado.")


def _codigo_de(tipo: type[ErroDominio]) -> int:
    """Resolve o status percorrendo a hierarquia da excecao.

    Uma excecao especifica -- criada por um router para um bloqueio proprio --
    herda o status da sua base em vez de cair no padrao. Consultar so o tipo
    exato faria toda subclasse nova voltar para 422 sem ninguem perceber.
    """

    for classe in tipo.__mro__:
        if classe in MAPA_HTTP:
            return MAPA_HTTP[classe]
    return HTTP_422


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(RecursoNaoEncontrado)
    async def _nao_encontrado(_: Request, exc: RecursoNaoEncontrado) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "erro": "RECURSO_NAO_ENCONTRADO",
                "entidade": exc.entidade,
                "identificador": str(exc.identificador),
                "mensagem": str(exc),
            },
        )

    @app.exception_handler(ErroDominio)
    async def _erro_dominio(_: Request, exc: ErroDominio) -> JSONResponse:
        codigo = _codigo_de(type(exc))
        return JSONResponse(
            status_code=codigo,
            content={
                "erro": type(exc).__name__,
                "mensagem": str(exc),
                "bloqueante": True,
            },
        )
