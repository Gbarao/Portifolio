"""Carga As Is LIDA DA APURACAO (sem recalculo) e reconciliacao R5.

Etapa 4 do fluxo: por estabelecimento e mes (ICMS, IPI) e por empresa e mes (PIS/COFINS):
  ICMS   = ICMS a recolher (E110) + debitos especiais + obrigacoes do E116 alem desse total
           (premissa 'carga_icms_as_is'); credito estimulo aproveitado e informativo
  IPI    = saldo devedor do E520 (IPI a recolher)
  PIS    = M200 VL_TOT_CONT_REC  | COFINS = M600 VL_TOT_CONT_REC
           (EFD Contribuicoes e da empresa inteira: rateio pela receita dos estabelecimentos
            do AM, premissa 'rateio_pis_cofins_am')
Cada carga e decomposta em: saidas (debitos), entradas (creditos), deducoes/beneficios,
fundos/obrigacoes fora da apuracao e efeito de saldo credor (fecha a conta).

Etapa 5 (R5): recalcula a mesma carga trocando os debitos/creditos da apuracao pelos
da BASE DE OPERACOES (ajustes, deducoes e saldos continuam os da apuracao) e compara.
"""
from __future__ import annotations

import warnings

import duckdb
import pandas as pd

from . import beneficio_atual as ba
from . import params
from .filtros import TODOS, Filtro

TRIBUTOS = ["ICMS", "IPI", "PIS", "COFINS"]
COLS = ["raiz", "cnpj_estab", "mes", "tributo", "carga", "saidas_debitos", "entradas_creditos",
        "deducoes_beneficios", "fundos_fora_apuracao", "efeito_saldo", "credito_estimulo",
        "fundos_classificados", "saldo_credor_final", "fator_rateio_am", "arquivo_id", "linha_num"]


def _premissa(chave: str, padrao: str) -> str:
    return params.premissa(None, chave, padrao).strip().lower()


# ---------------------------------------------------------------------------
# ICMS e IPI (por estabelecimento)
# ---------------------------------------------------------------------------
def _icms(con: duckdb.DuckDBPyConnection, f: Filtro, ops: bool = False) -> pd.DataFrame:
    regra = _premissa("carga_icms_as_is", "e110_mais_excesso_e116")
    df = con.execute(f"""
        WITH e116 AS (SELECT arquivo_id, sum(VL_OR) AS total FROM raw_icms_e116 GROUP BY 1),
        docs AS (
            SELECT c.arquivo_id,
                   sum(c.VL_ICMS) FILTER (WHERE v.sentido = 'saida') AS deb_ops,
                   sum(c.VL_ICMS) FILTER (WHERE v.sentido = 'entrada') AS cred_ops
            FROM raw_icms_c190 c JOIN v_docs v ON v.arquivo_id = c.arquivo_id AND v.doc_linha = c.pai_linha
            WHERE NOT v.cancelado GROUP BY 1)
        SELECT a.raiz, a.cnpj_estab, a.mes, a.arquivo_id, a.linha_num,
               CAST(a.debitos AS DOUBLE) AS debitos, CAST(a.ajustes_debito + a.estornos_credito AS DOUBLE) AS aj_deb,
               CAST(a.creditos AS DOUBLE) AS creditos, CAST(a.ajustes_credito + a.estornos_debito AS DOUBLE) AS aj_cred,
               CAST(a.saldo_credor_anterior AS DOUBLE) AS saldo_ant, CAST(a.deducoes AS DOUBLE) AS deducoes,
               CAST(a.icms_recolher AS DOUBLE) AS recolher, CAST(coalesce(a.debitos_especiais, 0) AS DOUBLE) AS deb_esp,
               CAST(coalesce(e116.total, 0) AS DOUBLE) AS e116_total,
               CAST(a.credito_estimulo AS DOUBLE) AS credito_estimulo, CAST(a.fundos AS DOUBLE) AS fundos,
               CAST(a.saldo_credor_transportar AS DOUBLE) AS saldo_credor_final,
               CAST(coalesce(d.deb_ops, 0) AS DOUBLE) AS deb_ops, CAST(coalesce(d.cred_ops, 0) AS DOUBLE) AS cred_ops
        FROM v_apur_icms a
        JOIN v_estabelecimentos e ON e.cnpj = a.cnpj_estab AND e.no_amazonas
        LEFT JOIN e116 USING (arquivo_id) LEFT JOIN docs d USING (arquivo_id)
        WHERE {f.sql('a.raiz', 'a.cnpj_estab', 'a.mes')}""").df()
    if df.empty:
        return pd.DataFrame(columns=COLS)
    base = df["recolher"] + df["deb_esp"]
    if regra == "somente_e110":
        extra = 0.0 * base
    elif regra == "e110_mais_fundos":
        extra = df["fundos"]
    else:
        extra = (df["e116_total"] - base).clip(lower=0)
    if ops:  # R5: debitos e creditos da base de operacoes
        saldo = df["deb_ops"] + df["aj_deb"] - df["cred_ops"] - df["aj_cred"] - df["saldo_ant"]
        recolher = (saldo.clip(lower=0) - df["deducoes"]).clip(lower=0)
        carga = recolher + df["deb_esp"] + extra
        deb, cred = df["deb_ops"], df["cred_ops"]
    else:
        carga = base + extra
        deb, cred = df["debitos"], df["creditos"]
    out = pd.DataFrame({
        "raiz": df["raiz"], "cnpj_estab": df["cnpj_estab"], "mes": df["mes"], "tributo": "ICMS",
        "carga": carga, "saidas_debitos": deb + df["aj_deb"] + df["deb_esp"],
        "entradas_creditos": -(cred + df["aj_cred"]), "deducoes_beneficios": -df["deducoes"],
        "fundos_fora_apuracao": extra, "credito_estimulo": df["credito_estimulo"],
        "fundos_classificados": df["fundos"], "saldo_credor_final": df["saldo_credor_final"],
        "fator_rateio_am": 1.0, "arquivo_id": df["arquivo_id"], "linha_num": df["linha_num"]})
    out["efeito_saldo"] = out["carga"] - (out["saidas_debitos"] + out["entradas_creditos"]
                                         + out["deducoes_beneficios"] + out["fundos_fora_apuracao"])
    return out[COLS]


def _ipi(con: duckdb.DuckDBPyConnection, f: Filtro, ops: bool = False) -> pd.DataFrame:
    df = con.execute(f"""
        WITH docs AS (
            SELECT c.arquivo_id,
                   sum(c.VL_IPI) FILTER (WHERE v.sentido = 'saida') AS deb_ops,
                   sum(c.VL_IPI) FILTER (WHERE v.sentido = 'entrada') AS cred_ops
            FROM raw_icms_c190 c JOIN v_docs v ON v.arquivo_id = c.arquivo_id AND v.doc_linha = c.pai_linha
            WHERE NOT v.cancelado GROUP BY 1)
        SELECT a.raiz, a.cnpj_estab, a.mes, a.arquivo_id, a.linha_num,
               CAST(a.debitos AS DOUBLE) AS debitos, CAST(a.outros_debitos AS DOUBLE) AS od,
               CAST(a.creditos AS DOUBLE) AS creditos, CAST(a.outros_creditos AS DOUBLE) AS oc,
               CAST(a.saldo_anterior AS DOUBLE) AS saldo_ant, CAST(a.saldo_devedor AS DOUBLE) AS devedor,
               CAST(a.saldo_credor AS DOUBLE) AS credor,
               CAST(coalesce(d.deb_ops, 0) AS DOUBLE) AS deb_ops, CAST(coalesce(d.cred_ops, 0) AS DOUBLE) AS cred_ops
        FROM v_apur_ipi a
        JOIN v_estabelecimentos e ON e.cnpj = a.cnpj_estab AND e.no_amazonas
        LEFT JOIN docs d USING (arquivo_id)
        WHERE {f.sql('a.raiz', 'a.cnpj_estab', 'a.mes')}""").df()
    if df.empty:
        return pd.DataFrame(columns=COLS)
    deb = df["deb_ops"] if ops else df["debitos"]
    cred = df["cred_ops"] if ops else df["creditos"]
    carga = (deb + df["od"] - cred - df["oc"] - df["saldo_ant"]).clip(lower=0) if ops else df["devedor"]
    out = pd.DataFrame({
        "raiz": df["raiz"], "cnpj_estab": df["cnpj_estab"], "mes": df["mes"], "tributo": "IPI",
        "carga": carga, "saidas_debitos": deb + df["od"], "entradas_creditos": -(cred + df["oc"]),
        "deducoes_beneficios": 0.0, "fundos_fora_apuracao": 0.0, "credito_estimulo": 0.0,
        "fundos_classificados": 0.0, "saldo_credor_final": df["credor"], "fator_rateio_am": 1.0,
        "arquivo_id": df["arquivo_id"], "linha_num": df["linha_num"]})
    out["efeito_saldo"] = out["carga"] - (out["saidas_debitos"] + out["entradas_creditos"])
    return out[COLS]


# ---------------------------------------------------------------------------
# PIS/COFINS (por empresa; rateio para os estabelecimentos do AM)
# ---------------------------------------------------------------------------
def fator_am(con: duckdb.DuckDBPyConnection, f: Filtro) -> pd.DataFrame:
    """Parcela da receita (itens da EFD Contribuicoes) dos estabelecimentos do AM
    selecionados, por empresa e mes. 1,0 se a premissa for 'nenhum'."""
    regra = _premissa("rateio_pis_cofins_am", "receita")
    df = con.execute(f"""
        SELECT s.raiz, s.mes,
               sum(CAST(s.receita AS DOUBLE)) AS total,
               sum(CAST(s.receita AS DOUBLE)) FILTER (WHERE s.estab_no_am AND {f.sql(None, 's.cnpj_estab', None)})
                   AS am
        FROM v_saidas_item s WHERE s.eh_receita AND {f.sql('s.raiz', None, 's.mes')}
        GROUP BY 1, 2""").df()
    if df.empty:
        return pd.DataFrame(columns=["raiz", "mes", "fator"])
    if regra == "nenhum":
        df["fator"] = 1.0
    else:
        df["fator"] = (df["am"].fillna(0) / df["total"].where(df["total"] != 0)).fillna(1.0)
    return df[["raiz", "mes", "fator"]]


def _pis_cofins(con: duckdb.DuckDBPyConnection, f: Filtro, ops: bool = False) -> pd.DataFrame:
    partes = []
    fat = fator_am(con, f)
    for trib, tot, det in (("PIS", "raw_contrib_m200", "raw_contrib_m210"),
                           ("COFINS", "raw_contrib_m600", "raw_contrib_m610")):
        campo = "vl_pis" if trib == "PIS" else "vl_cofins"
        campo_a = "VL_PIS" if trib == "PIS" else "VL_COFINS"
        df = con.execute(f"""
            WITH det AS (SELECT arquivo_id, sum(VL_CONT_APUR) AS apur, sum(VL_CONT_PER) AS per
                         FROM {det} GROUP BY 1),
            ops AS (
                SELECT raiz, mes, sum(v) AS contrib_ops FROM (
                    SELECT raiz, mes, CAST(coalesce({campo}, 0) AS DOUBLE) AS v FROM v_saidas_item
                    UNION ALL
                    SELECT a.raiz, month(a.dt_ini), CAST(coalesce(x.{campo_a}, 0) AS DOUBLE)
                    FROM raw_contrib_a100 x JOIN arquivos a USING (arquivo_id) WHERE a.ativo AND x.IND_OPER = '1'
                    UNION ALL
                    SELECT a.raiz, month(a.dt_ini), CAST(coalesce(x.{campo_a}, 0) AS DOUBLE)
                    FROM raw_contrib_f100 x JOIN arquivos a USING (arquivo_id)
                    WHERE a.ativo AND x.IND_OPER IN ('1', '2')) GROUP BY 1, 2)
            SELECT a.raiz, month(a.dt_ini) AS mes, a.arquivo_id, m.linha_num,
                   CAST(m.VL_TOT_CONT_NC_PER + m.VL_TOT_CONT_CUM_PER AS DOUBLE) AS contrib,
                   CAST(m.VL_TOT_CRED_DESC + m.VL_TOT_CRED_DESC_ANT AS DOUBLE) AS creditos,
                   CAST(m.VL_RET_NC + m.VL_OUT_DED_NC + m.VL_RET_CUM + m.VL_OUT_DED_CUM AS DOUBLE) AS deducoes,
                   CAST(m.VL_TOT_CONT_REC AS DOUBLE) AS recolher,
                   CAST(coalesce(det.apur, 0) AS DOUBLE) AS apur, CAST(coalesce(det.per, 0) AS DOUBLE) AS per,
                   CAST(coalesce(o.contrib_ops, 0) AS DOUBLE) AS contrib_ops
            FROM {tot} m JOIN arquivos a USING (arquivo_id)
            LEFT JOIN det USING (arquivo_id)
            LEFT JOIN ops o ON o.raiz = a.raiz AND o.mes = month(a.dt_ini)
            WHERE a.ativo AND a.tipo = 'CONTRIB' AND {f.sql('a.raiz', None, 'month(a.dt_ini)')}""").df()
        if df.empty:
            continue
        df = df.merge(fat, on=["raiz", "mes"], how="left")
        df["fator"] = df["fator"].fillna(1.0)
        if ops:  # R5: contribuicao sobre as operacoes + ajustes do bloco M (nao operacionais)
            contrib = df["contrib_ops"] + (df["per"] - df["apur"])
            carga = (contrib - df["creditos"] - df["deducoes"]).clip(lower=0)
        else:
            contrib = df["contrib"]
            carga = df["recolher"]
        k = df["fator"]
        o = pd.DataFrame({
            "raiz": df["raiz"], "cnpj_estab": None, "mes": df["mes"], "tributo": trib,
            "carga": carga * k, "saidas_debitos": contrib * k, "entradas_creditos": -df["creditos"] * k,
            "deducoes_beneficios": -df["deducoes"] * k, "fundos_fora_apuracao": 0.0,
            "credito_estimulo": 0.0, "fundos_classificados": 0.0, "saldo_credor_final": None,
            "fator_rateio_am": k, "arquivo_id": df["arquivo_id"], "linha_num": df["linha_num"]})
        o["efeito_saldo"] = o["carga"] - (o["saidas_debitos"] + o["entradas_creditos"] + o["deducoes_beneficios"])
        partes.append(o[COLS])
    if not partes:
        return pd.DataFrame(columns=COLS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def carga_mensal(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS, ops: bool = False) -> pd.DataFrame:
    """Carga As Is por (raiz, estabelecimento, mes, tributo). ops=True: recalculada (R5)."""
    partes = [p for p in (_icms(con, f, ops), _ipi(con, f, ops), _pis_cofins(con, f, ops)) if not p.empty]
    if not partes:
        return pd.DataFrame(columns=COLS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return pd.concat([p.astype({"cnpj_estab": object, "saldo_credor_final": float}) for p in partes],
                         ignore_index=True)


def meses_observados(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    """Meses com arquivo ativo por empresa (dentro do periodo filtrado)."""
    ano = int(params.premissa_num("ano_base", 2026))
    return con.execute(f"""
        SELECT raiz, month(dt_ini) AS mes FROM arquivos
        WHERE ativo AND year(dt_ini) = {ano} AND {f.sql('raiz', None, 'month(dt_ini)')}
        GROUP BY 1, 2 ORDER BY 1, 2""").df()


def anualizar(mensal: pd.DataFrame, meses: pd.DataFrame, valor: str = "carga",
              chaves: tuple[str, ...] = ("raiz", "tributo")) -> pd.DataFrame:
    """YTD ÷ numero de meses observados da empresa × 12."""
    if mensal.empty:
        return pd.DataFrame(columns=list(chaves) + [valor])
    n = meses.groupby("raiz")["mes"].nunique().rename("n_meses")
    s = mensal.groupby(list(chaves), as_index=False)[valor].sum().merge(n, on="raiz", how="left")
    s[valor] = s[valor] / s["n_meses"].where(s["n_meses"] > 0) * 12
    return s.drop(columns="n_meses").fillna({valor: 0.0})


def teses_mensais(con: duckdb.DuckDBPyConnection, f: Filtro, para_as_is: bool) -> pd.DataFrame:
    """Efeito mensal das teses (reducao de carga) por empresa e tributo, no ano-base.

    Teses 'ativas' ja estao na apuracao (premissa teses_ativas_ja_na_apuracao) e nao
    ajustam a carga As Is; no To Be elas ja vem embutidas no ICMS × fator."""
    t = params.carregar("param_teses")
    if t.empty:
        return pd.DataFrame(columns=["raiz", "mes", "tributo", "valor"])
    ja = _premissa("teses_ativas_ja_na_apuracao", "sim") in ("sim", "s")
    if ja:
        t = t[t["status"].str.strip().str.lower() != "ativa"]
    ano = int(params.premissa_num("ano_base", 2026))
    meses = meses_observados(con, f)
    rec = receita_incentivada_mensal(con, f)
    geral = ba._aliq_geral()
    linhas = []
    for tese in t.itertuples():
        alvo = meses if tese.raiz_cnpj in ("", "todas") else meses[meses.raiz == tese.raiz_cnpj]
        for r in alvo.itertuples():
            if not ba.em_vigencia(tese, ano, r.mes):
                continue
            ri = rec.get((r.raiz, r.mes), 0.0)
            v = ba.valor_tese(tese, ri, geral)
            if v:
                linhas.append({"raiz": r.raiz, "mes": r.mes, "tributo": tese.tributo.upper(), "valor": v,
                               "tese_id": tese.tese_id})
    return pd.DataFrame(linhas, columns=["raiz", "mes", "tributo", "valor", "tese_id"])


def receita_incentivada_mensal(con: duckdb.DuckDBPyConnection, f: Filtro) -> dict:
    r = con.execute(f"""SELECT raiz, mes, sum(valor) FROM v_base_operacoes
                        WHERE sentido = 'saida' AND incentivado AND tipo_operacao <> 'exportacao'
                          AND {f.sql()} GROUP BY 1, 2""").fetchall()
    return {(a, b): float(c or 0) for a, b, c in r}


def carga_anual(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS, com_teses: bool = False) -> pd.DataFrame:
    """Carga As Is anualizada por empresa e tributo (apuracao), com e sem recalculo (R5).

    Colunas: raiz, tributo, as_is (apuracao), as_is_base (recalculada das operacoes),
    ajuste_reconciliacao (= as_is − as_is_base), teses."""
    meses = meses_observados(con, f)
    ap = anualizar(carga_mensal(con, f), meses)
    rc = anualizar(carga_mensal(con, f, ops=True), meses).rename(columns={"carga": "as_is_base"})
    out = ap.rename(columns={"carga": "as_is"}).merge(rc, on=["raiz", "tributo"], how="outer").fillna(0.0)
    out["teses"] = 0.0
    if com_teses:
        tm = teses_mensais(con, f, True)
        if not tm.empty:
            ta = anualizar(tm, meses, "valor").rename(columns={"valor": "tese"})
            out = out.merge(ta, on=["raiz", "tributo"], how="left").fillna({"tese": 0.0})
            out["teses"] = out["tese"]
            out = out.drop(columns="tese")
            out["as_is"] -= out["teses"]
            out["as_is_base"] -= out["teses"]
    out["ajuste_reconciliacao"] = out["as_is"] - out["as_is_base"]
    return out


def reconciliacao_r5(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    """R5: carga da apuracao × carga recalculada a partir da base de operacoes."""
    a = carga_mensal(con, f)
    b = carga_mensal(con, f, ops=True)
    if a.empty:
        return pd.DataFrame(columns=["raiz", "cnpj_estab", "mes", "tributo", "carga_apuracao",
                                     "carga_base_operacoes", "diferenca", "tolerancia", "fecha"])
    k = ["raiz", "cnpj_estab", "mes", "tributo"]
    a = a.assign(cnpj_estab=a["cnpj_estab"].fillna("(empresa)"))
    b = b.assign(cnpj_estab=b["cnpj_estab"].fillna("(empresa)"))
    m = a[k + ["carga"]].rename(columns={"carga": "carga_apuracao"}).merge(
        b[k + ["carga"]].rename(columns={"carga": "carga_base_operacoes"}), on=k, how="outer").fillna(0.0)
    m["diferenca"] = m["carga_apuracao"] - m["carga_base_operacoes"]
    tol = params.premissa_num("tolerancia_conciliacao", 1.0)
    pct = params.premissa_num("tolerancia_receita_pct", 0.5) / 100
    m["tolerancia"] = [max(tol, pct * abs(c)) if t in ("PIS", "COFINS") else tol
                       for t, c in zip(m["tributo"], m["carga_apuracao"])]
    m["fecha"] = m["diferenca"].abs() <= m["tolerancia"]
    return m.sort_values(k).reset_index(drop=True)


def saldos_credores_finais(con: duckdb.DuckDBPyConnection, f: Filtro = TODOS) -> pd.DataFrame:
    """Saldos credores ao fim do periodo (informacao para a transicao)."""
    return con.execute(f"""
        WITH i AS (SELECT raiz, sum(saldo_credor_transportar) AS icms FROM (
                       SELECT * FROM v_apur_icms WHERE {f.sql()}
                       QUALIFY mes = max(mes) OVER (PARTITION BY cnpj_estab)) GROUP BY 1),
             p AS (SELECT raiz, sum(saldo_credor) AS ipi FROM (
                       SELECT * FROM v_apur_ipi WHERE {f.sql()}
                       QUALIFY mes = max(mes) OVER (PARTITION BY cnpj_estab)) GROUP BY 1),
             c AS (SELECT raiz, sum(coalesce(saldo_credito_pis, 0)) AS pis,
                          sum(coalesce(saldo_credito_cofins, 0)) AS cofins FROM (
                       SELECT * FROM v_apur_pis_cofins WHERE {f.sql(estab=None)}
                       QUALIFY mes = max(mes) OVER (PARTITION BY raiz)) GROUP BY 1)
        SELECT coalesce(i.raiz, p.raiz, c.raiz) AS raiz, i.icms, p.ipi, c.pis, c.cofins
        FROM i FULL JOIN p ON p.raiz = i.raiz FULL JOIN c ON c.raiz = coalesce(i.raiz, p.raiz)
        ORDER BY 1""").df()
