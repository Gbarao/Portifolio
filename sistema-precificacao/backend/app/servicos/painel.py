"""Indicadores do painel gerencial (secao 12.3).

Agrega o que o banco realmente tem. Indicador que dependa de dado ausente nao
e estimado nem preenchido com zero disfarcado: vem com ``disponivel=False`` e
uma explicacao do que falta. A especificacao proibe inventar numero (secao 15),
e um painel que mente e pior que um painel incompleto.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.abc import TaxaAtividade, calcular_ociosidade
from app.dominio.excecoes import ErroDominio
from app.dominio.unidades import ZERO, dec, dividir
from app.models import Atividade, EventoProcesso, LoteCompra, LoteSaida, Material
from app.servicos.lote import calcular_resultado_lote
from app.servicos.parametros import taxas_vigentes


@dataclass
class IndicadorMaterial:
    """Margem de contribuicao por material de saida."""

    material_codigo: str
    material_descricao: str
    quantidade_kg: Decimal
    custo_variavel_por_kg: Decimal
    preco_estimado_por_kg: Decimal
    margem_contribuicao_por_kg: Decimal
    margem_percentual: Decimal


@dataclass
class IndicadorOciosidade:
    atividade_codigo: str
    atividade_nome: str
    capacidade_pratica: Decimal
    utilizacao_real: Decimal
    percentual_ocupacao: Decimal
    custo_ociosidade: Decimal
    unidade_direcionador: str


@dataclass
class IndicadorIndisponivel:
    """Indicador que a base ainda nao sustenta."""

    nome: str
    motivo: str


@dataclass
class PainelGerencial:
    periodo_inicio: date | None
    periodo_fim: date | None

    lotes_apurados: int
    lotes_com_erro: int

    quantidade_aceita_kg: Decimal = ZERO
    quantidade_vendavel_kg: Decimal = ZERO
    rejeito_kg: Decimal = ZERO
    perda_normal_kg: Decimal = ZERO
    perda_anormal_kg: Decimal = ZERO
    rendimento_medio: Decimal = ZERO

    custo_aquisicao_total: Decimal = ZERO
    custo_transformacao_total: Decimal = ZERO
    custo_capital_total: Decimal = ZERO
    custo_total: Decimal = ZERO
    custo_por_tonelada_vendavel: Decimal = ZERO
    preco_medio_compra_kg: Decimal = ZERO

    custo_ociosidade_total: Decimal = ZERO
    ociosidade_por_atividade: list[IndicadorOciosidade] = field(default_factory=list)

    creditos_confirmados: Decimal = ZERO
    creditos_condicionados: Decimal = ZERO

    dias_ciclo_financeiro: Decimal = ZERO
    capital_empregado: Decimal = ZERO

    margem_por_material: list[IndicadorMaterial] = field(default_factory=list)
    indisponiveis: list[IndicadorIndisponivel] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)


def montar_painel(
    sessao: Session,
    *,
    unidade_id: uuid.UUID | None = None,
    inicio: date | None = None,
    fim: date | None = None,
) -> PainelGerencial:
    consulta = select(LoteCompra)
    if unidade_id is not None:
        consulta = consulta.where(LoteCompra.unidade_id == unidade_id)
    if inicio is not None:
        consulta = consulta.where(LoteCompra.data_entrada >= inicio)
    if fim is not None:
        consulta = consulta.where(LoteCompra.data_entrada <= fim)

    lotes = list(sessao.scalars(consulta.order_by(LoteCompra.data_entrada)).all())
    painel = PainelGerencial(
        periodo_inicio=inicio, periodo_fim=fim, lotes_apurados=0, lotes_com_erro=0
    )

    if not lotes:
        painel.alertas.append(
            "Nenhum lote no período selecionado: os indicadores ficam zerados."
        )
        return painel

    _agregar_lotes(sessao, lotes, painel)
    _agregar_ociosidade(sessao, lotes, painel)
    _agregar_margem_por_material(sessao, lotes, painel)
    _registrar_indisponiveis(painel)

    return painel


def _agregar_lotes(
    sessao: Session, lotes: list[LoteCompra], painel: PainelGerencial
) -> None:
    """Percorre os lotes reaproveitando o mesmo motor da tela de lote.

    Um lote que nao apura -- sem balanca, sem taxa vigente -- e contado em
    ``lotes_com_erro`` e fica de fora das somas, em vez de derrubar o painel.
    """

    dias_ponderados = ZERO
    valor_negociado = ZERO

    for lote in lotes:
        try:
            resultado = calcular_resultado_lote(
                sessao, lote, bloquear_fora_da_tolerancia=False
            )
        except ErroDominio as erro:
            painel.lotes_com_erro += 1
            painel.alertas.append(f"Lote {lote.codigo} não apurado: {erro}")
            continue

        painel.lotes_apurados += 1
        balanco = resultado.balanco

        painel.quantidade_aceita_kg += balanco.quantidade_aceita
        painel.quantidade_vendavel_kg += balanco.quantidade_vendavel
        painel.rejeito_kg += balanco.quantidade_rejeito
        painel.perda_normal_kg += balanco.perda_normal
        painel.perda_anormal_kg += balanco.perda_anormal

        painel.custo_aquisicao_total += resultado.aquisicao.custo_total
        painel.custo_transformacao_total += resultado.custo_transformacao
        painel.custo_capital_total += resultado.capital.custo_financeiro
        painel.custo_total += resultado.custo_total

        painel.creditos_confirmados += dec(lote.creditos_fiscais_confirmados)
        painel.creditos_condicionados += resultado.aquisicao.creditos_pendentes

        painel.capital_empregado += resultado.aquisicao.custo_total
        dias_ponderados += (
            Decimal(resultado.capital.dias_comprometidos)
            * resultado.aquisicao.custo_total
        )
        valor_negociado += dec(lote.preco_unitario_bruto) * dec(
            lote.quantidade_negociada_kg
        )

    if painel.quantidade_aceita_kg > ZERO:
        painel.rendimento_medio = dividir(
            painel.quantidade_vendavel_kg,
            painel.quantidade_aceita_kg,
            "rendimento médio do período",
        )
        painel.preco_medio_compra_kg = dividir(
            valor_negociado, painel.quantidade_aceita_kg, "preço médio de compra"
        )

    if painel.quantidade_vendavel_kg > ZERO:
        painel.custo_por_tonelada_vendavel = dividir(
            painel.custo_total * Decimal("1000"),
            painel.quantidade_vendavel_kg,
            "custo por tonelada vendável",
        )

    if painel.capital_empregado > ZERO:
        painel.dias_ciclo_financeiro = dividir(
            dias_ponderados, painel.capital_empregado, "ciclo financeiro médio"
        )


def _agregar_ociosidade(
    sessao: Session, lotes: list[LoteCompra], painel: PainelGerencial
) -> None:
    """Capacidade paga e nao utilizada, por atividade.

    O custo fica no periodo, jamais rateado nos lotes -- e o que impede a
    espiral de preco quando o volume cai (secao 7.3).
    """

    ids_lote = [lote.id for lote in lotes]
    data_ref = max(lote.data_entrada for lote in lotes)

    eventos = list(
        sessao.scalars(
            select(EventoProcesso).where(EventoProcesso.lote_id.in_(ids_lote))
        ).all()
    )
    if not eventos:
        return

    utilizacao: dict[uuid.UUID, Decimal] = {}
    for evento in eventos:
        utilizacao[evento.atividade_id] = utilizacao.get(
            evento.atividade_id, ZERO
        ) + dec(evento.quantidade_direcionador)

    taxas = taxas_vigentes(sessao, data_ref)
    atividades = {
        a.id: a
        for a in sessao.scalars(
            select(Atividade).where(Atividade.id.in_(utilizacao.keys()))
        ).all()
    }

    for atividade_id, usado in utilizacao.items():
        atividade = atividades.get(atividade_id)
        taxa = taxas.get(atividade_id)
        if atividade is None or taxa is None:
            continue

        ociosidade = calcular_ociosidade(
            TaxaAtividade(
                codigo=atividade.codigo,
                nome=atividade.nome,
                direcionador=str(
                    getattr(atividade.direcionador, "value", atividade.direcionador)
                ),
                pool_custo=dec(taxa.pool_custo_mensal),
                capacidade_pratica=dec(taxa.capacidade_pratica_direcionador),
                percentual_fixo=(
                    dec(taxa.percentual_fixo_do_pool)
                    if taxa.percentual_fixo_do_pool is not None
                    else None
                ),
            ),
            utilizacao_real=usado,
        )

        painel.custo_ociosidade_total += ociosidade.custo_ociosidade
        painel.ociosidade_por_atividade.append(
            IndicadorOciosidade(
                atividade_codigo=atividade.codigo,
                atividade_nome=atividade.nome,
                capacidade_pratica=ociosidade.capacidade_pratica,
                utilizacao_real=ociosidade.utilizacao_real,
                percentual_ocupacao=ociosidade.percentual_ocupacao,
                custo_ociosidade=ociosidade.custo_ociosidade,
                unidade_direcionador=atividade.unidade_direcionador,
            )
        )

    painel.ociosidade_por_atividade.sort(key=lambda i: i.percentual_ocupacao)


def _agregar_margem_por_material(
    sessao: Session, lotes: list[LoteCompra], painel: PainelGerencial
) -> None:
    """Margem de contribuicao por material de saida.

    Usa o preco estimado de venda gravado no lote de saida. Enquanto nao houver
    venda faturada, esta e uma margem **esperada**, e a interface diz isso.
    """

    ids_lote = [lote.id for lote in lotes]
    saidas = list(
        sessao.scalars(
            select(LoteSaida).where(LoteSaida.lote_origem_id.in_(ids_lote))
        ).all()
    )
    if not saidas:
        return

    materiais = {
        m.id: m
        for m in sessao.scalars(
            select(Material).where(Material.id.in_({s.material_id for s in saidas}))
        ).all()
    }

    # Custo variavel do periodo por kg vendavel: aquisicao + transformacao.
    # Estrutura e capital ficam fora da margem de contribuicao (secao 2).
    custo_variavel_total = painel.custo_aquisicao_total + painel.custo_transformacao_total
    custo_por_kg = (
        dividir(custo_variavel_total, painel.quantidade_vendavel_kg, "custo variável/kg")
        if painel.quantidade_vendavel_kg > ZERO
        else ZERO
    )

    acumulado: dict[uuid.UUID, dict[str, Decimal]] = {}
    for saida in saidas:
        if saida.preco_estimado_venda_kg is None:
            continue
        registro = acumulado.setdefault(
            saida.material_id, {"quantidade": ZERO, "receita": ZERO}
        )
        registro["quantidade"] += dec(saida.quantidade_kg)
        registro["receita"] += dec(saida.quantidade_kg) * dec(
            saida.preco_estimado_venda_kg
        )

    for material_id, registro in acumulado.items():
        material = materiais.get(material_id)
        if material is None or registro["quantidade"] <= ZERO:
            continue
        preco_medio = dividir(
            registro["receita"], registro["quantidade"], "preço médio estimado"
        )
        margem = preco_medio - custo_por_kg
        painel.margem_por_material.append(
            IndicadorMaterial(
                material_codigo=material.codigo,
                material_descricao=material.descricao,
                quantidade_kg=registro["quantidade"],
                custo_variavel_por_kg=custo_por_kg,
                preco_estimado_por_kg=preco_medio,
                margem_contribuicao_por_kg=margem,
                margem_percentual=(
                    dividir(margem, preco_medio, "margem percentual")
                    if preco_medio > ZERO
                    else ZERO
                ),
            )
        )

    painel.margem_por_material.sort(
        key=lambda i: i.margem_contribuicao_por_kg, reverse=True
    )


def _registrar_indisponiveis(painel: PainelGerencial) -> None:
    """Declara o que o painel ainda nao pode mostrar, e por que."""

    painel.indisponiveis.append(
        IndicadorIndisponivel(
            nome="Ponte de margem cotada × realizada",
            motivo=(
                "Exige vendas faturadas e recebidas para comparar com a cotação. "
                "Sem pedidos de venda liquidados, qualquer decomposição seria "
                "inventada."
            ),
        )
    )
    painel.indisponiveis.append(
        IndicadorIndisponivel(
            nome="Inadimplência e concentração realizadas",
            motivo=(
                "Dependem do histórico de recebimento por cliente, ainda não "
                "registrado em pedido_venda."
            ),
        )
    )
    if painel.perda_anormal_kg > ZERO:
        painel.alertas.append(
            f"Perda anormal de {painel.perda_anormal_kg} kg no período: é desvio "
            f"do resultado, não custo-padrão."
        )
