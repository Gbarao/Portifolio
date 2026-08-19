"""Dependencias compartilhadas pelos routers."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date
from typing import Annotated, Any, TypeVar

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.api.erros import RecursoNaoEncontrado
from app.db.session import SessionLocal

T = TypeVar("T")


def obter_sessao() -> Iterator[Session]:
    sessao = SessionLocal()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


SessaoDep = Annotated[Session, Depends(obter_sessao)]


def buscar_ou_404(sessao: Session, modelo: type[T], identificador: uuid.UUID) -> T:
    registro = sessao.get(modelo, identificador)
    if registro is None:
        raise RecursoNaoEncontrado(modelo.__name__, identificador)
    return registro


class Paginacao:
    """Paginacao simples por deslocamento."""

    def __init__(
        self,
        limite: Annotated[int, Query(ge=1, le=200)] = 50,
        deslocamento: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limite = limite
        self.deslocamento = deslocamento


PaginacaoDep = Annotated[Paginacao, Depends(Paginacao)]


def data_referencia(
    em: Annotated[date | None, Query(description="Data usada para vigencia")] = None,
) -> date:
    """Data que decide qual versao de regra e parametro vale.

    O padrao e hoje, mas consultar uma cotacao antiga exige informar a data da
    operacao -- e ela, nunca a data atual, que seleciona a regra.
    """

    return em or date.today()


DataRefDep = Annotated[date, Depends(data_referencia)]


def como_dicionario(objeto: Any, campos: tuple[str, ...]) -> dict[str, Any]:
    return {campo: getattr(objeto, campo, None) for campo in campos}
