"""Schemas de cotacao, escada de precos e simulacoes."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import Field

from app.api.schemas.comum import Base, ContextoFiscalIn, MemoriaOut


class ComponenteCustoIn(Base):
    """Um componente do custo do lote, com a camada em que passa a contar."""

    nome: str
    valor: Decimal
    camada_minima: str = "CONTRIBUICAO"
    visoes: list[str] = Field(default_factory=lambda: ["CONTABIL", "GERENCIAL_COMPLETO"])
    e_desembolso: bool = True
    e_relevante_para_decisao: bool = True


class DegrauPrecoOut(Base):
    camada: str
    custo_unitario: Decimal
    deducoes_r: Decimal
    margem_m: Decimal
    preco_unitario: Decimal
    receita_liquida_unitaria: Decimal
    margem_valor: Decimal
    margem_percentual: Decimal
    finalidade: str
    alerta: str | None = None


class SimulacaoCotacaoIn(Base):
    """Cotacao simulada: calcula a escada sem persistir nada."""

    contexto: ContextoFiscalIn
    quantidade_kg: Decimal
    componentes_custo: list[ComponenteCustoIn]
    margem_alvo: Decimal
    margem_contribuicao_minima: Decimal
    comissao_percentual: Decimal = Decimal("0")
    desconto_contratual_percentual: Decimal = Decimal("0")
    preco_mercado: Decimal | None = None
    preco_proposto: Decimal | None = None


class AvaliacaoPropostaOut(Base):
    preco_proposto: Decimal
    faixa: str
    alcada_necessaria: str
    valor_concessao: Decimal
    bloqueado: bool
    mensagem: str


class CotacaoCalculadaOut(Base):
    status: str
    status_fiscal: str
    permite_cotacao_definitiva: bool
    deducoes_r: Decimal
    detalhamento_r: dict[str, Decimal]
    quantidade_kg: Decimal
    custo_por_camada: dict[str, Decimal]
    precos: list[DegrauPrecoOut]
    avaliacao_proposta: AvaliacaoPropostaOut | None = None
    alertas: list[str] = Field(default_factory=list)
    memoria: MemoriaOut


class CotacaoIn(SimulacaoCotacaoIn):
    """Cotacao persistida: exige cliente, material e unidade."""

    unidade_id: uuid.UUID
    cliente_id: uuid.UUID
    material_id: uuid.UUID
    codigo: str | None = None
    criado_por: str | None = None


class CotacaoOut(Base):
    id: uuid.UUID
    codigo: str
    status: str
    versao_atual: int
    quantidade_kg: Decimal
    data_referencia: date
    calculo: CotacaoCalculadaOut


class RevisaoCotacaoIn(Base):
    """Alteracao de premissa: gera nova versao, preserva a anterior."""

    margem_alvo: Decimal | None = None
    margem_contribuicao_minima: Decimal | None = None
    quantidade_kg: Decimal | None = None
    componentes_custo: list[ComponenteCustoIn] | None = None
    preco_mercado: Decimal | None = None
    motivo: str | None = None


class PrecoMaximoCompraIn(Base):
    preco_venda_unitario: Decimal
    quantidade_vendavel: Decimal
    quantidade_aceita_esperada: Decimal
    demais_custos: Decimal
    margem_alvo: Decimal
    contexto: ContextoFiscalIn | None = None
    deducoes_r: Decimal | None = None


class PrecoMaximoCompraOut(Base):
    receita_liquida_total: Decimal
    demais_custos: Decimal
    lucro_alvo: Decimal
    preco_maximo_total: Decimal
    preco_maximo_unitario: Decimal
    deducoes_r: Decimal
    memoria: MemoriaOut
