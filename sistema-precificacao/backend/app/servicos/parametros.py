"""Selecao de parametros e regras vigentes na data da operacao.

Toda consulta aqui filtra por vigencia, nunca pelo registro "mais recente":
reproduzir uma cotacao de marco exige as regras de marco.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AtividadeTaxa, EmpresaParametro, FaixaSimplesNacional, RegraTributaria


def _filtro_vigencia(modelo, data_operacao: date):
    return (
        modelo.vigencia_inicio <= data_operacao,
        or_(modelo.vigencia_fim.is_(None), modelo.vigencia_fim >= data_operacao),
    )


def parametro_vigente(
    sessao: Session, unidade_id: uuid.UUID, data_operacao: date
) -> EmpresaParametro | None:
    return sessao.scalar(
        select(EmpresaParametro)
        .where(
            EmpresaParametro.unidade_id == unidade_id,
            *_filtro_vigencia(EmpresaParametro, data_operacao),
        )
        .order_by(EmpresaParametro.vigencia_inicio.desc())
        .limit(1)
    )


def regras_vigentes(
    sessao: Session,
    data_operacao: date,
    *,
    incluir_vencidas: bool = True,
) -> list[RegraTributaria]:
    """Regras candidatas para a data.

    As vencidas sao trazidas de proposito: e o motor de resolucao que precisa
    enxerga-las para bloquear a cotacao, e nao simplesmente ignora-las.
    """

    if incluir_vencidas:
        return list(sessao.scalars(select(RegraTributaria)).all())
    return list(
        sessao.scalars(
            select(RegraTributaria).where(*_filtro_vigencia(RegraTributaria, data_operacao))
        ).all()
    )


def faixas_simples(sessao: Session, data_operacao: date) -> list[FaixaSimplesNacional]:
    return list(
        sessao.scalars(
            select(FaixaSimplesNacional)
            .where(*_filtro_vigencia(FaixaSimplesNacional, data_operacao))
            .order_by(FaixaSimplesNacional.ordem_faixa)
        ).all()
    )


def taxas_vigentes(sessao: Session, data_operacao: date) -> dict[uuid.UUID, AtividadeTaxa]:
    """Taxa vigente por atividade, indexada pelo id da atividade."""

    registros = sessao.scalars(
        select(AtividadeTaxa)
        .where(*_filtro_vigencia(AtividadeTaxa, data_operacao))
        .order_by(AtividadeTaxa.vigencia_inicio)
    ).all()
    return {taxa.atividade_id: taxa for taxa in registros}
