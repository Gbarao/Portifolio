"""Calculo do resultado economico de um lote a partir dos eventos gravados.

Reconstroi o custo do lote como a especificacao manda: balanco de massa pelos
eventos de balanca e qualidade, aquisicao pelos campos do lote, transformacao
pelos direcionadores apontados e capital pelo ciclo financeiro.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.abc import ConsumoAtividade, TaxaAtividade, calcular_custo_transformacao
from app.dominio.aquisicao import (
    CustoAquisicao,
    EntradasAquisicao,
    calcular_custo_aquisicao,
)
from app.dominio.capital import CicloFinanceiro, CustoCapital, calcular_custo_capital
from app.dominio.excecoes import DadoObrigatorioAusenteError
from app.dominio.massa import BalancoMassa, calcular_balanco
from app.dominio.memoria import Memoria
from app.dominio.unidades import ZERO, dec, dividir
from app.models import Atividade, EventoProcesso, LoteCompra
from app.models.enums import TipoPerda
from app.servicos.parametros import parametro_vigente, taxas_vigentes

# Perdas que integram o rendimento esperado, separadas das anormais (secao 6.6).
TIPOS_PERDA_NORMAL = {
    TipoPerda.PERDA_NORMAL,
    TipoPerda.UMIDADE,
    TipoPerda.DIFERENCA_BALANCA,
}
TIPOS_PERDA_ANORMAL = {
    TipoPerda.PERDA_ANORMAL,
    TipoPerda.FURTO_AVARIA,
    TipoPerda.DETERIORACAO,
}


@dataclass
class ResultadoLote:
    lote: LoteCompra
    balanco: BalancoMassa
    aquisicao: CustoAquisicao
    custo_transformacao: Decimal
    capital: CustoCapital
    custo_total: Decimal
    custo_unitario_vendavel: Decimal
    memoria: Memoria
    alertas: list[str]


def calcular_resultado_lote(
    sessao: Session,
    lote: LoteCompra,
    *,
    data_referencia: date | None = None,
    bloquear_fora_da_tolerancia: bool = True,
) -> ResultadoLote:
    data_ref = data_referencia or lote.data_entrada
    memoria = Memoria(titulo=f"Resultado do lote {lote.codigo}")

    parametro = parametro_vigente(sessao, lote.unidade_id, data_ref)
    if parametro is None:
        raise DadoObrigatorioAusenteError(
            f"Nenhum parâmetro vigente para a unidade em {data_ref.isoformat()}: "
            f"cadastre empresa_parametro antes de apurar o lote."
        )

    if not lote.eventos_balanca:
        raise DadoObrigatorioAusenteError(
            f"Lote {lote.codigo} sem evento de balança: peso bruto e tara são "
            f"obrigatórios para fechar o balanço de massa."
        )

    peso_bruto = sum((dec(e.peso_bruto_kg) for e in lote.eventos_balanca), ZERO)
    tara = sum((dec(e.tara_kg) for e in lote.eventos_balanca), ZERO)
    recusada = sum(
        (dec(e.quantidade_recusada_kg) for e in lote.eventos_qualidade), ZERO
    )
    vendavel = sum(
        (dec(s.quantidade_kg) for s in lote.saidas if not s.e_subproduto), ZERO
    )
    rejeito = sum(
        (dec(p.quantidade_kg) for p in lote.perdas if p.tipo == TipoPerda.REJEITO), ZERO
    )
    perda_normal = sum(
        (dec(p.quantidade_kg) for p in lote.perdas if p.tipo in TIPOS_PERDA_NORMAL), ZERO
    )
    perda_anormal = sum(
        (dec(p.quantidade_kg) for p in lote.perdas if p.tipo in TIPOS_PERDA_ANORMAL), ZERO
    )

    balanco = calcular_balanco(
        peso_bruto=peso_bruto,
        tara=tara,
        quantidade_recusada=recusada,
        quantidade_vendavel=vendavel,
        quantidade_rejeito=rejeito,
        perda_normal=perda_normal,
        perda_anormal=perda_anormal,
        tolerancia=dec(parametro.tolerancia_balanco_massa),
        memoria=memoria,
        bloquear_fora_da_tolerancia=bloquear_fora_da_tolerancia,
    )

    descontos_qualidade = sum(
        (dec(e.desconto_aplicado) for e in lote.eventos_qualidade), ZERO
    )
    aquisicao = calcular_custo_aquisicao(
        EntradasAquisicao(
            preco_bruto=dec(lote.preco_unitario_bruto) * dec(lote.quantidade_negociada_kg),
            descontos=dec(lote.desconto_comercial) + descontos_qualidade,
            bonificacoes=dec(lote.bonificacao),
            tributos_nao_recuperaveis=dec(lote.tributos_nao_recuperaveis),
            frete_entrada=dec(lote.frete_entrada),
            seguro_entrada=dec(lote.seguro_entrada),
            pedagio=dec(lote.pedagio_entrada),
            coleta_carga_descarga=dec(lote.coleta_carga_descarga),
            pesagem_inspecao=dec(lote.pesagem_inspecao),
            embalagem_nao_retornavel=dec(lote.embalagem_nao_retornavel),
            comissao_compra=dec(lote.comissao_compra),
            destinacao_rejeito=dec(lote.destinacao_rejeito_estimada),
            outros_custos=dec(lote.outros_custos_aquisicao),
            creditos_confirmados=dec(lote.creditos_fiscais_confirmados),
            creditos_condicionados=dec(lote.creditos_fiscais_condicionados),
        ),
        quantidade_aceita=balanco.quantidade_aceita,
        quantidade_vendavel=balanco.quantidade_vendavel,
        memoria=memoria,
    )

    custo_transformacao = _custo_transformacao_do_lote(sessao, lote, data_ref, memoria)

    capital = calcular_custo_capital(
        capital_comprometido=aquisicao.custo_total,
        ciclo=CicloFinanceiro(
            dias_estoque=parametro.dias_uteis_mes,
            dias_recebimento=0,
            dias_pagamento=lote.prazo_pagamento_dias,
        ),
        taxa_anual=dec(parametro.taxa_minima_atratividade_anual),
        memoria=memoria,
    )

    total = aquisicao.custo_total + custo_transformacao + capital.custo_financeiro
    unitario = dividir(total, balanco.quantidade_vendavel, "custo unitario do lote")

    memoria.registrar(
        "Custo total do lote",
        "C_total = aquisição + transformação + custo de capital",
        {
            "aquisicao": aquisicao.custo_total,
            "transformacao": custo_transformacao,
            "capital": capital.custo_financeiro,
        },
        total,
        "BRL",
    )

    return ResultadoLote(
        lote=lote,
        balanco=balanco,
        aquisicao=aquisicao,
        custo_transformacao=custo_transformacao,
        capital=capital,
        custo_total=total,
        custo_unitario_vendavel=unitario,
        memoria=memoria,
        alertas=list(dict.fromkeys(list(aquisicao.alertas) + memoria.alertas)),
    )


def _custo_transformacao_do_lote(
    sessao: Session, lote: LoteCompra, data_ref: date, memoria: Memoria
) -> Decimal:
    """Converte os eventos de processo em consumo de atividade."""

    eventos = list(
        sessao.scalars(
            select(EventoProcesso).where(EventoProcesso.lote_id == lote.id)
        ).all()
    )
    if not eventos:
        return ZERO

    taxas_por_atividade = taxas_vigentes(sessao, data_ref)
    atividades = {
        atividade.id: atividade
        for atividade in sessao.scalars(
            select(Atividade).where(
                Atividade.id.in_({e.atividade_id for e in eventos})
            )
        ).all()
    }

    taxas: dict[str, TaxaAtividade] = {}
    consumos: list[ConsumoAtividade] = []

    for evento in eventos:
        atividade = atividades[evento.atividade_id]
        taxa = taxas_por_atividade.get(atividade.id)
        if taxa is None:
            raise DadoObrigatorioAusenteError(
                f"Atividade {atividade.codigo} sem taxa vigente em "
                f"{data_ref.isoformat()}: apure a taxa antes de custear o lote."
            )
        taxas[atividade.codigo] = TaxaAtividade(
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
        )
        consumos.append(
            ConsumoAtividade(
                codigo_atividade=atividade.codigo,
                quantidade_direcionador=dec(evento.quantidade_direcionador),
            )
        )

    custos_diretos = sum((dec(e.custo_direto_exclusivo) for e in eventos), ZERO)
    resultado = calcular_custo_transformacao(consumos, taxas, memoria=memoria)
    return resultado.custo_total + custos_diretos


def buscar_lote(sessao: Session, lote_id: uuid.UUID) -> LoteCompra | None:
    return sessao.get(LoteCompra, lote_id)
