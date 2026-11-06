"""Componentes comuns das telas (Streamlit)."""
from __future__ import annotations

import contextlib
from decimal import Decimal

import duckdb
import pandas as pd
import streamlit as st

from . import db
from .config import logger
from .empresas import empresas

CHAVE_SELECAO = "empresas_selecionadas"
CHAVE_TODAS = "todas_empresas"


@st.cache_resource(show_spinner=False)
def _conexao_base() -> duckdb.DuckDBPyConnection:
    return db.conectar()


def conexao() -> duckdb.DuckDBPyConnection | None:
    """Conexao com o banco local. Cada execucao de tela usa um cursor proprio."""
    try:
        return _conexao_base().cursor()
    except duckdb.IOException:
        logger().exception("Banco local em uso")
        st.error("O banco de dados local está em uso por outra janela do programa. "
                 "Feche as outras janelas pretas do programa e abra de novo pelo iniciar.bat.")
        return None


def cabecalho(titulo: str, para_que_serve: str) -> None:
    st.title(titulo)
    st.info(para_que_serve)


@contextlib.contextmanager
def protegido(acao: str):
    """Mostra mensagem simples em vez de detalhe tecnico; o detalhe vai para o log."""
    try:
        yield
    except Exception as e:  # noqa: BLE001
        logger().exception("Erro na tela ao %s", acao)
        st.error(f"Ocorreu um problema ao {acao}. O detalhe técnico foi gravado em "
                 f"data/logs/zfm.log ({type(e).__name__}). Envie esse arquivo ao Claude Code.")


def formatar_brl(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    v = Decimal(str(v)).quantize(Decimal("0.01"))
    sinal = "-" if v < 0 else ""
    inteiro, dec = f"{abs(v):.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(grupos)},{dec}"


def seletor_empresas(con: duckdb.DuckDBPyConnection | None) -> list[str] | None:
    """Seletor da barra lateral. Retorna a lista de raizes de CNPJ selecionadas
    (None = todas as empresas, consolidado)."""
    with st.sidebar:
        st.subheader("Empresas")
        if con is None:
            return None
        emp = empresas(con)
        if emp.empty:
            st.caption("Nenhuma empresa ainda. Carregue as EFDs na tela 'Carga de arquivos'.")
            return None
        rotulos = {r.raiz: f"{r.razao_social} ({r.raiz})" for r in emp.itertuples()}
        st.session_state.setdefault(CHAVE_TODAS, True)
        todas = st.checkbox("Todas as empresas (consolidado)", key=CHAVE_TODAS)
        if todas:
            sel = None
        else:
            sel = st.multiselect("Escolha uma ou várias", options=list(rotulos),
                                 format_func=lambda r: rotulos[r], key=CHAVE_SELECAO)
    if sel is None:
        st.caption(f"Exibindo: consolidado de {len(rotulos)} empresa(s)")
    elif not sel:
        st.warning("Nenhuma empresa selecionada na barra lateral.")
    else:
        st.caption("Exibindo: " + ", ".join(rotulos[r] for r in sel))
    return sel
