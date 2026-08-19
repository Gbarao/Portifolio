"""Operacoes: lotes, eventos e resultado economico."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import PaginacaoDep, SessaoDep, buscar_ou_404
from app.api.schemas.comum import Pagina
from app.api.schemas.operacao import (
    BalancoOut,
    EventoBalancaIn,
    EventoQualidadeIn,
    LoteIn,
    LoteOut,
    LoteSaidaIn,
    PerdaIn,
    ResultadoLoteOut,
)
from app.models import EventoBalanca, EventoQualidade, LoteCompra, LoteSaida, RejeitoPerda
from app.models.enums import StatusLote
from app.servicos.lote import calcular_resultado_lote

router = APIRouter(prefix="/lotes", tags=["operacoes"])


@router.get("", response_model=Pagina[LoteOut])
def listar_lotes(
    sessao: SessaoDep,
    paginacao: PaginacaoDep,
    status_lote: str | None = Query(default=None, alias="status"),
):
    consulta = select(LoteCompra)
    if status_lote:
        consulta = consulta.where(LoteCompra.status == status_lote)

    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = sessao.scalars(
        consulta.order_by(LoteCompra.data_entrada.desc())
        .limit(paginacao.limite)
        .offset(paginacao.deslocamento)
    ).all()
    return Pagina(
        itens=list(itens),
        total=total,
        limite=paginacao.limite,
        deslocamento=paginacao.deslocamento,
    )


@router.post("", response_model=LoteOut, status_code=status.HTTP_201_CREATED)
def criar_lote(dados: LoteIn, sessao: SessaoDep):
    lote = LoteCompra(
        **dados.model_dump(),
        data_competencia=dados.data_entrada,
        status=StatusLote.ABERTO,
    )
    sessao.add(lote)
    sessao.flush()
    return lote


@router.get("/{lote_id}", response_model=LoteOut)
def obter_lote(lote_id: uuid.UUID, sessao: SessaoDep):
    return buscar_ou_404(sessao, LoteCompra, lote_id)


@router.post(
    "/{lote_id}/eventos-balanca", response_model=LoteOut, status_code=status.HTTP_201_CREATED
)
def registrar_balanca(lote_id: uuid.UUID, dados: EventoBalancaIn, sessao: SessaoDep):
    """Ticket de balanca. O peso liquido e derivado, nunca informado solto."""

    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    sessao.add(
        EventoBalanca(
            lote_id=lote.id,
            peso_liquido_kg=dados.peso_bruto_kg - dados.tara_kg,
            **dados.model_dump(),
        )
    )
    sessao.flush()
    return lote


@router.post(
    "/{lote_id}/eventos-qualidade",
    response_model=LoteOut,
    status_code=status.HTTP_201_CREATED,
)
def registrar_qualidade(lote_id: uuid.UUID, dados: EventoQualidadeIn, sessao: SessaoDep):
    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    sessao.add(EventoQualidade(lote_id=lote.id, **dados.model_dump()))
    sessao.flush()
    return lote


@router.post("/{lote_id}/saidas", response_model=LoteOut, status_code=status.HTTP_201_CREATED)
def registrar_saida(lote_id: uuid.UUID, dados: LoteSaidaIn, sessao: SessaoDep):
    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    sessao.add(LoteSaida(lote_origem_id=lote.id, **dados.model_dump()))
    lote.status = StatusLote.EM_PROCESSAMENTO
    sessao.flush()
    return lote


@router.post("/{lote_id}/perdas", response_model=LoteOut, status_code=status.HTTP_201_CREATED)
def registrar_perda(lote_id: uuid.UUID, dados: PerdaIn, sessao: SessaoDep):
    """Perda anormal nao integra o custo-padrao sem aprovacao formal."""

    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    integra_padrao = dados.tipo not in {
        "PERDA_ANORMAL",
        "FURTO_AVARIA",
        "DETERIORACAO",
    }
    sessao.add(
        RejeitoPerda(
            lote_id=lote.id, integra_custo_padrao=integra_padrao, **dados.model_dump()
        )
    )
    sessao.flush()
    return lote


@router.get("/{lote_id}/balanco", response_model=BalancoOut)
def obter_balanco(
    lote_id: uuid.UUID,
    sessao: SessaoDep,
    bloquear: bool = Query(
        default=False,
        description="Se verdadeiro, divergencia acima da tolerancia retorna 409",
    ),
):
    """Balanco de massa do lote.

    Por padrao devolve o balanco mesmo fora da tolerancia, para que a tela
    mostre a divergencia. ``bloquear=true`` reproduz a regra do encerramento.
    """

    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    resultado = calcular_resultado_lote(
        sessao, lote, bloquear_fora_da_tolerancia=bloquear
    )
    return resultado.balanco


@router.get("/{lote_id}/resultado", response_model=ResultadoLoteOut)
def obter_resultado(lote_id: uuid.UUID, sessao: SessaoDep):
    """Resultado economico do lote com memoria de calculo (secao 12.2)."""

    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    resultado = calcular_resultado_lote(sessao, lote, bloquear_fora_da_tolerancia=False)

    return ResultadoLoteOut(
        lote_id=lote.id,
        codigo=lote.codigo,
        balanco=resultado.balanco,
        custo_aquisicao_total=resultado.aquisicao.custo_total,
        custo_aquisicao_por_kg_aceito=resultado.aquisicao.custo_por_kg_aceito,
        custo_aquisicao_por_kg_vendavel=resultado.aquisicao.custo_por_kg_vendavel,
        custo_transformacao=resultado.custo_transformacao,
        custo_capital=resultado.capital.custo_financeiro,
        custo_total=resultado.custo_total,
        custo_unitario_vendavel=resultado.custo_unitario_vendavel,
        creditos_pendentes=resultado.aquisicao.creditos_pendentes,
        alertas=resultado.alertas,
        memoria=resultado.memoria.exportar(),
    )


@router.post("/{lote_id}/encerrar", response_model=ResultadoLoteOut)
def encerrar_lote(
    lote_id: uuid.UUID,
    sessao: SessaoDep,
    justificativa: str | None = Query(default=None),
    aprovado_por: str | None = Query(default=None),
):
    """Encerra o lote apos fechar o balanco de massa.

    Divergencia acima da tolerancia retorna 409 e so e liberada com
    justificativa e aprovador -- a excecao da regra 1 da secao 11.
    """

    lote = buscar_ou_404(sessao, LoteCompra, lote_id)
    excecao_aprovada = bool(justificativa and aprovado_por)

    resultado = calcular_resultado_lote(
        sessao, lote, bloquear_fora_da_tolerancia=not excecao_aprovada
    )

    lote.status = StatusLote.FECHADO
    lote.encerrado_por = aprovado_por
    if justificativa:
        lote.justificativa_excecao = justificativa
    sessao.flush()

    return ResultadoLoteOut(
        lote_id=lote.id,
        codigo=lote.codigo,
        balanco=resultado.balanco,
        custo_aquisicao_total=resultado.aquisicao.custo_total,
        custo_aquisicao_por_kg_aceito=resultado.aquisicao.custo_por_kg_aceito,
        custo_aquisicao_por_kg_vendavel=resultado.aquisicao.custo_por_kg_vendavel,
        custo_transformacao=resultado.custo_transformacao,
        custo_capital=resultado.capital.custo_financeiro,
        custo_total=resultado.custo_total,
        custo_unitario_vendavel=resultado.custo_unitario_vendavel,
        creditos_pendentes=resultado.aquisicao.creditos_pendentes,
        alertas=resultado.alertas,
        memoria=resultado.memoria.exportar(),
    )
