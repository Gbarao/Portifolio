"""Servico de cotacao: liga schemas HTTP, motor de calculo e persistencia."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.aplicacao.cotacao import PremissasCotacao, VersaoCotacao, gerar_versao
from app.dominio.camadas import (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
    ComponenteCusto,
)
from app.dominio.memoria import Memoria
from app.models import CotacaoPreco, CotacaoVenda, CotacaoVersao, MemoriaCalculo, MemoriaPasso
from app.models.enums import (
    CamadaPreco,
    RegimeTributario,
    StatusCotacao,
    StatusRegraFiscal,
    UnidadeMedida,
    VisaoCusto,
)
from app.servicos.parametros import regras_vigentes
from app.tributario.resolucao import ContextoFiscal

CAMADAS_ORDENADAS = (
    CAMADA_CAIXA,
    CAMADA_CONTRIBUICAO,
    CAMADA_OPERACIONAL,
    CAMADA_SUSTENTAVEL,
)

# Visao de custo associada a cada degrau da escada.
VISAO_POR_CAMADA = {
    "CAIXA": VisaoCusto.RELEVANTE,
    "CONTRIBUICAO": VisaoCusto.RELEVANTE,
    "OPERACIONAL": VisaoCusto.CONTABIL,
    "SUSTENTAVEL": VisaoCusto.GERENCIAL_COMPLETO,
    "ALVO": VisaoCusto.GERENCIAL_COMPLETO,
    "MERCADO_COMPARAVEL": VisaoCusto.GERENCIAL_COMPLETO,
}


def contexto_de(entrada) -> ContextoFiscal:
    return ContextoFiscal(**entrada.model_dump())


def componentes_de(entradas) -> tuple[ComponenteCusto, ...]:
    return tuple(
        ComponenteCusto(
            nome=c.nome,
            valor=c.valor,
            camada_minima=c.camada_minima,
            visoes=tuple(c.visoes),
            e_desembolso=c.e_desembolso,
            e_relevante_para_decisao=c.e_relevante_para_decisao,
        )
        for c in entradas
    )


def calcular(
    sessao: Session,
    entrada,
    *,
    numero_versao: int = 1,
) -> VersaoCotacao:
    """Executa o motor com as regras vigentes na data do contexto."""

    contexto = contexto_de(entrada.contexto)
    premissas = PremissasCotacao(
        data_referencia=contexto.data_operacao,
        quantidade_kg=entrada.quantidade_kg,
        margem_alvo=entrada.margem_alvo,
        margem_contribuicao_minima=entrada.margem_contribuicao_minima,
        componentes_custo=componentes_de(entrada.componentes_custo),
        comissao_percentual=entrada.comissao_percentual,
        desconto_contratual_percentual=entrada.desconto_contratual_percentual,
        preco_mercado=entrada.preco_mercado,
    )
    return gerar_versao(
        premissas,
        regras_fiscais=regras_vigentes(sessao, contexto.data_operacao),
        contexto_fiscal=contexto,
        numero=numero_versao,
    )


def resposta_de(versao: VersaoCotacao, *, preco_proposto: Decimal | None = None) -> dict:
    """Converte o resultado do motor no corpo da resposta HTTP."""

    avaliacao = None
    if preco_proposto is not None:
        resultado = versao.escada.avaliar_proposta(preco_proposto)
        avaliacao = {
            "preco_proposto": resultado.preco_proposto,
            "faixa": resultado.faixa,
            "alcada_necessaria": resultado.alcada_necessaria,
            "valor_concessao": resultado.valor_concessao,
            "bloqueado": resultado.bloqueado,
            "mensagem": resultado.mensagem,
        }

    return {
        "status": versao.status,
        "status_fiscal": versao.deducoes.apuracao.status_consolidado,
        "permite_cotacao_definitiva": versao.deducoes.permite_cotacao_definitiva,
        "deducoes_r": versao.deducoes.r_total,
        "detalhamento_r": versao.deducoes.detalhamento,
        "quantidade_kg": versao.premissas.quantidade_kg,
        "custo_por_camada": {
            camada: versao.estrutura.unitario(camada) for camada in CAMADAS_ORDENADAS
        },
        "precos": [
            {
                "camada": degrau.camada,
                "custo_unitario": degrau.custo_unitario,
                "deducoes_r": degrau.deducoes_r,
                "margem_m": degrau.margem_m,
                "preco_unitario": degrau.preco_unitario,
                "receita_liquida_unitaria": degrau.receita_liquida_unitaria,
                "margem_valor": degrau.margem_valor,
                "margem_percentual": degrau.margem_percentual,
                "finalidade": degrau.finalidade,
                "alerta": degrau.alerta,
            }
            for degrau in versao.escada.degraus.values()
        ],
        "avaliacao_proposta": avaliacao,
        "alertas": list(versao.alertas),
        "memoria": versao.memoria.exportar(),
    }


def persistir_memoria(
    sessao: Session,
    memoria: Memoria,
    *,
    escopo: str,
    referencia_id: uuid.UUID,
    status_fiscal: str,
    criado_por: str | None = None,
) -> MemoriaCalculo:
    """Grava a memoria para que a cotacao continue reproduzivel no futuro."""

    cabecalho = MemoriaCalculo(
        escopo=escopo,
        referencia_id=referencia_id,
        titulo=memoria.titulo,
        status_fiscal=StatusRegraFiscal(status_fiscal)
        if status_fiscal in StatusRegraFiscal.__members__
        else None,
        criado_por=criado_por,
        versao_regras={"alertas": memoria.alertas},
    )
    sessao.add(cabecalho)
    sessao.flush()

    for passo in memoria.passos:
        sessao.add(
            MemoriaPasso(
                memoria_id=cabecalho.id,
                ordem=passo.ordem,
                rotulo=passo.rotulo,
                formula=passo.formula,
                entradas={k: str(v) for k, v in passo.entradas.items()},
                resultado=passo.resultado,
                unidade=passo.unidade,
                fonte=passo.fonte,
                vigencia_regra=passo.vigencia_regra,
                alerta=passo.alerta,
            )
        )
    return cabecalho


def persistir(
    sessao: Session,
    entrada,
    versao_calculada: VersaoCotacao,
    *,
    cotacao: CotacaoVenda | None = None,
) -> tuple[CotacaoVenda, CotacaoVersao]:
    """Grava cotacao, versao, precos por camada e memoria de calculo."""

    contexto = entrada.contexto
    horizonte = 7

    if cotacao is None:
        cotacao = CotacaoVenda(
            codigo=entrada.codigo or f"COT-{uuid.uuid4().hex[:10].upper()}",
            unidade_id=entrada.unidade_id,
            cliente_id=entrada.cliente_id,
            material_id=entrada.material_id,
            quantidade=entrada.quantidade_kg,
            unidade_comercial=UnidadeMedida.KG,
            quantidade_kg=entrada.quantidade_kg,
            uf_destino=contexto.uf_destino or "SP",
            municipio_destino=contexto.municipio,
            tipo_frete="FROTA_PROPRIA",
            data_referencia=contexto.data_operacao,
            criado_por=entrada.criado_por,
            status=StatusCotacao.RASCUNHO,
        )
        sessao.add(cotacao)
        sessao.flush()

    status_fiscal = versao_calculada.deducoes.apuracao.status_consolidado
    memoria = persistir_memoria(
        sessao,
        versao_calculada.memoria,
        escopo="COTACAO_VERSAO",
        referencia_id=cotacao.id,
        status_fiscal=status_fiscal,
        criado_por=entrada.criado_por,
    )

    versao = CotacaoVersao(
        cotacao_id=cotacao.id,
        numero_versao=versao_calculada.numero,
        regime_tributario=RegimeTributario(contexto.regime_tributario),
        premissas=versao_calculada.premissas.como_dicionario(),
        memoria_calculo_id=memoria.id,
        deducoes_r=versao_calculada.deducoes.r_total,
        margem_alvo_m=entrada.margem_alvo,
        status=(
            StatusCotacao.SIMULACAO
            if not versao_calculada.permite_venda_definitiva
            else StatusCotacao.RASCUNHO
        ),
        status_fiscal=(
            StatusRegraFiscal(status_fiscal)
            if status_fiscal in StatusRegraFiscal.__members__
            else StatusRegraFiscal.PROVISORIA
        ),
        validade_ate=contexto.data_operacao + timedelta(days=horizonte),
        criado_por=entrada.criado_por,
    )
    sessao.add(versao)
    sessao.flush()

    for degrau in versao_calculada.escada.degraus.values():
        sessao.add(
            CotacaoPreco(
                versao_id=versao.id,
                camada=CamadaPreco(degrau.camada),
                visao_custo=VISAO_POR_CAMADA[degrau.camada],
                custo_unitario=degrau.custo_unitario,
                deducoes_r=degrau.deducoes_r,
                margem_m=degrau.margem_m,
                preco_unitario=degrau.preco_unitario,
                preco_total=degrau.preco_unitario * versao_calculada.premissas.quantidade_kg,
                receita_liquida_unitaria=degrau.receita_liquida_unitaria,
                margem_valor=degrau.margem_valor,
                margem_percentual=degrau.margem_percentual,
                alerta=degrau.alerta,
            )
        )

    cotacao.versao_atual = versao.numero_versao
    sessao.flush()
    return cotacao, versao


def data_de(entrada) -> date:
    return entrada.contexto.data_operacao
