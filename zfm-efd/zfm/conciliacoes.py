"""Conciliacoes (etapa 5). Cada funcao devolve as divergencias (DataFrame vazio = conciliado).
Pressupoe visoes.preparar(con) executado.

Correspondencia com o roteiro de reconciliacao:
  R1 = Q5 (documentos × E110)      R2 = Q6 (documentos × E520)
  R3 = Q8 (receita × bloco M, tolerancia em %)   R4 = Q7 (mesmo documento nas duas EFDs)
  R5 = zfm/as_is.reconciliacao_r5 (carga recalculada pela base × carga da apuracao)
"""
from __future__ import annotations

import duckdb
import pandas as pd

from . import params
from .filtros import Filtro


def _tol() -> float:
    return params.premissa_num("tolerancia_conciliacao", 1.0)


def _pct() -> float:
    return params.premissa_num("tolerancia_receita_pct", 0.5) / 100


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
        UNION ALL
        SELECT a.raiz, d.cnpj_estab, month(a.dt_ini), d.NUM_DOC, d.CHV_NFE, d.arquivo_id, d.linha_num,
               d.VL_MERC, x.itens, NULL, NULL, NULL, NULL
        FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
        JOIN (SELECT arquivo_id, pai_linha, sum(VL_ITEM) AS itens FROM raw_contrib_c170 GROUP BY 1, 2) x
             ON x.arquivo_id = d.arquivo_id AND x.pai_linha = d.linha_num
        WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN ('02','03','04','05')
          AND abs(coalesce(d.VL_MERC, 0) - x.itens) > ?
        ORDER BY 1, 2, 3""", [_tol()] * 4).df()


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
    """R4: pareamento dos documentos Fiscal × Contribuicoes (zfm/cruzamentos.py): documento so numa EFD
    (com as duas carregadas) ou com cabecalho diferente; na escrituracao consolidada, total de saidas
    por estabelecimento e mes (C180 × C190 da ICMS/IPI)."""
    from . import cruzamentos
    detalhada = cruzamentos.pareamento_divergencias(con)
    consolidada = con.execute("""
        WITH c180 AS (
            SELECT a.raiz, h.cnpj_estab, month(a.dt_ini) AS mes, sum(h.VL_TOT_ITEM) AS saidas_c180
            FROM raw_contrib_c180 h JOIN arquivos a USING (arquivo_id)
            WHERE a.ativo AND h.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)
            GROUP BY ALL),
        icms AS (
            SELECT cnpj_estab, mes,
                   sum(vl_opr - coalesce(vl_ipi_c190, 0) - coalesce(vl_icms_st_c190, 0)) AS saidas_c190
            FROM v_saidas_doc WHERE emissao = 'propria' GROUP BY ALL)
        SELECT c.raiz, c.cnpj_estab, c.mes, 'saida' AS sentido, 'Fiscal × Contribuições' AS fonte,
               'Total de saídas diferente (escrituração consolidada C180 × C190)' AS problema,
               NULL AS num_doc, NULL AS chv_nfe, NULL AS participante,
               i.saidas_c190 AS valor_fiscal, c.saidas_c180 AS valor_contrib
        FROM c180 c LEFT JOIN icms i USING (cnpj_estab, mes)
        WHERE abs(coalesce(i.saidas_c190, 0) - c.saidas_c180) > greatest(?, ? * abs(c.saidas_c180))""",
                              [_tol(), _pct()]).df()
    return pd.concat([detalhada, consolidada], ignore_index=True)


def q8_receita_contrib_x_icms(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """R3: receitas de venda da base × receitas do bloco M (M210/M610 + M400/M800), por
    empresa e mes, tolerancia em % (premissa tolerancia_receita_pct).

    As duas pontas sao da EFD Contribuicoes da empresa inteira (inclui estabelecimentos fora
    do AM); a ponta "Fiscal" (C190 dos estabelecimentos do AM) e mostrada para referencia."""
    return con.execute("""
        WITH m AS (
            SELECT raiz, mes, sum(receita_tributada + receita_nao_tributada_pis) AS receita_bloco_m
            FROM v_apur_pis_cofins GROUP BY ALL),
        b AS (
            SELECT raiz, mes, sum(v) AS receita_base FROM (
                SELECT raiz, mes, CAST(receita AS DOUBLE) AS v FROM v_saidas_item WHERE eh_receita
                UNION ALL
                SELECT a.raiz, month(a.dt_ini), CAST(x.VL_DOC - coalesce(x.VL_DESC, 0) AS DOUBLE)
                FROM raw_contrib_a100 x JOIN arquivos a USING (arquivo_id) WHERE a.ativo AND x.IND_OPER = '1'
                UNION ALL
                SELECT a.raiz, month(a.dt_ini), CAST(x.VL_OPER AS DOUBLE)
                FROM raw_contrib_f100 x JOIN arquivos a USING (arquivo_id)
                WHERE a.ativo AND x.IND_OPER IN ('1', '2')) GROUP BY ALL),
        i AS (
            SELECT raiz, mes, sum(vl_opr - coalesce(vl_ipi_c190, 0) - coalesce(vl_icms_st_c190, 0)) AS receita_c190_am
            FROM v_saidas_doc WHERE eh_receita GROUP BY ALL)
        SELECT coalesce(m.raiz, b.raiz) AS raiz, coalesce(m.mes, b.mes) AS mes,
               m.receita_bloco_m, b.receita_base,
               coalesce(m.receita_bloco_m, 0) - coalesce(b.receita_base, 0) AS diferenca,
               i.receita_c190_am,
               CASE WHEN coalesce(m.raiz, b.raiz) IN (SELECT raiz FROM v_estabelecimentos WHERE NOT no_amazonas)
                    THEN 'Empresa tem estabelecimento fora do AM' ELSE '' END AS observacao
        FROM m FULL OUTER JOIN b ON m.raiz = b.raiz AND m.mes = b.mes
        LEFT JOIN i ON i.raiz = coalesce(m.raiz, b.raiz) AND i.mes = coalesce(m.mes, b.mes)
        WHERE abs(coalesce(m.receita_bloco_m, 0) - coalesce(b.receita_base, 0))
              > greatest(?, ? * abs(coalesce(m.receita_bloco_m, 0)))
        ORDER BY 1, 2""", [_tol(), _pct()]).df()


def q11_codigos_nao_classificados(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""
        SELECT registro, codigo, any_value(descricao) AS descricao, count(*) AS ocorrencias,
               sum(valor) AS valor_total
        FROM v_ajustes_icms WHERE nao_classificado GROUP BY 1, 2 ORDER BY valor_total DESC""").df()


def q12_e116_x_e110(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Guia Pratico: soma do E116 = ICMS a recolher + debitos especiais do E110. Diferenca
    positiva indica obrigacao informada alem da apuracao (ex.: fundos pagos a parte)."""
    return con.execute("""
        WITH e AS (SELECT arquivo_id, sum(VL_OR) AS e116 FROM raw_icms_e116 GROUP BY 1)
        SELECT a.raiz, a.cnpj_estab, a.mes, a.arquivo_id,
               a.icms_recolher + coalesce(a.debitos_especiais, 0) AS recolher_e110,
               coalesce(e.e116, 0) AS soma_e116,
               coalesce(e.e116, 0) - a.icms_recolher - coalesce(a.debitos_especiais, 0) AS diferenca
        FROM v_apur_icms a LEFT JOIN e USING (arquivo_id)
        WHERE abs(coalesce(e.e116, 0) - a.icms_recolher - coalesce(a.debitos_especiais, 0)) > ?
        ORDER BY 1, 2, 3""", [_tol()]).df()


def q13_c180_x_c181_c185(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """EFD Contribuicoes consolidada: soma do C181 (PIS) e do C185 (COFINS) = C180."""
    return con.execute("""
        WITH p AS (SELECT arquivo_id, pai_linha, sum(VL_ITEM) AS v FROM raw_contrib_c181 GROUP BY 1, 2),
             c AS (SELECT arquivo_id, pai_linha, sum(VL_ITEM) AS v FROM raw_contrib_c185 GROUP BY 1, 2)
        SELECT a.raiz, h.cnpj_estab, month(a.dt_ini) AS mes, h.COD_ITEM AS cod_item, h.arquivo_id,
               h.linha_num, h.VL_TOT_ITEM AS total_c180, p.v AS soma_c181, c.v AS soma_c185
        FROM raw_contrib_c180 h JOIN arquivos a USING (arquivo_id)
        LEFT JOIN p ON p.arquivo_id = h.arquivo_id AND p.pai_linha = h.linha_num
        LEFT JOIN c ON c.arquivo_id = h.arquivo_id AND c.pai_linha = h.linha_num
        WHERE a.ativo AND (abs(h.VL_TOT_ITEM - coalesce(p.v, 0)) > ? OR abs(h.VL_TOT_ITEM - coalesce(c.v, 0)) > ?)
        ORDER BY 1, 2, 3""", [_tol(), _tol()]).df()


CHECAGENS = {
    "Q3": ("C170 × C100 (itens × documento, nas duas EFDs)", q3_c170_x_c100),
    "Q4": ("C190 × C100 (analítico × documento)", q4_c190_x_c100),
    "Q5": ("R1 – Documentos × E110 (ICMS)", q5_docs_x_e110),
    "Q6": ("R2 – Documentos × E520 (IPI)", q6_docs_x_e520),
    "Q7": ("R4 – Mesmo documento nas duas EFDs (chave da NF-e)", q7_icms_x_contrib),
    "Q8": ("R3 – Receitas da base × bloco M (M210/M610 + M400/M800)", q8_receita_contrib_x_icms),
    "Q11": ("Códigos de ajuste E111/E116 sem classificação", q11_codigos_nao_classificados),
    "Q12": ("E116 × E110 (obrigações × ICMS a recolher)", q12_e116_x_e110),
    "Q13": ("C180 × C181/C185 (Contribuições consolidada)", q13_c180_x_c181_c185),
    "Q14": ("C170 × C190 por documento e CFOP (EFD ICMS/IPI)", lambda con: _cz().c170_x_c190(con)),
    "Q15": ("CFOP e itens do mesmo documento nas duas EFDs", lambda con: _cz().divergencias_itens(con)),
    "Q16": ("Documento repetido na mesma EFD (outros períodos)", lambda con: _cz().repetidos(con)),
    "Q17": ("Cobertura: EFD ICMS/IPI × EFD Contribuições por estabelecimento e mês",
            lambda con: _cz().q17_cobertura(con)),
    "Q18": ("Fechamento: PIS/COFINS das entradas na EFD Contribuições × base (deve ser zero)",
            lambda con: _cz().fechamento_pis_cofins(con)),
    "Q19": ("Créditos somente na EFD Contribuições (sem correspondência no SPED Fiscal)",
            lambda con: _cz().creditos_so_na_efd(con)),
    "Q20": ("Insumo/revenda com crédito de ICMS/IPI sem crédito de PIS/COFINS, e o inverso",
            lambda con: _cz().credito_icms_x_pis(con)),
    "Q21": ("Mesmo item + CFOP com CST diferente entre estabelecimentos", lambda con: _cz().cst_divergente_filiais(con)),
}


def _cz():
    from . import cruzamentos
    return cruzamentos


def filtrar(df: pd.DataFrame, f: "Filtro | list[str] | None") -> pd.DataFrame:
    """Aplica o filtro global (empresas, estabelecimentos, periodo) quando as colunas existem."""
    if f is None or df.empty:
        return df
    if not isinstance(f, Filtro):
        f = Filtro(raizes=tuple(f))
    m = pd.Series(True, index=df.index)
    if f.raizes is not None and "raiz" in df.columns:
        m &= df["raiz"].isin(f.raizes)
    if f.estabs is not None and "cnpj_estab" in df.columns:
        m &= df["cnpj_estab"].isin(f.estabs) | df["cnpj_estab"].isna()
    if "mes" in df.columns:
        m &= df["mes"].between(f.mes_ini, f.mes_fim) | df["mes"].isna()
    return df[m]


# Agrupamento das checagens para a tela (do mais basico ao mais especifico)
GRUPOS = {
    "1. Arquivos e cobertura": ["Q17"],
    "2. Dentro de cada EFD": ["Q3", "Q4", "Q14", "Q13", "Q16", "Q11", "Q12"],
    "3. Documentos × apuração": ["Q5", "Q6", "Q8"],
    "4. EFD ICMS/IPI × EFD Contribuições": ["Q7", "Q15", "Q18", "Q19", "Q20", "Q21"],
}


def grupo_de(cod: str) -> str:
    return next((g for g, lst in GRUPOS.items() if cod in lst), "")
