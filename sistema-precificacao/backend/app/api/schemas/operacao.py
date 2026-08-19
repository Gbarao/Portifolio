"""Schemas de lote e balanco de massa."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import Field

from app.api.schemas.comum import Base, MemoriaOut


class LoteIn(Base):
    codigo: str
    unidade_id: uuid.UUID
    fornecedor_id: uuid.UUID
    material_id: uuid.UUID
    data_entrada: date
    preco_unitario_bruto: Decimal
    unidade_negociada: str = "KG"
    quantidade_negociada: Decimal
    quantidade_negociada_kg: Decimal
    tipo_frete_entrada: str = "FROTA_PROPRIA"
    prazo_pagamento_dias: int = 0

    documento_modelo: str | None = None
    documento_numero: str | None = None
    cfop: str | None = None
    desconto_comercial: Decimal = Decimal("0")
    frete_entrada: Decimal = Decimal("0")
    seguro_entrada: Decimal = Decimal("0")
    pedagio_entrada: Decimal = Decimal("0")
    coleta_carga_descarga: Decimal = Decimal("0")
    pesagem_inspecao: Decimal = Decimal("0")
    destinacao_rejeito_estimada: Decimal = Decimal("0")
    tributos_nao_recuperaveis: Decimal = Decimal("0")
    creditos_fiscais_confirmados: Decimal = Decimal("0")
    creditos_fiscais_condicionados: Decimal = Decimal("0")


class LoteOut(Base):
    id: uuid.UUID
    codigo: str
    status: str
    status_dado: str
    data_entrada: date
    quantidade_negociada_kg: Decimal
    preco_unitario_bruto: Decimal


class EventoBalancaIn(Base):
    peso_bruto_kg: Decimal
    tara_kg: Decimal
    identificacao_balanca: str | None = None
    operador: str | None = None
    data_hora: datetime
    momento: str = "ENTRADA"


class EventoQualidadeIn(Base):
    quantidade_recusada_kg: Decimal = Decimal("0")
    umidade_percentual: Decimal | None = None
    impureza_percentual: Decimal | None = None
    classificacao: str | None = None
    desconto_aplicado: Decimal = Decimal("0")
    responsavel: str | None = None
    data_hora: datetime


class LoteSaidaIn(Base):
    codigo: str
    material_id: uuid.UUID
    quantidade_kg: Decimal
    preco_estimado_venda_kg: Decimal | None = None
    gastos_posteriores_estimados: Decimal = Decimal("0")
    numero_fardos: int | None = None
    data_producao: date
    e_subproduto: bool = False


class PerdaIn(Base):
    tipo: str
    quantidade_kg: Decimal
    destino: str | None = None
    custo_destinacao: Decimal = Decimal("0")
    causa: str | None = None
    data_evento: date


class BalancoOut(Base):
    quantidade_bruta: Decimal
    quantidade_recusada: Decimal
    quantidade_aceita: Decimal
    quantidade_vendavel: Decimal
    quantidade_rejeito: Decimal
    perda_normal: Decimal
    perda_anormal: Decimal
    diferenca_nao_explicada: Decimal
    rendimento: Decimal
    taxa_rejeito: Decimal
    dentro_da_tolerancia: bool


class ResultadoLoteOut(Base):
    """Resultado economico do lote com a memoria completa (secao 12.2)."""

    lote_id: uuid.UUID
    codigo: str
    balanco: BalancoOut
    custo_aquisicao_total: Decimal
    custo_aquisicao_por_kg_aceito: Decimal
    custo_aquisicao_por_kg_vendavel: Decimal
    custo_transformacao: Decimal
    custo_capital: Decimal
    custo_total: Decimal
    custo_unitario_vendavel: Decimal
    creditos_pendentes: Decimal
    alertas: list[str] = Field(default_factory=list)
    memoria: MemoriaOut
