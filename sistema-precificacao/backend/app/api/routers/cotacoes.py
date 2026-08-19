"""Cotacoes, escada de precos e simulacoes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import SessaoDep, buscar_ou_404
from app.api.schemas.comercial import (
    CotacaoCalculadaOut,
    CotacaoIn,
    CotacaoOut,
    PrecoMaximoCompraIn,
    PrecoMaximoCompraOut,
    RevisaoCotacaoIn,
    SimulacaoCotacaoIn,
)
from app.dominio.memoria import Memoria
from app.dominio.precos import calcular_preco_maximo_compra
from app.models import CotacaoVenda, CotacaoVersao
from app.servicos import cotacao as servico
from app.servicos.parametros import regras_vigentes
from app.tributario.regimes import calcular_deducoes_venda
from app.tributario.resolucao import ContextoFiscal

router = APIRouter(tags=["cotacoes e simulacoes"])


@router.post("/cotacoes/simular", response_model=CotacaoCalculadaOut)
def simular_cotacao(dados: SimulacaoCotacaoIn, sessao: SessaoDep):
    """Calcula a escada de precos sem persistir nada.

    E a tela de trabalho do comercial: muda premissa, ve o preco mudar. So
    vira registro quando o usuario decidir salvar.
    """

    versao = servico.calcular(sessao, dados)
    return servico.resposta_de(versao, preco_proposto=dados.preco_proposto)


@router.post("/cotacoes", response_model=CotacaoOut, status_code=status.HTTP_201_CREATED)
def criar_cotacao(dados: CotacaoIn, sessao: SessaoDep):
    """Persiste a cotacao com premissas congeladas e memoria de calculo."""

    versao_calculada = servico.calcular(sessao, dados)
    cotacao, _ = servico.persistir(sessao, dados, versao_calculada)

    return CotacaoOut(
        id=cotacao.id,
        codigo=cotacao.codigo,
        status=str(getattr(cotacao.status, "value", cotacao.status)),
        versao_atual=cotacao.versao_atual,
        quantidade_kg=cotacao.quantidade_kg,
        data_referencia=cotacao.data_referencia,
        calculo=servico.resposta_de(
            versao_calculada, preco_proposto=dados.preco_proposto
        ),
    )


@router.get("/cotacoes/{cotacao_id}", response_model=CotacaoOut)
def obter_cotacao(cotacao_id: uuid.UUID, sessao: SessaoDep):
    """Recupera a cotacao recalculando pela versao atual e suas premissas."""

    cotacao = buscar_ou_404(sessao, CotacaoVenda, cotacao_id)
    versao = sessao.scalar(
        select(CotacaoVersao)
        .where(CotacaoVersao.cotacao_id == cotacao.id)
        .order_by(CotacaoVersao.numero_versao.desc())
        .limit(1)
    )

    entrada = _entrada_a_partir_de(cotacao, versao)
    versao_calculada = servico.calcular(
        sessao, entrada, numero_versao=versao.numero_versao
    )

    return CotacaoOut(
        id=cotacao.id,
        codigo=cotacao.codigo,
        status=str(getattr(cotacao.status, "value", cotacao.status)),
        versao_atual=cotacao.versao_atual,
        quantidade_kg=cotacao.quantidade_kg,
        data_referencia=cotacao.data_referencia,
        calculo=servico.resposta_de(versao_calculada),
    )


@router.post(
    "/cotacoes/{cotacao_id}/versoes",
    response_model=CotacaoOut,
    status_code=status.HTTP_201_CREATED,
)
def revisar_cotacao(cotacao_id: uuid.UUID, dados: RevisaoCotacaoIn, sessao: SessaoDep):
    """Gera nova versao alterando premissas; a anterior permanece intacta."""

    cotacao = buscar_ou_404(sessao, CotacaoVenda, cotacao_id)
    versao_atual = sessao.scalar(
        select(CotacaoVersao)
        .where(CotacaoVersao.cotacao_id == cotacao.id)
        .order_by(CotacaoVersao.numero_versao.desc())
        .limit(1)
    )

    entrada = _entrada_a_partir_de(cotacao, versao_atual)
    for campo in (
        "margem_alvo",
        "margem_contribuicao_minima",
        "quantidade_kg",
        "componentes_custo",
        "preco_mercado",
    ):
        novo = getattr(dados, campo)
        if novo is not None:
            setattr(entrada, campo, novo)

    nova = servico.calcular(
        sessao, entrada, numero_versao=versao_atual.numero_versao + 1
    )
    servico.persistir(sessao, entrada, nova, cotacao=cotacao)

    return CotacaoOut(
        id=cotacao.id,
        codigo=cotacao.codigo,
        status=str(getattr(cotacao.status, "value", cotacao.status)),
        versao_atual=cotacao.versao_atual,
        quantidade_kg=cotacao.quantidade_kg,
        data_referencia=cotacao.data_referencia,
        calculo=servico.resposta_de(nova),
    )


@router.post("/simulacoes/preco-maximo-compra", response_model=PrecoMaximoCompraOut)
def preco_maximo_de_compra(dados: PrecoMaximoCompraIn, sessao: SessaoDep):
    """Quanto pagar pelo material dado um preco de venda de mercado (secao 14).

    Se o contexto fiscal for informado, `r` vem do motor tributario; caso
    contrario aceita-se o `r` explicito do cliente da API.
    """

    memoria = Memoria(titulo="Preco maximo de compra")

    if dados.contexto is not None:
        contexto = ContextoFiscal(**dados.contexto.model_dump())
        deducoes = calcular_deducoes_venda(
            regras_vigentes(sessao, contexto.data_operacao), contexto, memoria=memoria
        )
        r = deducoes.r_total
    else:
        r = dados.deducoes_r or 0

    resultado = calcular_preco_maximo_compra(
        preco_venda_unitario=dados.preco_venda_unitario,
        quantidade_vendavel=dados.quantidade_vendavel,
        deducoes_r=r,
        demais_custos=dados.demais_custos,
        margem_alvo=dados.margem_alvo,
        quantidade_aceita_esperada=dados.quantidade_aceita_esperada,
        memoria=memoria,
    )

    return PrecoMaximoCompraOut(
        receita_liquida_total=resultado.receita_liquida_total,
        demais_custos=resultado.demais_custos,
        lucro_alvo=resultado.lucro_alvo,
        preco_maximo_total=resultado.preco_maximo_total,
        preco_maximo_unitario=resultado.preco_maximo_unitario,
        deducoes_r=r,
        memoria=memoria.exportar(),
    )


def _entrada_a_partir_de(cotacao: CotacaoVenda, versao: CotacaoVersao) -> CotacaoIn:
    """Reconstroi a entrada a partir das premissas congeladas na versao.

    E o que garante que reabrir uma cotacao antiga reproduza o preco antigo:
    as premissas vem do registro, nao de uma consulta nova aos cadastros.
    """

    premissas = versao.premissas
    return CotacaoIn(
        unidade_id=cotacao.unidade_id,
        cliente_id=cotacao.cliente_id,
        material_id=cotacao.material_id,
        codigo=cotacao.codigo,
        quantidade_kg=premissas["quantidade_kg"],
        margem_alvo=premissas["margem_alvo"],
        margem_contribuicao_minima=premissas["margem_contribuicao_minima"],
        comissao_percentual=premissas["comissao_percentual"],
        desconto_contratual_percentual=premissas["desconto_contratual_percentual"],
        preco_mercado=premissas.get("preco_mercado"),
        componentes_custo=premissas["componentes_custo"],
        contexto={
            "data_operacao": cotacao.data_referencia,
            "tipo_operacao": "VENDA",
            "regime_tributario": str(
                getattr(versao.regime_tributario, "value", versao.regime_tributario)
            ),
            "uf_destino": cotacao.uf_destino,
            "municipio": cotacao.municipio_destino,
        },
    )
