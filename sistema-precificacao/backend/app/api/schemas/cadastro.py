"""Schemas de material e parceiro."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import Field

from app.api.schemas.comum import Base


class MaterialIn(Base):
    codigo: str = Field(max_length=60)
    descricao: str
    familia: str
    tipo: str = "ENTRADA"
    ncm: str | None = None
    unidade_padrao: str = "KG"
    densidade_kg_m3: Decimal | None = None
    umidade_maxima_aceita: Decimal | None = None
    contaminacao_maxima_aceita: Decimal | None = None
    rendimento_padrao: Decimal | None = None
    perda_normal_padrao: Decimal | None = None
    processo_necessario: str | None = None
    status_dado: str = "CONFIRMADO"


class MaterialOut(MaterialIn):
    id: uuid.UUID
    ativo: bool


class ParceiroIn(Base):
    codigo: str
    nome: str
    papel: str
    natureza: str
    cnpj_cpf: str | None = None
    inscricao_estadual: str | None = None
    contribuinte_icms: bool = False
    regime_tributario: str | None = None
    uf: str
    municipio: str
    prazo_pagamento_dias: int | None = None
    prazo_recebimento_dias: int | None = None
    inadimplencia_historica: Decimal | None = None


class ParceiroOut(ParceiroIn):
    id: uuid.UUID
    ativo: bool


class UnidadeOut(Base):
    id: uuid.UUID
    codigo: str
    nome: str
    uf: str
    municipio: str


class ParametroOut(Base):
    id: uuid.UUID
    regime_tributario: str
    anexo_simples: str | None = None
    moeda: str
    taxa_minima_atratividade_anual: Decimal
    meta_margem_alvo: Decimal
    meta_margem_contribuicao_minima: Decimal
    tolerancia_balanco_massa: Decimal
    horizonte_validade_cotacao_dias: int
    vigencia_inicio: object
    vigencia_fim: object | None = None
