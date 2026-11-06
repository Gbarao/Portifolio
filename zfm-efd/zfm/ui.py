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
    if v == 0:
        v = Decimal("0.00")
    sinal = "-" if v < 0 else ""
    inteiro, dec = f"{abs(v):.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(grupos)},{dec}"


def _widget_persistente(widget, rotulo: str, chave: str, padrao, **kw):
    """Widget cujo valor sobrevive a troca de pagina (o Streamlit apaga o estado de
    widgets entre paginas; o valor fica guardado numa chave propria)."""
    st.session_state.setdefault(chave, padrao)
    chave_w = f"_w_{chave}"

    def _copiar():
        st.session_state[chave] = st.session_state[chave_w]

    if widget is st.multiselect:
        return widget(rotulo, default=st.session_state[chave], key=chave_w, on_change=_copiar, **kw)
    if widget in (st.radio, st.selectbox):
        opcoes = list(kw["options"])
        i = opcoes.index(st.session_state[chave]) if st.session_state[chave] in opcoes else 0
        return widget(rotulo, index=i, key=chave_w, on_change=_copiar, **kw)
    return widget(rotulo, value=st.session_state[chave], key=chave_w, on_change=_copiar, **kw)


def formatar_brl_curto(v) -> str:
    """Para cartoes: R$ 1,23 mi / R$ 34,0 mil."""
    if v is None or pd.isna(v):
        return "-"
    v = float(v)
    if abs(v) < 0.005:
        v = 0.0
    a = abs(v)
    if a >= 1e9:
        t = f"{v / 1e9:,.2f} bi"
    elif a >= 1e6:
        t = f"{v / 1e6:,.2f} mi"
    elif a >= 1e3:
        t = f"{v / 1e3:,.1f} mil"
    else:
        t = f"{v:,.2f}"
    return "R$ " + t.replace(",", "X").replace(".", ",").replace("X", ".")


def exigir_empresas(raizes: list[str]) -> None:
    if not raizes:
        st.warning("Nenhuma empresa selecionada (ou todas marcadas para não entrar na análise "
                   "em Parâmetros > Empresas).")
        st.stop()


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
        todas = _widget_persistente(st.checkbox, "Todas as empresas (consolidado)", CHAVE_TODAS, True)
        if todas:
            sel = None
        else:
            atual = [r for r in st.session_state.get(CHAVE_SELECAO, []) if r in rotulos]
            st.session_state[CHAVE_SELECAO] = atual
            sel = _widget_persistente(st.multiselect, "Escolha uma ou várias", CHAVE_SELECAO, [],
                                      options=list(rotulos), format_func=lambda r: rotulos[r])
    if sel is None:
        st.caption(f"Exibindo: consolidado de {len(rotulos)} empresa(s)")
    elif not sel:
        st.warning("Nenhuma empresa selecionada na barra lateral.")
    else:
        st.caption("Exibindo: " + ", ".join(rotulos[r] for r in sel))
    return sel


# ---------------------------------------------------------------------------
# Fases 2 a 7
# ---------------------------------------------------------------------------
CHAVE_TESES = "com_teses"
CHAVE_INTRAGRUPO = "eliminar_intragrupo"


def preparar(con: duckdb.DuckDBPyConnection) -> bool:
    """Sincroniza parametros e visoes. Retorna False se nao ha dados."""
    from . import visoes
    visoes.preparar(con)
    return con.execute("SELECT count(*) FROM arquivos WHERE ativo").fetchall()[0][0] > 0


def filtros_globais() -> tuple[bool, bool]:
    with st.sidebar:
        st.subheader("Filtros")
        teses = _widget_persistente(st.toggle, "Com teses", CHAVE_TESES, False,
                                    help="Inclui o efeito das teses cadastradas em Parâmetros > Teses.")
        intra = _widget_persistente(st.toggle, "Eliminar operações entre empresas do grupo",
                                    CHAVE_INTRAGRUPO, False,
                                    help="Retira do benefício as vendas para outras empresas do grupo.")
    return teses, intra


def raizes_analise(con: duckdb.DuckDBPyConnection, selecao: list[str] | None) -> list[str]:
    """Empresas efetivamente analisadas: selecao da barra lateral ∩ 'incluir na analise'."""
    from . import params
    pe = params.carregar("param_empresas")
    excluidas = set(pe.loc[~pe["incluir_na_analise"], "raiz_cnpj"]) if not pe.empty else set()
    todas = [r[0] for r in con.execute("SELECT DISTINCT raiz FROM arquivos WHERE ativo ORDER BY 1").fetchall()]
    base = todas if selecao is None else selecao
    return [r for r in base if r not in excluidas]


def nomes_empresas() -> dict[str, str]:
    from . import params
    pe = params.carregar("param_empresas")
    return {r.raiz_cnpj: (r.nome_curto or r.razao_social or r.raiz_cnpj) for r in pe.itertuples()}


def tabela(df: pd.DataFrame, moeda: list[str] | None = None, pct: list[str] | None = None,
           altura: int | None = None) -> None:
    """Mostra tabela com valores em R$ no formato brasileiro."""
    if df is None or df.empty:
        st.caption("Sem dados para a seleção.")
        return
    pct = pct or []
    moeda = [c for c in (moeda if moeda is not None else
                         [c for c in df.columns if pd.api.types.is_float_dtype(df[c]) and c not in pct])
             if c in df.columns]
    fmt = {c: formatar_brl for c in moeda}
    for c in pct:
        if c in df.columns:
            fmt[c] = lambda v: "-" if pd.isna(v) else f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    kw = {"height": altura} if altura else {}
    st.dataframe(df.style.format(fmt, na_rep="-"), hide_index=True, use_container_width=True, **kw)


def por_empresa(df: pd.DataFrame, indice: list[str], valor: str, nomes: dict[str, str]) -> pd.DataFrame:
    """Uma coluna por empresa e uma de total (SPEC 8)."""
    if df.empty:
        return df
    p = df.pivot_table(index=indice, columns="raiz", values=valor, aggfunc="sum", fill_value=0.0)
    p.columns = [nomes.get(c, c) for c in p.columns]
    if len(p.columns) > 1:
        p["Total"] = p.sum(axis=1)
    return p.reset_index()


def aviso_sem_dados() -> None:
    st.warning("Nenhuma EFD carregada. Use a tela '1. Carga de arquivos'.")


VISOES = ["Completa", "Só saídas", "Só entradas"]


def seletor_visao() -> str:
    """Visao do beneficio: completa, so o efeito das saidas ou so o efeito das entradas."""
    with st.sidebar:
        return _widget_persistente(
            st.radio, "Visão do benefício", "visao", "Completa", options=VISOES,
            help="Só saídas: efeito sobre as vendas (débitos, isenções, créditos presumidos do art. 450, "
                 "ICMS). Só entradas: efeito sobre as compras (créditos presumidos dos arts. 447/449 "
                 "e, hoje, compras com isenção/suspensão — informativo).")
