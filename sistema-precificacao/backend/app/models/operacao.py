"""Eventos operacionais do lote: entrada, balanca, qualidade, processo,
saidas, perdas e frete (secao 4).

Regra estrutural: eventos historicos nunca sao sobrescritos. Correcao entra
como novo lancamento de ajuste (``ajuste_de_evento_id``), preservando o
original -- exigencia das secoes 4 e 15.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    CompetenciaCaixaMixin,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    PercentualOpc,
    Quantidade,
    QuantidadeOpc,
    TextoOpc,
    TimestampMixin,
)
from app.models._tipos import coluna_enum
from app.models.empresa import Unidade
from app.models.enums import (
    MetodoCustoConjunto,
    StatusDado,
    StatusLote,
    TipoEventoProcesso,
    TipoFrete,
    TipoPerda,
    UnidadeMedida,
)


class LoteCompra(IdMixin, TimestampMixin, CompetenciaCaixaMixin, Base):
    """Unidade basica de rastreamento (secao 3).

    Os pesos sao campos distintos e nao intercambiaveis (regra 4 da secao 11):
    negociado, bruto, liquido e aceito vivem em colunas separadas -- os tres
    ultimos alimentados pelos eventos de balanca e qualidade.
    """

    __tablename__ = "lote_compra"

    codigo: Mapped[str] = mapped_column(unique=True)
    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    fornecedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parceiro.id"))
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contrato_tabela.id")
    )

    documento_modelo: Mapped[str | None]
    documento_numero: Mapped[str | None]
    documento_serie: Mapped[str | None]
    cfop: Mapped[str | None]
    cst_csosn: Mapped[str | None]
    data_entrada: Mapped[date]

    # Condicao negociada, na unidade original do documento. A conversao para
    # kg fica em `quantidade_negociada_kg`, preservando a unidade de origem
    # para auditoria (secao 3).
    preco_unitario_bruto: Mapped[Dinheiro]
    unidade_negociada: Mapped[UnidadeMedida] = coluna_enum(UnidadeMedida)
    quantidade_negociada: Mapped[Quantidade]
    quantidade_negociada_kg: Mapped[Quantidade]

    desconto_comercial: Mapped[Dinheiro] = mapped_column(default=0)
    bonificacao: Mapped[Dinheiro] = mapped_column(default=0)
    tributos_nao_recuperaveis: Mapped[Dinheiro] = mapped_column(default=0)
    # Somente creditos confirmados, documentados e realizaveis (secao 6.1).
    creditos_fiscais_confirmados: Mapped[Dinheiro] = mapped_column(default=0)
    creditos_fiscais_condicionados: Mapped[Dinheiro] = mapped_column(default=0)

    frete_entrada: Mapped[Dinheiro] = mapped_column(default=0)
    seguro_entrada: Mapped[Dinheiro] = mapped_column(default=0)
    pedagio_entrada: Mapped[Dinheiro] = mapped_column(default=0)
    coleta_carga_descarga: Mapped[Dinheiro] = mapped_column(default=0)
    pesagem_inspecao: Mapped[Dinheiro] = mapped_column(default=0)
    comissao_compra: Mapped[Dinheiro] = mapped_column(default=0)
    embalagem_nao_retornavel: Mapped[Dinheiro] = mapped_column(default=0)
    destinacao_rejeito_estimada: Mapped[Dinheiro] = mapped_column(default=0)
    outros_custos_aquisicao: Mapped[Dinheiro] = mapped_column(default=0)

    tipo_frete_entrada: Mapped[TipoFrete] = coluna_enum(TipoFrete)
    prazo_pagamento_dias: Mapped[int] = mapped_column(default=0)

    status: Mapped[StatusLote] = coluna_enum(StatusLote, default=StatusLote.ABERTO)
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    encerrado_em: Mapped[datetime | None]
    encerrado_por: Mapped[str | None]
    justificativa_excecao: Mapped[TextoOpc]
    observacao: Mapped[TextoOpc]

    unidade: Mapped[Unidade] = relationship()
    eventos_balanca: Mapped[list["EventoBalanca"]] = relationship(
        back_populates="lote"
    )
    eventos_qualidade: Mapped[list["EventoQualidade"]] = relationship(
        back_populates="lote"
    )
    eventos_processo: Mapped[list["EventoProcesso"]] = relationship(
        back_populates="lote"
    )
    saidas: Mapped[list["LoteSaida"]] = relationship(back_populates="lote_origem")
    perdas: Mapped[list["RejeitoPerda"]] = relationship(back_populates="lote")


class EventoBalanca(IdMixin, TimestampMixin, Base):
    """Ticket de balanca: peso bruto, tara e liquido com evidencia."""

    __tablename__ = "evento_balanca"

    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_compra.id"))
    momento: Mapped[str] = mapped_column(default="ENTRADA")
    peso_bruto_kg: Mapped[Quantidade]
    tara_kg: Mapped[Quantidade]
    peso_liquido_kg: Mapped[Quantidade]
    identificacao_balanca: Mapped[str | None]
    operador: Mapped[str | None]
    data_hora: Mapped[datetime]
    evidencia_url: Mapped[str | None]
    ajuste_de_evento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evento_balanca.id")
    )
    justificativa_ajuste: Mapped[TextoOpc]

    lote: Mapped[LoteCompra] = relationship(
        back_populates="eventos_balanca", foreign_keys=[lote_id]
    )


class EventoQualidade(IdMixin, TimestampMixin, Base):
    """Inspecao e classificacao que definem a quantidade aceita (secao 7.1)."""

    __tablename__ = "evento_qualidade"

    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_compra.id"))
    amostra: Mapped[str | None]
    umidade_percentual: Mapped[PercentualOpc]
    impureza_percentual: Mapped[PercentualOpc]
    classificacao: Mapped[str | None]
    quantidade_recusada_kg: Mapped[Quantidade] = mapped_column(default=0)
    desconto_aplicado: Mapped[Dinheiro] = mapped_column(default=0)
    responsavel: Mapped[str | None]
    data_hora: Mapped[datetime]
    ajuste_de_evento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evento_qualidade.id")
    )
    justificativa_ajuste: Mapped[TextoOpc]

    lote: Mapped[LoteCompra] = relationship(
        back_populates="eventos_qualidade", foreign_keys=[lote_id]
    )


class EventoProcesso(IdMixin, TimestampMixin, Base):
    """Consumo de atividade pelo lote -- base do custeio ABC (secao 7.3).

    ``custo_direto_exclusivo`` so pode ser usado para gastos que NAO estao no
    pool da atividade, sob pena de dupla contagem (caso de teste 8).
    """

    __tablename__ = "evento_processo"

    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_compra.id"))
    lote_saida_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote_saida.id"))
    atividade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atividade.id"))
    recurso_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurso.id"))
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_custo.id"))
    tipo_evento: Mapped[TipoEventoProcesso] = coluna_enum(TipoEventoProcesso)

    inicio: Mapped[datetime]
    fim: Mapped[datetime | None]
    quantidade_direcionador: Mapped[Quantidade]
    quantidade_processada_kg: Mapped[QuantidadeOpc]
    consumo_energia_kwh: Mapped[QuantidadeOpc]
    consumo_agua_m3: Mapped[QuantidadeOpc]
    custo_direto_exclusivo: Mapped[Dinheiro] = mapped_column(default=0)

    responsavel: Mapped[str | None]
    observacao: Mapped[TextoOpc]

    lote: Mapped[LoteCompra] = relationship(back_populates="eventos_processo")


class LoteSaida(IdMixin, TimestampMixin, Base):
    """Produto gerado pelo processamento de um lote de entrada.

    ``custo_conjunto_atribuido`` e gravado no encerramento do lote junto com o
    fator usado, para que o rateio seja reproduzivel (secao 7.4).
    """

    __tablename__ = "lote_saida"

    codigo: Mapped[str] = mapped_column(unique=True)
    lote_origem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_compra.id"))
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))

    quantidade_kg: Mapped[Quantidade]
    numero_fardos: Mapped[int | None]
    qualidade: Mapped[str | None]
    umidade_percentual: Mapped[PercentualOpc]

    preco_estimado_venda_kg: Mapped[DinheiroOpc]
    gastos_posteriores_estimados: Mapped[Dinheiro] = mapped_column(default=0)
    metodo_custo_conjunto: Mapped[MetodoCustoConjunto] = coluna_enum(
        MetodoCustoConjunto, default=MetodoCustoConjunto.VRL_RELATIVO
    )
    fator_rateio_aplicado: Mapped[PercentualOpc]
    custo_conjunto_atribuido: Mapped[DinheiroOpc]
    e_subproduto: Mapped[bool] = mapped_column(default=False)

    data_producao: Mapped[date]
    status: Mapped[StatusLote] = coluna_enum(StatusLote, default=StatusLote.ABERTO)
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )

    lote_origem: Mapped[LoteCompra] = relationship(back_populates="saidas")


class RejeitoPerda(IdMixin, TimestampMixin, Base):
    """Rejeitos e perdas segregados por natureza (secao 6.6).

    ``integra_custo_padrao`` e falso para perda anormal: ela e desvio do
    periodo e so entra no custo mediante aprovacao formal (regra 6, secao 11).
    """

    __tablename__ = "rejeito_perda"

    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_compra.id"))
    lote_saida_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote_saida.id"))
    tipo: Mapped[TipoPerda] = coluna_enum(TipoPerda)
    quantidade_kg: Mapped[Quantidade]
    integra_custo_padrao: Mapped[bool] = mapped_column(default=True)
    destino: Mapped[str | None]
    custo_destinacao: Mapped[Dinheiro] = mapped_column(default=0)
    receita_destinacao: Mapped[Dinheiro] = mapped_column(default=0)
    causa: Mapped[TextoOpc]
    aprovado_por: Mapped[str | None]
    data_evento: Mapped[date]

    lote: Mapped[LoteCompra] = relationship(back_populates="perdas")


class EventoFrete(IdMixin, TimestampMixin, Base):
    """Viagem de entrada ou saida (secao 6.3).

    ``km_vazio`` e campo obrigatorio e separado: viagem com retorno vazio
    precisa incluir todos os quilometros (caso de teste 6).
    """

    __tablename__ = "evento_frete"

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    lote_compra_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lote_compra.id")
    )
    lote_saida_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lote_saida.id"))
    pedido_venda_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pedido_venda.id")
    )

    tipo_frete: Mapped[TipoFrete] = coluna_enum(TipoFrete)
    transportador_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parceiro.id"))
    recurso_veiculo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurso.id"))

    origem: Mapped[str]
    destino: Mapped[str]
    km_carregado: Mapped[Quantidade] = mapped_column(default=0)
    km_vazio: Mapped[Quantidade] = mapped_column(default=0)
    horas_totais: Mapped[Quantidade] = mapped_column(default=0)
    horas_espera: Mapped[Quantidade] = mapped_column(default=0)
    carga_util_kg: Mapped[Quantidade]
    ocupacao: Mapped[PercentualOpc]

    pedagio: Mapped[Dinheiro] = mapped_column(default=0)
    estadia: Mapped[Dinheiro] = mapped_column(default=0)
    despesas_especificas: Mapped[Dinheiro] = mapped_column(default=0)
    valor_contratado_terceiro: Mapped[DinheiroOpc]
    custo_calculado: Mapped[DinheiroOpc]

    data_viagem: Mapped[date]
    observacao: Mapped[TextoOpc]


class MovimentoEstoque(IdMixin, TimestampMixin, CompetenciaCaixaMixin, Base):
    """Idade e giro do estoque por lote de saida (indicadores da secao 12.3)."""

    __tablename__ = "movimento_estoque"

    lote_saida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lote_saida.id"))
    tipo_movimento: Mapped[str]
    quantidade_kg: Mapped[Quantidade]
    custo_unitario: Mapped[Dinheiro]
    valor_realizavel_liquido_unitario: Mapped[DinheiroOpc]
    saldo_quantidade_kg: Mapped[Quantidade]
    saldo_valor: Mapped[Dinheiro]
    dias_em_estoque: Mapped[int | None]
