"""Cadastro de materiais, parceiros e tabelas contratuais (secao 5)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    Percentual,
    PercentualOpc,
    QuantidadeOpc,
    TextoOpc,
    TimestampMixin,
    VigenciaMixin,
)
from app.models._tipos import coluna_enum
from app.models.enums import (
    MetodoCustoConjunto,
    NaturezaParceiro,
    PapelParceiro,
    RegimeTributario,
    StatusDado,
    TipoFrete,
    TipoMaterial,
    UnidadeMedida,
)


class Material(IdMixin, TimestampMixin, Base):
    """Material de entrada e produto de saida no mesmo cadastro.

    Um mesmo item pode ser as duas coisas (papelao comprado solto e vendido
    enfardado), por isso o discriminador e ``tipo`` e nao tabelas separadas.
    """

    __tablename__ = "material"

    codigo: Mapped[str] = mapped_column(unique=True)
    descricao: Mapped[str]
    familia: Mapped[str]
    tipo: Mapped[TipoMaterial] = coluna_enum(TipoMaterial)

    # NCM fica opcional no cadastro mas e obrigatorio para fechar cotacao
    # definitiva (secao 9.3): a validacao e do motor fiscal, nao do schema.
    ncm: Mapped[str | None]
    unidade_padrao: Mapped[UnidadeMedida] = coluna_enum(
        UnidadeMedida, default=UnidadeMedida.KG
    )
    densidade_kg_m3: Mapped[QuantidadeOpc]

    umidade_referencia: Mapped[PercentualOpc]
    umidade_maxima_aceita: Mapped[PercentualOpc]
    contaminacao_maxima_aceita: Mapped[PercentualOpc]
    especificacao_qualidade: Mapped[TextoOpc]

    rendimento_padrao: Mapped[PercentualOpc]
    perda_normal_padrao: Mapped[PercentualOpc]
    processo_necessario: Mapped[TextoOpc]
    forma_armazenagem: Mapped[str | None]
    vida_util_comercial_dias: Mapped[int | None]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    ativo: Mapped[bool] = mapped_column(default=True)

    saidas_esperadas: Mapped[list["MaterialSaidaEsperada"]] = relationship(
        back_populates="material_entrada",
        foreign_keys="MaterialSaidaEsperada.material_entrada_id",
    )


class MaterialSaidaEsperada(IdMixin, TimestampMixin, Base):
    """Mix esperado de produtos de saida por material de entrada.

    Sustenta o custo-padrao e o rateio de custo conjunto quando um lote de
    triagem gera varios produtos (secao 7.4).
    """

    __tablename__ = "material_saida_esperada"
    __table_args__ = (UniqueConstraint("material_entrada_id", "material_saida_id"),)

    material_entrada_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))
    material_saida_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))
    rendimento_padrao: Mapped[Percentual]
    metodo_custo_conjunto: Mapped[MetodoCustoConjunto] = coluna_enum(
        MetodoCustoConjunto, default=MetodoCustoConjunto.VRL_RELATIVO
    )
    gastos_posteriores_estimados_kg: Mapped[DinheiroOpc]
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.ESTIMADO
    )

    material_entrada: Mapped[Material] = relationship(
        back_populates="saidas_esperadas", foreign_keys=[material_entrada_id]
    )
    material_saida: Mapped[Material] = relationship(foreign_keys=[material_saida_id])


class Parceiro(IdMixin, TimestampMixin, Base):
    """Fornecedor, cliente ou transportador (secao 5.3).

    O regime tributario e a condicao de contribuinte do parceiro entram como
    chave da regra fiscal -- nao sao dado meramente cadastral.
    """

    __tablename__ = "parceiro"

    codigo: Mapped[str] = mapped_column(unique=True)
    nome: Mapped[str]
    papel: Mapped[PapelParceiro] = coluna_enum(PapelParceiro)
    natureza: Mapped[NaturezaParceiro] = coluna_enum(NaturezaParceiro)

    cnpj_cpf: Mapped[str | None]
    inscricao_estadual: Mapped[str | None]
    contribuinte_icms: Mapped[bool] = mapped_column(default=False)
    regime_tributario: Mapped[RegimeTributario | None] = coluna_enum(
        RegimeTributario, nullable=True
    )
    uf: Mapped[str]
    municipio: Mapped[str]
    endereco_logistico: Mapped[TextoOpc]

    prazo_pagamento_dias: Mapped[int | None]
    prazo_recebimento_dias: Mapped[int | None]
    limite_credito: Mapped[DinheiroOpc]

    # Historico serve as provisoes de risco da secao 6.8. Percentual generico
    # de "imprevistos" nao entra aqui: so indicador com base historica.
    inadimplencia_historica: Mapped[PercentualOpc]
    indice_qualidade: Mapped[PercentualOpc]
    indice_pontualidade: Mapped[PercentualOpc]
    concentracao_receita: Mapped[PercentualOpc]

    restricoes_acesso: Mapped[TextoOpc]
    observacao: Mapped[TextoOpc]
    ativo: Mapped[bool] = mapped_column(default=True)


class ContratoTabela(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Tabela comercial vigente por parceiro e material (secao 10)."""

    __tablename__ = "contrato_tabela"

    parceiro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parceiro.id"))
    material_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material.id"))

    preco_unitario: Mapped[Dinheiro]
    unidade_comercial: Mapped[UnidadeMedida] = coluna_enum(UnidadeMedida)
    indexador: Mapped[str | None]
    faixa_qualidade: Mapped[TextoOpc]
    tolerancia_peso: Mapped[PercentualOpc]
    prazo_pagamento_dias: Mapped[int | None]
    tipo_frete: Mapped[TipoFrete] = coluna_enum(TipoFrete)
    quantidade_minima_kg: Mapped[QuantidadeOpc]
    quantidade_maxima_kg: Mapped[QuantidadeOpc]
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    observacao: Mapped[TextoOpc]

    parceiro: Mapped[Parceiro] = relationship()
    material: Mapped[Material] = relationship()
