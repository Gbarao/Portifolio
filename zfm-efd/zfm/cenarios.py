"""Analise por cenario ZFM (C1-C6): matriz, As Is escriturado x To Be, IPI por produto e alertas.

A classificacao de cada operacao esta na visao v_cenarios (zfm/visoes.py). O tratamento
To Be de cada cenario vem de param_regras_cenario; as conferencias As Is, de
param_conferencia_cenario.

Atribuicao por cenario (fluxos das operacoes):
  As Is  = tributo escriturado na operacao: debito nas saidas (+), credito nas entradas (−);
           credito estimulo e fundos do ICMS alocados as vendas incentivadas (C4) pelo ICMS debitado.
  To Be  = debito − credito − creditos presumidos gerados pelo cenario, com as aliquotas do ano;
           ICMS = As Is × fator do ano; IPI proprio = As Is × fator_ipi_proprio; PIS/COFINS = 0.
  "Nao atribuido" = carga total (apuracao / motor) − soma dos cenarios: ajustes da apuracao,
           saldos credores, absorcao dos creditos presumidos e teses. Assim a soma dos cenarios
           mais o "nao atribuido" e igual a diferenca total da empresa (sem compensar empresas).
Convencao: diferenca = To Be − As Is (positivo = a empresa paga mais).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from . import as_is as _as_is
from . import params, simulacao
from .filtros import TODOS, Filtro

NAO_ATRIBUIDO = "Não atribuído (ajustes, saldos, absorção, teses)"
TRIBUTOS = ["ICMS", "IPI", "PIS", "COFINS", "CBS", "IBS", "Contribuição art. 457"]
ORDEM = ["C1a", "C1b", "C1c", "C2a", "C2b", "C2c", "C3a", "C3b", "C4a", "C4b", "C4c", "C4d", "C5M", "C5S",
         "GER_S", "GER_E", "EXP", "TR", "REM", "SRV", "NC_S", "NC_E", NAO_ATRIBUIDO]
STATUS = ["Elegível", "Potencialmente elegível - depende de validação", "Informação insuficiente para determinar",
          "Não elegível", "Fora dos incentivos"]


def descricoes() -> dict[str, str]:
    r = params.carregar("param_regras_cenario")
    d = {x.cenario: x.descricao for x in r.itertuples()}
    d[NAO_ATRIBUIDO] = NAO_ATRIBUIDO
    return d


def ordenar(df: pd.DataFrame, col: str = "cenario") -> pd.DataFrame:
    if df.empty:
        return df
    extras = [c for c in df[col].unique() if c not in ORDEM]
    df = df.copy()
    df[col] = pd.Categorical(df[col], categories=ORDEM + extras, ordered=True)
    return df.sort_values(col)


# ---------------------------------------------------------------------------
# 1. Matriz cenario x empresa
# ---------------------------------------------------------------------------
def matriz(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    return con.execute(f"""
        SELECT raiz, cenario, sentido, status_elegibilidade, sum(valor) AS valor,
               count(DISTINCT coalesce(chv_nfe, CAST(arquivo_id AS VARCHAR) || '-' || CAST(linha_num AS VARCHAR)))
                   AS documentos,
               count(*) AS linhas, bool_or(eh_grupo) AS tem_intragrupo
        FROM v_cenarios WHERE {f.sql()} GROUP BY ALL""").df()


# ---------------------------------------------------------------------------
# 2. As Is escriturado por cenario
# ---------------------------------------------------------------------------
def _fluxos_as_is_mensais(con: duckdb.DuckDBPyConnection, f: Filtro) -> pd.DataFrame:
    ops = con.execute(f"""
        SELECT raiz, cnpj_estab, mes, cenario,
               sum(CASE WHEN sentido = 'saida' THEN icms ELSE -icms END) AS icms,
               sum(CASE WHEN sentido = 'saida' THEN ipi ELSE -ipi END) AS ipi,
               sum(CASE WHEN sentido = 'saida' THEN pis
                        WHEN cst_pis BETWEEN '50' AND '66' THEN -pis ELSE 0 END) AS pis,
               sum(CASE WHEN sentido = 'saida' THEN cofins
                        WHEN cst_cofins BETWEEN '50' AND '66' THEN -cofins ELSE 0 END) AS cofins,
               sum(CASE WHEN sentido = 'saida' THEN icms ELSE 0 END) AS icms_debito,
               sum(valor) AS valor
        FROM v_cenarios WHERE {f.sql()} GROUP BY ALL""").df()
    if ops.empty:
        return ops
    # credito estimulo (deducao) e fundos fora da apuracao -> vendas incentivadas (C4)
    ap = _as_is.carga_mensal(con, f)
    ap = ap[ap.tributo == "ICMS"][["cnpj_estab", "mes", "deducoes_beneficios", "fundos_fora_apuracao"]]
    if not ap.empty:
        ap = ap.groupby(["cnpj_estab", "mes"], as_index=False).sum()
        ap["ajuste"] = ap["deducoes_beneficios"] + ap["fundos_fora_apuracao"]
        c4 = ops[ops.cenario.astype(str).str.startswith("C4")].copy()
        if not c4.empty:
            c4["peso_base"] = c4["icms_debito"].where(c4["icms_debito"] > 0, 0.0)
            tot = c4.groupby(["cnpj_estab", "mes"])["peso_base"].transform("sum")
            tot_v = c4.groupby(["cnpj_estab", "mes"])["valor"].transform("sum")
            c4["peso"] = (c4["peso_base"] / tot.where(tot > 0)).fillna(c4["valor"] / tot_v.where(tot_v != 0)).fillna(0)
            c4 = c4.merge(ap[["cnpj_estab", "mes", "ajuste"]], on=["cnpj_estab", "mes"], how="left")
            ops = ops.merge(c4[["cnpj_estab", "mes", "cenario", "peso", "ajuste"]],
                            on=["cnpj_estab", "mes", "cenario"], how="left")
            ops["icms"] = ops["icms"] + (ops["peso"].fillna(0) * ops["ajuste"].fillna(0))
            ops = ops.drop(columns=["peso", "ajuste"])
    return ops


def as_is_por_cenario(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS, com_teses: bool = False) -> pd.DataFrame:
    """raiz, cenario, tributo, as_is (anualizado). Inclui a linha NAO_ATRIBUIDO."""
    m = _fluxos_as_is_mensais(con, f)
    meses = _as_is.meses_observados(con, f)
    if m.empty:
        return pd.DataFrame(columns=["raiz", "cenario", "tributo", "as_is"])
    longo = m.melt(id_vars=["raiz", "cenario", "mes"], value_vars=["icms", "ipi", "pis", "cofins"],
                   var_name="tributo", value_name="as_is")
    longo["tributo"] = longo["tributo"].str.upper()
    ann = _as_is.anualizar(longo, meses, "as_is", ("raiz", "cenario", "tributo"))
    total = _as_is.carga_anual(con, f, com_teses)
    if not total.empty:
        soma = ann.groupby(["raiz", "tributo"], as_index=False)["as_is"].sum()
        na = total[["raiz", "tributo", "as_is"]].merge(soma, on=["raiz", "tributo"], how="left",
                                                      suffixes=("", "_cen")).fillna(0.0)
        na["as_is"] = na["as_is"] - na["as_is_cen"]
        na["cenario"] = NAO_ATRIBUIDO
        ann = pd.concat([ann, na[["raiz", "cenario", "tributo", "as_is"]]], ignore_index=True)
    return ann


# ---------------------------------------------------------------------------
# 3. To Be por cenario
# ---------------------------------------------------------------------------
def _bases_anuais(con: duckdb.DuckDBPyConnection, f: Filtro, conservador: bool | None = None) -> pd.DataFrame:
    with simulacao._ProdutosRegistrados(con):
        b = con.execute(f"""
            WITH x AS ({simulacao.sql_base_cenarios(f, conservador)})
            SELECT x.raiz, x.cenario, x.mes,
                   sum(x.base * x.r_cbs_debito) AS cbs_deb, sum(x.base * x.r_cbs_entrada * (1 - x.credok)) AS cbs_ent,
                   sum(x.base * x.r_cbs_forn * x.regular) AS cbs_forn,
                   sum(x.base * x.r_ibs_debito) AS ibs_deb, sum(x.base * x.r_ibs_entrada * (1 - x.credok)) AS ibs_ent,
                   sum(x.base * x.r_ibs_forn * x.regular) AS ibs_forn,
                   coalesce(sum(x.base * x.p_cbs * x.r_cbs_debito) FILTER (WHERE x.r_cp_cbs), 0) AS cp_cbs,
                   coalesce(sum(x.base * x.p_ibs * x.r_ibs_debito) FILTER (WHERE x.r_cp_ibs), 0) AS p_ibs_base,
                   coalesce(sum(x.base * x.pct447 * x.regular) FILTER (WHERE x.r_cp_ent = '447'), 0) AS cp447,
                   coalesce(sum(x.base * x.pct449 * x.regular) FILTER (WHERE x.r_cp_ent = '449'), 0) AS cp449,
                   coalesce(sum(x.base) FILTER (WHERE x.r_cp_ent = '444'), 0) AS cp444,
                   coalesce(sum(x.valor) FILTER (WHERE x.cenario LIKE 'C4%'), 0) AS receita_c4
            FROM x GROUP BY ALL""").df()
    if b.empty:
        return b
    meses = _as_is.meses_observados(con, f)
    cols = [c for c in b.columns if c not in ("raiz", "cenario", "mes")]
    longo = b.melt(id_vars=["raiz", "cenario", "mes"], value_vars=cols, var_name="medida", value_name="v")
    ann = _as_is.anualizar(longo, meses, "v", ("raiz", "cenario", "medida"))
    return ann.pivot_table(index=["raiz", "cenario"], columns="medida", values="v", aggfunc="sum",
                           fill_value=0.0).reset_index()


def to_be_por_cenario(con: duckdb.DuckDBPyConnection, anual: pd.DataFrame, f: Filtro = TODOS,
                      com_teses: bool = False, conservador: bool | None = None) -> pd.DataFrame:
    """cenario_aliq (base/baixo/...), ano, raiz, cenario, tributo, to_be. Inclui NAO_ATRIBUIDO.
    Percentuais e vigencias dos arts. 444/446/447/449/450 vem de Regras legais (zfm/regras.py)."""
    from . import regras
    tab = regras.carregar()
    pc = simulacao.percentuais()
    bases = _bases_anuais(con, f, conservador)
    asis = as_is_por_cenario(con, f, com_teses)
    asis = asis[asis.cenario != NAO_ATRIBUIDO]
    cen = params.carregar("param_aliquotas_cenario")
    cen = cen[cen["ano"].isin(simulacao.ANOS)]
    fator_ipi = params.premissa_num("fator_ipi_proprio", 0.0)
    linhas = []
    for r in cen.itertuples():
        a_cbs, a_ibs = (r.aliq_cbs or 0) / 100, (r.aliq_ibs or 0) / 100
        fator = float(r.fator_icms) if pd.notna(r.fator_icms) else 0.0
        f_cp = float(r.fator_cp_entrada) if pd.notna(r.fator_cp_entrada) else 0.0
        a450 = bool(r.aplica_cp_450)
        a457 = (r.aliq_contrib_art457 or 0) / 100
        v444, v446 = regras.fator("ART444_CP_IBS", r.ano, tab), regras.fator("ART446_IBS_ENTRADA", r.ano, tab)
        v447, v449 = regras.fator("ART447_SS", r.ano, tab), regras.fator("ART449_CP_IBS", r.ano, tab)
        v450i, v450c = regras.fator("ART450_IBS_FINAL", r.ano, tab), regras.fator("ART450_CBS_DEMAIS", r.ano, tab)
        eng = anual[(anual.cenario == r.cenario) & (anual.ano == r.ano)].set_index("raiz") if not anual.empty \
            else pd.DataFrame()
        if not bases.empty:
            tot_p = bases.groupby("raiz")["p_ibs_base"].sum()
            for b in bases.itertuples():
                cp450_total = float(eng.loc[b.raiz, "cp_ibs_450"]) if b.raiz in eng.index else 0.0
                share = b.p_ibs_base / tot_p[b.raiz] if tot_p.get(b.raiz, 0) else 0.0
                cbs = a_cbs * (b.cbs_deb + b.cbs_ent - b.cbs_forn) - (b.cp_cbs if (a450 and v450c) else 0.0)
                cp_ent = ((b.cp447 * v447 + b.cp449 * v449) * f_cp
                          + b.cp444 * a_ibs * pc["cp444"] / 100 * v444) if a_ibs > 0 else 0.0
                ibs_ent = b.ibs_ent * (pc["ibs_entrada_446"] / 100 * v446 if str(b.cenario).startswith("C2") else 1.0)
                ibs = a_ibs * (b.ibs_deb + ibs_ent - b.ibs_forn) - cp_ent - (
                    cp450_total * share if (a450 and v450i) else 0.0)
                for trib, v in (("CBS", cbs), ("IBS", ibs), ("Contribuição art. 457", b.receita_c4 * a457)):
                    linhas.append((r.cenario, r.ano, b.raiz, b.cenario, trib, v))
        for x in asis.itertuples():
            v = x.as_is * (fator if x.tributo == "ICMS" else fator_ipi if x.tributo == "IPI" else 0.0)
            linhas.append((r.cenario, r.ano, x.raiz, x.cenario, x.tributo, v))
    tb = pd.DataFrame(linhas, columns=["cenario_aliq", "ano", "raiz", "cenario", "tributo", "to_be"])
    tb = tb.groupby(["cenario_aliq", "ano", "raiz", "cenario", "tributo"], as_index=False)["to_be"].sum()
    if not anual.empty:
        mapa = {"ICMS": "to_be_icms", "IPI": "to_be_ipi", "PIS": "to_be_pis", "COFINS": "to_be_cofins",
                "CBS": "to_be_cbs", "IBS": "to_be_ibs", "Contribuição art. 457": "to_be_contrib_457"}
        tot = anual[["cenario", "ano", "raiz"] + list(mapa.values())].melt(
            id_vars=["cenario", "ano", "raiz"], var_name="col", value_name="total")
        tot["tributo"] = tot["col"].map({v: k for k, v in mapa.items()})
        tot = tot.rename(columns={"cenario": "cenario_aliq"})
        soma = tb.groupby(["cenario_aliq", "ano", "raiz", "tributo"], as_index=False)["to_be"].sum()
        na = tot.merge(soma, on=["cenario_aliq", "ano", "raiz", "tributo"], how="left").fillna({"to_be": 0.0})
        na["to_be"] = na["total"] - na["to_be"]
        na["cenario"] = NAO_ATRIBUIDO
        tb = pd.concat([tb, na[["cenario_aliq", "ano", "raiz", "cenario", "tributo", "to_be"]]], ignore_index=True)
    return tb


def resultado(con: duckdb.DuckDBPyConnection, anual: pd.DataFrame, f: Filtro = TODOS,
              com_teses: bool = False, conservador: bool | None = None) -> pd.DataFrame:
    """cenario_aliq, ano, raiz, cenario, tributo, as_is, to_be, diferenca (positivo = paga mais)."""
    tb = to_be_por_cenario(con, anual, f, com_teses, conservador)
    ai = as_is_por_cenario(con, f, com_teses)
    if tb.empty and ai.empty:
        return pd.DataFrame(columns=["cenario_aliq", "ano", "raiz", "cenario", "tributo", "as_is", "to_be",
                                     "diferenca"])
    chaves = tb[["cenario_aliq", "ano"]].drop_duplicates()
    ai_x = chaves.merge(ai, how="cross")
    r = tb.merge(ai_x, on=["cenario_aliq", "ano", "raiz", "cenario", "tributo"], how="outer").fillna(
        {"as_is": 0.0, "to_be": 0.0})
    r["diferenca"] = r["to_be"] - r["as_is"]
    r = r[(r["as_is"].abs() > 0.005) | (r["to_be"].abs() > 0.005)]
    return r


# ---------------------------------------------------------------------------
# 5. IPI por produto (C6)
# ---------------------------------------------------------------------------
def ipi_por_produto(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS, sem_ipi_protegido: bool = False) -> pd.DataFrame:
    rec = con.execute(f"""
        SELECT raiz, cod_item, sum(valor) AS receita_periodo
        FROM v_cenarios WHERE cenario LIKE 'C4%' AND {f.sql()} GROUP BY ALL""").df()
    if rec.empty:
        return pd.DataFrame()
    meses = _as_is.meses_observados(con, f)
    n = meses.groupby("raiz")["mes"].nunique()
    rec["receita_anual"] = rec["receita_periodo"] / rec["raiz"].map(n).replace(0, pd.NA) * 12
    prod = simulacao.produtos_com_percentuais(params.carregar("param_produtos"))
    pc = simulacao.percentuais()
    d = rec.merge(prod, left_on=["raiz", "cod_item"], right_on=["raiz_cnpj", "cod_item"], how="left")
    aliq = d["aliq_ipi"].astype(float)          # aliquota do IPI lida da EFD (TIPI do produto)
    lim = pc["limite_tipi_ipi"]
    art454 = d["art454"].fillna(False).astype(bool)
    protegido = (aliq >= lim) & ~sem_ipi_protegido
    classe = pd.Series("IPI abaixo do limite, sem industrialização em 2024: conferir", index=d.index)
    classe = classe.mask(art454, "Art. 454: IPI < 6,5% e industrializado na ZFM em 2024 — IPI zero para todos")
    classe = classe.mask(aliq >= lim, "IPI ≥ 6,5%: IPI mantido para o concorrente (vantagem mantida)")
    classe = classe.mask(d["eh_tic"].fillna(False).astype(bool), "TIC: excluído da redução do art. 454 — análise manual")
    classe = classe.mask(d["excluido_art441"].fillna("").str.lower().eq("sim"), "Excluído do regime (art. 441)")
    classe = classe.mask(aliq.isna(), "Sem alíquota de IPI na EFD: informar em Cadastros > Produtos")
    d["classe_ipi"] = classe
    d["enquadrado_art454"] = art454
    d["aliq_ipi_futura"] = aliq.where(protegido, 0.0)
    d["vantagem_hoje"] = d["receita_anual"] * aliq.fillna(0) / 100
    d["vantagem_to_be"] = d["vantagem_hoje"].where(protegido, 0.0)
    d["perda_vantagem"] = d["vantagem_hoje"] - d["vantagem_to_be"]
    d["cp_cbs_pct"] = d["p_cbs_450"] * 100
    d["cp_ibs_pct"] = d["p_ibs_450"] * 100
    d["alerta_credito_estimulo"] = d["alerta_ibs"].fillna(False)
    d["comprador_perde_credito_ipi"] = art454
    d["carga_propria_ipi"] = 0.0
    return d[["raiz", "cod_item", "ncm", "descricao", "tipo_bem", "aliq_ipi", "fonte_aliq_ipi", "produzido_zfm_2024",
              "eh_tic", "enquadrado_art454", "aliq_ipi_futura", "classe_ipi", "receita_anual", "carga_propria_ipi",
              "vantagem_hoje", "vantagem_to_be", "perda_vantagem", "cp_cbs_pct", "cp_ibs_pct", "nivel_credito_estimulo",
              "alerta_credito_estimulo", "comprador_perde_credito_ipi"]]


# ---------------------------------------------------------------------------
# Conferencias e alertas
# ---------------------------------------------------------------------------
_COL = {"ICMS": ("icms", "cst_icms", None), "IPI": ("ipi", "cst_ipi", None),
        "PIS": ("pis", "cst_pis", "aliq_pis"), "COFINS": ("cofins", "cst_cofins", "aliq_cofins")}


def conferencias(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    regras = params.carregar("param_conferencia_cenario")
    partes = []
    for r in regras.itertuples():
        cens = [c.strip() for c in r.cenarios.split(";") if c.strip()]
        if not cens or r.tributo not in _COL:
            continue
        val, cst, aliq = _COL[r.tributo]
        lista = [x.strip() for x in str(r.valores).split(";") if x.strip()]
        in_cen = ", ".join(f"'{c}'" for c in cens)
        if r.regra == "aliquota_em" and aliq:
            nums = [params._para_num(x) for x in lista]
            cond = f"{aliq} IS NOT NULL AND round({aliq}, 4) NOT IN ({', '.join(str(round(x, 4)) for x in nums if x is not None) or 'NULL'})"
            mostra = aliq
        elif r.regra == "cst_em":
            cond = f"{cst} IS NOT NULL AND {cst} NOT IN ({', '.join(repr(x) for x in lista) or 'NULL'})"
            mostra = cst
        elif r.regra == "valor_zero":
            cond = f"abs(coalesce({val}, 0)) > 0.005"
            mostra = val
        else:
            continue
        d = con.execute(f"""
            SELECT raiz, cnpj_estab, cenario, CAST({mostra} AS VARCHAR) AS encontrado, count(*) AS ocorrencias,
                   sum(valor) AS valor_operacoes, min(arquivo_id) AS arquivo_exemplo, min(linha_num) AS linha_exemplo
            FROM v_cenarios WHERE cenario IN ({in_cen}) AND {cond} AND {f.sql()}
              AND natureza NOT IN ('devolucao_venda', 'devolucao_compra')
            GROUP BY ALL""").df()
        if not d.empty:
            d.insert(3, "tributo", r.tributo)
            d.insert(4, "mensagem", r.mensagem)
            partes.append(d)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(
        columns=["raiz", "cnpj_estab", "cenario", "tributo", "mensagem", "encontrado", "ocorrencias",
                 "valor_operacoes", "arquivo_exemplo", "linha_exemplo"])


def alertas(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    """Lista unica: tipo, gravidade, raiz, cenario, descricao, ocorrencias, valor, onde_corrigir."""
    cols = ["tipo", "gravidade", "raiz", "cenario", "descricao", "ocorrencias", "valor", "onde_corrigir"]
    out = []
    nc = con.execute(f"""SELECT raiz, cenario, motivo, count(*) AS n, sum(valor) AS v FROM v_cenarios
                         WHERE cenario IN ('NC_S', 'NC_E') AND {f.sql()} GROUP BY ALL""").df()
    for x in nc.itertuples():
        out.append(("Não classificado", "alta", x.raiz, x.cenario, x.motivo or "Sem regra", x.n, x.v,
                    "Empresas ZFM / Produtos / CFOPs (Parâmetros)"))
    el = con.execute(f"""
        SELECT raiz, cenario_candidato, status_elegibilidade,
               CASE status_elegibilidade WHEN 'Não elegível' THEN requisitos_falha
                    WHEN 'Informação insuficiente para determinar' THEN requisitos_insuficientes
                    ELSE requisitos_pendentes END AS req, count(*) AS n, sum(valor) AS v
        FROM v_cenarios
        WHERE cenario_candidato SIMILAR TO 'C[0-9].*' AND status_elegibilidade <> 'Elegível' AND {f.sql()}
        GROUP BY ALL""").df()
    for x in el.itertuples():
        tipo, grav, onde = {
            "Não elegível": ("Não elegível: requisito não atendido (vai para a regra geral)", "alta",
                             "Conferir o requisito; a operação foi simulada pela regra geral (art. 453)"),
            "Informação insuficiente para determinar": ("Informação insuficiente para determinar", "alta",
                                                        "Cadastros > Produtos / Empresas ZFM"),
        }.get(x.status_elegibilidade, ("Potencialmente elegível: requisito não comprovado", "média",
                                       "Cadastros complementares (Parâmetros)"))
        out.append((tipo, grav, x.raiz, x.cenario_candidato, x.req, x.n, x.v, onde))
    from . import regras
    tab = regras.carregar()
    for r in regras.pendencias(tab):
        out.append(("Regra pendente de regulamentação", "baixa", "", "", f"{r.codigo} ({r.dispositivo}): {r.descricao}"
                    " — não aplicada; sem conclusão definitiva", 1, None, "Cadastros > Regras legais"))
    for cod in ("ART444_CP_IBS", "ART446_IBS_ENTRADA", "ART447_SS", "ART447_DEMAIS", "ART449_CP_IBS",
                "ART450_IBS_FINAL", "ART450_IBS_CAPITAL", "ART450_IBS_INTERMEDIARIO", "ART450_IBS_INFORMATICA",
                "ART450_IBS_CE100", "ART450_CBS_454", "ART450_CBS_DEMAIS", "ART454_LIMITE_TIPI"):
        if regras.pct(cod, tab) is None:
            out.append(("Percentual legal não parametrizado", "alta", "", "", cod, 1, None, "Cadastros > Regras legais"))
    cen_al = params.carregar("param_aliquotas_cenario")
    sem = cen_al[cen_al["aliq_cbs"].isna() | cen_al["aliq_ibs"].isna()]
    for x in sem.itertuples():
        out.append(("Alíquota não parametrizada", "alta", "", "", f"Cenário {x.cenario}, {x.ano}: CBS ou IBS vazia",
                    1, None, "Cadastros > Alíquotas por ano"))
    rc = params.carregar("param_regras_cenario").set_index("cenario")
    if "C4d" in rc.index and (rc.loc["C4d", "cp_ibs_450"] or rc.loc["C4d", "cp_cbs_450"]):
        out.append(("Operação do art. 448 recebendo crédito do art. 450", "alta", "", "C4d",
                    "A regra do cenário C4d concede crédito presumido do art. 450 (trava do art. 450 para operações do "
                    "art. 448)", 1, None, "Cadastros > Regras por cenário"))
    if "C3a" in rc.index and (rc.loc["C3a", "cp_ibs_450"] or rc.loc["C3a", "cp_cbs_450"]):
        out.append(("Crédito presumido duplicado (arts. 449 e 450)", "alta", "", "C3a",
                    "C3a com crédito do art. 449 e do art. 450 sobre a mesma operação", 1, None,
                    "Cadastros > Regras por cenário"))
    for x in conferencias(con, f).itertuples():
        out.append(("Divergência CST/alíquota", "média", x.raiz, x.cenario,
                    f"{x.mensagem} (encontrado: {x.encontrado}; ex.: arquivo {x.arquivo_exemplo}, linha {x.linha_exemplo})",
                    x.ocorrencias, x.valor_operacoes, "Conferir a escrituração"))
    c2 = con.execute(f"""SELECT raiz, cenario, count(*) AS n, sum(valor) AS v FROM v_cenarios
                         WHERE cenario IN ('C1b', 'C2a', 'C2b', 'C2c') AND req_ingresso <> 'ok' AND {f.sql()}
                         GROUP BY ALL""").df()
    for x in c2.itertuples():
        out.append(("Comprovação de ingresso (risco)", "média", x.raiz, x.cenario,
                    "Sem comprovação de ingresso (internamento Suframa), a alíquota zero cai e o crédito presumido é "
                    "estornado com acréscimos. Valor em risco: compare com a simulação conservadora (Cenários ZFM > Pendências).",
                    x.n, x.v, "Cadastros > Controle de internamento"))
    c1 = con.execute(f"""SELECT raiz, count(*) AS n, sum(valor) AS v FROM v_cenarios
                         WHERE cenario = 'C1a' AND categoria_origem = 'uso_consumo' AND {f.sql()} GROUP BY ALL""").df()
    for x in c1.itertuples():
        out.append(("Importação de uso e consumo", "média", x.raiz, "C1a",
                    "Bem de uso e consumo não se beneficia da suspensão do art. 443.", x.n, x.v, "Conferir"))
    ipi = ipi_por_produto(con, f)
    if not ipi.empty:
        for x in ipi[ipi["alerta_credito_estimulo"]].itertuples():
            out.append(("Produto candidato a perda no IBS", "alta", x.raiz, "C6",
                        f"{x.cod_item}: crédito estímulo atual {x.nivel_credito_estimulo:g}% > crédito presumido "
                        f"do art. 450 ({x.cp_ibs_pct:g}%)", 1, x.receita_anual, "Cadastros > Produtos"))
        for x in ipi[ipi["aliq_ipi"].isna()].itertuples():
            out.append(("Produto sem alíquota de IPI na EFD", "alta", x.raiz, "C6", f"{x.cod_item} – {x.descricao}", 1,
                        x.receita_anual, "Cadastros > Produtos"))
        for x in ipi[ipi["eh_tic"].fillna(False).astype(bool)].itertuples():
            out.append(("Produto TIC", "média", x.raiz, "C6",
                        f"{x.cod_item}: regra própria do art. 454, § 2º (análise manual)", 1, x.receita_anual,
                        "Análise manual"))
    ez = params.carregar("param_empresas_zfm")
    if not ez.empty:
        pend = ez[~ez["revisado"]]
        if len(pend):
            out.append(("Tipo ZFM definido automaticamente", "baixa", "", "", f"{len(pend)} CNPJ(s) sem revisão "
                        "(indústria incentivada/habilitado/não habilitado e regime)", len(pend), None,
                        "Cadastros > Empresas ZFM"))
    r5 = _as_is.reconciliacao_r5(con, f)
    if not r5.empty and (~r5["fecha"]).any():
        d = r5[~r5["fecha"]].groupby(["raiz", "tributo"], as_index=False)["diferenca"].agg(["sum", "count"])
        for x in d.itertuples():
            out.append(("Reconciliação (R5) não fecha", "alta", x.raiz, "", f"{x.tributo}: base de operações não "
                        "explica a apuração", x[4], x[3], "Perímetro e qualidade"))
    a = pd.DataFrame(out, columns=cols)
    if f.raizes is not None and not a.empty:
        a = a[(a["raiz"] == "") | a["raiz"].isin(f.raizes)]
    ordem = {"alta": 0, "média": 1, "baixa": 2}
    return a.sort_values(by="gravidade", key=lambda s: s.map(ordem)).reset_index(drop=True)
