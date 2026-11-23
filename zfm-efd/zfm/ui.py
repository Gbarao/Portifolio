"""Componentes comuns das telas (Streamlit): estilo, barra lateral, filtros, cartoes, tabelas,
graficos, cache dos calculos e importacao em segundo plano. Tudo local (sem recursos da internet)."""
from __future__ import annotations

import contextlib
import html
from decimal import Decimal

import duckdb
import pandas as pd
import streamlit as st

from . import db
from .config import logger
from .empresas import empresas
from .filtros import Filtro

CHAVE_SELECAO = "empresas_selecionadas"
CHAVE_TODAS = "todas_empresas"
CHAVE_TESES = "com_teses"
CHAVE_INTRAGRUPO = "eliminar_intragrupo"
VISOES = ["Completa", "Só saídas", "Só entradas"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

CORES = ["#1E5A8A", "#2E8B57", "#D98E04", "#7E57C2", "#C0392B", "#5B6875", "#00838F", "#AD1457"]

# ---------------------------------------------------------------------------
# Estilo (CSS local)
# ---------------------------------------------------------------------------
_CSS = """
<style>
:root { --zfm-azul:#0F3D63; --zfm-azul2:#1E5A8A; --zfm-fundo:#F5F7FA; --zfm-borda:#E1E6ED;
        --zfm-texto:#1F2933; --zfm-sub:#5B6875; --zfm-verde:#1E7B4F; --zfm-vermelho:#B42318; }
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] {background: transparent;}
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1480px;}
section[data-testid="stSidebar"] {background: var(--zfm-fundo); border-right: 1px solid var(--zfm-borda);}
section[data-testid="stSidebar"] .block-container {padding-top: 1rem;}
.zfm-marca {font-weight:700; color:var(--zfm-azul); font-size:1.05rem; line-height:1.2; margin-bottom:.6rem;}
.zfm-marca small {display:block; font-weight:400; color:var(--zfm-sub); font-size:.74rem; margin-top:2px;}
.zfm-header {border-bottom:1px solid var(--zfm-borda); padding-bottom:.75rem; margin-bottom:1rem;}
.zfm-crumb {font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--zfm-sub);}
.zfm-header h1 {font-size:1.6rem; font-weight:650; color:var(--zfm-azul); margin:.1rem 0 0; padding:0;}
.zfm-header p {color:var(--zfm-sub); margin:.3rem 0 0; font-size:.93rem; max-width:1100px;}
.zfm-badges {margin-top:.5rem;}
.zfm-badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem;
            background:#EAF1F8; color:var(--zfm-azul2); margin:0 6px 4px 0; border:1px solid #D5E3F1;}
.zfm-badge.alerta {background:#FFF4E5; color:#8A4B00; border-color:#F5D9AE;}
.zfm-cards {display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:12px; margin:.4rem 0 1rem;}
.zfm-card {background:#fff; border:1px solid var(--zfm-borda); border-radius:10px; padding:14px 16px;
           box-shadow:0 1px 2px rgba(16,24,40,.05);}
.zfm-card .rot {font-size:.74rem; color:var(--zfm-sub); text-transform:uppercase; letter-spacing:.05em;}
.zfm-card .val {font-size:1.42rem; font-weight:650; color:var(--zfm-texto); margin-top:4px; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis;}
.zfm-card .det {font-size:.76rem; color:var(--zfm-sub); margin-top:3px;}
.zfm-card.perda .val {color:var(--zfm-vermelho);} .zfm-card.ganho .val {color:var(--zfm-verde);}
.zfm-card.destaque {border-left:4px solid var(--zfm-azul2);}
.zfm-sec {font-size:1.06rem; font-weight:620; color:var(--zfm-texto); margin:1.3rem 0 .15rem;}
.zfm-sec-sub {font-size:.84rem; color:var(--zfm-sub); margin:0 0 .55rem;}
.zfm-vazio {border:1px dashed #C9D3DF; border-radius:10px; padding:26px; text-align:center; color:var(--zfm-sub);
            background:#FBFCFE; margin:.5rem 0 1rem;}
.zfm-vazio b {color:var(--zfm-texto);}
.zfm-passos {counter-reset: passo; margin:.2rem 0 .8rem; padding:0;}
.zfm-passo {list-style:none; border:1px solid var(--zfm-borda); border-radius:8px; padding:10px 14px; margin-bottom:8px;
            background:#fff; display:flex; justify-content:space-between; align-items:center; font-size:.92rem;}
.zfm-passo .st {font-size:.78rem; padding:2px 9px; border-radius:999px;}
.zfm-passo .ok {background:#E7F5EE; color:var(--zfm-verde);} .zfm-passo .pend {background:#FFF4E5; color:#8A4B00;}
div[data-testid="stTabs"] button p {font-size:.93rem; font-weight:500;}
div[data-testid="stExpander"] details {border-radius:8px;}
div[data-testid="stMetric"] {background:#fff; border:1px solid var(--zfm-borda); border-radius:10px; padding:10px 14px;}
</style>
"""


def estilo() -> None:
    st.html(_CSS)


# ---------------------------------------------------------------------------
# Conexao, importacao em segundo plano e preparacao das analises
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _conexao_base() -> duckdb.DuckDBPyConnection:
    return db.conectar()


@st.cache_resource(show_spinner=False)
def gerenciador():
    from .importacao import Gerenciador
    return Gerenciador()


def conexao() -> duckdb.DuckDBPyConnection | None:
    """Conexao com o banco local. Cada execucao de tela usa um cursor proprio."""
    try:
        return _conexao_base().cursor()
    except duckdb.IOException:
        logger().exception("Banco local em uso")
        st.error("O banco de dados local está em uso por outra janela do programa. "
                 "Feche as outras janelas pretas do programa e abra de novo pelo iniciar.bat.")
        return None


def ao_final_da_importacao(con: duckdb.DuckDBPyConnection) -> None:
    """Depois da importacao: prepara as analises e acrescenta os cadastros novos aos parametros
    (sem apagar o que o usuario ja editou)."""
    from . import params, visoes
    visoes.preparar(con)
    params.preencher_a_partir_das_efds(con)


def importacao_rodando() -> bool:
    return gerenciador().rodando


def preparar(con: duckdb.DuckDBPyConnection) -> bool:
    """Sincroniza parametros e visoes (so reconstroi se algo mudou). Retorna False se nao ha dados.
    Durante uma importacao, usa o estado ja preparado (as analises sao atualizadas ao final)."""
    from . import visoes
    from .importacao import TRAVA_BANCO
    try:
        tem = con.execute("SELECT count(*) FROM arquivos WHERE ativo").fetchall()[0][0] > 0
        if importacao_rodando():
            return tem
        with TRAVA_BANCO:
            visoes.preparar(con)
        return tem
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ in ("StopException", "RerunException"):
            raise
        logger().exception("Falha ao preparar parametros e visoes")
        st.error("Não foi possível preparar os parâmetros e as visões do banco local "
                 f"({type(e).__name__}). O detalhe técnico foi gravado em data/logs/zfm.log. "
                 "Se um CSV de parâmetros foi editado no Excel, confira as colunas; envie o log ao Claude Code.")
        st.stop()


def analises_prontas(con: duckdb.DuckDBPyConnection) -> bool:
    """Ha analises preparadas com dados (a versao gravada tem arquivos)?"""
    from . import visoes
    partes = versao(con).split("|")
    return visoes._estado_ok(con) and len(partes) > 1 and partes[1].isdigit() and int(partes[1]) > 0


def aviso_importacao(con: duckdb.DuckDBPyConnection) -> None:
    """Durante a importacao: mostra os dados anteriores com aviso, ou para a tela se ainda nao ha nenhum."""
    if not importacao_rodando():
        return
    if not analises_prontas(con):
        vazio("Importação em andamento", "As análises ficam disponíveis quando a importação terminar. "
              "Acompanhe o progresso na barra lateral; você pode navegar livremente.")
        st.stop()
    st.info("Importação em andamento: esta tela mostra os dados importados antes dela. Os números são "
            "atualizados automaticamente ao final.", icon=":material/hourglass_top:")


def versao(con: duckdb.DuckDBPyConnection) -> str:
    try:
        r = con.execute("SELECT valor FROM _meta WHERE chave = 'versao'").fetchall()
        return r[0][0] if r else "0"
    except duckdb.Error:
        return "0"


# ---------------------------------------------------------------------------
# Cache dos calculos (por versao dos dados + filtro): trocar de tela ou de aba nao recalcula
# ---------------------------------------------------------------------------
def _executar(nome: str, f: Filtro, teses: bool, extra: tuple):
    from . import as_is, beneficio_atual, cenarios, conciliacoes, qualidade, simulacao
    con = _conexao_base().cursor()
    kw = dict(extra)
    if nome == "simular":
        return simulacao.simular(con, f, teses, kw.get("conservador"))
    if nome == "carga_anual":
        return as_is.carga_anual(con, f, teses)
    if nome == "carga_mensal":
        return as_is.carga_mensal(con, f)
    if nome == "r5":
        return as_is.reconciliacao_r5(con, f)
    if nome == "saldos":
        return as_is.saldos_credores_finais(con, f)
    if nome == "conciliacao":
        return conciliacoes.filtrar(conciliacoes.CHECAGENS[kw["q"]][1](con), f)
    if nome == "q1":
        return qualidade.q1_completude(con, mes_fim=kw.get("mes_fim"))
    if nome == "matriz":
        return cenarios.matriz(con, f)
    if nome == "resultado_cenarios":
        anual, _ = calcular("simular", f, teses, conservador=kw.get("conservador"))
        return cenarios.resultado(con, anual, f, teses, kw.get("conservador"))
    if nome == "elegibilidade":
        return con.execute(f"""
            SELECT raiz, cenario_candidato, cenario, status_elegibilidade, requisitos_falha, requisitos_insuficientes,
                   requisitos_pendentes, count(*) AS linhas, sum(valor) AS valor
            FROM v_cenarios WHERE {f.sql()} GROUP BY ALL""").df()
    if nome == "ipi_produto":
        return cenarios.ipi_por_produto(con, f, kw.get("sem_protegido", False))
    if nome == "alertas":
        return cenarios.alertas(con, f)
    if nome == "pareamento":
        from . import cruzamentos
        return cruzamentos.resumo_pareamento(con)
    if nome == "diagnostico":
        from . import cruzamentos
        return cruzamentos.diagnostico_niveis(con)
    if nome == "cobertura":
        from . import cruzamentos
        return cruzamentos.cobertura_banco(con, kw.get("so_am", True))
    if nome == "beneficio":
        return beneficio_atual.calcular(con, com_teses=teses, eliminar_intragrupo=kw.get("intra", False), f=f)
    if nome == "receita_incentivada":
        return beneficio_atual.receita_incentivada(con, kw.get("intra", False), f)
    if nome == "composicao":
        anual, _ = calcular("simular", f, teses)
        sel = anual[(anual.cenario == kw["cenario"]) & (anual.ano == kw["ano"])]
        return simulacao.composicao(sel, con, f)
    raise KeyError(nome)


@st.cache_data(show_spinner=False, max_entries=96)
def _calcular_cache(nome: str, versao_dados: str, f: Filtro, teses: bool, extra: tuple):
    return _executar(nome, f, teses, extra)


def calcular(nome: str, f: Filtro, teses: bool = False, **extra):
    v = versao(_conexao_base().cursor())
    return _calcular_cache(nome, v, f, bool(teses), tuple(sorted(extra.items())))


# ---------------------------------------------------------------------------
# Formatacao
# ---------------------------------------------------------------------------
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


def formatar_num(v, casas: int = 0) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Blocos visuais
# ---------------------------------------------------------------------------
def cabecalho(titulo: str, texto: str, secao: str = "", badges: list[str] | None = None) -> None:
    b = "".join(f'<span class="zfm-badge">{html.escape(x)}</span>' for x in (badges or []))
    st.markdown(
        f'<div class="zfm-header"><div class="zfm-crumb">{html.escape(secao)}</div>'
        f'<h1>{html.escape(titulo)}</h1><p>{html.escape(texto)}</p>'
        f'{"<div class=zfm-badges>" + b + "</div>" if b else ""}</div>', unsafe_allow_html=True)


def secao(titulo: str, sub: str = "") -> None:
    st.markdown(f'<div class="zfm-sec">{html.escape(titulo)}</div>'
                + (f'<div class="zfm-sec-sub">{html.escape(sub)}</div>' if sub else ""), unsafe_allow_html=True)


def cartoes(valores: dict, sinal: bool = False, destaque: str | None = None) -> None:
    """Cartoes de valor. valores: {rotulo: valor} ou {rotulo: (valor, detalhe)}.
    sinal=True: positivo em vermelho (perda), negativo em verde (ganho)."""
    itens = []
    for rot, v in valores.items():
        det = ""
        if isinstance(v, tuple):
            v, det = v
        if isinstance(v, str):
            txt, titulo, cls = v, v, ""
        else:
            txt, titulo = formatar_brl_curto(v), formatar_brl(v)
            cls = ("perda" if v > 0.005 else "ganho" if v < -0.005 else "") if sinal else ""
        if destaque == rot:
            cls += " destaque"
        itens.append(f'<div class="zfm-card {cls}" title="{html.escape(titulo)}"><div class="rot">'
                     f'{html.escape(rot)}</div><div class="val">{html.escape(txt)}</div>'
                     f'{f"<div class=det>{html.escape(det)}</div>" if det else ""}</div>')
    st.markdown(f'<div class="zfm-cards">{"".join(itens)}</div>', unsafe_allow_html=True)


def vazio(titulo: str, texto: str = "") -> None:
    st.markdown(f'<div class="zfm-vazio"><b>{html.escape(titulo)}</b><br>{html.escape(texto)}</div>',
                unsafe_allow_html=True)


def passos(itens: list[tuple[str, bool, str]]) -> None:
    """Checklist: (texto, concluido, detalhe)."""
    li = []
    for txt, ok, det in itens:
        st_ = '<span class="st ok">concluído</span>' if ok else '<span class="st pend">pendente</span>'
        li.append(f'<li class="zfm-passo"><span>{html.escape(txt)}'
                  f'{"<br><small style=color:#5B6875>" + html.escape(det) + "</small>" if det else ""}</span>{st_}</li>')
    st.markdown(f'<ul class="zfm-passos">{"".join(li)}</ul>', unsafe_allow_html=True)


@contextlib.contextmanager
def protegido(acao: str):
    """Mostra mensagem simples em vez de detalhe tecnico; o detalhe vai para o log."""
    try:
        yield
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ in ("StopException", "RerunException"):
            raise
        logger().exception("Erro na tela ao %s", acao)
        st.error(f"Ocorreu um problema ao {acao}. O detalhe técnico foi gravado em "
                 f"data/logs/zfm.log ({type(e).__name__}). Envie esse arquivo ao Claude Code.")


# ---------------------------------------------------------------------------
# Tabelas e graficos
# ---------------------------------------------------------------------------
ROTULOS = {
    "raiz": "Raiz CNPJ", "cnpj_estab": "Estabelecimento", "cnpj": "CNPJ", "mes": "Mês", "ano": "Ano",
    "cenario": "Cenário", "cenario_aliq": "Cenário de alíquotas", "tributo": "Tributo", "as_is": "As Is (R$)",
    "to_be": "To Be (R$)", "diferenca": "Diferença (R$)", "valor": "Valor (R$)", "documentos": "Documentos",
    "linhas": "Linhas", "empresa": "Empresa", "descricao": "Descrição", "motivo": "Motivo", "cfop": "CFOP",
    "cod_item": "Produto", "ncm": "NCM", "sentido": "Sentido", "natureza": "Natureza", "uf": "UF",
    "ocorrencias": "Ocorrências", "gravidade": "Gravidade", "tipo": "Tipo", "onde_corrigir": "Onde corrigir",
    "mensagem": "Mensagem", "arquivo_id": "Arquivo nº", "linha_num": "Linha", "nome_arquivo": "Arquivo",
    "carga": "Carga (R$)", "carga_apuracao": "Carga da apuração (R$)",
    "carga_base_operacoes": "Carga pela base (R$)", "tolerancia": "Tolerância (R$)", "fecha": "Fecha?",
    "receita_anual": "Receita anualizada (R$)", "vantagem_hoje": "Vantagem hoje (R$)",
    "vantagem_to_be": "Vantagem To Be (R$)", "perda_vantagem": "Perda de vantagem (R$)",
    "classe_ipi": "Situação do IPI", "aliq_tipi_2023": "TIPI 31/12/2023 (%)", "cp_cbs_pct": "CP CBS (%)",
    "cp_ibs_pct": "CP IBS (%)", "tipo_bem": "Tipo de bem", "beneficio": "Benefício (R$)",
    "situacao": "Situação", "cenario_candidato": "Cenário candidato", "status_elegibilidade": "Status",
    "requisitos": "Requisitos (falha, dado ausente ou não comprovado)", "estabelecimentos": "Estabelecimentos", "meses": "Meses", "faltando": "Faltando",
    "o_que_fazer": "O que fazer", "fonte": "Fonte", "problema": "Problema", "participante": "Participante",
    "num_doc": "Número", "chv_nfe": "Chave NF-e", "nivel_cruzamento": "Nível do cruzamento", "vinculo": "Vínculo",
    "pct_linhas": "% das linhas", "pis": "PIS (R$)", "cofins": "COFINS (R$)", "cnpj_part": "CNPJ participante", "uf_part": "UF participante",
}


def _rotulo(c: str) -> str:
    return ROTULOS.get(c, str(c).replace("_", " ").strip().capitalize() if str(c).islower() else str(c))


def tabela(df: pd.DataFrame | None, moeda: list[str] | None = None, pct: list[str] | None = None,
           altura: int | None = None, limite: int = 3000, chave: str | None = None) -> None:
    """Tabela rapida (sem estilos pesados), numeros no formato do navegador (pt-BR: 1.234,56)."""
    if df is None or df.empty:
        st.caption("Sem dados para a seleção.")
        return
    total = len(df)
    if total > limite:
        df = df.head(limite)
        st.caption(f"Mostrando {formatar_num(limite)} de {formatar_num(total)} linhas. Use os filtros ou "
                   "baixe o CSV para ver todas.")
    pct = pct or []
    if moeda is None:
        moeda = [c for c in df.columns if pd.api.types.is_float_dtype(df[c]) and c not in pct]
    cfg = {}
    for c in df.columns:
        cfg[c] = st.column_config.Column(_rotulo(c))
        if c in moeda:
            cfg[c] = st.column_config.NumberColumn(_rotulo(c), format="localized")
        elif c in pct:
            cfg[c] = st.column_config.NumberColumn(_rotulo(c), format="%.2f%%")
        elif pd.api.types.is_bool_dtype(df[c]):
            cfg[c] = st.column_config.CheckboxColumn(_rotulo(c))
    kw = {"height": altura} if altura else {}
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg, key=chave, **kw)


def por_empresa(df: pd.DataFrame, indice: list[str], valor: str, nomes: dict[str, str]) -> pd.DataFrame:
    """Uma coluna por empresa e uma de total."""
    if df is None or df.empty:
        return pd.DataFrame()
    p = df.pivot_table(index=indice, columns="raiz", values=valor, aggfunc="sum", fill_value=0.0, observed=True)
    p.columns = [nomes.get(c, c) for c in p.columns]
    if len(p.columns) > 1:
        p["Total"] = p.sum(axis=1)
    return p.reset_index()


def grafico(fig, altura: int = 380) -> None:
    fig.update_layout(height=altura, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="white",
                      plot_bgcolor="white", font=dict(family="Segoe UI, Arial, sans-serif", size=12,
                                                       color="#1F2933"),
                      colorway=CORES, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      separators=",.")
    fig.update_xaxes(showgrid=False, linecolor="#E1E6ED")
    fig.update_yaxes(gridcolor="#EEF1F5", zerolinecolor="#C9D3DF")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def baixar_csv(df: pd.DataFrame, nome: str, rotulo: str = "Baixar CSV") -> None:
    if df is not None and not df.empty:
        st.download_button(rotulo, df.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                           file_name=f"{nome}.csv", mime="text/csv", key=f"csv_{nome}",
                           icon=":material/download:")


def filtros_tabela(df: pd.DataFrame, colunas: dict[str, str], chave: str, por_linha: int = 4) -> pd.DataFrame:
    """Filtros (multiselecao) sobre colunas de uma tabela ja agregada; vazio = todos."""
    if df is None or df.empty:
        return df
    cols = [c for c in colunas if c in df.columns]
    for i in range(0, len(cols), por_linha):
        grupo = cols[i:i + por_linha]
        caixas = st.columns(por_linha)
        for caixa, c in zip(caixas, grupo):
            opcoes = sorted(df[c].dropna().astype(str).unique())
            sel = caixa.multiselect(colunas[c], opcoes, key=f"ft_{chave}_{c}", placeholder="Todos")
            if sel:
                df = df[df[c].astype(str).isin(sel)]
    return df


def filtros_sql(con: duckdb.DuckDBPyConnection, tabela_sql: str, colunas: dict[str, str], chave: str,
                onde: str = "TRUE", por_linha: int = 4) -> str:
    """Filtros cujas opcoes vem do banco (SELECT DISTINCT); devolve a condicao SQL."""
    conds = []
    cols = list(colunas)
    for i in range(0, len(cols), por_linha):
        caixas = st.columns(por_linha)
        for caixa, c in zip(caixas, cols[i:i + por_linha]):
            ops = [r[0] for r in con.execute(
                f"SELECT DISTINCT CAST({c} AS VARCHAR) FROM {tabela_sql} WHERE {onde} AND {c} IS NOT NULL "
                f"ORDER BY 1 LIMIT 2000").fetchall()]
            sel = caixa.multiselect(colunas[c], ops, key=f"fs_{chave}_{c}", placeholder="Todos")
            if sel:
                lista = ", ".join("'" + str(x).replace("'", "''") + "'" for x in sel)
                conds.append(f"CAST({c} AS VARCHAR) IN ({lista})")
    return " AND ".join(conds) if conds else "TRUE"


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
def _widget_persistente(widget, rotulo: str, chave: str, padrao, **kw):
    """Widget cujo valor sobrevive a troca de pagina (o valor fica numa chave propria)."""
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


def marca() -> None:
    with st.sidebar:
        st.markdown('<div class="zfm-marca">ZFM × Reforma Tributária<small>Análise As Is × To Be · '
                    'execução local, nenhum dado sai do computador</small></div>', unsafe_allow_html=True)
        status_importacao()


@st.fragment(run_every=2)
def status_importacao() -> None:
    """Cartao de progresso da importacao em segundo plano (atualiza sozinho)."""
    g = gerenciador()
    job = g.atual
    if job is None:
        return
    r = job.resumo()
    if r["rodando"]:
        if r["n_feitos"] >= r["n_total"]:
            txt = f"Preparando as análises · {int(r['progresso'] * 100)}%"
        else:
            txt = f"Importando {r['n_feitos'] + 1} de {r['n_total']} · {int(r['progresso'] * 100)}%"
        st.progress(r["progresso"], text=txt)
        st.caption(f"{r['atual'] or r['etapa']} · pode navegar à vontade; a importação continua.")
    elif st.session_state.get("_import_visto") != id(job):
        if r["etapa"] == "concluída":
            st.success(f"Importação concluída: {r['n_carregados']} arquivo(s) novo(s).", icon=":material/check_circle:")
            try:
                from . import cruzamentos
                n = len(cruzamentos.faltas(cruzamentos.cobertura_banco(_conexao_base().cursor())))
                if n:
                    st.warning(f"{n} escrituração(ões) faltando (EFD ICMS/IPI ou Contribuições). Veja a tela "
                               "Importação.", icon=":material/warning:")
            except Exception:  # noqa: BLE001
                logger().exception("Falha ao validar a cobertura")
        elif r["erro_final"]:
            st.error("Importação interrompida. Veja a tela Importação.", icon=":material/error:")


def seletor_empresas(con: duckdb.DuckDBPyConnection | None) -> list[str] | None:
    """Retorna as raizes de CNPJ selecionadas (None = todas, consolidado)."""
    with st.sidebar:
        st.markdown("**Empresas**")
        if con is None:
            return None
        emp = empresas(con)
        if emp.empty:
            st.caption("Nenhuma empresa ainda. Importe as EFDs.")
            return None
        rotulos = {r.raiz: f"{r.razao_social} ({r.raiz})" for r in emp.itertuples()}
        todas = _widget_persistente(st.checkbox, "Todas as empresas (consolidado)", CHAVE_TODAS, True)
        if todas:
            return None
        atual = [r for r in st.session_state.get(CHAVE_SELECAO, []) if r in rotulos]
        st.session_state[CHAVE_SELECAO] = atual
        return _widget_persistente(st.multiselect, "Escolha uma ou várias", CHAVE_SELECAO, [],
                                   options=list(rotulos), format_func=lambda r: rotulos[r],
                                   placeholder="Selecione")


def raizes_analise(con: duckdb.DuckDBPyConnection, selecao: list[str] | None) -> list[str]:
    """Selecao da barra lateral ∩ 'incluir na analise' (Parametros > Empresas)."""
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


class Contexto:
    def __init__(self, con, filtro, raizes, nomes, teses, intra, ano):
        self.con, self.filtro, self.raizes, self.nomes = con, filtro, raizes, nomes
        self.teses, self.intra, self.ano = teses, intra, ano

    def nome(self, raiz: str) -> str:
        return self.nomes.get(raiz, raiz)


def _periodo_estab(con: duckdb.DuckDBPyConnection, raizes: list[str]):
    from . import params
    ano = params.ano_base(con)
    r = con.execute("SELECT min(month(dt_ini)), max(month(dt_ini)) FROM arquivos WHERE ativo AND year(dt_ini) = ?",
                    [ano]).fetchall()[0]
    mmin, mmax = int(r[0] or 1), int(r[1] or 12)
    est = con.execute("SELECT cnpj, raiz, nome FROM v_estabelecimentos WHERE no_amazonas ORDER BY 1").df()
    est = est[est["raiz"].isin(raizes)]
    with st.sidebar:
        st.markdown("**Período e estabelecimentos**")
        ini, fim = st.session_state.get("periodo", (mmin, mmax))
        # novos meses carregados ampliam o periodo automaticamente
        if st.session_state.get("_periodo_max") != mmax:
            ini, fim = mmin, mmax
            st.session_state["_periodo_max"] = mmax
        ini, fim = max(1, min(ini, 12)), max(1, min(fim, 12))
        st.session_state["periodo"] = (ini, fim)
        per = st.select_slider(f"Meses de {ano}", options=list(range(1, 13)), value=(ini, fim),
                               format_func=lambda m: MESES[m - 1], key="_w_periodo",
                               on_change=lambda: st.session_state.update(periodo=st.session_state["_w_periodo"]),
                               help="O As Is e a base de operações são anualizados pelos meses deste período.")
        opcoes = list(est["cnpj"])
        rot = {c: f"{c} – {n}" for c, n in zip(est["cnpj"], est["nome"])}
        st.session_state["estabs"] = [c for c in st.session_state.get("estabs", []) if c in opcoes]
        sel = _widget_persistente(st.multiselect, "Estabelecimentos", "estabs", [], options=opcoes,
                                  format_func=lambda c: rot.get(c, c), placeholder="Todos",
                                  help="Abre a empresa por estabelecimento (CNPJ completo + IE).")
    return ano, Filtro(raizes=tuple(raizes), estabs=tuple(sel) if sel else None,
                       mes_ini=int(per[0]), mes_fim=int(per[1]))


def contexto(titulo: str, texto: str, secao_nome: str = "", intragrupo: bool = False) -> Contexto:
    """Cabecalho + barra lateral (empresas, periodo, estabelecimentos, opcoes). Para a tela se nao
    houver dados, explicando o motivo."""
    marca()
    con = conexao()
    if con is None:
        st.stop()
    sel = seletor_empresas(con)
    tem = preparar(con)
    if not tem or (importacao_rodando() and not analises_prontas(con)):
        cabecalho(titulo, texto, secao_nome)
        aviso_importacao(con)
        vazio("Nenhuma EFD carregada", "Use a tela Importação para ler os arquivos .txt das EFDs.")
        st.stop()
    raizes = raizes_analise(con, sel)
    if not raizes:
        cabecalho(titulo, texto, secao_nome)
        vazio("Nenhuma empresa selecionada",
              "Marque 'Todas as empresas' na barra lateral ou escolha empresas. Empresas marcadas para não "
              "entrar na análise (Parâmetros > Empresas) não aparecem.")
        st.stop()
    ano, f = _periodo_estab(con, raizes)
    with st.sidebar:
        st.markdown("**Opções**")
        teses = _widget_persistente(st.toggle, "Com teses", CHAVE_TESES, False,
                                    help="Aplica as teses cadastradas em Parâmetros > Teses.")
        intra = False
        if intragrupo:
            intra = _widget_persistente(st.toggle, "Eliminar operações entre empresas do grupo",
                                        CHAVE_INTRAGRUPO, False)
    nomes = nomes_empresas()
    sel_txt = "Consolidado do grupo" if sel is None else ", ".join(nomes.get(r, r) for r in raizes)
    badges = [sel_txt, f"{MESES[f.mes_ini - 1]}–{MESES[f.mes_fim - 1]}/{ano}"]
    if f.estabs:
        badges.append(f"{len(f.estabs)} estabelecimento(s)")
    if teses:
        badges.append("com teses")
    if importacao_rodando():
        badges.append("importação em andamento")
    cabecalho(titulo, texto, secao_nome, badges)
    aviso_importacao(con)
    return Contexto(con, f, raizes, nomes, teses, intra, ano)
