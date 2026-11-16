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
    try:
        visoes.preparar(con)
        return con.execute("SELECT count(*) FROM arquivos WHERE ativo").fetchall()[0][0] > 0
    except Exception as e:  # noqa: BLE001
        logger().exception("Falha ao preparar parametros e visoes")
        st.error("Não foi possível preparar os parâmetros e as visões do banco local "
                 f"({type(e).__name__}). O detalhe técnico foi gravado em data/logs/zfm.log. "
                 "Se um CSV de parâmetros foi editado no Excel, confira as colunas; envie o log ao Claude Code.")
        st.stop()


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
    p = df.pivot_table(index=indice, columns="raiz", values=valor, aggfunc="sum", fill_value=0.0,
                       observed=True)
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


# ---------------------------------------------------------------------------
# Contexto comum das telas de analise (filtro global)
# ---------------------------------------------------------------------------
class Contexto:
    def __init__(self, con, filtro, raizes, nomes, teses, intra):
        self.con, self.filtro, self.raizes, self.nomes = con, filtro, raizes, nomes
        self.teses, self.intra = teses, intra


def filtro_periodo_estab(con: duckdb.DuckDBPyConnection, raizes: list[str]):
    """Periodo (meses de 2026) e estabelecimentos do AM, na barra lateral."""
    from . import params, qualidade
    from .filtros import Filtro
    ano = int(params.premissa_num("ano_base", 2026))
    r = con.execute("SELECT min(month(dt_ini)), max(month(dt_ini)) FROM arquivos WHERE ativo AND year(dt_ini) = ?",
                    [ano]).fetchall()[0]
    mmin, mmax = int(r[0] or 1), int(r[1] or 12)
    est = con.execute("SELECT cnpj, raiz, nome FROM v_estabelecimentos WHERE no_amazonas ORDER BY 1").df()
    est = est[est["raiz"].isin(raizes)]
    with st.sidebar:
        st.session_state.setdefault("periodo", (mmin, mmax))
        ini, fim = st.session_state["periodo"]
        ini, fim = max(1, min(ini, 12)), max(1, min(fim, 12))
        per = st.select_slider("Período (meses de %d)" % ano, options=list(range(1, 13)),
                               value=(ini, fim), format_func=lambda m: qualidade.MESES[m - 1],
                               key="_w_periodo",
                               on_change=lambda: st.session_state.update(periodo=st.session_state["_w_periodo"]),
                               help="O As Is e a base de operações são anualizados pelos meses deste período.")
        opcoes = list(est["cnpj"])
        rot = {c: f"{c} – {n}" for c, n in zip(est["cnpj"], est["nome"])}
        atual = [c for c in st.session_state.get("estabs", []) if c in opcoes]
        st.session_state["estabs"] = atual
        sel = _widget_persistente(st.multiselect, "Estabelecimentos (vazio = todos)", "estabs", [],
                                  options=opcoes, format_func=lambda c: rot.get(c, c),
                                  help="Abre a empresa por estabelecimento (CNPJ completo).")
    return Filtro(raizes=tuple(raizes), estabs=tuple(sel) if sel else None,
                  mes_ini=int(per[0]), mes_fim=int(per[1]))


def contexto(titulo: str, texto: str, intragrupo: bool = False) -> Contexto:
    """Cabecalho + barra lateral (empresas, periodo, estabelecimentos, teses). Para a tela
    se nao houver dados ou empresas."""
    cabecalho(titulo, texto)
    con = conexao()
    sel = seletor_empresas(con)
    if con is None:
        st.stop()
    if not preparar(con):
        aviso_sem_dados()
        st.stop()
    raizes = raizes_analise(con, sel)
    exigir_empresas(raizes)
    f = filtro_periodo_estab(con, raizes)
    with st.sidebar:
        st.subheader("Opções")
        teses = _widget_persistente(st.toggle, "Com teses", CHAVE_TESES, False,
                                    help="Aplica as teses cadastradas em Parâmetros > Teses.")
        intra = False
        if intragrupo:
            intra = _widget_persistente(st.toggle, "Eliminar operações entre empresas do grupo",
                                        CHAVE_INTRAGRUPO, False)
    if f.estabs:
        st.caption(f"Estabelecimentos filtrados: {len(f.estabs)} · Período: "
                   f"{f.mes_ini:02d} a {f.mes_fim:02d}")
    return Contexto(con, f, raizes, nomes_empresas(), teses, intra)


def filtros_tabela(df: pd.DataFrame, colunas: dict[str, str], chave: str, por_linha: int = 4) -> pd.DataFrame:
    """Filtros (multiselecao) sobre colunas de uma tabela; vazio = todos."""
    if df.empty:
        return df
    cols = [c for c in colunas if c in df.columns]
    linhas = [cols[i:i + por_linha] for i in range(0, len(cols), por_linha)]
    for grupo in linhas:
        caixas = st.columns(len(grupo))
        for caixa, c in zip(caixas, grupo):
            opcoes = sorted(df[c].dropna().astype(str).unique())
            sel = caixa.multiselect(colunas[c], opcoes, key=f"ft_{chave}_{c}")
            if sel:
                df = df[df[c].astype(str).isin(sel)]
    return df


def baixar_csv(df: pd.DataFrame, nome: str, rotulo: str = "Baixar CSV (abre no Excel)") -> None:
    if df is not None and not df.empty:
        st.download_button(rotulo, df.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                           file_name=f"{nome}.csv", mime="text/csv", key=f"csv_{nome}")


def cartoes(valores: dict[str, float], por_linha: int = 3) -> None:
    """Cartoes de valor em R$ (no maximo 3 por linha para nao cortar o numero)."""
    itens = list(valores.items())
    for i in range(0, len(itens), por_linha):
        cols = st.columns(por_linha)
        for c, (rotulo, v) in zip(cols, itens[i:i + por_linha]):
            c.metric(rotulo, formatar_brl_curto(v), help=formatar_brl(v))
