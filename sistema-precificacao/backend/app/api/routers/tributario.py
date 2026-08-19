"""Matriz tributaria: consulta, cadastro, validacao e calculos por regime."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import DataRefDep, PaginacaoDep, SessaoDep, buscar_ou_404
from app.api.schemas.comum import Pagina
from app.api.schemas.fiscal import (
    AliquotaSimplesIn,
    AliquotaSimplesOut,
    DeducoesIn,
    DeducoesOut,
    MudancaFaixaIn,
    MudancaFaixaOut,
    RegraTributariaIn,
    RegraTributariaOut,
    ValidacaoRegraIn,
)
from app.dominio.memoria import Memoria
from app.models import RegraTributaria
from app.models.enums import StatusRegraFiscal
from app.servicos.parametros import faixas_simples, regras_vigentes
from app.tributario.regimes import (
    calcular_aliquota_efetiva_simples,
    calcular_deducoes_venda,
    simular_mudanca_faixa,
)
from app.tributario.resolucao import ContextoFiscal, esta_vigente

router = APIRouter(prefix="/tributario", tags=["motor tributario"])


@router.get("/regras", response_model=Pagina[RegraTributariaOut])
def listar_regras(
    sessao: SessaoDep,
    paginacao: PaginacaoDep,
    regime: str | None = Query(default=None),
    tributo: str | None = Query(default=None),
    tipo_operacao: str | None = Query(default=None),
    apenas_vigentes: bool = Query(default=False),
    em: date | None = Query(default=None, description="Data para o filtro de vigencia"),
):
    """Lista a matriz. ``apenas_vigentes`` filtra pela data informada."""

    consulta = select(RegraTributaria)
    if regime:
        consulta = consulta.where(RegraTributaria.regime_tributario == regime)
    if tributo:
        consulta = consulta.where(RegraTributaria.tributo == tributo)
    if tipo_operacao:
        consulta = consulta.where(RegraTributaria.tipo_operacao == tipo_operacao)

    registros = list(sessao.scalars(consulta.order_by(RegraTributaria.codigo)).all())
    if apenas_vigentes:
        referencia = em or date.today()
        registros = [r for r in registros if esta_vigente(r, referencia)]

    total = len(registros)
    recorte = registros[
        paginacao.deslocamento : paginacao.deslocamento + paginacao.limite
    ]
    return Pagina(
        itens=recorte,
        total=total,
        limite=paginacao.limite,
        deslocamento=paginacao.deslocamento,
    )


@router.post(
    "/regras", response_model=RegraTributariaOut, status_code=status.HTTP_201_CREATED
)
def criar_regra(dados: RegraTributariaIn, sessao: SessaoDep):
    """Cadastra a regra sempre como PROVISORIA.

    Nao existe caminho pela API para criar regra ja validada: a validacao e
    ato separado do responsavel fiscal, e fica registrada com autor e data.
    """

    regra = RegraTributaria(**dados.model_dump(), status=StatusRegraFiscal.PROVISORIA)
    sessao.add(regra)
    sessao.flush()
    return regra


@router.post("/regras/{regra_id}/validar", response_model=RegraTributariaOut)
def validar_regra(regra_id: uuid.UUID, dados: ValidacaoRegraIn, sessao: SessaoDep):
    """Promove a regra para VALIDADA, registrando quem validou e quando."""

    regra = buscar_ou_404(sessao, RegraTributaria, regra_id)
    regra.status = StatusRegraFiscal.VALIDADA
    regra.validado_por = dados.validado_por
    regra.validado_em = date.today()
    if dados.observacao:
        regra.observacao = dados.observacao
    sessao.flush()
    return regra


@router.post("/deducoes", response_model=DeducoesOut)
def calcular_deducoes(dados: DeducoesIn, sessao: SessaoDep):
    """Calcula a variavel `r` para um contexto de venda.

    A resposta traz o detalhamento por tributo e o status fiscal consolidado:
    uma regra vencida derruba ``permite_cotacao_definitiva`` para falso sem
    impedir a simulacao.
    """

    contexto = ContextoFiscal(**dados.contexto.model_dump())
    memoria = Memoria(titulo="Deducoes sobre a venda")

    deducoes = calcular_deducoes_venda(
        regras_vigentes(sessao, contexto.data_operacao),
        contexto,
        comissao_percentual=dados.comissao_percentual,
        desconto_contratual_percentual=dados.desconto_contratual_percentual,
        memoria=memoria,
    )

    return DeducoesOut(
        r_total=deducoes.r_total,
        detalhamento=deducoes.detalhamento,
        status_fiscal=deducoes.apuracao.status_consolidado,
        permite_cotacao_definitiva=deducoes.permite_cotacao_definitiva,
        tributos=deducoes.apuracao.resultados,
        alertas=deducoes.alertas,
        memoria=memoria.exportar(),
    )


@router.post("/simples/aliquota-efetiva", response_model=AliquotaSimplesOut)
def aliquota_efetiva_simples(dados: AliquotaSimplesIn, sessao: SessaoDep, data: DataRefDep):
    resultado = calcular_aliquota_efetiva_simples(
        faixas_simples(sessao, dados.data_operacao or data),
        rbt12=dados.rbt12,
        anexo=dados.anexo,
        icms_segregado=dados.icms_segregado,
    )
    return resultado


@router.post("/simples/mudanca-faixa", response_model=MudancaFaixaOut)
def mudanca_de_faixa(dados: MudancaFaixaIn, sessao: SessaoDep, data: DataRefDep):
    """Alerta critico da secao 7.7-C.

    Responde quanto a venda realmente custa de DAS, considerando que a
    aliquota nova alcanca todo o faturamento do mes.
    """

    return simular_mudanca_faixa(
        faixas_simples(sessao, data),
        rbt12_atual=dados.rbt12_atual,
        receita_mes_sem_a_venda=dados.receita_mes_sem_a_venda,
        receita_da_venda=dados.receita_da_venda,
        anexo=dados.anexo,
    )
