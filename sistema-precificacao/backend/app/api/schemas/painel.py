"""Schemas do painel gerencial (secao 12.3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import Field

from app.api.schemas.comum import Base


class MargemMaterialOut(Base):
    material_codigo: str
    material_descricao: str
    quantidade_kg: Decimal
    custo_variavel_por_kg: Decimal
    preco_estimado_por_kg: Decimal
    margem_contribuicao_por_kg: Decimal
    margem_percentual: Decimal


class OciosidadeOut(Base):
    atividade_codigo: str
    atividade_nome: str
    capacidade_pratica: Decimal
    utilizacao_real: Decimal
    percentual_ocupacao: Decimal
    custo_ociosidade: Decimal
    unidade_direcionador: str


class IndicadorIndisponivelOut(Base):
    """Indicador que a base ainda nao sustenta -- declarado, nao omitido."""

    nome: str
    motivo: str


class PainelOut(Base):
    periodo_inicio: date | None = None
    periodo_fim: date | None = None

    lotes_apurados: int
    lotes_com_erro: int

    quantidade_aceita_kg: Decimal
    quantidade_vendavel_kg: Decimal
    rejeito_kg: Decimal
    perda_normal_kg: Decimal
    perda_anormal_kg: Decimal
    rendimento_medio: Decimal

    custo_aquisicao_total: Decimal
    custo_transformacao_total: Decimal
    custo_capital_total: Decimal
    custo_total: Decimal
    custo_por_tonelada_vendavel: Decimal
    preco_medio_compra_kg: Decimal

    custo_ociosidade_total: Decimal
    ociosidade_por_atividade: list[OciosidadeOut] = Field(default_factory=list)

    creditos_confirmados: Decimal
    creditos_condicionados: Decimal

    dias_ciclo_financeiro: Decimal
    capital_empregado: Decimal

    margem_por_material: list[MargemMaterialOut] = Field(default_factory=list)
    indisponiveis: list[IndicadorIndisponivelOut] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
