"""Cruzamentos SPED Fiscal (EFD ICMS/IPI) × EFD Contribuicoes e cobertura das escrituracoes.

Mecanica do sped_analytics_app (branch claude/wonderful-rubin-5qi5sj): ver zfm/vinculo.py.
- Empresa = raiz do CNPJ; filial = CNPJ do 0000 (Fiscal) e do 0140/C010 (Contribuicoes).
- Fornecedor = CNPJ/CPF do 0150 de cada arquivo (COD_PART e codigo interno e nao e comparado).
- Documentos vinculados 1:1 (v_doc_par): pela chave (qualquer competencia) ou, sem chave num dos lados,
  filial + competencia + fornecedor + modelo + serie + numero.
- PIS/COFINS das entradas vem da EFD Contribuicoes por nivel (N1_ITEM, N1V_POSICAO_VALOR, N2_ITEM_CFOP,
  N3_CONSOLIDADO_C190, EC_EXCLUSIVO, EC_SEM_PAR) e o fechamento prova que nada some e nada duplica.
Auditorias (mesma lista do sped_analytics_app, app/database/audit.py), adaptadas a entradas e saidas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from . import params
from .vinculo import NIVEIS

CANCELADOS = "('02','03','04','05')"
NAS_DUAS = "Nas duas EFDs"
SO_FISCAL = "Só na EFD ICMS/IPI"
SO_FISCAL_ENTRADA = "Só na EFD ICMS/IPI (entrada sem crédito de PIS/COFINS?)"
SO_CONTRIB = "Só na EFD Contribuições"
SEM_CONTRIB = "Sem contrapartida: EFD Contribuições do mês não carregada"
SEM_FISCAL = "Sem contrapartida: EFD ICMS/IPI do estabelecimento/mês não carregada"
CONSOLIDADA = "Contribuições consolidada (C180/C190, sem documento)"
REPETIDO = "Repetido na mesma EFD (fora do vínculo)"
CST_CRED = "('50','51','52','53','54','55','56','60','61','62','63','64','65','66')"
TIPO_INSUMO_REVENDA = "('00','01','02','03','04','05','06','10')"


def _tol() -> float:
    return params.premissa_num("tolerancia_conciliacao", 1.0)


# ---------------------------------------------------------------------------
# Documentos das duas EFDs e situacao do vinculo
# ---------------------------------------------------------------------------
SQL_DOCS = f"""
WITH f AS (
    SELECT 'Fiscal' AS fonte, a.raiz, a.cnpj AS cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END AS sentido,
           d.COD_MOD AS cod_mod, d.SER AS ser, d.NUM_DOC AS num_doc, d.CHV_NFE AS chv_nfe, d.DT_DOC AS dt_doc,
           coalesce(nullif(p.cnpj_part, ''), nullif(p.cpf_part, ''), 'COD:' || d.COD_PART) AS participante,
           CAST(d.VL_DOC AS DOUBLE) AS vl_doc, CAST(d.VL_MERC AS DOUBLE) AS vl_merc, CAST(d.VL_PIS AS DOUBLE) AS vl_pis,
           CAST(d.VL_COFINS AS DOUBLE) AS vl_cofins, d.arquivo_id, d.linha_num
    FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN (SELECT DISTINCT ON (arquivo_id, cod_part) * FROM v_participantes) p
         ON p.arquivo_id = d.arquivo_id AND p.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANCELADOS}),
c AS (
    SELECT 'Contribuições', a.raiz, d.cnpj_estab, year(a.dt_ini), month(a.dt_ini),
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END,
           d.COD_MOD, d.SER, d.NUM_DOC, d.CHV_NFE, d.DT_DOC,
           coalesce(nullif(p.cnpj_part, ''), nullif(p.cpf_part, ''), 'COD:' || d.COD_PART),
           CAST(d.VL_DOC AS DOUBLE), CAST(d.VL_MERC AS DOUBLE), CAST(d.VL_PIS AS DOUBLE), CAST(d.VL_COFINS AS DOUBLE),
           d.arquivo_id, d.linha_num
    FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN (SELECT DISTINCT ON (arquivo_id, cnpj_estab, cod_part) * FROM v_participantes_contrib) p
         ON p.arquivo_id = d.arquivo_id AND p.cnpj_estab = d.cnpj_estab AND p.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANCELADOS}),
u AS (
    SELECT *, CASE WHEN regexp_full_match(upper(coalesce(chv_nfe, '')), '[0-9A-Z]{{44}}') THEN upper(chv_nfe)
                   ELSE 'K|' || coalesce(cod_mod, '') || '|' || ltrim(coalesce(ser, ''), '0') || '|'
                        || ltrim(coalesce(num_doc, ''), '0') || '|' || participante END AS chave
    FROM (SELECT * FROM f UNION ALL SELECT * FROM c)),
o AS (
    SELECT *, row_number() OVER (PARTITION BY fonte, cnpj_estab, sentido, chave
                                 ORDER BY ano, mes, arquivo_id, linha_num) AS ocorrencia,
              count(*) OVER (PARTITION BY fonte, cnpj_estab, sentido, chave) AS n_ocorrencias
    FROM u),
cobf AS (SELECT DISTINCT cnpj, year(dt_ini) AS ano, month(dt_ini) AS mes FROM arquivos
         WHERE ativo AND tipo = 'ICMS_IPI'),
cobc AS (SELECT DISTINCT raiz, year(dt_ini) AS ano, month(dt_ini) AS mes FROM arquivos
         WHERE ativo AND tipo = 'CONTRIB'),
cons AS (SELECT DISTINCT x.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes
         FROM raw_contrib_c010 x JOIN arquivos a USING (arquivo_id)
         WHERE a.ativo AND x.IND_ESCRI = '1'),
par AS (SELECT sf_arquivo_id AS arquivo_id, sf_linha AS linha_num, 'Fiscal' AS fonte, via FROM v_doc_par
        UNION ALL SELECT ec_arquivo_id, ec_linha, 'Contribuições', via FROM v_doc_par),
docs AS (
    SELECT o.*, pr.via,
           CASE WHEN pr.via IS NOT NULL THEN '{NAS_DUAS}'
                WHEN o.ocorrencia > 1 THEN '{REPETIDO}'
                WHEN o.fonte = 'Fiscal' AND cc.raiz IS NULL THEN '{SEM_CONTRIB}'
                WHEN o.fonte = 'Fiscal' AND co.cnpj_estab IS NOT NULL THEN '{CONSOLIDADA}'
                WHEN o.fonte = 'Fiscal' AND o.sentido = 'entrada' THEN '{SO_FISCAL_ENTRADA}'
                WHEN o.fonte = 'Fiscal' THEN '{SO_FISCAL}'
                WHEN cf.cnpj IS NULL THEN '{SEM_FISCAL}'
                ELSE '{SO_CONTRIB}' END AS situacao
    FROM o
    LEFT JOIN par pr ON pr.arquivo_id = o.arquivo_id AND pr.linha_num = o.linha_num AND pr.fonte = o.fonte
    LEFT JOIN cobc cc ON cc.raiz = o.raiz AND cc.ano = o.ano AND cc.mes = o.mes
    LEFT JOIN cobf cf ON cf.cnpj = o.cnpj_estab AND cf.ano = o.ano AND cf.mes = o.mes
    LEFT JOIN cons co ON co.cnpj_estab = o.cnpj_estab AND co.ano = o.ano AND co.mes = o.mes)
"""


def documentos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(SQL_DOCS + """
        SELECT fonte, situacao, via AS vinculo, sentido, raiz, cnpj_estab, ano, mes, cod_mod, ser, num_doc, chv_nfe,
               dt_doc, participante, vl_doc, vl_pis, vl_cofins, ocorrencia, n_ocorrencias, arquivo_id, linha_num
        FROM docs""").df()


def resumo_pareamento(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Documentos por fonte, sentido e situacao do vinculo (quantidade e valor)."""
    return con.execute(SQL_DOCS + """
        SELECT raiz, fonte, sentido, situacao, coalesce(via, '') AS vinculo, count(*) AS documentos, sum(vl_doc) AS valor
        FROM docs GROUP BY ALL ORDER BY raiz, fonte, sentido, situacao""").df()


def pareamento_divergencias(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """R4: documento so numa EFD (com as duas carregadas) ou vinculado com valor do documento/mercadoria,
    data, fornecedor ou (nas saidas) PIS/COFINS diferentes."""
    tol = _tol()
    so_um = con.execute(SQL_DOCS + f"""
        SELECT raiz, cnpj_estab, mes, sentido, fonte, situacao AS problema, num_doc, chv_nfe, participante,
               vl_doc AS valor_fiscal, NULL::DOUBLE AS valor_contrib, arquivo_id, linha_num
        FROM docs WHERE situacao IN ('{SO_FISCAL}', '{SO_CONTRIB}')""").df()
    dif = con.execute(SQL_DOCS + f"""
        , df AS (SELECT * FROM docs WHERE fonte = 'Fiscal'), dc AS (SELECT * FROM docs WHERE fonte = 'Contribuições')
        SELECT f.raiz, f.cnpj_estab, f.mes, f.sentido, 'Vínculo por ' || lower(m.via) AS fonte,
               'Diferente nas duas EFDs: ' || concat_ws(', ',
                   CASE WHEN abs(coalesce(f.vl_doc, 0) - coalesce(c.vl_doc, 0)) > {tol} THEN 'valor do documento' END,
                   CASE WHEN abs(coalesce(f.vl_merc, 0) - coalesce(c.vl_merc, 0)) > {tol} THEN 'valor da mercadoria' END,
                   CASE WHEN f.dt_doc IS DISTINCT FROM c.dt_doc THEN 'data' END,
                   CASE WHEN f.participante <> c.participante AND f.participante NOT LIKE 'COD:%'
                             AND c.participante NOT LIKE 'COD:%' THEN 'fornecedor/cliente (CNPJ)' END,
                   CASE WHEN f.sentido = 'saida' AND (abs(coalesce(f.vl_pis, 0) - coalesce(c.vl_pis, 0)) > {tol}
                             OR abs(coalesce(f.vl_cofins, 0) - coalesce(c.vl_cofins, 0)) > {tol})
                        THEN 'PIS/COFINS' END) AS problema,
               f.num_doc, f.chv_nfe, f.participante, f.vl_doc, c.vl_doc, f.arquivo_id, f.linha_num
        FROM v_doc_par m
        JOIN df f ON f.arquivo_id = m.sf_arquivo_id AND f.linha_num = m.sf_linha
        JOIN dc c ON c.arquivo_id = m.ec_arquivo_id AND c.linha_num = m.ec_linha
        WHERE abs(coalesce(f.vl_doc, 0) - coalesce(c.vl_doc, 0)) > {tol}
           OR abs(coalesce(f.vl_merc, 0) - coalesce(c.vl_merc, 0)) > {tol}
           OR f.dt_doc IS DISTINCT FROM c.dt_doc
           OR (f.participante <> c.participante AND f.participante NOT LIKE 'COD:%' AND c.participante NOT LIKE 'COD:%')
           OR (f.sentido = 'saida' AND (abs(coalesce(f.vl_pis, 0) - coalesce(c.vl_pis, 0)) > {tol}
               OR abs(coalesce(f.vl_cofins, 0) - coalesce(c.vl_cofins, 0)) > {tol}))""").df()
    dif.columns = so_um.columns
    return pd.concat([so_um, dif], ignore_index=True)


def divergencias_itens(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Documentos vinculados: (a) itens na mesma posicao (NUM_ITEM) com codigo, CFOP ou valor diferente
    (C170 Fiscal × C170 Contribuicoes); (b) CFOP so de um lado (C190 da Fiscal × C170 da Contribuicoes) —
    o CFOP liga o produto (Contribuicoes) ao destino (Fiscal)."""
    tol = _tol()
    return con.execute(f"""
        WITH m AS (SELECT p.*, d.raiz, d.cnpj_estab, d.mes, d.sentido, d.num_doc, d.chv_nfe
                   FROM v_doc_par p JOIN v_docs d ON d.arquivo_id = p.sf_arquivo_id AND d.doc_linha = p.sf_linha),
        fi AS (SELECT m.sf_arquivo_id, m.sf_linha, i.NUM_ITEM AS num_item, any_value(i.CFOP) AS cfop,
                      any_value(i.COD_ITEM) AS cod_item, any_value(CAST(i.VL_ITEM AS DOUBLE)) AS vl_item
               FROM m JOIN raw_icms_c170 i ON i.arquivo_id = m.sf_arquivo_id AND i.pai_linha = m.sf_linha
               GROUP BY ALL HAVING count(*) = 1),
        ci AS (SELECT m.sf_arquivo_id, m.sf_linha, i.NUM_ITEM AS num_item, any_value(i.CFOP) AS cfop,
                      any_value(i.COD_ITEM) AS cod_item, any_value(CAST(i.VL_ITEM AS DOUBLE)) AS vl_item
               FROM m JOIN raw_contrib_c170 i ON i.arquivo_id = m.ec_arquivo_id AND i.pai_linha = m.ec_linha
               GROUP BY ALL HAVING count(*) = 1),
        it AS (SELECT fi.sf_arquivo_id, fi.sf_linha, fi.cfop, fi.vl_item AS valor_fiscal, ci.vl_item AS valor_contrib,
                      'Item ' || fi.num_item || ' na mesma posição com ' || concat_ws(', ',
                          CASE WHEN fi.cod_item <> ci.cod_item THEN 'código ' || fi.cod_item || ' × ' || ci.cod_item END,
                          CASE WHEN coalesce(fi.cfop, '') <> coalesce(ci.cfop, '') THEN 'CFOP ' || fi.cfop || ' × ' || ci.cfop END,
                          CASE WHEN abs(fi.vl_item - ci.vl_item) > {tol} THEN 'valor diferente' END) AS problema
               FROM fi JOIN ci USING (sf_arquivo_id, sf_linha, num_item)
               WHERE fi.cod_item <> ci.cod_item OR coalesce(fi.cfop, '') <> coalesce(ci.cfop, '')
                  OR abs(fi.vl_item - ci.vl_item) > {tol}),
        fc AS (SELECT m.sf_arquivo_id, m.sf_linha, c.CFOP AS cfop, sum(CAST(c.VL_OPR AS DOUBLE)) AS v
               FROM m JOIN raw_icms_c190 c ON c.arquivo_id = m.sf_arquivo_id AND c.pai_linha = m.sf_linha GROUP BY ALL),
        cc AS (SELECT m.sf_arquivo_id, m.sf_linha, i.CFOP AS cfop, sum(CAST(i.VL_ITEM - coalesce(i.VL_DESC, 0) AS DOUBLE)) AS v
               FROM m JOIN raw_contrib_c170 i ON i.arquivo_id = m.ec_arquivo_id AND i.pai_linha = m.ec_linha GROUP BY ALL),
        cf AS (SELECT coalesce(a.sf_arquivo_id, b.sf_arquivo_id) AS sf_arquivo_id, coalesce(a.sf_linha, b.sf_linha) AS sf_linha,
                      coalesce(a.cfop, b.cfop) AS cfop, a.v AS valor_fiscal, b.v AS valor_contrib,
                      CASE WHEN b.cfop IS NULL THEN 'CFOP só na EFD ICMS/IPI (C190)'
                           ELSE 'CFOP só na EFD Contribuições (C170)' END AS problema
               FROM fc a FULL JOIN cc b ON a.sf_arquivo_id = b.sf_arquivo_id AND a.sf_linha = b.sf_linha AND a.cfop = b.cfop
               WHERE (a.cfop IS NULL OR b.cfop IS NULL)),
        cf_ok AS (SELECT * FROM cf WHERE (sf_arquivo_id, sf_linha) IN (SELECT sf_arquivo_id, sf_linha FROM cc)
                                    AND (sf_arquivo_id, sf_linha) IN (SELECT sf_arquivo_id, sf_linha FROM fc)),
        x AS (SELECT * FROM it UNION ALL BY NAME SELECT * FROM cf_ok)
        SELECT m.raiz, m.cnpj_estab, m.mes, m.sentido, x.problema, x.cfop, m.num_doc, m.chv_nfe,
               x.valor_fiscal, x.valor_contrib, m.sf_arquivo_id AS arquivo_id, m.sf_linha AS linha_num
        FROM x JOIN m USING (sf_arquivo_id, sf_linha) ORDER BY 1, 2, 3""").df()


def repetidos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Mesmo documento escriturado mais de uma vez na mesma EFD (ex.: em dois periodos)."""
    return con.execute(SQL_DOCS + """
        SELECT raiz, cnpj_estab, mes, sentido, fonte, num_doc, chv_nfe, participante, vl_doc, ocorrencia,
               n_ocorrencias, CASE WHEN ocorrencia = 1 THEN 'Primeira ocorrência' ELSE 'Repetição' END AS situacao,
               arquivo_id, linha_num
        FROM docs WHERE n_ocorrencias > 1 ORDER BY raiz, cnpj_estab, chave, ocorrencia""").df()


def c170_x_c190(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """EFD ICMS/IPI: itens C170 × analitico C190 por documento + CST + CFOP + aliquota (item sem C190
    correspondente, ou BC/ICMS/IPI diferentes)."""
    tol = _tol()
    return con.execute(f"""
        WITH i AS (SELECT arquivo_id, pai_linha, coalesce(CST_ICMS, '') AS cst, coalesce(CFOP, '') AS cfop,
                          round(coalesce(ALIQ_ICMS, 0), 2) AS aliq, sum(coalesce(VL_BC_ICMS, 0)) AS bc,
                          sum(coalesce(VL_ICMS, 0)) AS icms, sum(coalesce(VL_IPI, 0)) AS ipi
                   FROM raw_icms_c170 GROUP BY ALL),
             a AS (SELECT arquivo_id, pai_linha, coalesce(CST_ICMS, '') AS cst, coalesce(CFOP, '') AS cfop,
                          round(coalesce(ALIQ_ICMS, 0), 2) AS aliq, sum(coalesce(VL_BC_ICMS, 0)) AS bc,
                          sum(coalesce(VL_ICMS, 0)) AS icms, sum(coalesce(VL_IPI, 0)) AS ipi
                   FROM raw_icms_c190
                   WHERE (arquivo_id, pai_linha) IN (SELECT DISTINCT arquivo_id, pai_linha FROM raw_icms_c170)
                   GROUP BY ALL),
             c AS (SELECT coalesce(i.arquivo_id, a.arquivo_id) AS arquivo_id,
                          coalesce(i.pai_linha, a.pai_linha) AS doc_linha, coalesce(i.cst, a.cst) AS cst_icms,
                          coalesce(i.cfop, a.cfop) AS cfop, coalesce(i.aliq, a.aliq) AS aliq_icms,
                          CASE WHEN a.cfop IS NULL THEN 'Item C170 sem C190 correspondente (CST/CFOP/alíquota)'
                               WHEN i.cfop IS NULL THEN 'C190 sem item C170 correspondente'
                               ELSE 'Valores do C170 diferentes do C190' END AS problema,
                          coalesce(i.bc, 0) AS bc_icms_c170, coalesce(a.bc, 0) AS bc_icms_c190,
                          coalesce(i.icms, 0) AS icms_c170, coalesce(a.icms, 0) AS icms_c190,
                          coalesce(i.ipi, 0) AS ipi_c170, coalesce(a.ipi, 0) AS ipi_c190
                   FROM i FULL JOIN a ON i.arquivo_id = a.arquivo_id AND i.pai_linha = a.pai_linha AND i.cst = a.cst
                        AND i.cfop = a.cfop AND i.aliq = a.aliq)
        SELECT d.raiz, d.cnpj_estab, d.mes, d.sentido, d.num_doc, d.chv_nfe, c.problema, c.cst_icms, c.cfop, c.aliq_icms,
               c.bc_icms_c170, c.bc_icms_c190, c.icms_c170, c.icms_c190, c.ipi_c170, c.ipi_c190,
               c.arquivo_id, c.doc_linha
        FROM c JOIN v_docs d ON d.arquivo_id = c.arquivo_id AND d.doc_linha = c.doc_linha
        WHERE NOT d.cancelado AND (c.problema <> 'Valores do C170 diferentes do C190'
              OR abs(c.bc_icms_c170 - c.bc_icms_c190) > {tol} OR abs(c.icms_c170 - c.icms_c190) > {tol}
              OR abs(c.ipi_c170 - c.ipi_c190) > {tol})
        ORDER BY 1, 2, 3""").df()


# ---------------------------------------------------------------------------
# Fechamento e auditorias do cruzamento de PIS/COFINS (entradas)
# ---------------------------------------------------------------------------
def fechamento_pis_cofins(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """PIS/COFINS das entradas na EFD Contribuicoes (C170 de entrada, C191/C195, A170, F100) × o que entrou
    na base de operacoes, por estabelecimento do AM e mes. Deve ser sempre zero (nada some, nada duplica)."""
    tol = 0.01
    return con.execute(f"""
        WITH am AS (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas),
        bruto AS (
            SELECT d.cnpj_estab, a.raiz, month(a.dt_ini) AS mes, sum(i.VL_PIS) AS pis, sum(i.VL_COFINS) AS cofins
            FROM raw_contrib_c170 i JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
            JOIN arquivos a ON a.arquivo_id = i.arquivo_id
            WHERE a.ativo AND d.IND_OPER = '0' AND coalesce(d.COD_SIT, '00') NOT IN {CANCELADOS} GROUP BY ALL
            UNION ALL
            SELECT h.cnpj_estab, a.raiz, month(a.dt_ini), sum(x.VL_PIS), 0 FROM raw_contrib_c191 x
            JOIN raw_contrib_c190 h ON h.arquivo_id = x.arquivo_id AND h.linha_num = x.pai_linha
            JOIN arquivos a ON a.arquivo_id = x.arquivo_id WHERE a.ativo GROUP BY ALL
            UNION ALL
            SELECT h.cnpj_estab, a.raiz, month(a.dt_ini), 0, sum(x.VL_COFINS) FROM raw_contrib_c195 x
            JOIN raw_contrib_c190 h ON h.arquivo_id = x.arquivo_id AND h.linha_num = x.pai_linha
            JOIN arquivos a ON a.arquivo_id = x.arquivo_id WHERE a.ativo GROUP BY ALL
            UNION ALL
            SELECT cnpj_estab, raiz, mes, sum(vl_pis), sum(vl_cofins) FROM v_entradas_servicos GROUP BY ALL),
        e AS (SELECT cnpj_estab, raiz, mes, CAST(sum(pis) AS DOUBLE) AS pis, CAST(sum(cofins) AS DOUBLE) AS cofins
              FROM bruto WHERE cnpj_estab IN (SELECT cnpj FROM am) GROUP BY ALL),
        b AS (SELECT cnpj_estab, raiz, mes, sum(coalesce(vl_pis, 0)) AS pis, sum(coalesce(vl_cofins, 0)) AS cofins
              FROM (SELECT cnpj_estab, raiz, mes, vl_pis, vl_cofins FROM v_entradas_item
                    UNION ALL SELECT cnpj_estab, raiz, mes, vl_pis, vl_cofins FROM v_entradas_servicos
                    WHERE cnpj_estab IN (SELECT cnpj FROM am)) GROUP BY ALL)
        SELECT coalesce(e.raiz, b.raiz) AS raiz, coalesce(e.cnpj_estab, b.cnpj_estab) AS cnpj_estab,
               coalesce(e.mes, b.mes) AS mes, coalesce(e.pis, 0) AS pis_efd, coalesce(b.pis, 0) AS pis_base,
               coalesce(e.pis, 0) - coalesce(b.pis, 0) AS dif_pis, coalesce(e.cofins, 0) AS cofins_efd,
               coalesce(b.cofins, 0) AS cofins_base, coalesce(e.cofins, 0) - coalesce(b.cofins, 0) AS dif_cofins
        FROM e FULL JOIN b ON b.cnpj_estab = e.cnpj_estab AND b.mes = e.mes
        WHERE abs(coalesce(e.pis, 0) - coalesce(b.pis, 0)) > {tol} OR abs(coalesce(e.cofins, 0) - coalesce(b.cofins, 0)) > {tol}
        ORDER BY 1, 2, 3""").df()


def creditos_so_na_efd(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Creditos da EFD Contribuicoes sem correspondencia no SPED Fiscal (linhas EC_SEM_PAR)."""
    return con.execute("""
        SELECT raiz, cnpj_estab, mes, reg_origem, chv_nfe, cnpj_part, cod_item, cfop, cst_pis, vl_pis, cst_cofins,
               vl_cofins, arquivo_id, linha_num
        FROM v_entradas_item WHERE nivel_cruzamento = 'EC_SEM_PAR'
        ORDER BY coalesce(vl_pis, 0) + coalesce(vl_cofins, 0) DESC""").df()


def credito_icms_x_pis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Insumo/revenda (TIPO_ITEM do 0200) com credito de ICMS/IPI e sem credito de PIS/COFINS, e o inverso.
    Entradas com CST de PIS 70 a 75 (sem direito a credito: suspensao, aliquota zero, isencao) nao sao
    apontadas, porque e a situacao normal das compras com beneficio da ZFM."""
    return con.execute(f"""
        WITH t AS (SELECT DISTINCT ON (arquivo_id, COD_ITEM) arquivo_id, COD_ITEM AS cod_item, TIPO_ITEM AS tipo_item
                   FROM raw_icms_0200 ORDER BY arquivo_id, COD_ITEM),
        e AS (SELECT e.*, t.tipo_item,
                     (coalesce(e.vl_icms, 0) > 0 OR (coalesce(e.cst_ipi, '') IN ('00', '49', '50') AND coalesce(e.vl_ipi, 0) > 0))
                         AS cred_icms,
                     (coalesce(e.cst_pis, '') IN {CST_CRED} AND coalesce(e.vl_pis, 0) + coalesce(e.vl_cofins, 0) > 0) AS cred_pis
              FROM v_entradas_item e LEFT JOIN t ON t.arquivo_id = e.arquivo_id AND t.cod_item = e.cod_item
              WHERE e.reg_origem = 'C170' AND e.devolucao_de NOT IN ('venda_producao', 'venda_revenda'))
        SELECT raiz, cnpj_estab, mes,
               CASE WHEN cred_icms THEN 'Crédito de ICMS/IPI sem crédito de PIS/COFINS'
                    ELSE 'Crédito de PIS/COFINS sem crédito de ICMS/IPI' END AS problema,
               chv_nfe, cnpj_part, cod_item, tipo_item, cfop, cst_icms, cst_ipi, cst_pis, nivel_cruzamento, valor,
               vl_icms, vl_ipi, vl_pis, vl_cofins, arquivo_id, linha_num
        FROM e WHERE tipo_item IN {TIPO_INSUMO_REVENDA} AND cred_icms <> cred_pis
          -- CST 70 a 75 (aquisicao sem credito: suspensao, aliquota zero, isencao...) e o esperado na ZFM
          AND NOT (cred_icms AND coalesce(cst_pis, '') BETWEEN '70' AND '75')
        ORDER BY valor DESC""").df()


def cst_divergente_filiais(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Mesmo item + CFOP com CST diferente entre estabelecimentos da mesma empresa (entradas)."""
    return con.execute("""
        WITH b AS (SELECT raiz, cod_item, cfop, cnpj_estab,
                          string_agg(DISTINCT coalesce(cst_icms, '-'), '/' ORDER BY coalesce(cst_icms, '-')) AS cst_icms,
                          string_agg(DISTINCT coalesce(cst_pis, '-'), '/' ORDER BY coalesce(cst_pis, '-')) AS cst_pis,
                          string_agg(DISTINCT coalesce(cst_cofins, '-'), '/' ORDER BY coalesce(cst_cofins, '-')) AS cst_cofins,
                          sum(valor) AS valor, min(mes) AS mes
                   FROM v_entradas_item WHERE reg_origem = 'C170' AND cod_item IS NOT NULL GROUP BY ALL),
        d AS (SELECT raiz, cod_item, cfop FROM b GROUP BY ALL
              HAVING count(DISTINCT cnpj_estab) > 1
                 AND (count(DISTINCT cst_icms) > 1 OR count(DISTINCT cst_pis) > 1 OR count(DISTINCT cst_cofins) > 1))
        SELECT b.* FROM b JOIN d USING (raiz, cod_item, cfop) ORDER BY b.raiz, b.cod_item, b.cfop, b.cnpj_estab""").df()


def diagnostico_niveis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Informativo: distribuicao das linhas de entrada e do PIS/COFINS por nivel de cruzamento."""
    d = con.execute("""
        SELECT raiz, cnpj_estab, mes, nivel_cruzamento, count(*) AS linhas, sum(valor) AS valor,
               sum(coalesce(vl_pis, 0)) AS pis, sum(coalesce(vl_cofins, 0)) AS cofins
        FROM v_entradas_item GROUP BY ALL ORDER BY raiz, cnpj_estab, mes, linhas DESC""").df()
    if not d.empty:
        d.insert(4, "descricao", d["nivel_cruzamento"].map(NIVEIS).fillna(""))
        tot = d.groupby(["cnpj_estab", "mes"])["linhas"].transform("sum")
        d["pct_linhas"] = 100 * d["linhas"] / tot
    return d


# ---------------------------------------------------------------------------
# Cobertura: EFD ICMS/IPI de cada estabelecimento × EFD Contribuicoes da empresa, mes a mes
# ---------------------------------------------------------------------------
@dataclass
class Escrituracao:
    tipo: str                     # ICMS_IPI | CONTRIB
    cnpj: str
    ano: int
    mes: int
    uf: str = ""
    nome: str = ""
    origem: str = "banco"         # banco | pasta
    arquivo: str = ""
    estabs: list[tuple[str, str, str, str]] = field(default_factory=list)  # Contrib 0140: cnpj, uf, ie, nome

    @property
    def raiz(self) -> str:
        return self.cnpj[:8]


def _contribuinte_icms(ie: str | None) -> bool:
    return bool(ie and ie.strip() and not ie.strip().upper().startswith("ISENT"))


def escrituracoes_do_banco(con: duckdb.DuckDBPyConnection) -> list[Escrituracao]:
    arq = con.execute("""SELECT arquivo_id, tipo, cnpj, year(dt_ini), month(dt_ini), uf, nome, nome_arquivo
                         FROM arquivos WHERE ativo""").fetchall()
    est: dict[int, list] = {}
    for aid, cnpj, uf, ie, nome in con.execute(
            """SELECT e.arquivo_id, e.CNPJ, e.UF, e.IE, e.NOME FROM raw_contrib_0140 e
               JOIN arquivos a USING (arquivo_id) WHERE a.ativo""").fetchall():
        est.setdefault(aid, []).append((cnpj or "", uf or "", ie or "", nome or ""))
    return [Escrituracao(t, c, int(an), int(m), u or "", n or "", "banco", na, est.get(aid, []))
            for aid, t, c, an, m, u, n, na in arq]


def identificar_rapido(caminho: Path) -> Escrituracao:
    """Le so o registro 0000 (e, na EFD Contribuicoes, os 0140 do bloco 0) para saber tipo,
    estabelecimento/empresa e periodo, sem importar o arquivo."""
    from .parsers.base import detectar_encoding, identificar, ler_primeira_linha, separar_campos
    enc = detectar_encoding(caminho)
    ide = identificar(ler_primeira_linha(caminho, enc))
    e = Escrituracao(ide.tipo, ide.cnpj, ide.dt_ini.year, ide.dt_ini.month, ide.uf or "", ide.nome or "",
                     "pasta", caminho.name)
    if ide.tipo == "CONTRIB":
        with open(caminho, encoding=enc, errors="replace") as fh:
            for i, linha in enumerate(fh):
                if linha.startswith("|0140|"):
                    c = separar_campos(linha) or []
                    c += [""] * 9
                    e.estabs.append((c[3], c[4], c[5], c[2]))   # CNPJ, UF, IE, NOME
                elif linha.startswith("|0990|") or (i > 50 and linha[:2] in ("|A", "|C", "|D", "|F", "|M", "|1")):
                    break
    return e


def cobertura(escrituracoes: list[Escrituracao], so_amazonas: bool = True) -> pd.DataFrame:
    """Uma linha por empresa × estabelecimento × mes: tem EFD ICMS/IPI? tem EFD Contribuicoes?

    Estabelecimentos considerados: os que tem EFD ICMS/IPI e os do 0140 da EFD Contribuicoes com
    inscricao estadual (contribuintes do ICMS). so_amazonas=True limita ao AM (perimetro da analise).
    Meses considerados: do primeiro ao ultimo mes com qualquer escrituracao da empresa."""
    if not escrituracoes:
        return pd.DataFrame(columns=["raiz", "empresa", "cnpj_estab", "uf", "ano", "mes", "icms_ipi",
                                     "contribuicoes", "no_0140", "situacao", "o_que_fazer"])
    fis = {(e.cnpj, e.ano, e.mes): e for e in escrituracoes if e.tipo == "ICMS_IPI"}
    con_ = {(e.raiz, e.ano, e.mes): e for e in escrituracoes if e.tipo == "CONTRIB"}
    nomes: dict[str, str] = {}
    estab_uf: dict[str, str] = {}
    estabs_raiz: dict[str, set] = {}
    no_0140: set = set()
    meses_raiz: dict[str, set] = {}
    for e in escrituracoes:
        meses_raiz.setdefault(e.raiz, set()).add((e.ano, e.mes))
        if e.tipo == "CONTRIB":
            nomes.setdefault(e.raiz, e.nome)
            for cnpj, uf, ie, _ in e.estabs:
                no_0140.add((cnpj, e.ano, e.mes))
                if cnpj and _contribuinte_icms(ie):
                    estab_uf.setdefault(cnpj, uf)
                    estabs_raiz.setdefault(e.raiz, set()).add(cnpj)
        else:
            nomes.setdefault(e.raiz, e.nome)
            estab_uf[e.cnpj] = e.uf
            estabs_raiz.setdefault(e.raiz, set()).add(e.cnpj)
    linhas = []
    for raiz, meses in meses_raiz.items():
        a0, a1 = min(meses), max(meses)
        todos = [(a, m) for a in range(a0[0], a1[0] + 1) for m in range(1, 13) if a0 <= (a, m) <= a1]
        ests = estabs_raiz.get(raiz) or {raiz}
        for cnpj in sorted(ests):
            uf = estab_uf.get(cnpj, "")
            if so_amazonas and uf and uf != "AM":
                continue
            for a, m in todos:
                ti = (cnpj, a, m) in fis
                tc = (raiz, a, m) in con_
                n0140 = (cnpj, a, m) in no_0140
                if ti and tc:
                    sit, faz = "OK", ""
                elif tc:
                    sit = "Falta EFD ICMS/IPI"
                    faz = ("Importar a EFD ICMS/IPI do estabelecimento" if n0140 else
                           "Importar a EFD ICMS/IPI (estabelecimento não está no 0140 deste mês: conferir)")
                elif ti:
                    sit, faz = "Falta EFD Contribuições", "Importar a EFD Contribuições da empresa (matriz)"
                else:
                    sit, faz = "Faltam as duas", "Importar as duas EFDs do mês"
                if ti and tc and not n0140 and con_[(raiz, a, m)].estabs:
                    sit, faz = "OK (estabelecimento fora do 0140)", "Conferir o 0140 da EFD Contribuições"
                linhas.append({"raiz": raiz, "empresa": nomes.get(raiz, ""), "cnpj_estab": cnpj, "uf": uf,
                               "ano": a, "mes": m, "icms_ipi": ti, "contribuicoes": tc, "no_0140": n0140,
                               "situacao": sit, "o_que_fazer": faz})
    return pd.DataFrame(linhas)


def cobertura_banco(con: duckdb.DuckDBPyConnection, so_amazonas: bool = True) -> pd.DataFrame:
    return cobertura(escrituracoes_do_banco(con), so_amazonas)


def faltas(cob: pd.DataFrame) -> pd.DataFrame:
    return cob[~cob["situacao"].str.startswith("OK")] if not cob.empty else cob


def q17_cobertura(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Conciliacao: escrituracoes faltando (estabelecimentos do AM)."""
    f = faltas(cobertura_banco(con))
    return f.rename(columns={"cnpj_estab": "cnpj_estab"}) if not f.empty else f
