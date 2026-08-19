"""Cotacao, versionamento de premissas, escada de precos e pedidos (secoes 8, 12.1 e 14)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    Percentual,
    PercentualOpc,
    Quantidade,
    TextoOpc,
    TimestampMixin,
)
from app.models._tipos import coluna_enum
from app.models.enums import (
    CamadaPreco,
    RegimeTributario,
    StatusCotacao,
    StatusDado,
    StatusRegraFiscal,
    TipoFrete,
    UnidadeMedida,
    VisaoCusto,
)


class CotacaoVenda(IdMixin, TimestampMixin, Base):
    """Cabecalho da cotacao. As premissas vivem nas versoes."""

    __tablename__ = "cotacao_venda"

    codigo: Mapped[str] = mapped_column(unique=True)
    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parceiro.id"))
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))

    quantidade: Mapped[Quantidade]
    unidade_comercial: Mapped[UnidadeMedida] = coluna_enum(UnidadeMedida)
    quantidade_kg: Mapped[Quantidade]

    uf_destino: Mapped[str]
    municipio_destino: Mapped[str | None]
    tipo_frete: Mapped[TipoFrete] = coluna_enum(TipoFrete)
    prazo_recebimento_dias: Mapped[int] = mapped_column(default=0)
    data_referencia: Mapped[date]

    status: Mapped[StatusCotacao] = coluna_enum(
        StatusCotacao, default=StatusCotacao.RASCUNHO
    )
    versao_atual: Mapped[int] = mapped_column(default=1)
    criado_por: Mapped[str | None]
    observacao: Mapped[TextoOpc]

    versoes: Mapped[list["CotacaoVersao"]] = relationship(back_populates="cotacao")


class CotacaoVersao(IdMixin, TimestampMixin, Base):
    """Versao imutavel de uma cotacao (regra 9 da secao 11).

    ``premissas`` congela em JSON tudo que foi usado: taxas de atividade,
    parametros da empresa, ids e versoes das regras fiscais, rendimento,
    frete e prazos. Alteracao posterior gera nova versao; a anterior e
    preservada para reproducao do preco.
    """

    __tablename__ = "cotacao_versao"
    __table_args__ = (UniqueConstraint("cotacao_id", "numero_versao"),)

    cotacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacao_venda.id"))
    numero_versao: Mapped[int]
    regime_tributario: Mapped[RegimeTributario] = coluna_enum(RegimeTributario)

    premissas: Mapped[dict[str, Any]]
    memoria_calculo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memoria_calculo.id")
    )

    # Deducoes proporcionais sobre o preco bruto -- a variavel `r` da secao 7.6.
    deducoes_r: Mapped[Percentual]
    margem_alvo_m: Mapped[Percentual]

    preco_proposto: Mapped[DinheiroOpc]
    margem_contribuicao_valor: Mapped[DinheiroOpc]
    margem_contribuicao_percentual: Mapped[PercentualOpc]
    margem_operacional_percentual: Mapped[PercentualOpc]
    margem_completa_percentual: Mapped[PercentualOpc]

    capital_giro_dias: Mapped[int | None]
    capital_giro_custo: Mapped[DinheiroOpc]

    status: Mapped[StatusCotacao] = coluna_enum(
        StatusCotacao, default=StatusCotacao.RASCUNHO
    )
    status_fiscal: Mapped[StatusRegraFiscal] = coluna_enum(
        StatusRegraFiscal, default=StatusRegraFiscal.PROVISORIA
    )
    indice_completude_dados: Mapped[PercentualOpc]
    validade_ate: Mapped[date | None]

    criado_por: Mapped[str | None]
    aprovado_por: Mapped[str | None]
    aprovado_em: Mapped[datetime | None]
    motivo_excecao: Mapped[TextoOpc]
    prazo_excecao_ate: Mapped[date | None]

    cotacao: Mapped[CotacaoVenda] = relationship(back_populates="versoes")
    precos: Mapped[list["CotacaoPreco"]] = relationship(back_populates="versao")


class CotacaoPreco(IdMixin, TimestampMixin, Base):
    """Um degrau da escada de precos (secao 8).

    Cada degrau carrega o proprio custo e a propria margem: preco nunca e
    apresentado sem indicar de qual camada de custo veio (secao 15).
    """

    __tablename__ = "cotacao_preco"
    __table_args__ = (UniqueConstraint("versao_id", "camada"),)

    versao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacao_versao.id"))
    camada: Mapped[CamadaPreco] = coluna_enum(CamadaPreco)
    visao_custo: Mapped[VisaoCusto] = coluna_enum(VisaoCusto)

    custo_unitario: Mapped[Dinheiro]
    deducoes_r: Mapped[Percentual]
    margem_m: Mapped[Percentual]
    preco_unitario: Mapped[Dinheiro]
    preco_total: Mapped[Dinheiro]
    receita_liquida_unitaria: Mapped[Dinheiro]
    margem_valor: Mapped[Dinheiro]
    margem_percentual: Mapped[Percentual]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    alerta: Mapped[TextoOpc]

    versao: Mapped[CotacaoVersao] = relationship(back_populates="precos")


class SimulacaoCenario(IdMixin, TimestampMixin, Base):
    """Cenarios obrigatorios da secao 14: base, otimista, estressado e
    ponto de equilibrio, mais preco maximo de compra."""

    __tablename__ = "simulacao_cenario"

    versao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacao_versao.id"))
    nome: Mapped[str]
    variaveis_alteradas: Mapped[dict[str, Any]]
    resultado: Mapped[dict[str, Any]]
    preco_maximo_compra_kg: Mapped[DinheiroOpc]
    preco_minimo_venda_kg: Mapped[DinheiroOpc]
    ponto_equilibrio_quantidade_kg: Mapped[Dinheiro | None]
    memoria_calculo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memoria_calculo.id")
    )


class PedidoVenda(IdMixin, TimestampMixin, Base):
    """Cotacao aprovada que virou pedido (secao 10)."""

    __tablename__ = "pedido_venda"

    codigo: Mapped[str] = mapped_column(unique=True)
    cotacao_versao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cotacao_versao.id"))
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parceiro.id"))
    lote_saida_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote_saida.id"))

    quantidade_kg: Mapped[Quantidade]
    preco_unitario: Mapped[Dinheiro]
    condicao_pagamento: Mapped[str | None]
    tipo_frete: Mapped[TipoFrete] = coluna_enum(TipoFrete)

    data_pedido: Mapped[date]
    data_entrega_prevista: Mapped[date | None]
    data_faturamento: Mapped[date | None]
    data_recebimento_prevista: Mapped[date | None]
    data_recebimento_efetiva: Mapped[date | None]

    status: Mapped[str] = mapped_column(default="ABERTO")
    observacao: Mapped[TextoOpc]
