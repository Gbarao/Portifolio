"""Conciliacoes Q3 a Q11 (SPEC 7.1). Cada funcao devolve as divergencias
(DataFrame vazio = conciliado). Pressupoe visoes.preparar(con) executado."""
from __future__ import annotations

import duckdb
import pandas as pd

from . import params


def _tol() -> float:
    return params.premissa_num("tolerancia_conciliacao", 1.0)


def q3_c170_x_c100(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH s AS (
            SELECT arquivo_id, pai_linha, sum(VL_ITEM) AS itens, sum(VL_ICMS) AS icms_itens,
                   sum(VL_IPI) AS ipi_itens
            FROM raw_icms_c170 GROUP BY 1, 2)
        SELECT d.raiz, d.cnpj_estab, d.mes, d.num_doc, d.chv_nfe, d.arquivo_id, d.doc_linha,
               d.vl_merc AS mercadoria_c100, s.itens AS mercadoria_c170,
               d.vl_icms AS icms_c100, s.icms_itens AS icms_c170,
               d.vl_ipi AS ipi_c100, s.ipi_itens AS ipi_c170
        FROM v_docs d JOIN s ON s.arquivo_id = d.arquivo_id AND s.pai_linha = d.doc_linha
        WHERE NOT d.cancelado AND (abs(coalesce(d.vl_merc, 0) - s.itens) > ?
              OR abs(coalesce(d.vl_icms, 0) - coalesce(s.icms_itens, 0)) > ?
              OR abs(coalesce(d.vl_ipi, 0) - coalesce(s.ipi_itens, 0)) > ?)
        ORDER BY 1, 2, 3""", [_tol()] * 3).df()


def q4_c190_x_c100(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH s AS (
            SELECT arquivo_id, pai_linha, sum(VL_OPR) AS opr, sum(VL_ICMS) AS icms, sum(VL_IPI) AS ipi
            FROM raw_icms_c190 GROUP BY 1, 2)
        SELECT d.raiz, d.cnpj_estab, d.mes, d.num_doc, d.chv_nfe, d.arquivo_id, d.doc_linha,
               d.vl_doc AS valor_c100, s.opr AS valor_c190, d.vl_icms AS icms_c100, s.icms AS icms_c190,
               d.vl_ipi AS ipi_c100, s.ipi AS ipi_c190
        FROM v_docs d JOIN s ON s.arquivo_id = d.arquivo_id AND s.pai_linha = d.doc_linha
        WHERE NOT d.cancelado AND (abs(coalesce(d.vl_doc, 0) - coalesce(s.opr, 0)) > ?
              OR abs(coalesce(d.vl_icms, 0) - coalesce(s.icms, 0)) > ?
              OR abs(coalesce(d.vl_ipi, 0) - coalesce(s.ipi, 0)) > ?)
        ORDER BY 1, 2, 3""", [_tol()] * 3).df()


def q5_docs_x_e110(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH d AS (
            SELECT c.arquivo_id,
                   sum(c.VL_ICMS) FILTER (WHERE v.sentido = 'saida') AS icms_saidas,
                   sum(c.VL_ICMS) FILTER (WHERE v.sentido = 'entrada') AS icms_entradas
            FROM raw_icms_c190 c JOIN v_docs v ON v.arquivo_id = c.arquivo_id AND v.doc_linha = c.pai_linha
            WHERE NOT v.cancelado GROUP BY 1)
        SELECT e.raiz, e.cnpj_estab, e.mes, e.arquivo_id,
               coalesce(d.icms_saidas, 0) AS icms_saidas_docs, e.debitos AS debitos_e110,
               coalesce(d.icms_saidas, 0) - e.debitos AS dif_debitos,
               coalesce(d.icms_entradas, 0) AS icms_entradas_docs, e.creditos AS creditos_e110,
               coalesce(d.icms_entradas, 0) - e.creditos AS dif_creditos
        FROM v_apur_icms e LEFT JOIN d USING (arquivo_id)
        WHERE abs(coalesce(d.icms_saidas, 0) - e.debitos) > ? OR abs(coalesce(d.icms_entradas, 0) - e.creditos) > ?
        ORDER BY 1, 2, 3""", [_tol()] * 2).df()


def q6_docs_x_e520(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH d AS (
            SELECT c.arquivo_id,
                   sum(c.VL_IPI) FILTER (WHERE v.sentido = 'saida') AS ipi_saidas,
                   sum(c.VL_IPI) FILTER (WHERE v.sentido = 'entrada') AS ipi_entradas
            FROM raw_icms_c190 c JOIN v_docs v ON v.arquivo_id = c.arquivo_id AND v.doc_linha = c.pai_linha
            WHERE NOT v.cancelado GROUP BY 1)
        SELECT e.raiz, e.cnpj_estab, e.mes, e.arquivo_id,
               coalesce(d.ipi_saidas, 0) AS ipi_saidas_docs, e.debitos AS debitos_e520,
               coalesce(d.ipi_entradas, 0) AS ipi_entradas_docs, e.creditos AS creditos_e520
        FROM v_apur_ipi e LEFT JOIN d USING (arquivo_id)
        WHERE abs(coalesce(d.ipi_saidas, 0) - e.debitos) > ? OR abs(coalesce(d.ipi_entradas, 0) - e.creditos) > ?
        ORDER BY 1, 2, 3""", [_tol()] * 2).df()


def q7_icms_x_contrib(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Escrituracao detalhada: cruzamento por CHV_NFE. Consolidada: total de saidas
    por estabelecimento e mes (C180 x C190 da ICMS/IPI)."""
    detalhada = con.execute("""
        WITH ci AS (
            SELECT raiz, cnpj_estab, mes, chv_nfe, num_doc, vl_doc, vl_pis, vl_cofins
            FROM v_docs WHERE NOT cancelado AND chv_nfe IS NOT NULL),
        cc AS (
            SELECT a.raiz, d.cnpj_estab, month(a.dt_ini) AS mes, d.CHV_NFE AS chv_nfe,
                   d.NUM_DOC AS num_doc, d.VL_DOC AS vl_doc, d.VL_PIS AS vl_pis, d.VL_COFINS AS vl_cofins
            FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
            WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN ('02','03','04','05')
              AND d.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)),
        estab_det AS (SELECT DISTINCT cnpj_estab, mes FROM cc)
        SELECT coalesce(ci.raiz, cc.raiz) AS raiz, coalesce(ci.cnpj_estab, cc.cnpj_estab) AS cnpj_estab,
               coalesce(ci.mes, cc.mes) AS mes, coalesce(ci.chv_nfe, cc.chv_nfe) AS chv_nfe,
               CASE WHEN cc.chv_nfe IS NULL THEN 'Só na EFD ICMS/IPI'
                    WHEN ci.chv_nfe IS NULL THEN 'Só na EFD Contribuições'
                    ELSE 'Valores diferentes' END AS problema,
               ci.vl_doc AS valor_icms_ipi, cc.vl_doc AS valor_contrib,
               ci.vl_pis AS pis_icms_ipi, cc.vl_pis AS pis_contrib,
               ci.vl_cofins AS cofins_icms_ipi, cc.vl_cofins AS cofins_contrib
        FROM ci FULL OUTER JOIN cc ON ci.chv_nfe = cc.chv_nfe
        WHERE (ci.chv_nfe IS NULL OR EXISTS (SELECT 1 FROM estab_det e
                                          WHERE e.cnpj_estab = ci.cnpj_estab AND e.mes = ci.mes))
          AND (ci.chv_nfe IS NULL OR cc.chv_nfe IS NULL
               OR abs(coalesce(ci.vl_doc, 0) - coalesce(cc.vl_doc, 0)) > ?
               OR abs(coalesce(ci.vl_pis, 0) - coalesce(cc.vl_pis, 0)) > ?
               OR abs(coalesce(ci.vl_cofins, 0) - coalesce(cc.vl_cofins, 0)) > ?)
        """, [_tol()] * 3).df()
    consolidada = con.execute("""
        WITH c180 AS (
            SELECT a.raiz, h.cnpj_estab, month(a.dt_ini) AS mes, sum(h.VL_TOT_ITEM) AS saidas_c180
            FROM raw_contrib_c180 h JOIN arquivos a USING (arquivo_id)
            WHERE a.ativo AND h.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)
            GROUP BY ALL),
        icms AS (
            SELECT cnpj_estab, mes, sum(vl_opr - coalesce(vl_ipi_c190, 0)) AS saidas_c190
            FROM v_saidas_doc WHERE emissao = 'propria' GROUP BY ALL)
        SELECT c.raiz, c.cnpj_estab, c.mes, NULL AS chv_nfe,
               'Total de saídas diferente (escrituração consolidada)' AS problema,
               i.saidas_c190 AS valor_icms_ipi, c.saidas_c180 AS valor_contrib
        FROM c180 c LEFT JOIN icms i USING (cnpj_estab, mes)
        WHERE abs(coalesce(i.saidas_c190, 0) - c.saidas_c180) > ?""", [_tol()]).df()
    return pd.concat([detalhada, consolidada], ignore_index=True)


def q8_receita_contrib_x_icms(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        WITH c AS (
            SELECT raiz, mes, sum(receita_tributada + receita_nao_tributada_pis) AS receita_bloco_m
            FROM v_apur_pis_cofins GROUP BY ALL),
        i AS (
            SELECT raiz, mes, sum(vl_opr - coalesce(vl_ipi_c190, 0)) AS receita_c190
            FROM v_saidas_doc WHERE eh_receita GROUP BY ALL)
        SELECT coalesce(c.raiz, i.raiz) AS raiz, coalesce(c.mes, i.mes) AS mes,
               c.receita_bloco_m, i.receita_c190,
               coalesce(c.receita_bloco_m, 0) - coalesce(i.receita_c190, 0) AS diferenca,
               CASE WHEN coalesce(c.raiz, i.raiz) IN (SELECT raiz FROM v_estabelecimentos
                                                      WHERE NOT no_amazonas)
                    THEN 'Empresa tem estabelecimento fora do AM (o bloco M inclui a receita dele)'
                    ELSE '' END AS observacao
        FROM c FULL OUTER JOIN i ON c.raiz = i.raiz AND c.mes = i.mes
        WHERE abs(coalesce(c.receita_bloco_m, 0) - coalesce(i.receita_c190, 0)) > ?
        ORDER BY 1, 2""", [_tol()]).df()


def q9_aliquotas_pis_cofins(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    pis = params.premissa_lista_num("aliq_pis_zfm_validas") or [0.65, 1.3, 0]
    cof = params.premissa_lista_num("aliq_cofins_zfm_validas") or [3, 6, 0]
    df = con.execute("""
        SELECT s.raiz, s.cnpj_estab, s.mes, s.cod_item, s.cfop, s.reg_origem, s.arquivo_id, s.linha_num,
               s.receita, CAST(s.aliq_pis AS DOUBLE) AS aliq_pis, CAST(s.aliq_cofins AS DOUBLE) AS aliq_cofins
        FROM v_saidas_item s JOIN param_produtos p ON p.raiz_cnpj = s.raiz AND p.cod_item = s.cod_item
        WHERE p.incentivado AND s.categoria_cfop = 'venda_producao' AND s.estab_no_am
          AND s.cfop NOT LIKE '7%'""").df()
    if df.empty:
        return df
    pares_validos = {(0.65, 3.0), (1.3, 6.0), (0.0, 0.0)}
    ok_pis = df["aliq_pis"].round(4).isin([round(x, 4) for x in pis])
    ok_cof = df["aliq_cofins"].round(4).isin([round(x, 4) for x in cof])
    par = [(round(a, 4) if pd.notna(a) else None, round(b, 4) if pd.notna(b) else None) in pares_validos
           for a, b in zip(df["aliq_pis"], df["aliq_cofins"])]
    return df[~(ok_pis & ok_cof & pd.Series(par, index=df.index))].reset_index(drop=True)


def q10_cst_ipi_incentivado(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    isentos = [c.strip() for c in params.premissa(None, "cst_ipi_isento", "52").split(";") if c.strip()]
    lista = ", ".join(f"'{c}'" for c in isentos) or "'52'"
    return con.execute(f"""
        SELECT s.raiz, s.cnpj_estab, s.mes, s.cod_item, s.cfop, s.cst_ipi, s.reg_origem,
               s.arquivo_id, s.linha_num, s.receita
        FROM v_saidas_item s JOIN param_produtos p ON p.raiz_cnpj = s.raiz AND p.cod_item = s.cod_item
        WHERE p.incentivado AND s.categoria_cfop = 'venda_producao' AND s.cst_ipi IS NOT NULL
          AND s.cst_ipi NOT IN ({lista}) AND s.cfop NOT LIKE '7%'
        ORDER BY 1, 2, 3""").df()


def q11_codigos_nao_classificados(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT registro, codigo, any_value(descricao) AS descricao, count(*) AS ocorrencias,
               sum(valor) AS valor_total
        FROM v_ajustes_icms WHERE nao_classificado GROUP BY 1, 2 ORDER BY valor_total DESC""").df()


CHECAGENS = {
    "Q3": ("C170 × C100 (itens × documento)", q3_c170_x_c100),
    "Q4": ("C190 × C100 (analítico × documento)", q4_c190_x_c100),
    "Q5": ("Documentos × E110 (ICMS)", q5_docs_x_e110),
    "Q6": ("Documentos × E520 (IPI)", q6_docs_x_e520),
    "Q7": ("EFD ICMS/IPI × EFD Contribuições", q7_icms_x_contrib),
    "Q8": ("Receita do bloco M × saídas do C190", q8_receita_contrib_x_icms),
    "Q9": ("Alíquotas de PIS/COFINS nas saídas incentivadas", q9_aliquotas_pis_cofins),
    "Q10": ("CST de IPI nas saídas incentivadas", q10_cst_ipi_incentivado),
    "Q11": ("Códigos de ajuste E111/E116 sem classificação", q11_codigos_nao_classificados),
}


def filtrar(df: pd.DataFrame, raizes: list[str] | None) -> pd.DataFrame:
    if raizes is None or df.empty or "raiz" not in df.columns:
        return df
    return df[df["raiz"].isin(raizes)]
