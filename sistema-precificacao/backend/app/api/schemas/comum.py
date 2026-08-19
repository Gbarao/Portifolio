"""Schemas compartilhados: memoria de calculo, alertas e paginacao."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PassoMemoriaOut(Base):
    """Um passo reproduzivel do calculo (secao 15)."""

    ordem: int
    rotulo: str
    formula: str
    entradas: dict[str, Any]
    resultado: Decimal
    unidade: str
    fonte: str | None = None
    vigencia_regra: str | None = None
    status_dado: str
    alerta: str | None = None


class MemoriaOut(Base):
    titulo: str
    passos: list[PassoMemoriaOut]
    alertas: list[str] = Field(default_factory=list)


class AlertaOut(Base):
    codigo: str
    severidade: str
    bloqueante: bool
    mensagem: str


class Pagina(BaseModel, Generic[T]):
    itens: list[T]
    total: int
    limite: int
    deslocamento: int


class IdentificadorOut(Base):
    id: uuid.UUID


class ContextoFiscalIn(BaseModel):
    """Chaves da operacao usadas para resolver a regra tributaria."""

    data_operacao: date
    tipo_operacao: str = "VENDA"
    regime_tributario: str
    uf_origem: str | None = None
    uf_destino: str | None = None
    municipio: str | None = None
    ncm: str | None = None
    cfop: str | None = None
    cst_csosn: str | None = None
    familia_material: str | None = None
    natureza_parceiro: str | None = None
    regime_parceiro: str | None = None
    parceiro_contribuinte: bool | None = None
