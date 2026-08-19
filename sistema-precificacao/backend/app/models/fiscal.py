"""Matriz tributaria parametrizavel (secao 9).

Principio: o modulo tributario e uma matriz de regras, nunca um percentual
unico. Cada regra declara em quais operacoes se aplica, como calcula, se o
resultado e recuperavel e ate quando vale. Nenhuma aliquota do setor esta
escrita em codigo -- todas entram por cadastro e sao validadas pelo
responsavel fiscal antes de sair do status PROVISORIA.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import (
    Base,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    Percentual,
    PercentualOpc,
    Texto,
    TextoOpc,
    TimestampMixin,
    VigenciaMixin,
)
from app.models._tipos import coluna_enum
from app.models.enums import (
    AnexoSimples,
    FormaCalculoBase,
    NaturezaParceiro,
    Recuperabilidade,
    RegimeTributario,
    StatusRegraFiscal,
    TipoOperacaoFiscal,
    TratamentoTributario,
    Tributo,
)


class RegraTributaria(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Regra unitaria da matriz tributaria (secao 9.2).

    Campos-chave nulos funcionam como coringa: ``uf_destino`` nulo significa
    "qualquer UF". A resolucao escolhe sempre a regra mais especifica vigente
    na data da operacao -- nunca na data de hoje.

    Tres flags governam o efeito economico e nao devem ser confundidas:

    * ``compoe_deducao_venda`` -- entra na variavel ``r`` da formula de preco.
    * ``gera_credito_compra`` -- reduz o custo ``C``, e apenas quando a
      recuperabilidade for ELEGIVEL e a condicao estiver confirmada.
    * ``compoe_custo_nao_recuperavel`` -- soma ao custo de aquisicao.
    """

    __tablename__ = "regra_tributaria"
    __table_args__ = (
        Index("ix_regra_tributaria_resolucao", "tributo", "tipo_operacao", "regime_tributario"),
    )

    codigo: Mapped[str]
    descricao: Mapped[str]

    # --- Chaves de aplicacao (secao 9.2) ---
    empresa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("empresa.id"))
    unidade_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unidade.id"))
    regime_tributario: Mapped[RegimeTributario | None] = coluna_enum(
        RegimeTributario, nullable=True
    )
    tipo_operacao: Mapped[TipoOperacaoFiscal] = coluna_enum(TipoOperacaoFiscal)
    tributo: Mapped[Tributo] = coluna_enum(Tributo)

    material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("material.id"))
    familia_material: Mapped[str | None]
    ncm: Mapped[str | None]
    cfop: Mapped[str | None]
    cst_csosn: Mapped[str | None]
    modelo_documento: Mapped[str | None]

    uf_origem: Mapped[str | None]
    uf_destino: Mapped[str | None]
    municipio: Mapped[str | None]

    natureza_parceiro: Mapped[NaturezaParceiro | None] = coluna_enum(
        NaturezaParceiro, nullable=True
    )
    regime_parceiro: Mapped[RegimeTributario | None] = coluna_enum(
        RegimeTributario, nullable=True
    )
    parceiro_contribuinte: Mapped[bool | None]

    # --- Calculo (secao 9.2 e 7.6) ---
    forma_calculo_base: Mapped[FormaCalculoBase] = coluna_enum(
        FormaCalculoBase, default=FormaCalculoBase.POR_FORA
    )
    aliquota: Mapped[PercentualOpc]
    percentual_reducao_base: Mapped[PercentualOpc]
    # Presuncao de IRPJ/CSLL no Lucro Presumido: base = receita x presuncao,
    # depois aliquota sobre essa base (secao 7.7-B).
    percentual_presuncao_base: Mapped[PercentualOpc]
    valor_fixo: Mapped[DinheiroOpc]
    valor_pauta_unitario: Mapped[DinheiroOpc]

    tratamento: Mapped[TratamentoTributario] = coluna_enum(TratamentoTributario)
    recuperabilidade: Mapped[Recuperabilidade] = coluna_enum(
        Recuperabilidade, default=Recuperabilidade.NAO_APLICAVEL
    )
    percentual_recuperavel: Mapped[PercentualOpc]
    prazo_realizacao_credito_dias: Mapped[int | None]

    # --- Efeito economico ---
    compoe_deducao_venda: Mapped[bool] = mapped_column(default=False)
    gera_credito_compra: Mapped[bool] = mapped_column(default=False)
    compoe_custo_nao_recuperavel: Mapped[bool] = mapped_column(default=False)
    # IRPJ/CSLL no Lucro Real incidem sobre o lucro apurado, nao sobre a
    # receita: ficam fora de `r` e a margem-alvo e tratada como pre-tributo.
    incide_sobre_lucro: Mapped[bool] = mapped_column(default=False)

    # --- Condicao verificavel ---
    # Ex.: Lei 15.394/2026 exige que o adquirente esteja no lucro real e use
    # o residuo como materia-prima. Enquanto a condicao nao for confirmada, o
    # credito nao reduz o custo -- apenas gera alerta.
    condicao_descricao: Mapped[TextoOpc]
    requer_confirmacao_condicao: Mapped[bool] = mapped_column(default=False)

    # --- Governanca (secao 9.2) ---
    fundamento_legal: Mapped[Texto]
    status: Mapped[StatusRegraFiscal] = coluna_enum(
        StatusRegraFiscal, default=StatusRegraFiscal.PROVISORIA
    )
    validado_por: Mapped[str | None]
    validado_em: Mapped[date | None]
    observacao: Mapped[TextoOpc]


class FaixaSimplesNacional(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Faixas do Simples Nacional por anexo (secao 9.4).

    A aliquota efetiva nao e a nominal:
    ``efetiva = (RBT12 x nominal - parcela_deduzir) / RBT12``.

    A reparticao por tributo permite segregar a parcela de ICMS de dentro do
    DAS quando a operacao com sucata gozar de isencao ou diferimento estadual,
    evitando pagamento indevido no recolhimento unificado.
    """

    __tablename__ = "faixa_simples_nacional"
    __table_args__ = (
        UniqueConstraint("anexo", "ordem_faixa", "vigencia_inicio"),
    )

    anexo: Mapped[AnexoSimples] = coluna_enum(AnexoSimples)
    ordem_faixa: Mapped[int]
    rbt12_inicio: Mapped[Dinheiro]
    rbt12_fim: Mapped[Dinheiro]
    aliquota_nominal: Mapped[Percentual]
    parcela_deduzir: Mapped[Dinheiro]

    percentual_irpj: Mapped[Percentual] = mapped_column(default=0)
    percentual_csll: Mapped[Percentual] = mapped_column(default=0)
    percentual_cofins: Mapped[Percentual] = mapped_column(default=0)
    percentual_pis: Mapped[Percentual] = mapped_column(default=0)
    percentual_cpp: Mapped[Percentual] = mapped_column(default=0)
    percentual_icms: Mapped[Percentual] = mapped_column(default=0)
    percentual_ipi: Mapped[Percentual] = mapped_column(default=0)
    percentual_iss: Mapped[Percentual] = mapped_column(default=0)

    status: Mapped[StatusRegraFiscal] = coluna_enum(
        StatusRegraFiscal, default=StatusRegraFiscal.PROVISORIA
    )
    fundamento_legal: Mapped[TextoOpc]


class ApuracaoRbt12(IdMixin, TimestampMixin, Base):
    """Receita bruta acumulada de 12 meses, por unidade e competencia.

    Base do alerta critico da secao 7.7-C: uma venda volumosa pode empurrar a
    RBT12 para a faixa seguinte e elevar a aliquota efetiva de todo o
    faturamento do mes, nao apenas daquela venda.
    """

    __tablename__ = "apuracao_rbt12"
    __table_args__ = (UniqueConstraint("unidade_id", "competencia"),)

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    competencia: Mapped[date]
    receita_bruta_mes: Mapped[Dinheiro]
    rbt12: Mapped[Dinheiro]
    anexo: Mapped[AnexoSimples] = coluna_enum(AnexoSimples)
    faixa_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faixa_simples_nacional.id")
    )
    aliquota_efetiva: Mapped[PercentualOpc]
    valor_das: Mapped[DinheiroOpc]
    icms_segregado: Mapped[Dinheiro] = mapped_column(default=0)
    observacao: Mapped[TextoOpc]


class ApuracaoTributaria(IdMixin, TimestampMixin, Base):
    """Saida obrigatoria do motor fiscal (secao 9.6), gravada por operacao.

    Cada linha responde: base, aliquota nominal e efetiva, valor destacado,
    valor devido, credito relacionado, valor recuperavel, efeito no resultado,
    efeito e data no caixa, fundamento, vigencia e status da regra.
    """

    __tablename__ = "apuracao_tributaria"

    escopo: Mapped[str]  # LOTE_COMPRA | COTACAO_VERSAO | PEDIDO_VENDA | FRETE
    referencia_id: Mapped[uuid.UUID]
    regra_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regra_tributaria.id"))
    tributo: Mapped[Tributo] = coluna_enum(Tributo)
    tipo_operacao: Mapped[TipoOperacaoFiscal] = coluna_enum(TipoOperacaoFiscal)

    base_calculo: Mapped[Dinheiro]
    aliquota_nominal: Mapped[Percentual]
    aliquota_efetiva: Mapped[Percentual]
    valor_destacado: Mapped[Dinheiro] = mapped_column(default=0)
    valor_devido: Mapped[Dinheiro] = mapped_column(default=0)
    credito_entrada_relacionado: Mapped[Dinheiro] = mapped_column(default=0)
    valor_recuperavel: Mapped[Dinheiro] = mapped_column(default=0)
    efeito_liquido_resultado: Mapped[Dinheiro] = mapped_column(default=0)
    efeito_caixa: Mapped[Dinheiro] = mapped_column(default=0)
    data_provavel_caixa: Mapped[date | None]

    tratamento: Mapped[TratamentoTributario] = coluna_enum(TratamentoTributario)
    recuperabilidade: Mapped[Recuperabilidade] = coluna_enum(Recuperabilidade)
    fundamento_legal: Mapped[TextoOpc]
    vigencia_regra_inicio: Mapped[date | None]
    vigencia_regra_fim: Mapped[date | None]
    versao_regra: Mapped[int | None]
    status: Mapped[StatusRegraFiscal] = coluna_enum(StatusRegraFiscal)
    alerta: Mapped[TextoOpc]
