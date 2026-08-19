"""Empresa, unidades, parametros vigentes e usuarios."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Dinheiro,
    IdMixin,
    Percentual,
    TextoOpc,
    TimestampMixin,
    VigenciaMixin,
)
from app.models._tipos import coluna_enum
from app.models.enums import (
    AnexoSimples,
    MetodoCustoConjunto,
    MetodoEstoque,
    PerfilUsuario,
    RegimeTributario,
)


class Empresa(IdMixin, TimestampMixin, Base):
    __tablename__ = "empresa"

    razao_social: Mapped[str]
    nome_fantasia: Mapped[str | None]
    cnpj: Mapped[str] = mapped_column(unique=True)
    ativo: Mapped[bool] = mapped_column(default=True)

    unidades: Mapped[list["Unidade"]] = relationship(back_populates="empresa")


class Unidade(IdMixin, TimestampMixin, Base):
    """Estabelecimento: matriz, filial ou galpao (secao 3)."""

    __tablename__ = "unidade"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresa.id"))
    codigo: Mapped[str]
    nome: Mapped[str]
    cnpj: Mapped[str | None]
    uf: Mapped[str] = mapped_column(nullable=False)
    municipio: Mapped[str]
    endereco: Mapped[str | None]
    area_total_m2: Mapped[Dinheiro | None]
    ativo: Mapped[bool] = mapped_column(default=True)

    empresa: Mapped[Empresa] = relationship(back_populates="unidades")
    parametros: Mapped[list["EmpresaParametro"]] = relationship(back_populates="unidade")


class EmpresaParametro(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Parametros gerais versionados por vigencia (secao 5.1).

    Nunca sao editados no lugar: uma alteracao de meta de margem ou de taxa
    de capital encerra a vigencia atual e abre uma nova, para que cotacoes
    antigas continuem reproduziveis.
    """

    __tablename__ = "empresa_parametro"

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))

    regime_tributario: Mapped[RegimeTributario] = coluna_enum(RegimeTributario)
    anexo_simples: Mapped[AnexoSimples | None] = coluna_enum(AnexoSimples, nullable=True)

    moeda: Mapped[str] = mapped_column(default="BRL")
    casas_decimais_apresentacao: Mapped[int] = mapped_column(default=4)
    metodo_arredondamento: Mapped[str] = mapped_column(default="ROUND_HALF_UP")

    metodo_estoque: Mapped[MetodoEstoque] = coluna_enum(
        MetodoEstoque, default=MetodoEstoque.CUSTO_MEDIO_PONDERADO
    )
    metodo_custo_conjunto: Mapped[MetodoCustoConjunto] = coluna_enum(
        MetodoCustoConjunto, default=MetodoCustoConjunto.VRL_RELATIVO
    )
    # Secao 7.4: reduzir custo conjunto pela receita de subproduto exige
    # politica formalmente aprovada -- por isso o padrao e falso.
    subproduto_reduz_custo_conjunto: Mapped[bool] = mapped_column(default=False)

    # Taxa minima de atratividade anual; o motor converte para taxa diaria
    # ao calcular o custo financeiro do lote (secao 6.8).
    taxa_minima_atratividade_anual: Mapped[Percentual]
    meta_margem_alvo: Mapped[Percentual]
    meta_margem_contribuicao_minima: Mapped[Percentual]

    # Secao 7.1: diferenca de massa acima desta tolerancia bloqueia o
    # encerramento do lote.
    tolerancia_balanco_massa: Mapped[Percentual]
    tolerancia_reconciliacao_mensal: Mapped[Percentual]

    horizonte_validade_cotacao_dias: Mapped[int] = mapped_column(default=7)
    dias_uteis_mes: Mapped[int] = mapped_column(default=21)

    observacao: Mapped[TextoOpc]

    unidade: Mapped[Unidade] = relationship(back_populates="parametros")


class Usuario(IdMixin, TimestampMixin, Base):
    """Perfis da secao 13.1, base para segregacao de funcoes e alcadas."""

    __tablename__ = "usuario"

    nome: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    perfil: Mapped[PerfilUsuario] = coluna_enum(PerfilUsuario)
    unidade_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unidade.id"))
    # Alcada em valor de concessao que o usuario pode aprovar (secao 13.2).
    alcada_valor: Mapped[Dinheiro | None]
    pode_ver_dados_salariais: Mapped[bool] = mapped_column(default=False)
    ativo: Mapped[bool] = mapped_column(default=True)
    ultimo_acesso: Mapped[date | None]
