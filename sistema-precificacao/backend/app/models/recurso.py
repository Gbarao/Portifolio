"""Centros de custo, recursos, fichas de custo e taxas de atividade.

As fichas de custo (empregado, veiculo, maquina, imovel) guardam apenas os
componentes. Nenhum total derivado e persistido aqui: custo mensal integral,
custo por hora produtiva e custo por km sao calculados pela camada de dominio
a partir destes campos, para que a memoria de calculo possa reproduzir cada
etapa (secoes 6.2 a 6.5).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Dinheiro,
    DinheiroOpc,
    IdMixin,
    PercentualOpc,
    Quantidade,
    QuantidadeOpc,
    TextoOpc,
    TimestampMixin,
    VigenciaMixin,
)
from app.models._tipos import coluna_enum
from app.models.empresa import Unidade
from app.models.enums import (
    Direcionador,
    NaturezaCentroCusto,
    StatusDado,
    TipoEventoProcesso,
    TipoRecurso,
)


class CentroCusto(IdMixin, TimestampMixin, Base):
    __tablename__ = "centro_custo"
    __table_args__ = (UniqueConstraint("unidade_id", "codigo"),)

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    codigo: Mapped[str]
    nome: Mapped[str]
    natureza: Mapped[NaturezaCentroCusto] = coluna_enum(NaturezaCentroCusto)
    responsavel: Mapped[str | None]
    orcamento_mensal: Mapped[DinheiroOpc]
    regra_apropriacao: Mapped[TextoOpc]
    ativo: Mapped[bool] = mapped_column(default=True)

    unidade: Mapped[Unidade] = relationship()


class Recurso(IdMixin, TimestampMixin, Base):
    """Identidade comum de empregado, equipe, maquina, veiculo e area.

    A ficha de custo especifica de cada tipo fica em tabela propria; aqui
    ficam apenas identificacao, centro de custo e capacidade pratica.
    """

    __tablename__ = "recurso"
    __table_args__ = (UniqueConstraint("unidade_id", "codigo"),)

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_custo.id"))
    tipo: Mapped[TipoRecurso] = coluna_enum(TipoRecurso)
    codigo: Mapped[str]
    nome: Mapped[str]
    descricao: Mapped[TextoOpc]

    # Capacidade pratica = teorica menos paradas normais justificadas
    # (secao 6.4). E ela, nunca a teorica, que rateia custo fixo.
    capacidade_teorica_mes: Mapped[QuantidadeOpc]
    capacidade_pratica_mes: Mapped[QuantidadeOpc]
    unidade_capacidade: Mapped[str | None]

    ativo: Mapped[bool] = mapped_column(default=True)

    unidade: Mapped[Unidade] = relationship()
    centro_custo: Mapped[CentroCusto] = relationship()


class EmpregadoCusto(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Custo integral por componentes, sem multiplicador universal (secao 6.2).

    ``horas_produtivas_praticas_mes`` ja exclui ferias, feriados, treinamentos,
    pausas e ociosidade normal -- e o denominador do custo por hora produtiva.
    """

    __tablename__ = "empregado_custo"

    recurso_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recurso.id"))
    funcao: Mapped[str]
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_custo.id"))

    salario_base: Mapped[Dinheiro]
    adicionais: Mapped[Dinheiro] = mapped_column(default=0)
    horas_extras_media: Mapped[Dinheiro] = mapped_column(default=0)
    encargos_patronais: Mapped[Dinheiro] = mapped_column(default=0)
    fgts: Mapped[Dinheiro] = mapped_column(default=0)
    beneficios: Mapped[Dinheiro] = mapped_column(default=0)
    provisao_ferias_e_adicional: Mapped[Dinheiro] = mapped_column(default=0)
    provisao_decimo_terceiro: Mapped[Dinheiro] = mapped_column(default=0)
    provisao_rescisao: Mapped[Dinheiro] = mapped_column(default=0)
    epi_uniforme_exames: Mapped[Dinheiro] = mapped_column(default=0)
    treinamento: Mapped[Dinheiro] = mapped_column(default=0)
    outros_custos_posto: Mapped[Dinheiro] = mapped_column(default=0)

    horas_pagas_mes: Mapped[Quantidade]
    horas_produtivas_praticas_mes: Mapped[Quantidade]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    observacao: Mapped[TextoOpc]

    recurso: Mapped[Recurso] = relationship()


class VeiculoCusto(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Custo fixo mensal e variavel por km/hora do veiculo (secao 6.3)."""

    __tablename__ = "veiculo_custo"

    recurso_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recurso.id"))
    placa: Mapped[str | None]
    capacidade_util_kg: Mapped[Quantidade]

    depreciacao_ou_arrendamento_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    seguro_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    licenciamento_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    rastreamento_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    pessoal_fixo_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    estrutura_dedicada_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    custo_capital_mensal: Mapped[Dinheiro] = mapped_column(default=0)

    combustivel_por_km: Mapped[Dinheiro] = mapped_column(default=0)
    pneus_por_km: Mapped[Dinheiro] = mapped_column(default=0)
    manutencao_variavel_por_km: Mapped[Dinheiro] = mapped_column(default=0)
    lubrificantes_consumiveis_por_km: Mapped[Dinheiro] = mapped_column(default=0)
    custo_por_hora_operacao: Mapped[Dinheiro] = mapped_column(default=0)

    km_praticos_mes: Mapped[Quantidade]
    horas_praticas_mes: Mapped[Quantidade]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    observacao: Mapped[TextoOpc]

    recurso: Mapped[Recurso] = relationship()


class MaquinaCusto(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Composicao da hora-maquina (secao 6.4)."""

    __tablename__ = "maquina_custo"

    recurso_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recurso.id"))

    depreciacao_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    custo_capital_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    manutencao_preventiva_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    seguro_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    outros_fixos_mensal: Mapped[Dinheiro] = mapped_column(default=0)

    energia_kwh_por_hora: Mapped[Quantidade] = mapped_column(default=0)
    custo_energia_por_kwh: Mapped[Dinheiro] = mapped_column(default=0)
    agua_m3_por_hora: Mapped[Quantidade] = mapped_column(default=0)
    custo_agua_por_m3: Mapped[Dinheiro] = mapped_column(default=0)
    consumiveis_por_hora: Mapped[Dinheiro] = mapped_column(default=0)
    manutencao_variavel_por_hora: Mapped[Dinheiro] = mapped_column(default=0)

    horas_teoricas_mes: Mapped[Quantidade]
    horas_praticas_mes: Mapped[Quantidade]
    disponibilidade: Mapped[PercentualOpc]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    observacao: Mapped[TextoOpc]

    recurso: Mapped[Recurso] = relationship()


class ImovelCusto(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Custo de ocupacao apropriado por area e tempo (secao 6.5)."""

    __tablename__ = "imovel_custo"

    recurso_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recurso.id"))

    aluguel_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    depreciacao_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    iptu_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    condominio_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    vigilancia_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    seguro_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    limpeza_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    manutencao_predial_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    utilidades_mensal: Mapped[Dinheiro] = mapped_column(default=0)
    licencas_ambientais_mensal: Mapped[Dinheiro] = mapped_column(default=0)

    area_total_m2: Mapped[Quantidade]
    area_produtiva_m2: Mapped[Quantidade]
    area_armazenagem_m2: Mapped[QuantidadeOpc]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )

    recurso: Mapped[Recurso] = relationship()


class Atividade(IdMixin, TimestampMixin, Base):
    """Atividade do ABC com seu direcionador causal (secao 4.1)."""

    __tablename__ = "atividade"
    __table_args__ = (UniqueConstraint("unidade_id", "codigo"),)

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_custo.id"))
    codigo: Mapped[str]
    nome: Mapped[str]
    tipo_evento: Mapped[TipoEventoProcesso] = coluna_enum(TipoEventoProcesso)
    direcionador: Mapped[Direcionador] = coluna_enum(Direcionador)
    unidade_direcionador: Mapped[str]
    # Rateio por faturamento e excecao documentada, nunca padrao (secao 4.1).
    justificativa_direcionador: Mapped[TextoOpc]
    ativo: Mapped[bool] = mapped_column(default=True)

    unidade: Mapped[Unidade] = relationship()
    centro_custo: Mapped[CentroCusto] = relationship()
    taxas: Mapped[list["AtividadeTaxa"]] = relationship(back_populates="atividade")


class AtividadeTaxa(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Taxa da atividade calculada pela capacidade pratica (secao 7.3).

    A taxa e persistida porque congela a premissa usada nas cotacoes daquela
    vigencia. A diferenca entre capacidade pratica e utilizacao real vira
    custo de ociosidade do periodo -- jamais aumento da taxa.
    """

    __tablename__ = "atividade_taxa"

    atividade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atividade.id"))
    pool_custo_mensal: Mapped[Dinheiro]
    capacidade_pratica_direcionador: Mapped[Quantidade]
    utilizacao_prevista_direcionador: Mapped[QuantidadeOpc]
    taxa: Mapped[Dinheiro]
    percentual_fixo_do_pool: Mapped[PercentualOpc]

    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
    memoria_composicao: Mapped[TextoOpc]
    observacao: Mapped[TextoOpc]

    atividade: Mapped[Atividade] = relationship(back_populates="taxas")


class DespesaEstrutural(IdMixin, TimestampMixin, VigenciaMixin, Base):
    """Despesas administrativas e comerciais (secao 6.7).

    Ficam fora do custo contabil do estoque, mas entram no preco sustentavel.
    A separacao e explicita para impedir dupla contagem (regra 12 da secao 11).
    """

    __tablename__ = "despesa_estrutural"

    unidade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unidade.id"))
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centro_custo.id"))
    descricao: Mapped[str]
    valor_mensal: Mapped[Dinheiro]
    base_rateio: Mapped[str]
    integra_custo_contabil: Mapped[bool] = mapped_column(default=False)
    integra_preco_sustentavel: Mapped[bool] = mapped_column(default=True)
    percentual_rateio: Mapped[PercentualOpc]
    status_dado: Mapped[StatusDado] = coluna_enum(
        StatusDado, default=StatusDado.CONFIRMADO
    )
