# -*- coding: utf-8 -*-
"""
Consolidador EFD — interface.

Execute com:   python iniciar.py      (ou:  streamlit run app.py)

A interface roda no navegador, mas tudo acontece neste computador: os
arquivos são lidos do disco local e a base fica gravada em disco (por padrão
em Documentos/Consolidador EFD). Fechar o programa ou desligar o computador
não apaga nada. Nenhum dado é enviado para fora.
"""

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from efd import __version__, base, comando_modulo, comparacao, consulta, empacotado  # noqa: E402
from efd.leiautes import (ATENCAO, CONTRIB, FISCAL, MEDIDAS_PADRAO, NOME_FONTE,  # noqa: E402
                          ROTULO_MEDIDA, ROTULO_PAREAMENTO)


def _pasta_base_padrao() -> str:
    """Pasta permanente da base: Documentos/Consolidador EFD. Uma base criada pela
    versão anterior (pasta base/ ao lado do programa) continua sendo usada."""
    antiga = os.path.join(APP_DIR, "base")
    if not empacotado() and os.path.isfile(os.path.join(antiga, "efd.duckdb")):
        return antiga
    casa = os.path.expanduser("~")
    docs = os.path.join(casa, "Documents")
    return os.path.join(docs if os.path.isdir(docs) else casa, "Consolidador EFD")


PASTA_BASE = os.environ.get("EFD_BASE") or _pasta_base_padrao()
ARQ_DB = os.path.join(PASTA_BASE, "efd.duckdb")
ARQ_CFG = os.path.join(PASTA_BASE, "filtros_e_campos.json")
ARQ_ESTADO = os.path.join(PASTA_BASE, "ultima_visao.json")

st.set_page_config(page_title="Consolidador EFD", page_icon=":material/receipt_long:",
                   layout="wide")


# ============================================================================
# Utilitários
# ============================================================================

@st.cache_resource(show_spinner=False)
def _abrir_base():
    return base.abrir(ARQ_DB)


def conexao():
    try:
        return _abrir_base()
    except Exception as e:
        if "lock" in str(e).lower():
            st.error("A base de dados já está aberta por outra janela do Consolidador EFD "
                     "(ou por outro programa). Feche a outra janela e recarregue esta página.")
        else:
            st.error(f"Não foi possível abrir a base em {ARQ_DB}: {e}")
        st.stop()


def versao() -> str:
    return base.estado(conexao(), "versao", "0")


def br(x, casas=2) -> str:
    """Número no padrão brasileiro (1.234,56)."""
    if x is None or (isinstance(x, float) and x != x):
        return ""
    return f"{float(x):,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def inteiro(x) -> str:
    return "" if x is None else f"{int(x):,}".replace(",", ".")


def mascara(doc) -> str:
    d = str(doc or "")
    if len(d) == 14 and d.isdigit():
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11 and d.isdigit():
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 8 and d.isdigit():
        return f"{d[:2]}.{d[2:5]}.{d[5:]}"
    return d


def mes(d) -> str:
    return "" if d is None or d != d else pd.Timestamp(d).strftime("%m/%Y")


def curto(campo_id: str) -> str:
    return consulta.CAMPOS[campo_id]["rotulo"].split(" (")[0]


def medida_curta(m: str, f: str) -> str:
    return f"{m.upper()} · {'Fiscal' if f == FISCAL else 'Contribuições'}"


NOME_JUNTO = {"empresa_nome": "Nome da empresa", "part_nome": "Nome do fornecedor",
              "estab_nome": "Nome do estabelecimento",
              "descr_item": "Descrição do item", "cfop_descricao": "Descrição do CFOP",
              "cfop_conc_descricao": "Descrição do CFOP conciliado",
              "chave": "Chave eletrônica", "n_linhas": "Linhas"}
ACAO = {"CARREGAR": "Carregar", "JA_CARREGADO": "Já está na base", "IGNORADO": "Ignorar",
        "CONFLITO": "Bloqueado", "INVALIDO": "Inválido"}


@st.cache_data(show_spinner=False)
def opcoes(campo_id: str, _versao: str):
    return consulta.valores_distintos(conexao(), campo_id)


def base_vazia() -> bool:
    return conexao().cursor().execute("SELECT count(*) FROM arquivos").fetchone()[0] == 0


def abrir_dialogo(modo: str):
    """Abre a janela nativa de seleção em outro processo. Devolve (caminhos, erro)."""
    try:
        r = subprocess.run(comando_modulo("efd.seletor", modo), capture_output=True,
                           text=True, cwd=APP_DIR, timeout=900,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        dados = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return [], ("Não foi possível abrir a janela de seleção neste ambiente. "
                    "Cole os caminhos no campo abaixo.")
    return dados.get("caminhos", []), dados.get("erro", "")


def arquivos_da_pasta(pasta: str) -> list[str]:
    achados = []
    for raiz, _, nomes in os.walk(pasta):
        achados += [os.path.join(raiz, n) for n in nomes if n.lower().endswith(".txt")]
    return sorted(achados)


def tabela(dados, **kw):
    """st.dataframe com célula vazia em branco (o padrão seria mostrar "None")."""
    kw.setdefault("placeholder", "")
    return st.dataframe(dados, **kw)


TITULOS = {
    "nome_arquivo": "Arquivo", "num_doc": "NUM_DOC", "chave": "Chave eletrônica",
    "part_nome": "Fornecedor", "num_item": "NUM_ITEM", "cfop": "CFOP", "fonte": "Escrituração",
    "registro": "Registro", "dt_doc": "DT_DOC", "vl_doc": "VL_DOC", "ocorrencia": "Ocorrência",
    "n_ocorrencias": "Total de ocorrências", "periodo": "Período do arquivo",
    "linha_no_arquivo": "Linha no arquivo", "situacao": "Situação", "cod_item": "COD_ITEM",
    "descr_item": "Descrição", "vl_item": "VL_ITEM", "vl_pis": "VL_PIS",
    "vl_cofins": "VL_COFINS", "vezes": "Vezes", "documento": "Identificação do documento",
    "bc_c170": "VL_BC_ICMS · soma dos C170", "bc_c190": "VL_BC_ICMS · C190",
    "icms_c170": "VL_ICMS · soma dos C170", "icms_c190": "VL_ICMS · C190",
    "st_c170": "VL_ICMS_ST · soma dos C170", "st_c190": "VL_ICMS_ST · C190",
    "ipi_c170": "VL_IPI · soma dos C170", "ipi_c190": "VL_IPI · C190",
}


def titulos(df: pd.DataFrame) -> pd.DataFrame:
    """Nomes de coluna legíveis (x_fiscal -> X · Fiscal, x_contrib -> X · Contribuições)."""
    def nome(c):
        if c in TITULOS:
            return TITULOS[c]
        if c.endswith("_fiscal"):
            return f"{c[:-7].upper()} · Fiscal"
        if c.endswith("_contrib"):
            return f"{c[:-8].upper()} · Contribuições"
        return c
    return df.rename(columns={c: nome(c) for c in df.columns})


def dinheiro(df: pd.DataFrame) -> dict:
    return {c: br for c in df.columns if c.startswith("VL_")}


def data_br(d) -> str:
    return "" if d is None or d != d else pd.Timestamp(d).strftime("%d/%m/%Y")


def baixar(rotulo, dados, nome, mime, chave):
    st.download_button(rotulo, data=dados, file_name=nome, mime=mime, key=chave)


def csv_bytes(df) -> bytes:
    return df.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")


def gravar_json(caminho: str, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, caminho)


def ler_json(caminho: str):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ============================================================================
# Empresa / estabelecimento (vale para a Visão e para as Conferências)
# ============================================================================

def seletor_escopo(con, v):
    """Seletor no topo da página. Devolve (raízes, estabelecimentos)."""
    @st.cache_data(show_spinner=False)
    def _opcoes(_v):
        return base.empresas_e_estabelecimentos(conexao())

    ops = _opcoes(v)
    rotulos = {}
    for tipo, cod, nome in ops:
        if tipo == "E":
            rotulos[f"E:{cod}"] = f"Empresa {mascara(cod)} · {nome} (todos os estabelecimentos)"
        else:
            rotulos[f"S:{cod}"] = f"Estabelecimento {mascara(cod)} · {nome}"
    atual = [x for x in st.session_state.get("escopo", []) if x in rotulos]
    if st.session_state.get("w_escopo") is None or \
            any(x not in rotulos for x in st.session_state.get("w_escopo", [])):
        st.session_state["w_escopo"] = atual

    def _copiar():
        st.session_state["escopo"] = list(st.session_state["w_escopo"])

    escolhidos = st.multiselect(
        "Empresa ou estabelecimento", list(rotulos), format_func=rotulos.get, key="w_escopo",
        on_change=_copiar, placeholder="Todas as empresas e estabelecimentos (digite o CNPJ ou o nome para buscar)",
        help="Escolha uma empresa inteira (matriz e filiais) ou estabelecimentos específicos. "
             "Toda a consolidação e as conferências passam a considerar só essa escolha.")
    st.session_state["escopo"] = list(escolhidos)
    raizes = [x[2:] for x in escolhidos if x.startswith("E:")]
    estabs = [x[2:] for x in escolhidos if x.startswith("S:")]
    return raizes, estabs


def filtro_escopo(raizes, estabs) -> list:
    conds = []
    if raizes:
        conds.append({"grupo": 1, "campo": "empresa", "operador": "em", "valor": raizes})
    if estabs:
        conds.append({"grupo": 2, "campo": "estab", "operador": "em", "valor": estabs})
    return [conds] if conds else []


# ============================================================================
# Memória da tela: a última visão é gravada em disco e reaberta
# ============================================================================

CHAVES_VISAO = ("v_dims", "v_medidas", "v_calcs", "v_ordem", "v_sentido", "v_limite",
                "f_periodo", "f_fornecedor", "f_cfop_conc", "f_item", "f_pareamento",
                "f_salvos", "escopo", "busca_tabela", "filtros_tabela")


def restaurar_estado():
    """Recoloca na sessão os valores da última visão (gravados em disco)."""
    est = st.session_state.get("_estado_visao")
    if est is None:
        est = ler_json(ARQ_ESTADO) or {}
        st.session_state["_estado_visao"] = est
    for k, valor in est.items():
        if k in CHAVES_VISAO and k not in st.session_state:
            st.session_state[k] = valor


def guardar_estado():
    est = {k: st.session_state[k] for k in CHAVES_VISAO if k in st.session_state}
    if est != st.session_state.get("_estado_visao"):
        st.session_state["_estado_visao"] = est
        try:
            gravar_json(ARQ_ESTADO, est)
        except OSError:
            pass


def aplicar_visao(estado: dict):
    """Callback: troca a tela pela visão salva (roda antes de recriar os widgets)."""
    for k in CHAVES_VISAO:
        st.session_state.pop(k, None)
    st.session_state.pop("w_escopo", None)
    for k, valor in estado.items():
        if k in CHAVES_VISAO:
            st.session_state[k] = valor


# ============================================================================
# Pop-up: linhas do TXT lado a lado
# ============================================================================

COR_DIF = "background-color: #fde2e1"
COR_FOCO = "background-color: #fff4cc"


def _rotulo_lado(o) -> str:
    fonte, _, linha_doc, ocorr, n_oc, _, periodo, nome_arq, cnpj = o
    extra = f" · ocorrência {ocorr} de {n_oc}" if n_oc > 1 else ""
    return (f"**{NOME_FONTE[fonte]}**{extra}  \n{nome_arq} · período {mes(periodo)} · "
            f"estabelecimento {mascara(cnpj)}")


def _mostrar_linhas(con, arquivo_id, linha_doc, destacar=(), foco=()):
    linhas = base.linhas_documento(con, arquivo_id, linha_doc)
    if not linhas:
        st.warning("O texto original deste arquivo não está na base (ele foi carregado por uma "
                   "versão anterior do programa). Remova e carregue o arquivo de novo para ver as linhas.")
        return linhas
    df = pd.DataFrame(linhas, columns=["Linha", "Registro", "Texto do TXT"])

    def cor(row):
        if row["Linha"] in destacar:
            return [COR_DIF] * len(row)
        if row["Linha"] in foco:
            return [COR_FOCO] * len(row)
        return [""] * len(row)

    tabela(df.style.apply(cor, axis=1), hide_index=True, width="stretch",
           height=min(420, 40 + 35 * len(df)),
           column_config={"Linha": st.column_config.NumberColumn(format="%d", width="small"),
                          "Registro": st.column_config.TextColumn(width="small"),
                          "Texto do TXT": st.column_config.TextColumn(width="large")})
    return linhas


def _tabela_comparacao(comp, nome_a, nome_b):
    if not comp:
        st.info("Não há registros em comum para comparar campo a campo.")
        return
    so_dif = st.toggle("Mostrar só o que é diferente", value=True, key="pop_so_dif")
    df = pd.DataFrame(comp)
    if so_dif:
        df = df[df["situacao"] != comparacao.IGUAL]
    if df.empty:
        st.success("Todos os campos em comum são iguais nas duas linhas.")
        return
    df = df.rename(columns={"registro": "Registro", "referencia": "Item", "campo": "Campo",
                            "valor_a": nome_a, "valor_b": nome_b, "situacao": "Situação",
                            "linha_a": f"Linha · {nome_a}", "linha_b": f"Linha · {nome_b}"})

    def cor(row):
        return [COR_DIF if row["Situação"] == comparacao.DIFERENTE else ""] * len(row)

    tabela(df.style.apply(cor, axis=1), hide_index=True, width="stretch",
           height=min(380, 40 + 35 * len(df)))


@st.dialog("Linhas do TXT", width="large")
def popup_documento(empresa_raiz, doc_id, destaque_cfop=None, mensagem=""):
    """Mostra o documento como está nos TXT: EFD Contribuições à esquerda e
    EFD Fiscal à direita (ou as duas ocorrências, se for repetição)."""
    con = conexao()
    ocorr = base.ocorrencias_documento(con, empresa_raiz, doc_id)
    if not ocorr:
        st.warning("Documento não encontrado na base.")
        return
    if mensagem:
        st.caption(mensagem)
    contrib = [o for o in ocorr if o[0] == CONTRIB]
    fiscal = [o for o in ocorr if o[0] == FISCAL]
    if contrib and fiscal:
        lado_a, lado_b = contrib[0], fiscal[0]
    elif len(ocorr) > 1:
        lado_a, lado_b = ocorr[0], ocorr[1]
    else:
        lado_a, lado_b = ocorr[0], None

    if lado_b is None:
        st.markdown(_rotulo_lado(lado_a))
        foco = set()
        linhas = base.linhas_documento(con, lado_a[1], lado_a[2])
        if destaque_cfop:
            foco = {n for n, reg, txt in linhas if f"|{destaque_cfop}|" in txt}
        _mostrar_linhas(con, lado_a[1], lado_a[2], foco=foco)
        if destaque_cfop:
            st.caption(f"Em amarelo: linhas com o CFOP {destaque_cfop}.")
        st.info("Este documento só está em uma escrituração na base.")
        return

    texto_a = base.linhas_documento(con, lado_a[1], lado_a[2])
    texto_b = base.linhas_documento(con, lado_b[1], lado_b[2])
    comp, div_a, div_b = comparacao.comparar({"fonte": lado_a[0], "linhas": texto_a},
                                             {"fonte": lado_b[0], "linhas": texto_b})
    n_dif = sum(1 for c in comp if c["situacao"] == comparacao.DIFERENTE)
    if n_dif:
        st.error(f"{n_dif} campo(s) com conteúdo diferente. As linhas com diferença estão em vermelho.")
    elif comp:
        st.success("Os campos em comum têm o mesmo conteúdo nas duas linhas.")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(_rotulo_lado(lado_a))
        _mostrar_linhas(con, lado_a[1], lado_a[2], destacar=div_a)
    with col_b:
        st.markdown(_rotulo_lado(lado_b))
        _mostrar_linhas(con, lado_b[1], lado_b[2], destacar=div_b)

    nome_a = NOME_FONTE[lado_a[0]] if lado_a[0] != lado_b[0] else f"Ocorrência {lado_a[3]}"
    nome_b = NOME_FONTE[lado_b[0]] if lado_a[0] != lado_b[0] else f"Ocorrência {lado_b[3]}"
    if div_a or div_b:
        st.markdown("**Linhas com diferença, como estão nos arquivos**")
        por_linha_a = {n: t for n, _, t in texto_a}
        por_linha_b = {n: t for n, _, t in texto_b}
        pares = sorted({(c["linha_a"], c["linha_b"]) for c in comp
                        if c["situacao"] == comparacao.DIFERENTE})
        for la, lb in pares:
            if la in por_linha_a:
                st.caption(f"{nome_a} · linha {la}")
                st.code(por_linha_a[la], language=None, wrap_lines=True)
            if lb in por_linha_b:
                st.caption(f"{nome_b} · linha {lb}")
                st.code(por_linha_b[lb], language=None, wrap_lines=True)
    st.markdown("**Campo a campo**")
    _tabela_comparacao(comp, nome_a, nome_b)
    st.caption("Números são comparados pelo valor (1000,00 = 1000,0). Campo vazio de um lado "
               "aparece como \"informado só de um lado\". COD_PART e COD_ITEM são códigos "
               "internos de cada arquivo e podem ser diferentes sem erro.")


@st.dialog("Linha do TXT", width="large")
def popup_linha(arquivo_id, linha, mensagem=""):
    con = conexao()
    if mensagem:
        st.caption(mensagem)
    for n, reg, texto in base.linha_txt(con, arquivo_id, linha):
        st.caption(f"Linha {n} · registro {reg}")
        st.code(texto, language=None, wrap_lines=True)


def tabela_com_popup(df_tela, df_ref, chave, ao_selecionar, **kw):
    """Tabela em que selecionar uma linha abre o pop-up. df_ref tem as referências
    (mesma ordem de df_tela); colunas iniciadas por "_" ficam ocultas."""
    colunas = getattr(df_tela, "data", df_tela).columns       # aceita DataFrame ou Styler
    visiveis = [c for c in colunas if not str(c).startswith("_")]
    evento = tabela(df_tela, hide_index=True, width="stretch", on_select="rerun",
                    selection_mode="single-row", key=chave, column_order=visiveis, **kw)
    linhas = evento.selection.rows if evento and evento.selection else []
    marca = (chave, linhas[0]) if linhas else None
    c1, _ = st.columns([1.4, 5])
    abrir = c1.button("Ver linhas do TXT da linha selecionada", key=f"bt_{chave}",
                      disabled=not linhas)
    if linhas and linhas[0] < len(df_ref) and (abrir or st.session_state.get(f"_ult_{chave}") != marca):
        st.session_state[f"_ult_{chave}"] = marca
        ao_selecionar(df_ref.iloc[linhas[0]])
    elif not linhas:
        st.session_state[f"_ult_{chave}"] = None
    st.caption("Selecione uma linha (caixa à esquerda) para ver as linhas do TXT.")


# ============================================================================
# Página: Carregar EFDs
# ============================================================================

def _adicionar(caminhos):
    sel = st.session_state.setdefault("selecionados", [])
    for c in caminhos:
        c = c.strip().strip('"')
        if not c:
            continue
        novos = arquivos_da_pasta(c) if os.path.isdir(c) else [c]
        for n in novos:
            n = os.path.abspath(n)
            if n not in sel:
                sel.append(n)
    st.session_state.pop("plano", None)


def pagina_carregar():
    con = conexao()
    st.title("Carregar EFDs")
    st.write("Selecione os arquivos `.txt` da **EFD ICMS/IPI (Fiscal)** e da "
             "**EFD-Contribuições**, de qualquer empresa e período, todos de uma vez. "
             "O tipo de cada arquivo é reconhecido pelo registro 0000. Só as **entradas** "
             "são carregadas.")

    resultado = st.session_state.pop("resultado_carga", None)
    if resultado:
        ok = [r for r in resultado["res"] if r["ok"]]
        ruins = [r for r in resultado["res"] if not r["ok"]]
        if ok:
            st.success(f"{len(ok)} arquivo(s) carregado(s) e conferido(s) em "
                       f"{br(resultado['segundos'], 1)} s: "
                       + "; ".join(f"{r['nome_arquivo']} ({inteiro(r['linhas'])} linhas)" for r in ok))
        for r in ruins:
            st.error(f"{r['nome_arquivo']}: {r['mensagem']}")
        for nome, acao, motivo in resultado["fora"]:
            st.warning(f"{nome} — {ACAO[acao]}: {motivo}")

    c1, c2, _ = st.columns([1.3, 1.3, 4])
    if c1.button("Selecionar arquivos…", type="primary", width="stretch"):
        caminhos, erro = abrir_dialogo("arquivos")
        _adicionar(caminhos)
        st.session_state["erro_dialogo"] = erro
    if c2.button("Selecionar pasta…", width="stretch"):
        caminhos, erro = abrir_dialogo("pasta")
        _adicionar(caminhos)
        st.session_state["erro_dialogo"] = erro
    erro = st.session_state.get("erro_dialogo")
    if erro:
        st.warning(erro)
    with st.expander("Colar caminhos de arquivos ou de uma pasta", expanded=bool(erro)):
        texto = st.text_area("Um caminho por linha (uma pasta inclui todos os .txt dentro dela)",
                             key="caminhos_colados", height=110)
        if st.button("Adicionar à seleção"):
            _adicionar(texto.splitlines())
            st.rerun()

    sel = st.session_state.get("selecionados", [])
    if sel:
        chave = (tuple(sel), versao())
        if st.session_state.get("plano", (None, None))[0] != chave:
            with st.spinner(f"Identificando {len(sel)} arquivo(s)…"):
                st.session_state["plano"] = (chave, base.planejar(con, sel))
        plano = st.session_state["plano"][1]
        linhas = []
        for p in plano:
            i = p["info"]
            linhas.append({
                "Arquivo": i["nome_arquivo"],
                "Escrituração": NOME_FONTE.get(i.get("tipo"), "—"),
                "Empresa": i.get("nome", ""),
                "CNPJ": mascara(i.get("cnpj", "")),
                "Período": (f"{pd.Timestamp(i['dt_ini']).strftime('%d/%m/%Y')} a "
                            f"{pd.Timestamp(i['dt_fin']).strftime('%d/%m/%Y')}") if i.get("dt_ini") else "",
                "Finalidade": ("Retificadora" if i.get("retificadora") else "Original") if i.get("tipo") else "",
                "Tamanho (MB)": round(i.get("tamanho", 0) / 1e6, 1),
                "O que será feito": ACAO[p["acao"]],
                "Observação": p["motivo"],
            })
        st.subheader("Arquivos selecionados")
        tabela(pd.DataFrame(linhas), hide_index=True, width="stretch")
        n = sum(1 for p in plano if p["acao"] == "CARREGAR")
        bloqueados = sum(1 for p in plano if p["acao"] == "CONFLITO")
        if bloqueados:
            st.error(f"{bloqueados} arquivo(s) bloqueado(s): há mais de uma versão da mesma "
                     "escrituração para o mesmo período. Veja a coluna Observação.")
        b1, b2, _ = st.columns([1.6, 1.2, 4])
        if b1.button(f"Carregar {n} arquivo(s) na base", type="primary", disabled=n == 0,
                     width="stretch"):
            barra = st.progress(0.0, text="Lendo os arquivos…")

            def progresso(feitos, total, nome):
                barra.progress(feitos / total, text=f"Lido {feitos} de {total}: {nome}")

            t0 = time.time()
            res = base.carregar(con, plano, PASTA_BASE, progresso=progresso)
            st.session_state["resultado_carga"] = {
                "res": res, "segundos": time.time() - t0,
                "fora": [(p["info"]["nome_arquivo"], p["acao"], p["motivo"])
                         for p in plano if p["acao"] in ("CONFLITO", "INVALIDO")]}
            st.session_state["selecionados"] = []
            st.session_state.pop("plano", None)
            st.cache_data.clear()
            st.rerun()
        if b2.button("Limpar seleção", width="stretch"):
            st.session_state["selecionados"] = []
            st.session_state.pop("plano", None)
            st.rerun()

    st.divider()
    st.subheader("Escriturações na base")
    arqs = base.tabela_arquivos(con)
    if arqs.empty:
        st.info("A base está vazia. Selecione os arquivos acima para começar.")
    else:
        mostra = pd.DataFrame({
            "Escrituração": arqs["tipo"].map(NOME_FONTE),
            "Arquivo": arqs["nome_arquivo"],
            "Empresa": arqs["nome"],
            "CNPJ": arqs["cnpj"].map(mascara),
            "IE": arqs["ie"],
            "Período": arqs["dt_ini"].map(lambda d: pd.Timestamp(d).strftime("%m/%Y")),
            "Finalidade": arqs["retificadora"].map({True: "Retificadora", False: "Original"}),
            "Linhas do arquivo": arqs["linhas"],
            "Linhas de entrada carregadas": arqs["itens"],
            "Leitura (s)": arqs["segundos"],
        })
        tabela(mostra, hide_index=True, width="stretch")

        cob = base.cobertura(con)
        if not cob.empty:
            with st.expander("Cobertura: quais EFDs existem para cada estabelecimento e período"):
                st.caption("O cruzamento entre as duas escriturações só é possível onde as duas "
                           "estão carregadas. Nos demais casos as linhas aparecem como "
                           "\"a outra EFD deste período não foi carregada\".")
                tabela(pd.DataFrame({
                    "Estabelecimento": cob["estabelecimento"].map(mascara),
                    "Período": cob["periodo"].map(mes),
                    "EFD Fiscal": cob["efd_fiscal"].map({True: "Carregada", False: "Não carregada"}),
                    "EFD Contribuições": cob["efd_contribuicoes"].map({True: "Carregada", False: "Não carregada"}),
                }), hide_index=True, width="stretch")

        with st.expander("Remover uma escrituração ou limpar a base"):
            rotulos = {int(r.arquivo_id): f"{NOME_FONTE[r.tipo]} · {r.nome_arquivo} · "
                       f"{pd.Timestamp(r.dt_ini).strftime('%m/%Y')}" for r in arqs.itertuples()}
            alvo = st.selectbox("Escrituração", list(rotulos), format_func=rotulos.get)
            if st.button("Remover esta escrituração da base"):
                base.remover_arquivo(con, alvo)
                st.cache_data.clear()
                st.rerun()
            st.divider()
            certo = st.checkbox("Quero apagar todas as escriturações da base")
            if st.button("Limpar toda a base", disabled=not certo):
                base.limpar(con)
                st.cache_data.clear()
                st.rerun()

    st.divider()
    _secao_dados_e_backup(con)

    st.divider()
    st.subheader("Tabelas de apoio (opcionais)")
    t1, t2 = st.tabs(["Tabela de CFOP", "Regime tributário dos fornecedores"])
    with t1:
        st.write("A descrição dos CFOPs vem de um arquivo seu (CSV, TXT ou Excel) com o "
                 "código e a descrição, por exemplo a tabela publicada pelo SPED ou pelo "
                 "CONFAZ. Sem ela, o CFOP aparece só com o código.")
        st.caption("Situação: " + (base.estado(con, "cfop_origem") or "nenhuma tabela carregada."))
        up = st.file_uploader("Arquivo da tabela de CFOP", type=["csv", "txt", "xlsx", "xls"],
                              key="up_cfop")
        if up and st.button("Carregar tabela de CFOP"):
            caminho = _salvar_envio(up)
            try:
                n = base.carregar_cfop(con, caminho)
                st.cache_data.clear()
                st.success(f"{n} códigos de CFOP carregados.")
            except Exception as e:
                st.error(f"Não foi possível ler a tabela: {e}")
    with t2:
        st.write("Planilhas com as colunas `cnpj` e `forma_de_tributacao` (uma do Lucro "
                 "Real e outra do Lucro Presumido). O cruzamento é pela raiz do CNPJ do "
                 "fornecedor; havendo mais de um ano, vale o mais recente.")
        n_reg = con.cursor().execute("SELECT count(*) FROM regimes").fetchone()[0]
        st.caption(f"Situação: {inteiro(n_reg)} empresa(s) com regime carregado.")
        u1 = st.file_uploader("Planilha do Lucro Real", type=["csv", "txt", "xlsx", "xls"], key="up_real")
        u2 = st.file_uploader("Planilha do Lucro Presumido", type=["csv", "txt", "xlsx", "xls"], key="up_pres")
        if (u1 or u2) and st.button("Carregar planilhas de regime"):
            try:
                for envio, rotulo in ((u1, "LUCRO REAL"), (u2, "LUCRO PRESUMIDO")):
                    if envio:
                        base.carregar_regimes(con, _salvar_envio(envio), rotulo)
                st.cache_data.clear()
                st.success("Regimes carregados.")
            except Exception as e:
                st.error(f"Não foi possível ler a planilha: {e}")


def _pasta_temporaria(caminho: str) -> bool:
    c = os.path.abspath(caminho).lower().replace("\\", "/")
    return any(x in c for x in ("/appdata/local/temp", "/tmp/", "/temp/", ".zip/", "/_mei"))


def _secao_dados_e_backup(con):
    st.subheader("Onde os dados ficam e backup")
    st.write(f"A base fica gravada em **`{PASTA_BASE}`**. Fechar o programa ou desligar o "
             "computador não apaga nada: ao abrir de novo, as escriturações, os filtros salvos e "
             "a última visão continuam lá. Os arquivos `.txt` originais podem ser movidos ou "
             "apagados depois da carga, porque o conteúdo usado fica na base.")
    if _pasta_temporaria(PASTA_BASE):
        st.error("Esta pasta parece ser temporária (o Windows pode apagá-la). Extraia o programa "
                 "para uma pasta comum, como Documentos, antes de carregar os arquivos.")
    aviso = st.session_state.pop("aviso_backup", None)
    if aviso:
        st.success(aviso)
    b1, b2 = st.tabs(["Fazer backup", "Restaurar um backup"])
    with b1:
        st.session_state.setdefault("pasta_backup", os.path.join(PASTA_BASE, "backups"))
        if "_pend_pasta_backup" in st.session_state:        # valor escolhido na janela
            st.session_state["pasta_backup"] = st.session_state.pop("_pend_pasta_backup")
        c1, c2 = st.columns([4, 1.2])
        c1.text_input("Pasta do backup (pode ser um pen drive ou uma pasta na nuvem)",
                      key="pasta_backup")
        if c2.button("Escolher pasta…", width="stretch", key="bk_pasta"):
            caminhos, erro = abrir_dialogo("pasta")
            if caminhos:
                st.session_state["_pend_pasta_backup"] = caminhos[0]
                st.rerun()
            if erro:
                st.warning(erro)
        if st.button("Fazer backup agora", type="primary", key="bk_fazer"):
            try:
                with st.spinner("Copiando a base…"):
                    destino = base.fazer_backup(con, st.session_state["pasta_backup"],
                                                [ARQ_CFG, ARQ_ESTADO])
                    n = base.validar_backup(destino)
                st.success(f"Backup gravado e conferido ({n} escrituração(ões)): {destino}")
            except Exception as e:
                st.error(f"Não foi possível fazer o backup: {e}")
    with b2:
        st.write("Substitui a base atual pelo conteúdo de um backup. Antes de substituir, uma "
                 "cópia da base atual é guardada na pasta da base.")
        if "_pend_arq_restaurar" in st.session_state:
            st.session_state["arq_restaurar"] = st.session_state.pop("_pend_arq_restaurar")
        c1, c2 = st.columns([4, 1.2])
        c1.text_input("Arquivo de backup (.duckdb)", key="arq_restaurar")
        if c2.button("Escolher arquivo…", width="stretch", key="bk_arquivo"):
            caminhos, erro = abrir_dialogo("backup")
            if caminhos:
                st.session_state["_pend_arq_restaurar"] = caminhos[0]
                st.rerun()
            if erro:
                st.warning(erro)
        certo = st.checkbox("Entendo que a base atual será substituída pelo backup", key="bk_certo")
        if st.button("Restaurar backup", disabled=not certo, key="bk_restaurar"):
            origem = st.session_state.get("arq_restaurar", "").strip().strip('"')
            try:
                n = base.validar_backup(origem)
            except Exception as e:
                st.error(f"O arquivo não é um backup válido do Consolidador EFD: {e}")
            else:
                try:
                    con.execute("FORCE CHECKPOINT")
                except Exception:
                    pass
                con.close()
                _abrir_base.clear()
                carimbo = time.strftime("%Y-%m-%d_%H%M%S")
                if os.path.isfile(ARQ_DB):
                    shutil.copy2(ARQ_DB, os.path.join(PASTA_BASE, f"efd_antes_da_restauracao_{carimbo}.duckdb"))
                shutil.copy2(origem, ARQ_DB)
                if os.path.isfile(ARQ_DB + ".wal"):
                    os.remove(ARQ_DB + ".wal")
                base.reconstruir(conexao())
                st.cache_data.clear()
                st.session_state["aviso_backup"] = f"Backup restaurado: {n} escrituração(ões)."
                st.rerun()


def _salvar_envio(envio) -> str:
    pasta = os.path.join(PASTA_BASE, "tmp")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, os.path.basename(envio.name))
    with open(caminho, "wb") as f:
        f.write(envio.getbuffer())
    return caminho


# ============================================================================
# Página: Visão consolidada
# ============================================================================

def _filtros_rapidos(con, v) -> list:
    """Filtros da barra lateral -> lista de filtros (cada um, uma lista de condições)."""
    filtros = []
    st.sidebar.header("Filtros")

    def multiselecao(campo_id, titulo, formato):
        valores = opcoes(campo_id, v)
        # as chaves são texto para que a seleção possa ser gravada em disco
        mapa = {("" if x[0] is None else str(x[0])): formato(x) for x in valores}
        chave = f"f_{campo_id}"
        if chave in st.session_state:
            st.session_state[chave] = [x for x in st.session_state[chave] if x in mapa]
        escolhidos = st.sidebar.multiselect(titulo, list(mapa), format_func=mapa.get,
                                            key=chave, placeholder="Todos")
        if not escolhidos:
            return
        cheios = [x for x in escolhidos if x != ""]
        conds = []
        if cheios:
            conds.append({"grupo": 1, "campo": campo_id, "operador": "em", "valor": cheios})
        if len(cheios) < len(escolhidos):
            conds.append({"grupo": 2, "campo": campo_id, "operador": "vazio"})
        filtros.append(conds)

    multiselecao("periodo", "Período", lambda x: mes(x[0]))
    multiselecao("fornecedor", "Fornecedor",
                 lambda x: f"{mascara(x[0])} · {x[1] or ''}" if x[0] else "(sem participante)")
    multiselecao("cfop_conc", "CFOP", lambda x: x[0] or "(sem CFOP)")
    texto = st.sidebar.text_input("Item (código ou descrição contém)", key="f_item").strip()
    if texto:
        filtros.append([{"grupo": 1, "campo": "item", "operador": "contem", "valor": texto},
                        {"grupo": 2, "campo": "item_descricao", "operador": "contem", "valor": texto}])
    multiselecao("pareamento", "Situação nas duas EFDs", lambda x: ROTULO_PAREAMENTO.get(x[0], x[0]))
    return filtros


def _exibicao(dados: pd.DataFrame, medidas, nomes_calc) -> tuple[pd.DataFrame, dict, list]:
    """Prepara o resultado para a tela: nomes curtos, máscaras e ajuda com a origem."""
    rot = consulta.rotulos(list(dados.columns), medidas, st.session_state.get("_calc", {}), nomes_calc)
    cols_med = {consulta.col_medida(m, f): medida_curta(m, f) for m, f in medidas}
    nomes, numericas = {}, []
    tela = dados.copy()
    for c in dados.columns:
        if c in consulta.CAMPOS:
            nomes[c] = curto(c)
        elif c in NOME_JUNTO:
            nomes[c] = NOME_JUNTO[c]
        elif c in cols_med:
            nomes[c] = cols_med[c]
            numericas.append(nomes[c])
        elif c in nomes_calc:
            nomes[c] = nomes_calc[c]
            numericas.append(nomes[c])
        else:
            nomes[c] = c
    for c in ("fornecedor", "estab", "empresa"):
        if c in tela:
            tela[c] = tela[c].map(mascara)
    if "periodo" in tela:
        tela["periodo"] = tela["periodo"].map(mes)
    for c in ("dt_doc",):
        if c in tela:
            tela[c] = tela[c].map(lambda d: "" if d is None or d != d else pd.Timestamp(d).strftime("%d/%m/%Y"))
    if "pareamento" in tela:
        tela["pareamento"] = tela["pareamento"].map(lambda x: ROTULO_PAREAMENTO.get(x, x))
    if "fonte" in tela:
        tela["fonte"] = tela["fonte"].map(lambda x: NOME_FONTE.get(x, x))
    tela = tela.rename(columns=nomes)
    ajuda = {nomes[c]: rot[c] for c in dados.columns}
    return tela, ajuda, numericas


def _valido(chave, opcoes_validas, padrao, multiplo=True):
    """Garante que o valor guardado de um seletor ainda existe nas opções."""
    if chave not in st.session_state:
        st.session_state[chave] = padrao
    atual = st.session_state[chave]
    if multiplo:
        st.session_state[chave] = [x for x in (atual or []) if x in opcoes_validas]
    elif atual not in opcoes_validas:
        st.session_state[chave] = padrao


def _visoes_salvas(cfg):
    with st.expander("Visões salvas (agrupamento, colunas e filtros com um nome)"):
        c1, c2, c3 = st.columns([2.2, 1, 1])
        nomes = list(cfg["visoes"])
        escolha = c1.selectbox("Abrir uma visão salva", nomes, index=None,
                               placeholder="Nenhuma visão salva" if not nomes else "Escolha",
                               key="vs_escolha")
        c2.button("Abrir", disabled=escolha is None, width="stretch", key="vs_abrir",
                  on_click=aplicar_visao, args=(cfg["visoes"].get(escolha, {}),))
        if c3.button("Excluir", disabled=escolha is None, width="stretch", key="vs_excluir"):
            cfg["visoes"].pop(escolha, None)
            consulta.salvar_config(ARQ_CFG, cfg)
            st.rerun()
        c4, c5 = st.columns([3.2, 1])
        nome = c4.text_input("Salvar a visão atual com o nome", key="vs_nome",
                             placeholder="Ex.: Compras da matriz por fornecedor")
        if c5.button("Salvar visão", type="primary", width="stretch", key="vs_salvar",
                     disabled=not nome.strip()):
            cfg["visoes"][nome.strip()] = {k: st.session_state[k] for k in CHAVES_VISAO
                                           if k in st.session_state}
            consulta.salvar_config(ARQ_CFG, cfg)
            st.toast(f"Visão \"{nome.strip()}\" salva.")


def _filtros_da_tabela(dims, medidas, calculados, r_nomes_calc_previstos):
    """Busca e filtros sobre as linhas consolidadas (como o filtro de coluna do Excel)."""
    cols = consulta.colunas_resultado(dims, medidas, calculados)
    exib = {}
    for c in cols:
        if c in consulta.CAMPOS:
            exib[curto(c)] = c
        elif c in NOME_JUNTO:
            exib[NOME_JUNTO[c]] = c
        elif c.startswith("calc_"):
            exib[r_nomes_calc_previstos.get(c, c)] = c
        elif "__" in c:
            m, f = c.split("__")
            exib[medida_curta(m, FISCAL if f == "fiscal" else CONTRIB)] = c
        else:
            exib[c] = c
    op_por_rotulo = {v: k for k, v in consulta.OPERADORES.items()}
    st.text_input("Buscar na tabela", key="busca_tabela",
                  placeholder="Procura o texto em todas as colunas de texto (nome, código, descrição...)")
    guardados = [f for f in st.session_state.get("filtros_tabela", []) if f.get("coluna") in cols]
    with st.expander(f"Filtros por coluna da tabela ({len(guardados)} ativo(s))",
                     expanded=bool(guardados)):
        inicial = pd.DataFrame([{
            "Coluna": next((k for k, x in exib.items() if x == f["coluna"]), None),
            "Condição": consulta.OPERADORES.get(f["operador"]), "Valor": f.get("valor", "")}
            for f in guardados] or [{"Coluna": None, "Condição": None, "Valor": ""}])
        editado = st.data_editor(
            inicial, num_rows="dynamic", hide_index=True, width="stretch",
            key=f"ed_tabela_{hash(tuple(cols))}",
            column_config={
                "Coluna": st.column_config.SelectboxColumn(options=list(exib), required=True),
                "Condição": st.column_config.SelectboxColumn(options=list(op_por_rotulo), required=True),
                "Valor": st.column_config.TextColumn(width="large")})
        st.caption("Ex.: VL_ICMS · Fiscal \"é maior que\" 1000; Nome do fornecedor \"contém\" aço. "
                   "As condições valem juntas (E) e os totais acompanham.")
    novos = []
    for linha in editado.to_dict("records"):
        if linha.get("Coluna") in exib and linha.get("Condição") in op_por_rotulo:
            novos.append({"coluna": exib[linha["Coluna"]],
                          "operador": op_por_rotulo[linha["Condição"]],
                          "valor": "" if linha.get("Valor") is None else str(linha["Valor"])})
    st.session_state["filtros_tabela"] = novos
    resultado = list(novos)
    if st.session_state.get("busca_tabela", "").strip():
        resultado.append({"coluna": "*", "operador": "contem",
                          "valor": st.session_state["busca_tabela"].strip()})
    return resultado


def pagina_visao():
    con = conexao()
    if base_vazia():
        st.switch_page(PAGINAS["carregar"])
    restaurar_estado()
    st.title("Visão consolidada")
    v = versao()
    cfg = consulta.carregar_config(ARQ_CFG)
    raizes, estabs = seletor_escopo(con, v)
    filtros = filtro_escopo(raizes, estabs) + _filtros_rapidos(con, v)
    _valido("f_salvos", cfg["filtros"], [])
    salvos = st.sidebar.multiselect("Meus filtros salvos", list(cfg["filtros"]), key="f_salvos",
                                    placeholder="Nenhum",
                                    help="Criados na página \"Meus filtros e cálculos\". "
                                         "Vários filtros marcados valem juntos (E).")
    filtros += [cfg["filtros"][n] for n in salvos]
    _visoes_salvas(cfg)

    todas = consulta.medidas_disponiveis()
    rot_med = {medida_curta(m, f): (m, f) for m, f in todas}
    _valido("v_dims", consulta.DIMENSOES, consulta.DIMENSOES_PADRAO)
    _valido("v_medidas", rot_med, [medida_curta(m, f) for m, f in MEDIDAS_PADRAO])
    _valido("v_calcs", cfg["calculados"], [])
    c1, c2 = st.columns([1, 1])
    dims = c1.multiselect(
        "Agrupar por (a ordem escolhida é a ordem dos níveis)",
        consulta.DIMENSOES, format_func=curto, key="v_dims",
        placeholder="Sem agrupamento (só o total)",
        help="Campos do documento (número, data, conta contábil, alíquota) deixam a consulta "
             "um pouco mais lenta, porque ela passa a ler item a item.")
    escolhidas = c2.multiselect(
        "Colunas de valor", list(rot_med), key="v_medidas",
        placeholder="Escolha as colunas",
        help="Cada valor vem de uma única escrituração e fica em coluna própria. "
             "O mesmo tributo nunca é somado das duas fontes.")
    medidas = [rot_med[x] for x in escolhidas]
    c3, c4, c5, c6 = st.columns([2, 1.4, 0.9, 0.9])
    calcs = c3.multiselect("Campos calculados", list(cfg["calculados"]), key="v_calcs",
                           placeholder="Nenhum")
    calculados = {n: cfg["calculados"][n] for n in calcs}
    st.session_state["_calc"] = calculados
    opcoes_ordem = {"(primeira coluna de valor)": None, "Linhas": "n_linhas"}
    opcoes_ordem.update({medida_curta(m, f): consulta.col_medida(m, f) for m, f in medidas})
    opcoes_ordem.update({f"Nível: {curto(d)}": d for d in dims})
    _valido("v_ordem", opcoes_ordem, "(primeira coluna de valor)", multiplo=False)
    _valido("v_sentido", ["Maior primeiro", "Menor primeiro"], "Maior primeiro", multiplo=False)
    _valido("v_limite", [500, 2000, 10000, 50000], 2000, multiplo=False)
    ordem = c4.selectbox("Ordenar por", list(opcoes_ordem), key="v_ordem")
    sentido = c5.selectbox("Sentido", ["Maior primeiro", "Menor primeiro"], key="v_sentido")
    limite = c6.selectbox("Linhas na tela", [500, 2000, 10000, 50000], key="v_limite")

    nomes_calc_previstos = {f"calc_{i}": n for i, n in enumerate(calculados)}
    filtros_tabela = _filtros_da_tabela(dims, medidas, calculados, nomes_calc_previstos)
    guardar_estado()

    try:
        r = consulta.consolidar(con, dims, medidas, filtros=filtros, calculados=calculados,
                                ordem=opcoes_ordem[ordem],
                                decrescente=sentido == "Maior primeiro", limite=limite,
                                filtros_resultado=filtros_tabela)
    except consulta.FiltroInvalido as e:
        st.error(f"Filtro inválido: {e}")
        return
    dados = r["dados"]

    # ---- totais com os filtros atuais ----
    tot = r["totais"]
    linha_tot = {"Linhas somadas": inteiro(tot.get("n_linhas") or 0)}
    for m, f in medidas:
        linha_tot[medida_curta(m, f)] = br(tot.get(consulta.col_medida(m, f)) or 0)
    for col, nome in r["nomes_calc"].items():
        linha_tot[nome] = br(tot.get(col), 4)
    st.markdown("**Totais com os filtros atuais**")
    tabela(pd.DataFrame([linha_tot]), hide_index=True, width="stretch")

    tela, ajuda, numericas = _exibicao(dados, medidas, r["nomes_calc"])
    formatos = {c: (lambda x: br(x, 4)) if c in r["nomes_calc"].values() else br for c in numericas}
    if "Linhas" in tela:
        formatos["Linhas"] = inteiro
    config = {c: st.column_config.Column(help=h) for c, h in ajuda.items()}
    mostrados = len(dados)
    st.caption(
        f"{inteiro(r['total_grupos'])} linha(s) no resultado"
        + (f", mostrando as {inteiro(mostrados)} primeiras pela ordenação escolhida" if r["total_grupos"] > mostrados else "")
        + f" · consulta em {br(r['segundos'], 2)} s"
        + (" sobre a tabela pré-agregada" if r["tabela"] == "visao" else " sobre os itens")
        + ". Passe o mouse no título da coluna para ver a origem do dado. "
          "Clique na caixa à esquerda de uma linha para ver os documentos.")
    evento = tabela(tela.style.format(formatos, na_rep=""), hide_index=True,
                          width="stretch", height=520, column_config=config,
                          on_select="rerun", selection_mode="single-row", key="tabela_visao")

    if "cfop" in dims and len(dados) and (dados["cfop"] == "").any():
        st.info("Há linhas com o CFOP em branco: são registros da EFD Contribuições que não têm "
                "esse campo (energia, frete, comunicação, serviços e F100). Para vê-las no CFOP "
                "do mesmo documento na EFD Fiscal, troque o nível **CFOP** por **CFOP conciliado** "
                "em \"Agrupar por\".")

    # ---- exportação ----
    rot = consulta.rotulos(list(dados.columns), medidas, calculados, r["nomes_calc"])
    notas = [("Gerado em", dt.datetime.now().strftime("%d/%m/%Y %H:%M")),
             ("Agrupamento", " > ".join(curto(d) for d in dims) or "(total geral)"),
             ("Filtros aplicados", json.dumps(filtros, ensure_ascii=False, default=str) if filtros else "nenhum"),
             ("Escopo", "Somente entradas. Documentos cancelados, denegados e inutilizados ficam de fora. "
                        "Documentos repetidos na mesma escrituração contam uma vez."),
             ("Fontes", "Cada coluna de valor vem de uma única escrituração, indicada no cabeçalho.")]
    # Os arquivos são montados só quando o botão é clicado (geração adiada),
    # para não atrasar a tela a cada mudança de filtro.
    e1, e2, e3, _ = st.columns([1.3, 1.3, 2.6, 2.6])
    with e1:
        baixar("Baixar Excel", lambda: consulta.para_excel(dados, rot, notas=notas),
               "consolidado_efd.xlsx",
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "dl_xlsx")
    with e2:
        baixar("Baixar CSV", lambda: consulta.para_csv(dados, rot), "consolidado_efd.csv",
               "text/csv", "dl_csv")
    if r["total_grupos"] > mostrados:
        n_completo = min(r["total_grupos"], consulta.LIMITE_EXCEL)

        def csv_completo():
            completo = consulta.consolidar(
                con, dims, medidas, filtros=filtros, calculados=calculados,
                ordem=opcoes_ordem[ordem], decrescente=sentido == "Maior primeiro",
                limite=consulta.LIMITE_EXCEL, filtros_resultado=filtros_tabela)
            return consulta.para_csv(completo["dados"], rot)

        with e3:
            baixar(f"Baixar CSV com as {inteiro(n_completo)} linhas", csv_completo,
                   "consolidado_efd_completo.csv", "text/csv", "dl_csv_full")
        if r["total_grupos"] > consulta.LIMITE_EXCEL:
            st.warning(f"O resultado tem mais linhas do que o Excel aceita "
                       f"({inteiro(consulta.LIMITE_EXCEL)}). A exportação é cortada nesse limite; "
                       "agrupe por menos níveis ou aplique filtros.")

    # ---- detalhe do grupo selecionado ----
    selecionadas = evento.selection.rows if evento and evento.selection else []
    if selecionadas and selecionadas[0] < len(dados) and dims:
        linha = dados.iloc[selecionadas[0]]
        chaves = {d: linha[d] for d in dims}
        st.subheader("Documentos e itens do grupo selecionado")
        st.caption(" · ".join(f"{curto(d)}: {tela.iloc[selecionadas[0]][curto(d)]}" for d in dims))
        det = consulta.detalhar(con, filtros=filtros, chaves=chaves, limite=5000)
        colunas_num = [c for c in det.columns if c.startswith(("VL_", "ALIQ_", "QTD"))]
        vazias = [c for c in colunas_num if det[c].isna().all()]
        det = det.drop(columns=vazias)
        det["Período"] = det["Período"].map(mes)
        for c in ("DT_DOC", "Data de entrada"):
            det[c] = det[c].map(data_br)
        det["Escrituração"] = det["Escrituração"].map(lambda x: NOME_FONTE.get(x, x))
        for c in ("Estabelecimento (CNPJ)", "Fornecedor (CNPJ/CPF)"):
            det[c] = det[c].map(mascara)
        det["Situação nas duas EFDs"] = det["Situação nas duas EFDs"].map(lambda x: ROTULO_PAREAMENTO.get(x, x))
        fmt = {c: br for c in det.columns if c.startswith("VL_")}
        fmt.update({c: (lambda x: br(x, 4)) for c in det.columns if c.startswith(("ALIQ_", "QTD"))})

        def abrir(ref):
            if ref["_doc_id"] is not None and ref["_doc_id"] == ref["_doc_id"]:
                popup_documento(ref["_empresa_raiz"], ref["_doc_id"])
            else:
                popup_linha(ref["_arquivo_id"], ref["Linha no arquivo"],
                            "Registro sem documento (F100 ou consolidação C191/C195).")

        tabela_com_popup(det.style.format(fmt, na_rep=""), det, "tabela_detalhe", abrir,
                         height=min(420, 40 + 35 * max(len(det), 1)))
        if len(det) >= 5000:
            st.caption("Mostrando as 5.000 primeiras linhas do grupo.")
        baixar("Baixar o detalhe (CSV)",
               lambda: csv_bytes(det[[c for c in det.columns if not c.startswith("_")]]),
               "detalhe_grupo.csv", "text/csv", "dl_det")


# ============================================================================
# Página: Conferências
# ============================================================================

REF = {"empresa_raiz": "_empresa_raiz", "doc_id": "_doc_id", "arquivo_id": "_arquivo_id",
       "linha_doc": "_linha_doc"}


def _abrir_doc(mensagem=""):
    def abrir(ref):
        popup_documento(ref["_empresa_raiz"], ref["_doc_id"], mensagem=mensagem)
    return abrir


def pagina_conferencias():
    con = conexao()
    if base_vazia():
        st.title("Conferências")
        st.info("A base está vazia.")
        return
    restaurar_estado()
    st.title("Conferências")
    escopo = seletor_escopo(con, versao())
    guardar_estado()
    a1, a2, a3, a4, a5 = st.tabs(["Fiscal × Contribuições", "C190 × C170 (Fiscal)",
                                  "Cabeçalho × detalhes", "Documentos repetidos",
                                  "Linhas idênticas sem documento"])
    with a1:
        st.write("Cada documento de entrada é procurado nas duas escriturações pela chave "
                 "eletrônica; sem chave, por estabelecimento, modelo, série, número, data e "
                 "participante. Os valores abaixo já excluem documentos repetidos.")
        par = base.conf_pareamento(con, escopo=escopo)
        par["fonte"] = par["fonte"].map(NOME_FONTE)
        par["pareamento"] = par["pareamento"].map(lambda x: ROTULO_PAREAMENTO.get(x, x))
        par.columns = ["Escrituração", "Situação", "Documentos", "Linhas", "VL_ITEM", "VL_OPR",
                       "VL_ICMS", "VL_PIS", "VL_COFINS"]
        tabela(par.style.format({c: br for c in par.columns[4:]}, na_rep=""),
               hide_index=True, width="stretch")

        st.subheader("Itens com conteúdo diferente nas duas EFDs")
        st.caption("Mesmo documento e mesmo NUM_ITEM (registro C170 nos dois lados), com CFOP, "
                   "código do item ou valores diferentes. Ordenado pela maior diferença de ICMS.")
        div = base.divergencias_itens(con, escopo=escopo).rename(columns=REF)
        if div.empty:
            st.success("Nenhum item divergente entre as duas escriturações.")
        else:
            div = titulos(div)
            tabela_com_popup(div.style.format(dinheiro(div), na_rep=""), div, "tb_div",
                             _abrir_doc("Item com conteúdo diferente nas duas escriturações."))
            baixar("Baixar divergências (CSV)",
                   lambda: csv_bytes(div[[c for c in div.columns if not c.startswith("_")]]),
                   "divergencias_itens.csv", "text/csv", "dl_div")

        st.subheader("Documentos que estão em só uma das EFDs")
        st.caption("Com as duas escriturações do período carregadas, o documento foi encontrado "
                   "em apenas uma delas.")
        um = base.documentos_so_um_lado(con, escopo=escopo).rename(columns=REF)
        if um.empty:
            st.success("Nenhum documento em só uma das escriturações.")
        else:
            um["fonte"] = um["fonte"].map(NOME_FONTE)
            um["pareamento"] = um["pareamento"].map(lambda x: ROTULO_PAREAMENTO.get(x, x))
            um["dt_doc"] = um["dt_doc"].map(data_br)
            um = titulos(um).rename(columns={"pareamento": "Situação", "linhas": "Linhas",
                                             "vl_opr": "VL_OPR", "vl_icms": "VL_ICMS"})
            tabela_com_popup(um.style.format(dinheiro(um), na_rep=""), um, "tb_um",
                             _abrir_doc("Documento encontrado em só uma escrituração."))

    with a2:
        st.write("Na EFD Fiscal, o registro analítico **C190** deve fechar com a soma dos itens "
                 "**C170** do mesmo documento e CFOP. O C190 nunca é somado aos itens: serve só "
                 "para esta conferência (e como fonte quando o documento não tem C170).")
        resumo, difs = base.conf_c190(con, escopo=escopo)
        if resumo["grupos"]:
            m1, m2, m3 = st.columns(3)
            m1.metric("Grupos documento/CFOP conferidos", inteiro(resumo["grupos"]))
            m2.metric("Fecham", inteiro(resumo["iguais"]))
            m3.metric("Não fecham", inteiro(resumo["grupos"] - resumo["iguais"]))
            if difs.empty:
                st.success("Todos os C190 fecham com a soma dos C170.")
            else:
                difs = titulos(difs.rename(columns=REF))

                def abrir_c190(ref):
                    popup_documento(ref["_empresa_raiz"], ref["_doc_id"], destaque_cfop=ref["CFOP"],
                                    mensagem=f"C190 x soma dos C170 do CFOP {ref['CFOP']}: "
                                             f"VL_ICMS {br(ref['VL_ICMS · C190'])} no C190 e "
                                             f"{br(ref['VL_ICMS · soma dos C170'])} na soma dos C170.")

                tabela_com_popup(difs.style.format(dinheiro(difs), na_rep=""), difs, "tb_c190",
                                 abrir_c190)
                baixar("Baixar (CSV)",
                       lambda: csv_bytes(difs[[c for c in difs.columns if not c.startswith("_")]]),
                       "c190_x_c170.csv", "text/csv", "dl_c190")
        else:
            st.info("Não há documentos da EFD Fiscal com C170 na base.")

    with a3:
        st.write("Total informado no cabeçalho do documento comparado com a soma dos registros "
                 "de detalhe lidos. Esta conferência também prova que os campos estão sendo "
                 "lidos nas posições certas: se uma posição estivesse errada, quase nada fecharia.")
        cab = base.conf_cabecalho(con, escopo=escopo)
        if not cab.empty:
            total, dif = int(cab["documentos"].sum()), int(cab["diferentes"].sum())
            if dif == 0:
                st.success(f"As {inteiro(total)} comparações fecham.")
            elif dif > total * 0.2:
                st.error(f"{inteiro(dif)} de {inteiro(total)} comparações não fecham. Uma proporção "
                         "tão alta indica arquivo fora do leiaute esperado: confira a página "
                         "\"Auditoria da carga\" antes de usar os valores.")
            else:
                st.warning(f"{inteiro(dif)} de {inteiro(total)} comparações não fecham.")
            cab["fonte"] = cab["fonte"].map(NOME_FONTE)
            cab.columns = ["Escrituração", "Cabeçalho", "Campo", "Documentos", "Iguais",
                           "Diferentes", "Total no cabeçalho", "Total nos detalhes"]
            tabela(cab.style.format({"Total no cabeçalho": br, "Total nos detalhes": br}),
                   hide_index=True, width="stretch")
            if dif:
                st.markdown("**Documentos que não fecham**")
                docs = base.conf_cabecalho_docs(con, escopo=escopo).rename(columns=REF)
                docs["fonte"] = docs["fonte"].map(NOME_FONTE)
                docs = titulos(docs).rename(columns={"campo": "Campo",
                                                     "total_cabecalho": "Total no cabeçalho",
                                                     "total_detalhes": "Total nos detalhes",
                                                     "diferenca": "Diferença"})
                fmt = {c: br for c in ("Total no cabeçalho", "Total nos detalhes", "Diferença")}
                tabela_com_popup(docs.style.format(fmt, na_rep=""), docs, "tb_cab",
                                 _abrir_doc("Cabeçalho do documento x soma dos registros de detalhe."))

    with a4:
        st.write("Documentos que aparecem mais de uma vez na mesma escrituração (por exemplo, "
                 "a mesma nota em dois períodos). **Só a primeira ocorrência entra nos totais**; "
                 "a preferência é do arquivo cujo período contém a data de entrada.")
        rep = base.repeticoes(con, escopo=escopo).rename(columns=REF)
        if rep.empty:
            st.success("Nenhum documento repetido.")
        else:
            rep["fonte"] = rep["fonte"].map(NOME_FONTE)
            rep["periodo"] = rep["periodo"].map(mes)
            rep["dt_doc"] = rep["dt_doc"].map(data_br)
            rep = titulos(rep)
            tabela_com_popup(rep.style.format(dinheiro(rep), na_rep=""), rep, "tb_rep",
                             _abrir_doc("O mesmo documento escriturado mais de uma vez: à esquerda a "
                                        "ocorrência que conta nos totais, à direita a repetida."))
            baixar("Baixar (CSV)",
                   lambda: csv_bytes(rep[[c for c in rep.columns if not c.startswith("_")]]),
                   "documentos_repetidos.csv", "text/csv", "dl_rep")

    with a5:
        st.write("Registros que não têm identificação de documento (F100 e a consolidação "
                 "C191/C195) e aparecem com conteúdo idêntico no mesmo arquivo. **Eles não são "
                 "excluídos**: o arquivo não permite saber se é um lançamento repetido ou dois "
                 "lançamentos legítimos iguais. A decisão é sua.")
        ident = base.linhas_identicas(con, escopo=escopo).rename(columns={"arquivo_id": "_arquivo_id"})
        if ident.empty:
            st.success("Nenhuma linha idêntica.")
        else:
            ident["dt_doc"] = ident["dt_doc"].map(data_br)
            ident = titulos(ident).rename(columns={"primeira_linha": "Primeira linha"})
            tabela_com_popup(ident.style.format(dinheiro(ident), na_rep=""), ident, "tb_ident",
                             lambda ref: popup_linha(ref["_arquivo_id"], ref["Primeira linha"],
                                                     f"Aparece {ref['Vezes']} vezes no arquivo "
                                                     f"{ref['Arquivo']}."))


# ============================================================================
# Página: Meus filtros e cálculos
# ============================================================================

def pagina_filtros():
    con = conexao()
    st.title("Meus filtros e cálculos")
    cfg = consulta.carregar_config(ARQ_CFG)
    aviso = st.session_state.pop("aviso_cfg", None)
    if aviso:
        st.success(aviso)
    t1, t2, t3 = st.tabs(["Filtros", "Campos calculados", "Importar e exportar"])

    campo_por_rotulo = {curto(k): k for k in consulta.CAMPOS}
    op_por_rotulo = {v: k for k, v in consulta.OPERADORES.items()}

    with t1:
        st.write("Monte um filtro com quantas condições quiser e salve com um nome. Ele passa "
                 "a aparecer em **Meus filtros salvos**, na Visão consolidada.")
        novo = "(novo filtro)"
        escolha = st.selectbox("Filtro", [novo] + list(cfg["filtros"]), key="fl_escolha")
        nome = st.text_input("Nome do filtro", value="" if escolha == novo else escolha,
                             key=f"fl_nome_{escolha}")
        conds = cfg["filtros"].get(escolha, [])
        inicial = pd.DataFrame([{
            "Grupo": int(c.get("grupo") or 1), "Campo": curto(c["campo"]),
            "Condição": consulta.OPERADORES[c["operador"]],
            "Valor": "; ".join(c["valor"]) if isinstance(c.get("valor"), list) else str(c.get("valor") or ""),
        } for c in conds] or [{"Grupo": 1, "Campo": None, "Condição": None, "Valor": ""}])
        editado = st.data_editor(
            inicial, num_rows="dynamic", hide_index=True, width="stretch", key=f"fl_editor_{escolha}",
            column_config={
                "Grupo": st.column_config.NumberColumn(min_value=1, step=1, default=1, width="small"),
                "Campo": st.column_config.SelectboxColumn(options=list(campo_por_rotulo), required=True),
                "Condição": st.column_config.SelectboxColumn(options=list(op_por_rotulo), required=True),
                "Valor": st.column_config.TextColumn(width="large"),
            })
        st.caption("Condições com o mesmo número de **grupo** valem juntas (E). Grupos diferentes "
                   "são alternativas (OU). Em listas e em \"está entre\", separe os valores com "
                   "ponto e vírgula. Datas: DD/MM/AAAA ou MM/AAAA. CNPJ e CFOP podem ser digitados "
                   "com ou sem pontuação.")
        condicoes = []
        for linha in editado.to_dict("records"):
            if not linha.get("Campo") or not linha.get("Condição"):
                continue
            grupo = linha.get("Grupo")
            condicoes.append({"grupo": int(grupo) if grupo == grupo and grupo else 1,
                              "campo": campo_por_rotulo[linha["Campo"]],
                              "operador": op_por_rotulo[linha["Condição"]],
                              "valor": "" if linha.get("Valor") is None else str(linha["Valor"])})
        b1, b2, b3, _ = st.columns([1, 1, 1, 4])
        if b1.button("Testar", key="fl_testar", width="stretch"):
            try:
                com = consulta.consolidar(con, [], MEDIDAS_PADRAO, filtros=[condicoes])["totais"]
                sem = consulta.consolidar(con, [], MEDIDAS_PADRAO)["totais"]
                st.info(f"O filtro seleciona **{inteiro(com['n_linhas'])}** de "
                        f"{inteiro(sem['n_linhas'])} linhas.")
                tabela(pd.DataFrame([{medida_curta(m, f): br(com.get(consulta.col_medida(m, f)) or 0)
                                            for m, f in MEDIDAS_PADRAO}]), hide_index=True, width="stretch")
            except consulta.FiltroInvalido as e:
                st.error(str(e))
        if b2.button("Salvar", type="primary", key="fl_salvar", width="stretch"):
            try:
                consulta.montar_where(condicoes)
                if not nome.strip():
                    st.error("Dê um nome ao filtro.")
                elif not condicoes:
                    st.error("O filtro precisa de ao menos uma condição completa.")
                else:
                    if escolha != novo and escolha != nome.strip():
                        cfg["filtros"].pop(escolha, None)
                    cfg["filtros"][nome.strip()] = condicoes
                    consulta.salvar_config(ARQ_CFG, cfg)
                    st.session_state["aviso_cfg"] = f"Filtro \"{nome.strip()}\" salvo."
                    st.rerun()
            except consulta.FiltroInvalido as e:
                st.error(str(e))
        if b3.button("Excluir", key="fl_excluir", disabled=escolha == novo, width="stretch"):
            cfg["filtros"].pop(escolha, None)
            consulta.salvar_config(ARQ_CFG, cfg)
            st.session_state["aviso_cfg"] = f"Filtro \"{escolha}\" excluído."
            st.rerun()

    with t2:
        st.write("Um campo calculado é uma conta sobre os totais de cada linha da visão, por "
                 "exemplo a alíquota efetiva. Use os nomes das medidas, números, `+ - * /` e "
                 "parênteses.")
        novo_c = "(novo campo)"
        esc = st.selectbox("Campo calculado", [novo_c] + list(cfg["calculados"]), key="cc_escolha")
        nome_c = st.text_input("Nome", value="" if esc == novo_c else esc, key=f"cc_nome_{esc}")
        formula = st.text_input("Fórmula", value=cfg["calculados"].get(esc, ""), key=f"cc_formula_{esc}",
                                placeholder="VL_PIS_CONTRIB / VL_BC_PIS_CONTRIB * 100")
        with st.expander("Nomes de medidas aceitos na fórmula"):
            tabela(pd.DataFrame(
                [{"Nome na fórmula": n, "Origem": ROTULO_MEDIDA[m][f]}
                 for n, (m, f) in consulta.VARIAVEIS.items()]), hide_index=True, width="stretch")
        d1, d2, d3, _ = st.columns([1, 1, 1, 4])
        if d1.button("Testar", key="cc_testar", width="stretch"):
            try:
                x = consulta.consolidar(con, [], [], calculados={"resultado": formula})
                st.info(f"Resultado sobre a base inteira: **{br(x['totais'].get('calc_0'), 4) or 'vazio (divisão por zero)'}**")
            except consulta.FiltroInvalido as e:
                st.error(str(e))
        if d2.button("Salvar", type="primary", key="cc_salvar", width="stretch"):
            try:
                consulta.formula_para_sql(formula)
                if not nome_c.strip():
                    st.error("Dê um nome ao campo.")
                else:
                    if esc != novo_c and esc != nome_c.strip():
                        cfg["calculados"].pop(esc, None)
                    cfg["calculados"][nome_c.strip()] = formula.strip()
                    consulta.salvar_config(ARQ_CFG, cfg)
                    st.session_state["aviso_cfg"] = f"Campo \"{nome_c.strip()}\" salvo."
                    st.rerun()
            except consulta.FiltroInvalido as e:
                st.error(str(e))
        if d3.button("Excluir", key="cc_excluir", disabled=esc == novo_c, width="stretch"):
            cfg["calculados"].pop(esc, None)
            consulta.salvar_config(ARQ_CFG, cfg)
            st.session_state["aviso_cfg"] = f"Campo \"{esc}\" excluído."
            st.rerun()

    with t3:
        st.write("Os filtros e campos ficam em um arquivo JSON na pasta da base. Use esta aba "
                 "para levar suas definições para outro computador ou guardar uma cópia.")
        baixar("Baixar meus filtros e campos (JSON)",
               json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8"),
               "filtros_e_campos.json", "application/json", "dl_cfg")
        envio = st.file_uploader("Importar um arquivo de filtros e campos", type=["json"], key="up_cfg")
        if envio and st.button("Importar"):
            try:
                novo_cfg = json.loads(envio.getvalue().decode("utf-8"))
                erros = consulta.validar_config(novo_cfg)
                if erros:
                    st.error("O arquivo tem definições inválidas e não foi importado:\n\n- " + "\n- ".join(erros))
                else:
                    cfg["filtros"].update(novo_cfg.get("filtros") or {})
                    cfg["calculados"].update(novo_cfg.get("calculados") or {})
                    consulta.salvar_config(ARQ_CFG, cfg)
                    st.session_state["aviso_cfg"] = "Definições importadas."
                    st.rerun()
            except (ValueError, AttributeError, TypeError) as e:
                st.error(f"Arquivo inválido: {e}")


# ============================================================================
# Página: Auditoria da carga
# ============================================================================

def pagina_auditoria():
    con = conexao()
    st.title("Auditoria da carga")
    st.subheader("Verificações de integridade")
    st.caption("Rodam a cada carga, remoção ou atualização das tabelas de apoio. Se alguma "
               "falhar, os totais não devem ser usados.")
    ver = base.ultimas_verificacoes(con)
    for vr in ver:
        (st.success if vr["ok"] else st.error)(
            f"{'OK' if vr['ok'] else 'FALHOU'} — {vr['verificacao']} ({vr['detalhe']})")
    if st.button("Rodar as verificações de novo"):
        base.reconstruir(con)
        st.cache_data.clear()
        st.rerun()

    st.subheader("Leitura de cada arquivo")
    metas = base.metas(con)
    if not metas:
        st.info("A base está vazia.")
    for m in metas:
        problemas = len(m.get("anomalias") or {}) + len(m.get("divergencias_9900") or {}) \
            + len(m.get("registros_atencao") or {})
        with st.expander(f"{NOME_FONTE[m['tipo']]} · {m['nome_arquivo']}"
                         + (f" · {problemas} ponto(s) de atenção" if problemas else " · sem pontos de atenção")):
            d = m.get("descartes") or {}
            c = m["controle"]
            st.write(f"Linhas de entrada carregadas: **{inteiro(c['itens']['n'])}** em "
                     f"**{inteiro(c['docs']['n'])}** documentos. Fora do escopo: "
                     f"{inteiro(d.get('saidas', 0))} documento(s) de saída, "
                     f"{inteiro(d.get('situacao', 0))} cancelado(s)/denegado(s)/inutilizado(s), "
                     f"{inteiro(d.get('f100_nao_aquisicao', 0))} F100 que não é aquisição, "
                     f"{inteiro(d.get('c191_c195_saida', 0))} C191/C195 com CFOP de saída.")
            if m.get("tem_9900"):
                if m.get("divergencias_9900"):
                    st.error("A contagem de linhas por registro difere do registro 9900 do arquivo: "
                             + "; ".join(f"{r}: 9900 informa {q[0]}, lidas {q[1]}"
                                         for r, q in m["divergencias_9900"].items()))
                else:
                    st.success("A contagem de linhas de cada registro confere com o registro 9900 do arquivo.")
            else:
                st.warning("O arquivo não tem registro 9900; a contagem de linhas não pôde ser conferida.")
            if m.get("anomalias"):
                st.warning("Anomalias de leitura:")
                tabela(pd.DataFrame(
                    [{"Anomalia": k, "Ocorrências": q,
                      "Exemplos": "; ".join((m.get("exemplos_anomalias") or {}).get(k, []))}
                     for k, q in m["anomalias"].items()]), hide_index=True, width="stretch")
            if m.get("registros_atencao"):
                st.warning("Registros com possíveis valores de entrada ou de crédito que esta "
                           "versão **não consolida**:")
                tabela(pd.DataFrame(
                    [{"Registro": r, "Linhas": x["linhas"], "Conteúdo": x["descricao"]}
                     for r, x in m["registros_atencao"].items()]), hide_index=True, width="stretch")
            tratados = set(m.get("registros_tratados") or [])
            campos = m.get("campos_por_registro") or {}
            tabela(pd.DataFrame(
                [{"Registro": r, "Linhas no arquivo": q,
                  "Lido pela ferramenta": "Sim" if r in tratados else "Não",
                  "Quantidade de campos encontrada": ", ".join(
                      f"{k} campos ({inteiro(n)} linhas)" for k, n in sorted(campos.get(r, {}).items()))}
                 for r, q in sorted((m.get("contagem") or {}).items())]),
                hide_index=True, width="stretch", height=260)

    st.subheader("Como os dados são tratados")
    st.markdown("""
- **Escopo**: somente entradas (`IND_OPER = 0`). No C500 da EFD-Contribuições, que não tem
  `IND_OPER`, todas as linhas; no C191/C195, as de CFOP iniciado por 1, 2 ou 3; no F100, as de
  `IND_OPER = 0`. Documentos com `COD_SIT` 02, 03, 04 ou 05 ficam de fora.
- **Fonte de cada valor**: ICMS, ICMS ST e IPI da EFD Fiscal; PIS, COFINS e ISS da
  EFD-Contribuições. Os campos de ICMS que a EFD-Contribuições também traz no C170 aparecem em
  coluna própria, para comparação, e nunca são somados aos da Fiscal.
- **EFD Fiscal**: o documento entra pelos itens (C170). Sem C170, entra pelo analítico (C190).
  Energia, transporte e comunicação entram por C590, D190 e D590.
- **ISS**: o `VL_ISS` é do cabeçalho (A100) e é distribuído entre os itens A170 na proporção do
  `VL_ITEM`; a soma dos itens é exatamente o valor do documento.
- **Leiautes**: as posições de campo foram codificadas a partir dos leiautes da EFD ICMS/IPI e
  da EFD-Contribuições e são conferidas a cada carga contra o próprio arquivo (registro 9900,
  cabeçalho × detalhes, C190 × C170 e formato de CFOP, datas e chaves). Divergências aparecem
  nesta página e em **Conferências**.
""")
    st.caption(f"Consolidador EFD {__version__} · base em {PASTA_BASE}")


# ============================================================================
# Navegação
# ============================================================================

def _resumo_lateral():
    con = conexao()
    n_arq, n_it = con.cursor().execute(
        "SELECT (SELECT count(*) FROM arquivos), (SELECT count(*) FROM itens WHERE NOT repetido)").fetchone()
    ver = base.ultimas_verificacoes(con)
    st.sidebar.divider()
    st.sidebar.caption(f"Base: {inteiro(n_arq)} escrituração(ões) · {inteiro(n_it)} linhas de entrada")
    if ver and all(x["ok"] for x in ver):
        st.sidebar.caption(f"Integridade: {len(ver)} de {len(ver)} verificações passam")
    elif ver:
        st.sidebar.error("Há verificações de integridade com falha. Veja \"Auditoria da carga\".")


PAGINAS = {
    "visao": st.Page(pagina_visao, title="Visão consolidada", icon=":material/table_chart:",
                     url_path="visao", default=True),
    "carregar": st.Page(pagina_carregar, title="Carregar EFDs", icon=":material/upload_file:",
                        url_path="carregar"),
    "conferencias": st.Page(pagina_conferencias, title="Conferências",
                            icon=":material/fact_check:", url_path="conferencias"),
    "filtros": st.Page(pagina_filtros, title="Meus filtros e cálculos",
                       icon=":material/filter_alt:", url_path="filtros"),
    "auditoria": st.Page(pagina_auditoria, title="Auditoria da carga",
                         icon=":material/verified:", url_path="auditoria"),
}
pagina = st.navigation(list(PAGINAS.values()))
pagina.run()
_resumo_lateral()
