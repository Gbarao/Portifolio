"""Cadastros: unidades, parametros vigentes, materiais e parceiros."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import DataRefDep, PaginacaoDep, SessaoDep, buscar_ou_404
from app.api.erros import RecursoNaoEncontrado
from app.api.schemas.cadastro import (
    MaterialIn,
    MaterialOut,
    ParametroOut,
    ParceiroIn,
    ParceiroOut,
    UnidadeOut,
)
from app.api.schemas.comum import Pagina
from app.models import Material, Parceiro, Unidade
from app.servicos.parametros import parametro_vigente

router = APIRouter(tags=["cadastros"])


@router.get("/unidades", response_model=Pagina[UnidadeOut])
def listar_unidades(sessao: SessaoDep, paginacao: PaginacaoDep):
    total = sessao.scalar(select(func.count()).select_from(Unidade)) or 0
    itens = sessao.scalars(
        select(Unidade)
        .order_by(Unidade.codigo)
        .limit(paginacao.limite)
        .offset(paginacao.deslocamento)
    ).all()
    return Pagina(
        itens=list(itens),
        total=total,
        limite=paginacao.limite,
        deslocamento=paginacao.deslocamento,
    )


@router.get("/unidades/{unidade_id}/parametros", response_model=ParametroOut)
def parametros_vigentes(unidade_id: uuid.UUID, sessao: SessaoDep, data: DataRefDep):
    """Parametros que valiam na data informada -- nao os mais recentes."""

    parametro = parametro_vigente(sessao, unidade_id, data)
    if parametro is None:
        raise RecursoNaoEncontrado(
            "EmpresaParametro vigente", f"{unidade_id} em {data.isoformat()}"
        )
    return parametro


@router.get("/materiais", response_model=Pagina[MaterialOut])
def listar_materiais(
    sessao: SessaoDep,
    paginacao: PaginacaoDep,
    familia: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
):
    consulta = select(Material)
    if familia:
        consulta = consulta.where(Material.familia == familia)
    if tipo:
        consulta = consulta.where(Material.tipo == tipo)

    total = sessao.scalar(
        select(func.count()).select_from(consulta.subquery())
    ) or 0
    itens = sessao.scalars(
        consulta.order_by(Material.codigo)
        .limit(paginacao.limite)
        .offset(paginacao.deslocamento)
    ).all()
    return Pagina(
        itens=list(itens),
        total=total,
        limite=paginacao.limite,
        deslocamento=paginacao.deslocamento,
    )


@router.post("/materiais", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def criar_material(dados: MaterialIn, sessao: SessaoDep):
    material = Material(**dados.model_dump())
    sessao.add(material)
    sessao.flush()
    return material


@router.get("/materiais/{material_id}", response_model=MaterialOut)
def obter_material(material_id: uuid.UUID, sessao: SessaoDep):
    return buscar_ou_404(sessao, Material, material_id)


@router.get("/parceiros", response_model=Pagina[ParceiroOut])
def listar_parceiros(
    sessao: SessaoDep,
    paginacao: PaginacaoDep,
    papel: str | None = Query(default=None),
):
    consulta = select(Parceiro)
    if papel:
        consulta = consulta.where(Parceiro.papel == papel)

    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    itens = sessao.scalars(
        consulta.order_by(Parceiro.nome)
        .limit(paginacao.limite)
        .offset(paginacao.deslocamento)
    ).all()
    return Pagina(
        itens=list(itens),
        total=total,
        limite=paginacao.limite,
        deslocamento=paginacao.deslocamento,
    )


@router.post("/parceiros", response_model=ParceiroOut, status_code=status.HTTP_201_CREATED)
def criar_parceiro(dados: ParceiroIn, sessao: SessaoDep):
    parceiro = Parceiro(**dados.model_dump())
    sessao.add(parceiro)
    sessao.flush()
    return parceiro


@router.get("/parceiros/{parceiro_id}", response_model=ParceiroOut)
def obter_parceiro(parceiro_id: uuid.UUID, sessao: SessaoDep):
    return buscar_ou_404(sessao, Parceiro, parceiro_id)
