"""Painel gerencial: indicadores agregados do periodo (secao 12.3)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.api.deps import SessaoDep
from app.api.schemas.painel import PainelOut
from app.servicos.painel import montar_painel

router = APIRouter(prefix="/painel", tags=["painel gerencial"])


@router.get("/indicadores", response_model=PainelOut)
def indicadores(
    sessao: SessaoDep,
    unidade_id: uuid.UUID | None = Query(default=None),
    de: date | None = Query(default=None, description="Início do período"),
    ate: date | None = Query(default=None, description="Fim do período"),
):
    """Indicadores do período, apurados a partir dos lotes.

    Um lote que não apura (sem balança, sem taxa vigente) não derruba o
    painel: entra em `lotes_com_erro` com o motivo em `alertas`, e fica de
    fora das somas. Indicadores que a base ainda não sustenta são declarados
    em `indisponiveis`, com o motivo — nunca preenchidos com zero.
    """

    return montar_painel(sessao, unidade_id=unidade_id, inicio=de, fim=ate)
