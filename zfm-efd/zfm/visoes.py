"""Visoes normalizadas (SPEC 5.2). Criadas como VIEW sobre as tabelas brutas.

So entram arquivos ativos (retificadora prevalece). Os parametros (param_*)
sao lidos das tabelas sincronizadas por zfm.params.sincronizar().

Escrituracao da EFD Contribuicoes:
- detalhada: C100/C170 (destinatario exato pelo COD_PART);
- consolidada: C180 + C181 (PIS) + C185 (COFINS), sem destinatario: o destino
  e rateado pela proporcao do C190 + 0150 da EFD ICMS/IPI do mesmo
  estabelecimento, mes e CFOP (premissa rateio_produto_uf).
"""
from __future__ import annotations

import duckdb

from . import params, vinculo
from .empresas import SQL_ESTABELECIMENTOS

UFS = {
    "11": ("RO", "Norte"), "12": ("AC", "Norte"), "13": ("AM", "Norte"), "14": ("RR", "Norte"),
    "15": ("PA", "Norte"), "16": ("AP", "Norte"), "17": ("TO", "Norte"),
    "21": ("MA", "Nordeste"), "22": ("PI", "Nordeste"), "23": ("CE", "Nordeste"),
    "24": ("RN", "Nordeste"), "25": ("PB", "Nordeste"), "26": ("PE", "Nordeste"),
    "27": ("AL", "Nordeste"), "28": ("SE", "Nordeste"), "29": ("BA", "Nordeste"),
    "31": ("MG", "Sudeste"), "32": ("ES", "Sudeste"), "33": ("RJ", "Sudeste"),
    "35": ("SP", "Sudeste"), "41": ("PR", "Sul"), "42": ("SC", "Sul"), "43": ("RS", "Sul"),
    "50": ("MS", "Centro-Oeste"), "51": ("MT", "Centro-Oeste"), "52": ("GO", "Centro-Oeste"),
    "53": ("DF", "Centro-Oeste"),
}
SUL_SUDESTE_EXCETO_ES = ("MG", "RJ", "SP", "PR", "SC", "RS")

_COD_SIT_CANCELADO = "('02','03','04','05')"


def _sql_participantes(tabela: str, chave_estab: str) -> str:
    return f"""
    SELECT p.arquivo_id, {chave_estab} AS cnpj_estab, a.raiz, p.COD_PART AS cod_part,
           p.NOME AS nome_part, p.CNPJ AS cnpj_part, p.CPF AS cpf_part, p.COD_MUN AS cod_mun,
           p.SUFRAMA AS suframa,
           (coalesce(nullif(p.COD_PAIS, ''), '1058') NOT IN ('1058', '01058')) AS exterior,
           CASE WHEN coalesce(nullif(p.COD_PAIS, ''), '1058') NOT IN ('1058', '01058') THEN 'EX'
                ELSE u.uf END AS uf,
           CASE WHEN coalesce(nullif(p.COD_PAIS, ''), '1058') NOT IN ('1058', '01058')
                THEN 'Exterior' ELSE u.regiao END AS regiao,
           (u.uf = 'AM' AND p.COD_MUN IN (SELECT cod_ibge FROM param_municipios_zfm)) AS municipio_zfm,
           (u.uf = 'AM' AND p.COD_MUN IN (SELECT cod_ibge FROM param_municipios_zfm)
            AND nullif(p.CNPJ, '') IS NOT NULL
            AND (nullif(p.SUFRAMA, '') IS NOT NULL
                 OR coalesce((SELECT lower(valor) FROM param_premissas WHERE chave = 'zfm_exige_suframa'),
                             'sim') IN ('nao', 'não'))) AS eh_zfm,
           (nullif(p.CNPJ, '') IS NOT NULL AND (substr(p.CNPJ, 1, 8) IN (SELECT raiz_cnpj FROM param_empresas)
             OR substr(p.CNPJ, 1, 8) IN (SELECT raiz FROM arquivos))) AS eh_grupo,
           (nullif(p.CNPJ, '') IS NOT NULL AND nullif(p.IE, '') IS NOT NULL
            AND upper(p.IE) NOT LIKE 'ISENT%') AS contribuinte,
           coalesce(nullif(pz.tipo, ''),
                    CASE WHEN u.uf = 'AM' AND p.COD_MUN IN (SELECT cod_ibge FROM param_municipios_zfm)
                              AND nullif(p.CNPJ, '') IS NOT NULL AND nullif(p.SUFRAMA, '') IS NOT NULL
                         THEN 'habilitado' ELSE 'nao_habilitado' END) AS tipo_zfm,
           coalesce(nullif(pz.regime, ''), 'regular') AS regime_part
    FROM {tabela} p JOIN arquivos a USING (arquivo_id)
    LEFT JOIN ref_uf u ON u.cod = substr(p.COD_MUN, 1, 2)
    LEFT JOIN param_empresas_zfm pz ON pz.cnpj = p.CNPJ
    WHERE a.ativo
    """


VIEWS: list[tuple[str, str]] = [
    ("v_estabelecimentos", SQL_ESTABELECIMENTOS),
    ("v_participantes", _sql_participantes("raw_icms_0150", "a.cnpj")),
    ("v_participantes_contrib", _sql_participantes("raw_contrib_0150", "p.cnpj_estab")),
    ("v_docs", f"""
    SELECT d.arquivo_id, d.linha_num AS doc_linha, a.cnpj AS cnpj_estab, a.raiz, a.uf AS uf_estab,
           year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END AS sentido,
           CASE d.IND_EMIT WHEN '0' THEN 'propria' ELSE 'terceiros' END AS emissao,
           d.COD_SIT AS cod_sit, coalesce(d.COD_SIT, '00') IN {_COD_SIT_CANCELADO} AS cancelado,
           d.COD_PART AS cod_part, d.NUM_DOC AS num_doc, d.CHV_NFE AS chv_nfe, d.DT_DOC AS dt_doc,
           d.VL_DOC AS vl_doc, d.VL_MERC AS vl_merc, d.VL_DESC AS vl_desc, d.VL_BC_ICMS AS vl_bc_icms,
           d.VL_ICMS AS vl_icms, d.VL_IPI AS vl_ipi, d.VL_PIS AS vl_pis, d.VL_COFINS AS vl_cofins,
           p.nome_part, p.cnpj_part, p.uf, p.regiao, coalesce(p.exterior, FALSE) AS exterior,
           coalesce(p.eh_zfm, FALSE) AS eh_zfm, coalesce(p.municipio_zfm, FALSE) AS municipio_zfm,
           coalesce(p.eh_grupo, FALSE) AS eh_grupo, coalesce(p.contribuinte, FALSE) AS contribuinte,
           coalesce(p.tipo_zfm, 'nao_habilitado') AS tipo_zfm, coalesce(p.regime_part, 'regular') AS regime_part
    FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN v_participantes p ON p.arquivo_id = d.arquivo_id AND p.cod_part = d.COD_PART
    WHERE a.ativo
    """),
    ("v_saidas_doc", """
    SELECT v.*, c.linha_num, c.CFOP AS cfop, c.CST_ICMS AS cst_icms, c.ALIQ_ICMS AS aliq_icms,
           c.VL_OPR AS vl_opr, c.VL_BC_ICMS AS vl_bc_icms_c190, c.VL_ICMS AS vl_icms_c190,
           c.VL_IPI AS vl_ipi_c190, c.VL_ICMS_ST AS vl_icms_st_c190,
           coalesce(pc.categoria, 'outros') AS categoria_cfop, pc.devolucao_de,
           coalesce(pc.eh_receita, FALSE) AS eh_receita,
           CASE WHEN c.CFOP LIKE '7%' OR v.exterior THEN 'exportacao'
                WHEN c.CFOP LIKE '6%' THEN 'interestadual'
                WHEN v.eh_zfm THEN 'zfm_interna'
                ELSE 'interna' END AS tipo_operacao
    FROM raw_icms_c190 c
    JOIN v_docs v ON v.arquivo_id = c.arquivo_id AND v.doc_linha = c.pai_linha
    LEFT JOIN param_cfops pc ON pc.cfop = c.CFOP
    WHERE v.sentido = 'saida' AND NOT v.cancelado
    """),
    ("v_saidas_item", f"""
    WITH c170 AS (
        SELECT i.arquivo_id, i.linha_num, 'C170' AS reg_origem, i.cnpj_estab, i.COD_ITEM AS cod_item,
               i.CFOP AS cfop, i.VL_ITEM AS vl_item, coalesce(i.VL_DESC, 0) AS vl_desc,
               i.CST_PIS AS cst_pis, i.ALIQ_PIS AS aliq_pis, i.VL_PIS AS vl_pis,
               i.CST_COFINS AS cst_cofins, i.ALIQ_COFINS AS aliq_cofins, i.VL_COFINS AS vl_cofins,
               i.CST_IPI AS cst_ipi, i.VL_ICMS AS vl_icms, i.VL_IPI AS vl_ipi,
               i.VL_ITEM - coalesce(i.VL_DESC, 0) AS receita_cofins,
               d.COD_PART AS cod_part, d.CHV_NFE AS chv_nfe, CAST(NULL AS VARCHAR) AS ncm_c180
        FROM raw_contrib_c170 i
        JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
        WHERE d.IND_OPER = '1' AND coalesce(d.COD_SIT, '00') NOT IN {_COD_SIT_CANCELADO}
    ),
    c181 AS (SELECT *, row_number() OVER (PARTITION BY arquivo_id, pai_linha, CFOP, VL_ITEM,
                       coalesce(VL_DESC, 0) ORDER BY linha_num) AS rn FROM raw_contrib_c181),
    c185 AS (SELECT *, row_number() OVER (PARTITION BY arquivo_id, pai_linha, CFOP, VL_ITEM,
                       coalesce(VL_DESC, 0) ORDER BY linha_num) AS rn FROM raw_contrib_c185),
    -- C181 (PIS) define a receita; o C185 (COFINS) e casado pela mesma linha (CFOP, valor).
    -- C185 sem par entra so com a COFINS (receita 0), exceto se o C180 nao tiver nenhum C181:
    -- assim a receita nunca e contada duas vezes (DECISOES D-023).
    casados AS (
        SELECT a.arquivo_id, a.linha_num, a.pai_linha, a.CFOP, a.VL_ITEM, coalesce(a.VL_DESC, 0) AS VL_DESC,
               a.CST_PIS, a.ALIQ_PIS, a.VL_PIS, b.CST_COFINS, b.ALIQ_COFINS, b.VL_COFINS,
               (b.linha_num IS NOT NULL) AS tem_cofins
        FROM c181 a LEFT JOIN c185 b ON a.arquivo_id = b.arquivo_id AND a.pai_linha = b.pai_linha
             AND a.CFOP = b.CFOP AND a.VL_ITEM = b.VL_ITEM
             AND coalesce(a.VL_DESC, 0) = coalesce(b.VL_DESC, 0) AND a.rn = b.rn),
    sobra185 AS (
        SELECT b.* FROM c185 b WHERE NOT EXISTS (
            SELECT 1 FROM c181 a WHERE a.arquivo_id = b.arquivo_id AND a.pai_linha = b.pai_linha
              AND a.CFOP = b.CFOP AND a.VL_ITEM = b.VL_ITEM
              AND coalesce(a.VL_DESC, 0) = coalesce(b.VL_DESC, 0) AND a.rn = b.rn)),
    com_pis AS (SELECT DISTINCT arquivo_id, pai_linha FROM raw_contrib_c181),
    cons AS (
        SELECT a.arquivo_id, a.linha_num, 'C181/C185' AS reg_origem, h.cnpj_estab,
               h.COD_ITEM AS cod_item, a.CFOP AS cfop, a.VL_ITEM AS vl_item, a.VL_DESC AS vl_desc,
               a.CST_PIS AS cst_pis, a.ALIQ_PIS AS aliq_pis, a.VL_PIS AS vl_pis,
               a.CST_COFINS AS cst_cofins, a.ALIQ_COFINS AS aliq_cofins, a.VL_COFINS AS vl_cofins,
               CASE WHEN a.tem_cofins THEN a.VL_ITEM - a.VL_DESC ELSE 0 END AS receita_cofins,
               CAST(NULL AS VARCHAR) AS cst_ipi, CAST(NULL AS DECIMAL(18,2)) AS vl_icms,
               CAST(NULL AS DECIMAL(18,2)) AS vl_ipi, CAST(NULL AS VARCHAR) AS cod_part,
               CAST(NULL AS VARCHAR) AS chv_nfe, h.COD_NCM AS ncm_c180
        FROM casados a
        JOIN raw_contrib_c180 h ON h.arquivo_id = a.arquivo_id AND h.linha_num = a.pai_linha
        UNION ALL
        SELECT b.arquivo_id, b.linha_num, 'C185', h.cnpj_estab, h.COD_ITEM, b.CFOP,
               CASE WHEN cp.pai_linha IS NULL THEN b.VL_ITEM ELSE 0 END,
               CASE WHEN cp.pai_linha IS NULL THEN coalesce(b.VL_DESC, 0) ELSE 0 END,
               NULL, NULL, NULL, b.CST_COFINS, b.ALIQ_COFINS, b.VL_COFINS,
               b.VL_ITEM - coalesce(b.VL_DESC, 0), NULL, NULL, NULL, NULL, NULL, h.COD_NCM
        FROM sobra185 b
        JOIN raw_contrib_c180 h ON h.arquivo_id = b.arquivo_id AND h.linha_num = b.pai_linha
        LEFT JOIN com_pis cp ON cp.arquivo_id = b.arquivo_id AND cp.pai_linha = b.pai_linha
    ),
    u AS (SELECT * FROM c170 UNION ALL BY NAME SELECT * FROM cons)
    SELECT u.arquivo_id, u.linha_num, u.reg_origem, a.raiz, u.cnpj_estab,
           year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, u.cod_item,
           coalesce(nullif(u.ncm_c180, ''), pp.ncm) AS ncm, u.cfop,
           u.vl_item, u.vl_desc, u.vl_item - u.vl_desc AS receita, u.receita_cofins, u.chv_nfe,
           u.cst_pis, u.aliq_pis, u.vl_pis, u.cst_cofins, u.aliq_cofins, u.vl_cofins,
           u.cst_ipi, u.vl_icms, u.vl_ipi,
           coalesce(pc.categoria, 'outros') AS categoria_cfop, coalesce(pc.eh_receita, FALSE) AS eh_receita,
           CASE WHEN u.cod_part IS NULL THEN NULL
                WHEN u.cfop LIKE '7%' OR p.exterior THEN 'exportacao'
                WHEN u.cfop LIKE '6%' THEN 'interestadual'
                WHEN p.eh_zfm THEN 'zfm_interna' ELSE 'interna' END AS tipo_operacao_exato,
           CASE WHEN u.cod_part IS NULL THEN NULL ELSE coalesce(p.eh_grupo, FALSE) END AS eh_grupo_exato,
           p.uf AS uf_dest_exato, p.contribuinte AS contribuinte_exato, p.tipo_zfm AS tipo_zfm_exato,
           p.municipio_zfm AS municipio_zfm_exato,
           coalesce(e.no_amazonas, FALSE) AS estab_no_am
    FROM u JOIN arquivos a ON a.arquivo_id = u.arquivo_id AND a.ativo
    LEFT JOIN param_cfops pc ON pc.cfop = u.cfop
    LEFT JOIN v_participantes_contrib p ON p.arquivo_id = u.arquivo_id
         AND p.cnpj_estab = u.cnpj_estab AND p.cod_part = u.cod_part
    LEFT JOIN v_estabelecimentos e ON e.cnpj = u.cnpj_estab
    LEFT JOIN (SELECT raiz_cnpj, cod_item, max(ncm) AS ncm FROM param_produtos GROUP BY ALL) pp
         ON pp.raiz_cnpj = a.raiz AND pp.cod_item = u.cod_item
    """),
    ("v_saidas_dest", """
    WITH sh AS (
        SELECT cnpj_estab, mes, cfop, tipo_operacao, eh_grupo, uf AS uf_dest, contribuinte, tipo_zfm,
               municipio_zfm, sum(vl_opr) AS v
        FROM v_saidas_doc GROUP BY ALL),
    tot AS (SELECT cnpj_estab, mes, cfop, sum(v) AS t, count(*) AS n FROM sh GROUP BY ALL),
    icms AS (SELECT cnpj_estab, mes, cfop,
                    sum(vl_icms_c190) / nullif(sum(vl_opr), 0) AS r_icms
             FROM v_saidas_doc GROUP BY ALL),
    base AS (
        SELECT s.*,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN s.tipo_operacao_exato
                    WHEN sh.tipo_operacao IS NOT NULL THEN sh.tipo_operacao
                    WHEN s.cfop LIKE '7%' THEN 'exportacao'
                    WHEN s.cfop LIKE '6%' THEN 'interestadual' ELSE 'interna' END AS tipo_operacao,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN s.eh_grupo_exato
                    ELSE coalesce(sh.eh_grupo, FALSE) END AS eh_grupo,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN s.uf_dest_exato ELSE sh.uf_dest END AS uf_dest,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN coalesce(s.contribuinte_exato, FALSE)
                    ELSE coalesce(sh.contribuinte, s.cfop NOT LIKE '7%') END AS contribuinte,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN coalesce(s.tipo_zfm_exato, 'nao_habilitado')
                    ELSE coalesce(sh.tipo_zfm, 'nao_habilitado') END AS tipo_zfm_dest,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL THEN coalesce(s.municipio_zfm_exato, FALSE)
                    ELSE coalesce(sh.municipio_zfm, FALSE) END AS municipio_zfm_dest,
               CASE WHEN s.tipo_operacao_exato IS NOT NULL OR sh.v IS NULL THEN 1.0
                    WHEN coalesce(t.t, 0) = 0 THEN 1.0 / t.n
                    ELSE CAST(sh.v AS DOUBLE) / CAST(t.t AS DOUBLE) END AS fator_rateio,
               (s.tipo_operacao_exato IS NULL AND sh.v IS NOT NULL AND t.n > 1) AS rateado,
               coalesce(i.r_icms, 0) AS r_icms
        FROM v_saidas_item s
        LEFT JOIN sh ON s.tipo_operacao_exato IS NULL AND sh.cnpj_estab = s.cnpj_estab
             AND sh.mes = s.mes AND sh.cfop = s.cfop
        LEFT JOIN tot t ON t.cnpj_estab = s.cnpj_estab AND t.mes = s.mes AND t.cfop = s.cfop
        LEFT JOIN icms i ON i.cnpj_estab = s.cnpj_estab AND i.mes = s.mes AND i.cfop = s.cfop
    )
    SELECT *,
           CAST(receita AS DOUBLE) * fator_rateio AS receita_r,
           CAST(coalesce(vl_pis, 0) AS DOUBLE) * fator_rateio AS pis_r,
           CAST(coalesce(vl_cofins, 0) AS DOUBLE) * fator_rateio AS cofins_r,
           CAST(receita_cofins AS DOUBLE) * fator_rateio AS receita_cofins_r,
           CASE WHEN vl_icms IS NOT NULL THEN CAST(vl_icms AS DOUBLE)
                ELSE CAST(receita AS DOUBLE) * r_icms END * fator_rateio AS icms_est_r,
           (vl_icms IS NULL) AS icms_estimado
    FROM base
    """),
    ("v_doc_par", vinculo.V_DOC_PAR),
    ("v_entradas_linhas", vinculo.V_ENTRADAS_LINHAS),
    ("v_entradas_pc", vinculo.V_ENTRADAS_PC),
    ("v_entradas_item", f"""
    -- Entradas: linhas do SPED Fiscal (C170; Excecao 2; C190) com PIS/COFINS da EFD Contribuicoes por nivel
    -- de cruzamento (zfm/vinculo.py) + linhas que so existem na EFD Contribuicoes (EC_EXCLUSIVO/EC_SEM_PAR)
    WITH pc AS (SELECT * FROM v_entradas_pc),
    pcp AS (SELECT DISTINCT ON (arquivo_id, cnpj_estab, cod_part) * FROM v_participantes_contrib
            ORDER BY arquivo_id, cnpj_estab, cod_part),
    pcc AS (SELECT DISTINCT ON (arquivo_id, cnpj_estab, k) *
            FROM (SELECT *, regexp_replace(coalesce(cnpj_part, ''), '[^0-9A-Za-z]', '', 'g') AS k
                  FROM v_participantes_contrib) ORDER BY arquivo_id, cnpj_estab, k),
    lin AS (
        SELECT l.arquivo_id, l.linha_num, l.reg_origem, l.doc_linha, l.ec_arquivo_id, l.num_item, l.cod_item, l.cfop,
               l.vl_item, l.vl_desc, l.cst_icms, l.vl_icms, l.cst_ipi, l.vl_ipi,
               p.cst_pis, p.vl_pis, p.cst_cofins, p.vl_cofins, p.aliq_pis, p.aliq_cofins,
               coalesce(p.nivel, 'SEM_CREDITO') AS nivel_cruzamento, l.valor,
               v.raiz, v.cnpj_estab, v.ano, v.mes, v.cod_part, v.nome_part, v.cnpj_part, v.chv_nfe, v.uf, v.regiao,
               v.exterior, v.eh_zfm, v.eh_grupo, v.contribuinte, v.tipo_zfm, v.regime_part,
               v.municipio_zfm
        FROM v_entradas_linhas l JOIN v_docs v ON v.arquivo_id = l.arquivo_id AND v.doc_linha = l.doc_linha
        LEFT JOIN (SELECT * FROM pc WHERE tipo = 'linha') p ON p.lk = l.lk),
    so AS (
        SELECT s.ec_arquivo_id AS arquivo_id, coalesce(s.ec_linha, 0) AS linha_num,
               'EFD Contribuições ' || s.reg AS reg_origem, s.ec_doc AS doc_linha, s.ec_arquivo_id, s.num_item,
               s.cod_item, s.cfop,
               CASE WHEN s.nivel = 'EC_EXCLUSIVO' THEN s.vl_item ELSE 0.0 END AS vl_item,
               CASE WHEN s.nivel = 'EC_EXCLUSIVO' THEN s.vl_desc ELSE 0.0 END AS vl_desc,
               CAST(NULL AS VARCHAR) AS cst_icms,
               CASE WHEN s.nivel = 'EC_EXCLUSIVO' THEN s.vl_icms ELSE 0.0 END AS vl_icms,
               CAST(NULL AS VARCHAR) AS cst_ipi,
               CASE WHEN s.nivel = 'EC_EXCLUSIVO' THEN s.vl_ipi ELSE 0.0 END AS vl_ipi,
               s.cst_pis, s.vl_pis, s.cst_cofins, s.vl_cofins, s.aliq_pis, s.aliq_cofins, s.nivel AS nivel_cruzamento,
               CASE WHEN s.nivel = 'EC_EXCLUSIVO' THEN coalesce(s.vl_item, 0) - coalesce(s.vl_desc, 0) ELSE 0.0 END AS valor,
               s.raiz, s.cnpj_estab, s.ano, s.mes, d.COD_PART AS cod_part,
               coalesce(p.nome_part, q.nome_part) AS nome_part, coalesce(p.cnpj_part, q.cnpj_part, s.forn) AS cnpj_part,
               d.CHV_NFE AS chv_nfe, coalesce(p.uf, q.uf) AS uf, coalesce(p.regiao, q.regiao) AS regiao,
               coalesce(p.exterior, q.exterior, FALSE) AS exterior, coalesce(p.eh_zfm, q.eh_zfm, FALSE) AS eh_zfm,
               coalesce(p.eh_grupo, q.eh_grupo, FALSE) AS eh_grupo,
               coalesce(p.contribuinte, q.contribuinte, FALSE) AS contribuinte,
               coalesce(p.tipo_zfm, q.tipo_zfm, 'nao_habilitado') AS tipo_zfm,
               coalesce(p.regime_part, q.regime_part, 'regular') AS regime_part,
               coalesce(p.municipio_zfm, q.municipio_zfm, FALSE) AS municipio_zfm
        FROM (SELECT * FROM pc WHERE tipo = 'so_efd') s
        LEFT JOIN raw_contrib_c100 d ON d.arquivo_id = s.ec_arquivo_id AND d.linha_num = s.ec_doc
        LEFT JOIN pcp p ON p.arquivo_id = s.ec_arquivo_id AND p.cnpj_estab = s.cnpj_estab AND p.cod_part = d.COD_PART
        LEFT JOIN pcc q ON s.ec_doc IS NULL AND q.arquivo_id = s.ec_arquivo_id AND q.cnpj_estab = s.cnpj_estab
             AND q.k = s.forn
        WHERE s.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)),
    it AS (SELECT * FROM lin UNION ALL BY NAME SELECT * FROM so)
    SELECT it.*,
           coalesce(pc.categoria, 'outros') AS categoria_cfop, coalesce(pc.devolucao_de, '') AS devolucao_de,
           CASE WHEN it.cfop LIKE '3%' OR it.exterior THEN 'importacao'
                WHEN it.eh_zfm THEN 'zfm'
                WHEN it.uf = 'AM' THEN 'am_fora_zfm'
                ELSE 'nacional_fora_zfm' END AS origem,
           CASE WHEN it.cfop LIKE '3%' OR it.exterior THEN 'Importação'
                WHEN it.eh_zfm THEN 'ZFM'
                WHEN it.uf IN {SUL_SUDESTE_EXCETO_ES} THEN 'Sul/Sudeste exceto ES'
                WHEN it.uf = 'AM' THEN 'Amazonas fora da ZFM'
                ELSE 'Norte, Nordeste, Centro-Oeste e ES' END AS regiao_origem,
           (it.uf IN {SUL_SUDESTE_EXCETO_ES}) AS sul_sudeste_exceto_es
    FROM it LEFT JOIN param_cfops pc ON pc.cfop = it.cfop
    """),
    ("v_entradas_servicos", f"""
    SELECT a.raiz, i.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, i.arquivo_id,
           i.linha_num, 'A170' AS reg_origem, i.VL_ITEM - coalesce(i.VL_DESC, 0) AS valor,
           i.CST_PIS AS cst_pis, CAST(i.VL_PIS AS DOUBLE) AS vl_pis, i.CST_COFINS AS cst_cofins,
           CAST(i.VL_COFINS AS DOUBLE) AS vl_cofins
    FROM raw_contrib_a170 i JOIN raw_contrib_a100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
    JOIN arquivos a ON a.arquivo_id = i.arquivo_id
    WHERE a.ativo AND d.IND_OPER = '0' AND coalesce(d.COD_SIT, '00') NOT IN {_COD_SIT_CANCELADO}
    UNION ALL
    SELECT a.raiz, f.cnpj_estab, year(a.dt_ini), month(a.dt_ini), f.arquivo_id, f.linha_num, 'F100',
           f.VL_OPER, f.CST_PIS, CAST(f.VL_PIS AS DOUBLE), f.CST_COFINS, CAST(f.VL_COFINS AS DOUBLE)
    FROM raw_contrib_f100 f JOIN arquivos a USING (arquivo_id)
    WHERE a.ativo AND f.IND_OPER = '0'
    """),
    ("v_base_operacoes", """
    -- Base de operacoes normalizada (uma linha por item ou consolidacao). Uma fonte por visao:
    --   saidas por produto: EFD Contribuicoes (C170 ou C181/C185), destino pelo C190+0150 da Fiscal;
    --   entradas: EFD ICMS/IPI (C170; C190 quando o documento nao tem C170);
    --   devolucoes de venda (entradas 1201/2201...) abatem as saidas de origem (valores negativos);
    --   devolucoes de compra (saidas 5201/6201...) abatem as entradas de origem (valores negativos).
    WITH prm AS (
        SELECT coalesce((SELECT lower(valor) FROM param_premissas WHERE chave = 'abater_devolucoes'),
                        'sim') NOT IN ('nao', 'não') AS abater),
    s AS (
        SELECT 'saida' AS sentido, s.raiz, s.cnpj_estab, s.ano, s.mes, s.chv_nfe, s.reg_origem,
               s.arquivo_id, s.linha_num, s.cfop, s.categoria_cfop, s.categoria_cfop AS categoria_origem,
               s.eh_receita,
               CASE WHEN s.categoria_cfop = 'transferencia' THEN 'transferencia'
                    WHEN s.eh_receita AND s.tipo_operacao = 'exportacao' THEN 'exportacao'
                    WHEN s.eh_receita THEN 'venda'
                    WHEN s.categoria_cfop = 'remessa_retorno' THEN 'remessa'
                    ELSE s.categoria_cfop END AS natureza,
               s.cod_item, s.ncm, s.tipo_operacao, CAST(NULL AS VARCHAR) AS origem,
               CAST(NULL AS BOOLEAN) AS sul_sudeste_exceto_es, s.uf_dest AS uf_part,
               CAST(NULL AS VARCHAR) AS cnpj_part, coalesce(s.eh_grupo, FALSE) AS eh_grupo,
               s.receita_r AS valor, s.receita_cofins_r AS valor_cofins, s.icms_est_r AS icms,
               CAST(coalesce(s.vl_ipi, 0) AS DOUBLE) * s.fator_rateio AS ipi, s.pis_r AS pis,
               s.cofins_r AS cofins, CAST(NULL AS VARCHAR) AS cst_icms, s.cst_ipi, s.cst_pis,
               CAST(s.aliq_pis AS DOUBLE) AS aliq_pis, s.cst_cofins,
               CAST(s.aliq_cofins AS DOUBLE) AS aliq_cofins, s.fator_rateio, s.rateado, s.icms_estimado,
               s.contribuinte, s.tipo_zfm_dest AS tipo_zfm_part, CAST(NULL AS VARCHAR) AS regime_part,
               s.municipio_zfm_dest AS municipio_zfm_part
        FROM v_saidas_dest s LEFT JOIN param_cfops pc ON pc.cfop = s.cfop
        WHERE s.estab_no_am AND coalesce(pc.devolucao_de, '') = ''
    ),
    dv AS (
        SELECT 'saida', e.raiz, e.cnpj_estab, e.ano, e.mes, e.chv_nfe, 'devolução ' || e.reg_origem,
               e.arquivo_id, e.linha_num, e.cfop, e.categoria_cfop, e.devolucao_de, TRUE,
               'devolucao_venda', e.cod_item, NULL,
               CASE WHEN e.cfop LIKE '3%' OR e.exterior THEN 'exportacao'
                    WHEN e.cfop LIKE '2%' THEN 'interestadual'
                    WHEN e.eh_zfm THEN 'zfm_interna' ELSE 'interna' END,
               NULL, NULL, e.uf, e.cnpj_part, e.eh_grupo,
               -CAST(e.valor AS DOUBLE), -CAST(e.valor AS DOUBLE), -CAST(coalesce(e.vl_icms, 0) AS DOUBLE),
               -CAST(coalesce(e.vl_ipi, 0) AS DOUBLE), -CAST(coalesce(e.vl_pis, 0) AS DOUBLE),
               -CAST(coalesce(e.vl_cofins, 0) AS DOUBLE), e.cst_icms, e.cst_ipi, e.cst_pis,
               CAST(e.aliq_pis AS DOUBLE), e.cst_cofins, CAST(e.aliq_cofins AS DOUBLE), 1.0, FALSE, FALSE,
               e.contribuinte, e.tipo_zfm, e.regime_part, e.municipio_zfm
        FROM v_entradas_item e
        WHERE e.devolucao_de IN ('venda_producao', 'venda_revenda') AND (SELECT abater FROM prm)
    ),
    en AS (
        SELECT 'entrada', e.raiz, e.cnpj_estab, e.ano, e.mes, e.chv_nfe, e.reg_origem, e.arquivo_id,
               e.linha_num, e.cfop, e.categoria_cfop, e.categoria_cfop, FALSE,
               CASE WHEN e.origem = 'importacao' THEN 'importacao'
                    WHEN e.categoria_cfop = 'transferencia' THEN 'transferencia'
                    WHEN e.categoria_cfop = 'remessa_retorno' THEN 'remessa'
                    ELSE e.categoria_cfop END,
               e.cod_item, NULL, NULL, e.origem, e.sul_sudeste_exceto_es, e.uf, e.cnpj_part, e.eh_grupo,
               CAST(e.valor AS DOUBLE), CAST(e.valor AS DOUBLE), CAST(coalesce(e.vl_icms, 0) AS DOUBLE),
               CAST(coalesce(e.vl_ipi, 0) AS DOUBLE), CAST(coalesce(e.vl_pis, 0) AS DOUBLE),
               CAST(coalesce(e.vl_cofins, 0) AS DOUBLE), e.cst_icms, e.cst_ipi, e.cst_pis,
               CAST(e.aliq_pis AS DOUBLE), e.cst_cofins, CAST(e.aliq_cofins AS DOUBLE), 1.0, FALSE, FALSE,
               e.contribuinte, e.tipo_zfm, e.regime_part, e.municipio_zfm
        FROM v_entradas_item e
        WHERE e.devolucao_de NOT IN ('venda_producao', 'venda_revenda')
    ),
    dc AS (
        SELECT 'entrada', d.raiz, d.cnpj_estab, d.ano, d.mes, d.chv_nfe, 'devolução C190', d.arquivo_id,
               d.linha_num, d.cfop, d.categoria_cfop, d.devolucao_de, FALSE, 'devolucao_compra',
               NULL, NULL, NULL,
               CASE WHEN d.cfop LIKE '7%' OR d.exterior THEN 'importacao' WHEN d.eh_zfm THEN 'zfm'
                    WHEN d.uf = 'AM' THEN 'am_fora_zfm' ELSE 'nacional_fora_zfm' END,
               d.uf IN ('MG', 'RJ', 'SP', 'PR', 'SC', 'RS'), d.uf, d.cnpj_part, d.eh_grupo,
               -CAST(d.vl_opr - coalesce(d.vl_ipi_c190, 0) - coalesce(d.vl_icms_st_c190, 0) AS DOUBLE),
               -CAST(d.vl_opr - coalesce(d.vl_ipi_c190, 0) - coalesce(d.vl_icms_st_c190, 0) AS DOUBLE),
               -CAST(coalesce(d.vl_icms_c190, 0) AS DOUBLE), -CAST(coalesce(d.vl_ipi_c190, 0) AS DOUBLE),
               0.0, 0.0, d.cst_icms, NULL, NULL, NULL, NULL, NULL, 1.0, FALSE, FALSE,
               d.contribuinte, d.tipo_zfm, d.regime_part, d.municipio_zfm
        FROM v_saidas_doc d
        WHERE coalesce(d.devolucao_de, '') IN ('compra_industrializacao', 'compra_revenda', 'ativo', 'uso_consumo')
          AND d.uf_estab = 'AM' AND (SELECT abater FROM prm)
    ),
    sv AS (
        SELECT 'entrada', v.raiz, v.cnpj_estab, v.ano, v.mes, NULL, v.reg_origem, v.arquivo_id,
               v.linha_num, NULL, 'insumo_servico', 'insumo_servico', FALSE, 'servico_tomado', NULL, NULL,
               NULL, 'servicos', FALSE, NULL, NULL, FALSE, CAST(v.valor AS DOUBLE), CAST(v.valor AS DOUBLE),
               0.0, 0.0, coalesce(v.vl_pis, 0.0), coalesce(v.vl_cofins, 0.0), NULL, NULL, v.cst_pis, NULL,
               v.cst_cofins, NULL, 1.0, FALSE, FALSE,
               NULL, NULL, NULL, NULL
        FROM v_entradas_servicos v
        WHERE v.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)
    ),
    sp AS (  -- servicos prestados (A100/A170 de saida da EFD Contribuicoes): cenario 5 (art. 451) ou regra geral
        SELECT 'saida', a.raiz, i.cnpj_estab, year(a.dt_ini), month(a.dt_ini),
               coalesce(nullif(d.CHV_NFSE, ''), d.NUM_DOC), 'A170 (serviço prestado)', i.arquivo_id, i.linha_num,
               NULL, 'servico_prestado', 'servico_prestado', TRUE, 'servico_prestado', i.COD_ITEM, NULL,
               CASE WHEN p.exterior THEN 'exportacao' WHEN p.uf IS NOT NULL AND p.uf <> 'AM' THEN 'interestadual'
                    WHEN p.eh_zfm THEN 'zfm_interna' ELSE 'interna' END,
               NULL, NULL, p.uf, p.cnpj_part, coalesce(p.eh_grupo, FALSE),
               CAST(i.VL_ITEM - coalesce(i.VL_DESC, 0) AS DOUBLE), CAST(i.VL_ITEM - coalesce(i.VL_DESC, 0) AS DOUBLE),
               0.0, 0.0, CAST(coalesce(i.VL_PIS, 0) AS DOUBLE), CAST(coalesce(i.VL_COFINS, 0) AS DOUBLE),
               NULL, NULL, i.CST_PIS, CAST(i.ALIQ_PIS AS DOUBLE), i.CST_COFINS, CAST(i.ALIQ_COFINS AS DOUBLE),
               1.0, FALSE, FALSE, coalesce(p.contribuinte, FALSE), coalesce(p.tipo_zfm, 'nao_habilitado'),
               coalesce(p.regime_part, 'regular'), coalesce(p.municipio_zfm, FALSE)
        FROM raw_contrib_a170 i JOIN raw_contrib_a100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
        JOIN arquivos a ON a.arquivo_id = i.arquivo_id
        LEFT JOIN (SELECT DISTINCT ON (arquivo_id, cnpj_estab, cod_part) * FROM v_participantes_contrib
                   ORDER BY arquivo_id, cnpj_estab, cod_part) p
             ON p.arquivo_id = d.arquivo_id AND p.cnpj_estab = d.cnpj_estab AND p.cod_part = d.COD_PART
        WHERE a.ativo AND d.IND_OPER = '1' AND coalesce(d.COD_SIT, '00') NOT IN ('02','03','04','05')
          AND i.cnpj_estab IN (SELECT cnpj FROM v_estabelecimentos WHERE no_amazonas)
    ),
    u AS (SELECT * FROM s UNION ALL SELECT * FROM dv UNION ALL SELECT * FROM en
          UNION ALL SELECT * FROM dc UNION ALL SELECT * FROM sv UNION ALL SELECT * FROM sp)
    SELECT u.*, coalesce(nullif(u.ncm, ''), p.ncm) AS ncm_produto,
           coalesce(p.incentivado, FALSE) AND u.categoria_origem = 'venda_producao' AS incentivado,
           p.tipo_bem, p.aliq_ipi AS aliq_tipi
    FROM u LEFT JOIN param_produtos p ON p.raiz_cnpj = u.raiz AND p.cod_item = u.cod_item
    """),
    ("v_cenarios", """
    -- Classificacao de cada operacao nos seis macrocenarios (LC 214/2025, arts. 440-455) e teste dos requisitos.
    -- 1) cenario_candidato: pelos fatos da escrituracao (sentido, CFOP, UF, municipio, tipo ZFM, produto);
    -- 2) requisitos: 'ok', 'falha', 'pendente' (nao comprovado) ou 'insuficiente' (dado ausente); nada e presumido;
    -- 3) status_elegibilidade e cenario efetivo: requisito em falha leva a regra geral (art. 453).
    WITH prm AS (
        SELECT coalesce((SELECT lower(valor) FROM param_premissas WHERE chave = 'revenda_presencial'),
                        'sim') IN ('sim', 's') AS revenda,
               coalesce((SELECT lower(valor) FROM param_premissas WHERE chave = 'c3a_intermediario'),
                        'compra_industrializacao') AS c3a),
    proj AS (SELECT cnpj, lower(coalesce(status, '')) AS st, coalesce(cod_item, '') AS cod_item, coalesce(ncm, '') AS ncm,
                    try_cast(vigencia_ini AS DATE) AS vi, try_cast(vigencia_fim AS DATE) AS vf
             FROM param_projetos_suframa),
    est AS (SELECT DISTINCT ON (cnpj) cnpj, cod_mun FROM v_estabelecimentos ORDER BY cnpj),
    b AS (
        SELECT b.*, coalesce(nullif(e.tipo, ''), 'nao_habilitado') AS tipo_estab,
               coalesce(nullif(e.regime, ''), 'regular') AS regime_estab, coalesce(e.revisado, FALSE) AS estab_revisado,
               lower(coalesce(e.status_habilitacao, '')) AS st_hab, try_cast(e.validade_fim AS DATE) AS hab_fim, es.cod_mun AS cod_mun_estab,
               es.cod_mun IN (SELECT cod_ibge FROM param_municipios_zfm) AS estab_area_zfm,
               make_date(CAST(b.ano AS INTEGER), CAST(b.mes AS INTEGER), 1) AS dt_ref,
               coalesce(ef.revisado, FALSE) AS part_revisado,
               b.categoria_origem IN ('compra_industrializacao', 'compra_revenda', 'ativo', 'uso_consumo',
                                      'insumo_servico') AS compra,
               CASE WHEN b.natureza = 'devolucao_compra' THEN translate(substr(b.cfop, 1, 1), '567', '123')
                    ELSE substr(b.cfop, 1, 1) END AS dig,
               lower(coalesce(pp.excluido_art441, '')) AS x441, coalesce(pp.observacao, '') AS motivo_441,
               lower(coalesce(pp.origem, '')) AS xorig,
               lower(coalesce(pp.consumo_produtivo_comprovado, '')) AS xcons,
               lower(coalesce(it.status, '')) AS st_ing, lower(coalesce(sv.local_fisico_zfm, '')) AS st_srv
        FROM v_base_operacoes b
        LEFT JOIN param_empresas_zfm e ON e.cnpj = b.cnpj_estab
        LEFT JOIN param_empresas_zfm ef ON ef.cnpj = b.cnpj_part
        LEFT JOIN est es ON es.cnpj = b.cnpj_estab
        LEFT JOIN param_produtos pp ON pp.raiz_cnpj = b.raiz AND pp.cod_item = b.cod_item
        LEFT JOIN param_internamento it ON it.chv_nfe = b.chv_nfe
        LEFT JOIN param_servicos_zfm sv ON sv.cnpj_estab = b.cnpj_estab AND sv.documento = b.chv_nfe),
    c AS (
        SELECT b.*,
        CASE
            WHEN b.natureza = 'transferencia' THEN 'TR'
            WHEN b.sentido = 'entrada' AND b.origem = 'servicos' THEN 'SRV'
            WHEN b.sentido = 'entrada' AND NOT b.compra THEN 'REM'
            WHEN b.sentido = 'entrada' AND (b.dig = '3' OR b.origem = 'importacao') THEN
                CASE WHEN b.tipo_estab = 'industria_incentivada' THEN 'C1a'
                     WHEN b.tipo_estab = 'habilitado' THEN
                         CASE WHEN b.categoria_origem = 'compra_revenda' AND (SELECT revenda FROM prm)
                              THEN 'C1b' ELSE 'C1c' END
                     WHEN NOT b.estab_revisado THEN 'NC_E' ELSE 'GER_E' END
            WHEN b.sentido = 'entrada' AND b.dig = '2' AND coalesce(b.uf_part, '') <> 'AM' THEN
                CASE WHEN b.tipo_estab = 'industria_incentivada' THEN 'C2a'
                     WHEN b.tipo_estab = 'habilitado' AND b.regime_estab = 'simples' THEN 'C2c'
                     WHEN b.tipo_estab = 'habilitado' THEN 'C2b'
                     WHEN NOT b.estab_revisado THEN 'NC_E' ELSE 'GER_E' END
            WHEN b.sentido = 'entrada' AND b.dig = '1'
                 AND b.tipo_zfm_part IN ('industria_incentivada', 'habilitado') THEN
                CASE WHEN b.tipo_zfm_part = 'industria_incentivada' AND b.tipo_estab = 'industria_incentivada'
                          AND (b.tipo_bem = 'intermediario'
                               OR ((SELECT c3a FROM prm) = 'compra_industrializacao'
                                   AND b.categoria_origem = 'compra_industrializacao'))
                     THEN 'C3a' ELSE 'C3b' END
            WHEN b.sentido = 'entrada' AND b.dig = '1' AND coalesce(b.municipio_zfm_part, FALSE) THEN 'C3b'
            WHEN b.sentido = 'entrada' AND b.dig = '2' AND coalesce(b.uf_part, '') = 'AM' THEN 'NC_E'
            WHEN b.sentido = 'entrada' THEN 'GER_E'
            WHEN NOT b.eh_receita THEN 'REM'
            WHEN b.tipo_operacao = 'exportacao' THEN 'EXP'
            WHEN b.categoria_origem = 'servico_prestado' THEN
                CASE WHEN b.tipo_operacao = 'zfm_interna' OR coalesce(b.municipio_zfm_part, FALSE) THEN 'C5S'
                     ELSE 'GER_S' END
            WHEN b.categoria_origem = 'venda_producao' AND b.incentivado AND b.tipo_estab = 'industria_incentivada' THEN
                CASE WHEN b.tipo_operacao = 'zfm_interna' THEN
                         CASE WHEN b.tipo_zfm_part = 'industria_incentivada' AND b.tipo_bem = 'intermediario'
                              THEN 'C4d' ELSE 'C4c' END
                     WHEN b.contribuinte THEN 'C4a' ELSE 'C4b' END
            WHEN b.categoria_origem = 'venda_producao' AND b.incentivado AND NOT b.estab_revisado THEN 'NC_S'
            WHEN b.tipo_operacao = 'zfm_interna'
                 OR (b.tipo_operacao = 'interna' AND coalesce(b.municipio_zfm_part, FALSE)) THEN 'C5M'
            ELSE 'GER_S' END AS cenario_candidato,
        CASE
            WHEN b.natureza = 'transferencia' OR NOT (b.sentido = 'entrada' OR b.eh_receita) THEN ''
            WHEN b.sentido = 'entrada' AND (b.origem = 'servicos' OR NOT b.compra) THEN ''
            WHEN b.sentido = 'entrada' AND b.tipo_estab = 'nao_habilitado' AND b.dig IN ('2', '3')
                THEN CASE WHEN b.estab_revisado THEN 'Estabelecimento não habilitado: regra geral'
                          ELSE 'Estabelecimento do grupo sem tipo ZFM validado (Empresas ZFM)' END
            WHEN b.sentido = 'entrada' AND b.dig = '1' AND b.tipo_zfm_part NOT IN ('industria_incentivada', 'habilitado')
                 AND NOT coalesce(b.municipio_zfm_part, FALSE)
                THEN 'Compra interna de fornecedor fora da ZFM: regra geral'
            WHEN b.sentido = 'entrada' AND b.dig = '2' AND coalesce(b.uf_part, '') = 'AM'
                THEN 'CFOP interestadual com fornecedor do AM'
            WHEN b.sentido = 'saida' AND b.tipo_operacao = 'exportacao' THEN ''
            WHEN b.sentido = 'saida' AND b.categoria_origem = 'venda_producao' AND b.incentivado
                 AND b.tipo_estab <> 'industria_incentivada' AND NOT b.estab_revisado
                THEN 'Estabelecimento sem tipo ZFM validado (Empresas ZFM)'
            WHEN b.sentido = 'saida' AND b.tipo_operacao NOT IN ('zfm_interna') AND NOT coalesce(b.municipio_zfm_part, FALSE)
                 AND NOT (b.categoria_origem = 'venda_producao' AND b.incentivado AND b.tipo_estab = 'industria_incentivada')
                THEN 'Venda para fora da ZFM sem incentivo (revenda, produto não incentivado ou vendedor não '
                     || 'industrial): regra geral'
            ELSE '' END AS motivo_classificacao
        FROM b),
    r AS (
        SELECT c.*,
            CASE WHEN c.cenario_candidato NOT SIMILAR TO 'C[0-9].*' THEN ''
                 WHEN c.estab_area_zfm THEN 'ok' WHEN c.cod_mun_estab IS NULL THEN 'pendente' ELSE 'falha' END AS req_area,
            CASE WHEN c.cenario_candidato NOT SIMILAR TO 'C[1-4].*' THEN ''
                 WHEN c.st_hab IN ('suspensa', 'cancelada', 'vencida') THEN 'falha'
                 WHEN c.hab_fim IS NOT NULL AND c.dt_ref > c.hab_fim THEN 'falha'
                 WHEN c.estab_revisado THEN 'ok' ELSE 'pendente' END AS req_habilitacao,
            CASE WHEN c.cenario_candidato <> 'C3a' THEN ''
                 WHEN c.part_revisado THEN 'ok' ELSE 'pendente' END AS req_fornecedor,
            CASE WHEN c.cenario_candidato IN ('C1a', 'C3a') THEN
                     CASE WHEN NOT EXISTS (SELECT 1 FROM proj p WHERE p.cnpj = c.cnpj_estab) THEN 'pendente'
                          WHEN EXISTS (SELECT 1 FROM proj p WHERE p.cnpj = c.cnpj_estab AND p.st IN ('aprovado', 'ativo')
                                       AND (p.vi IS NULL OR c.dt_ref >= date_trunc('month', p.vi))
                                       AND (p.vf IS NULL OR c.dt_ref <= p.vf)) THEN 'ok'
                          ELSE 'falha' END
                 WHEN c.cenario_candidato LIKE 'C4%' THEN
                     CASE WHEN NOT EXISTS (SELECT 1 FROM proj p WHERE p.cnpj = c.cnpj_estab) THEN 'pendente'
                          WHEN EXISTS (SELECT 1 FROM proj p WHERE p.cnpj = c.cnpj_estab AND p.st IN ('aprovado', 'ativo')
                                       AND (p.cod_item = c.cod_item
                                            OR (p.cod_item = '' AND p.ncm <> '' AND starts_with(coalesce(c.ncm_produto, ''), p.ncm)))
                                       AND (p.vi IS NULL OR c.dt_ref >= date_trunc('month', p.vi))
                                       AND (p.vf IS NULL OR c.dt_ref <= p.vf)) THEN 'ok'
                          ELSE 'falha' END
                 ELSE '' END AS req_projeto,
            CASE WHEN c.cenario_candidato NOT SIMILAR TO 'C[1-4].*' THEN ''
                 WHEN coalesce(c.ncm_produto, '') <> '' THEN 'ok' ELSE 'insuficiente' END AS req_ncm,
            CASE WHEN c.cenario_candidato NOT SIMILAR TO 'C[1-4].*' AND c.cenario_candidato <> 'C5M' THEN ''
                 WHEN c.x441 = 'sim' THEN 'falha' WHEN c.x441 = 'nao' THEN 'ok' ELSE 'pendente' END AS req_art441,
            CASE WHEN c.cenario_candidato NOT SIMILAR TO 'C2.*' AND c.cenario_candidato <> 'C5M' THEN ''
                 WHEN c.xorig = 'nacional' THEN 'ok' WHEN c.xorig IN ('importada', 'estrangeira') THEN 'falha'
                 WHEN substr(coalesce(c.cst_icms, ''), 1, 1) IN ('0', '3', '4', '5', '8') AND length(c.cst_icms) = 3 THEN 'ok'
                 WHEN substr(coalesce(c.cst_icms, ''), 1, 1) IN ('1', '2', '6', '7') AND length(c.cst_icms) = 3 THEN 'falha'
                 ELSE 'insuficiente' END AS req_origem,
            (c.xorig = '' AND length(coalesce(c.cst_icms, '')) = 3) AS origem_inferida,
            CASE WHEN c.cenario_candidato NOT IN ('C1b', 'C2a', 'C2b', 'C2c') THEN ''
                 WHEN c.st_ing = 'confirmado' THEN 'ok' WHEN c.st_ing = 'negado' THEN 'falha' ELSE 'pendente' END AS req_ingresso,
            CASE WHEN c.cenario_candidato <> 'C3a' THEN ''
                 WHEN c.xcons = 'sim' THEN 'ok' WHEN c.xcons = 'nao' THEN 'falha' ELSE 'pendente' END AS req_consumo_produtivo,
            CASE WHEN c.cenario_candidato <> 'C5S' THEN ''
                 WHEN c.st_srv = 'sim' THEN 'ok' WHEN c.st_srv = 'nao' THEN 'falha' ELSE 'pendente' END AS req_servico_fisico,
            CASE WHEN c.cenario_candidato NOT LIKE 'C4%' THEN ''
                 WHEN coalesce(c.tipo_bem, '') <> '' THEN 'ok' ELSE 'insuficiente' END AS req_tipo_bem
        FROM c),
    t AS (
        SELECT r.*,
            concat_ws('; ',
                CASE WHEN req_area = 'falha' THEN 'estabelecimento fora da área da ZFM' END,
                CASE WHEN req_habilitacao = 'falha' THEN 'habilitação suspensa, cancelada ou fora da validade' END,
                CASE WHEN req_projeto = 'falha' THEN CASE WHEN cenario_candidato LIKE 'C4%'
                     THEN 'produto fora do projeto SUFRAMA aprovado' ELSE 'sem projeto SUFRAMA ativo' END END,
                CASE WHEN req_art441 = 'falha' THEN 'produto excluído pelo art. 441'
                     || CASE WHEN motivo_441 <> '' THEN ' (' || motivo_441 || ')' ELSE '' END END,
                CASE WHEN req_origem = 'falha' THEN 'bem de origem estrangeira'
                     || CASE WHEN origem_inferida THEN ' (inferido pela CST)' ELSE '' END END,
                CASE WHEN req_ingresso = 'falha' THEN 'ingresso na ZFM negado' END,
                CASE WHEN req_consumo_produtivo = 'falha' THEN 'bem não consumido na produção de bem final' END,
                CASE WHEN req_servico_fisico = 'falha' THEN 'serviço não prestado fisicamente na ZFM' END) AS requisitos_falha,
            concat_ws('; ',
                CASE WHEN req_ncm = 'insuficiente' THEN 'NCM ausente' END,
                CASE WHEN req_origem = 'insuficiente' THEN 'origem do bem não identificada' END,
                CASE WHEN req_tipo_bem = 'insuficiente' THEN 'tipo de bem não classificado' END) AS requisitos_insuficientes,
            concat_ws('; ',
                CASE WHEN req_area = 'pendente' THEN 'município do estabelecimento não informado' END,
                CASE WHEN req_habilitacao = 'pendente' THEN 'habilitação não validada (Empresas ZFM)' END,
                CASE WHEN req_fornecedor = 'pendente' THEN 'tipo do fornecedor não validado' END,
                CASE WHEN req_projeto = 'pendente' THEN 'projeto SUFRAMA não cadastrado' END,
                CASE WHEN req_art441 = 'pendente' THEN 'exclusão do art. 441 não validada' END,
                CASE WHEN req_origem = 'ok' AND origem_inferida THEN 'origem nacional inferida pela CST' END,
                CASE WHEN req_ingresso = 'pendente' THEN 'ingresso na ZFM não comprovado' END,
                CASE WHEN req_consumo_produtivo = 'pendente' THEN 'depende de comprovação produtiva' END,
                CASE WHEN req_servico_fisico = 'pendente' THEN 'local físico da prestação não comprovado' END
            ) AS requisitos_pendentes
        FROM r)
    SELECT t.*,
        CASE WHEN cenario_candidato IN ('EXP', 'TR', 'REM', 'SRV') THEN 'Fora dos incentivos'
             WHEN cenario_candidato IN ('GER_S', 'GER_E') THEN 'Não elegível'
             WHEN cenario_candidato IN ('NC_S', 'NC_E') THEN 'Informação insuficiente para determinar'
             WHEN requisitos_falha <> '' THEN 'Não elegível'
             WHEN requisitos_insuficientes <> '' THEN 'Informação insuficiente para determinar'
             WHEN requisitos_pendentes <> '' THEN 'Potencialmente elegível - depende de validação'
             ELSE 'Elegível' END AS status_elegibilidade,
        CASE WHEN cenario_candidato SIMILAR TO 'C[0-9].*' AND requisitos_falha <> ''
             THEN CASE sentido WHEN 'saida' THEN 'GER_S' ELSE 'GER_E' END
             ELSE cenario_candidato END AS cenario,
        CASE WHEN cenario_candidato SIMILAR TO 'C[0-9].*' AND requisitos_falha <> ''
             THEN 'Não elegível (' || cenario_candidato || '): ' || requisitos_falha
             ELSE motivo_classificacao END AS motivo
    FROM t
    """),
    ("v_ajustes_icms", """
    SELECT a.arquivo_id, a.cnpj AS cnpj_estab, a.raiz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           'E111' AS registro, e.COD_AJ_APUR AS codigo, e.DESCR_COMPL_AJ AS descricao,
           e.VL_AJ_APUR AS valor, coalesce(pc.classe, 'outros') AS classe,
           (pc.codigo IS NULL OR pc.classe = 'nao_classificado') AS nao_classificado, e.linha_num
    FROM raw_icms_e111 e JOIN arquivos a USING (arquivo_id)
    LEFT JOIN param_codigos_ajuste_icms pc ON pc.codigo = e.COD_AJ_APUR AND pc.registro = 'E111'
    WHERE a.ativo
    UNION ALL
    SELECT a.arquivo_id, a.cnpj, a.raiz, year(a.dt_ini), month(a.dt_ini), 'E116',
           coalesce(e.COD_REC, e.COD_OR), e.TXT_COMPL, e.VL_OR, coalesce(pc.classe, 'outros'),
           (pc.codigo IS NULL OR pc.classe = 'nao_classificado'), e.linha_num
    FROM raw_icms_e116 e JOIN arquivos a USING (arquivo_id)
    LEFT JOIN param_codigos_ajuste_icms pc ON pc.codigo = coalesce(e.COD_REC, e.COD_OR)
         AND pc.registro = 'E116'
    WHERE a.ativo
    """),
    ("v_apur_icms", """
    WITH aj AS (
        SELECT arquivo_id,
               sum(valor) FILTER (WHERE classe = 'credito_estimulo') AS credito_estimulo,
               sum(valor) FILTER (WHERE classe = 'credito_presumido_entrada') AS credito_presumido_entrada,
               sum(valor) FILTER (WHERE classe = 'fundo_FTI') AS fundo_fti,
               sum(valor) FILTER (WHERE classe = 'fundo_UEA') AS fundo_uea,
               sum(valor) FILTER (WHERE classe = 'fundo_FMPES') AS fundo_fmpes,
               sum(valor) FILTER (WHERE classe = 'outros_beneficios') AS outros_beneficios,
               sum(valor) FILTER (WHERE nao_classificado) AS nao_classificado
        FROM v_ajustes_icms GROUP BY 1)
    SELECT a.arquivo_id, a.cnpj AS cnpj_estab, a.raiz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           e.VL_TOT_DEBITOS AS debitos, e.VL_AJ_DEBITOS + e.VL_TOT_AJ_DEBITOS AS ajustes_debito,
           e.VL_ESTORNOS_CRED AS estornos_credito, e.VL_TOT_CREDITOS AS creditos,
           e.VL_AJ_CREDITOS + e.VL_TOT_AJ_CREDITOS AS ajustes_credito,
           e.VL_ESTORNOS_DEB AS estornos_debito, e.VL_SLD_CREDOR_ANT AS saldo_credor_anterior,
           e.VL_SLD_APURADO AS saldo_apurado, e.VL_TOT_DED AS deducoes,
           e.VL_ICMS_RECOLHER AS icms_recolher, e.VL_SLD_CREDOR_TRANSPORTAR AS saldo_credor_transportar,
           e.DEB_ESP AS debitos_especiais,
           coalesce(aj.credito_estimulo, 0) AS credito_estimulo,
           coalesce(aj.credito_presumido_entrada, 0) AS credito_presumido_entrada,
           coalesce(aj.fundo_fti, 0) AS fundo_fti, coalesce(aj.fundo_uea, 0) AS fundo_uea,
           coalesce(aj.fundo_fmpes, 0) AS fundo_fmpes,
           coalesce(aj.fundo_fti, 0) + coalesce(aj.fundo_uea, 0) + coalesce(aj.fundo_fmpes, 0) AS fundos,
           coalesce(aj.outros_beneficios, 0) AS outros_beneficios,
           coalesce(aj.nao_classificado, 0) AS valor_nao_classificado,
           e.linha_num
    FROM raw_icms_e110 e JOIN arquivos a USING (arquivo_id) LEFT JOIN aj USING (arquivo_id)
    WHERE a.ativo
    """),
    ("v_apur_ipi", """
    SELECT a.arquivo_id, a.cnpj AS cnpj_estab, a.raiz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           e.VL_SD_ANT_IPI AS saldo_anterior, e.VL_DEB_IPI AS debitos, e.VL_CRED_IPI AS creditos,
           e.VL_OD_IPI AS outros_debitos, e.VL_OC_IPI AS outros_creditos,
           e.VL_SC_IPI AS saldo_credor, e.VL_SD_IPI AS saldo_devedor, e.linha_num
    FROM raw_icms_e520 e JOIN arquivos a USING (arquivo_id) WHERE a.ativo
    """),
    ("v_apur_pis_cofins", """
    WITH m AS (
        SELECT arquivo_id,
               sum(VL_REC_BRT) AS receita_tributada_pis, sum(VL_CONT_PER) AS contrib_pis_detalhe
        FROM raw_contrib_m210 GROUP BY 1),
    mc AS (SELECT arquivo_id, sum(VL_CONT_PER) AS contrib_cofins_detalhe FROM raw_contrib_m610 GROUP BY 1),
    nt AS (SELECT arquivo_id, sum(VL_TOT_REC) AS receita_nao_tributada_pis FROM raw_contrib_m400 GROUP BY 1),
    ntc AS (SELECT arquivo_id, sum(VL_TOT_REC) AS receita_nao_tributada_cofins FROM raw_contrib_m800 GROUP BY 1),
    cp AS (SELECT arquivo_id, sum(VL_CRED) AS credito_pis_apurado FROM raw_contrib_m100 GROUP BY 1),
    cc AS (SELECT arquivo_id, sum(VL_CRED) AS credito_cofins_apurado FROM raw_contrib_m500 GROUP BY 1),
    sp AS (SELECT arquivo_id, sum(SLD_CRED_FIM) AS saldo_credito_pis FROM raw_contrib_1100 GROUP BY 1),
    sc AS (SELECT arquivo_id, sum(SLD_CRED_FIM) AS saldo_credito_cofins FROM raw_contrib_1500 GROUP BY 1)
    SELECT a.arquivo_id, a.raiz, a.cnpj AS cnpj_matriz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           p.VL_TOT_CONT_NC_PER AS pis_nc_periodo, p.VL_TOT_CRED_DESC AS pis_creditos_descontados,
           p.VL_TOT_CONT_REC AS pis_a_recolher,
           c.VL_TOT_CONT_NC_PER AS cofins_nc_periodo, c.VL_TOT_CRED_DESC AS cofins_creditos_descontados,
           c.VL_TOT_CONT_REC AS cofins_a_recolher,
           coalesce(m.receita_tributada_pis, 0) AS receita_tributada,
           coalesce(nt.receita_nao_tributada_pis, 0) AS receita_nao_tributada_pis,
           coalesce(ntc.receita_nao_tributada_cofins, 0) AS receita_nao_tributada_cofins,
           coalesce(cp.credito_pis_apurado, 0) AS credito_pis_apurado,
           coalesce(cc.credito_cofins_apurado, 0) AS credito_cofins_apurado,
           sp.saldo_credito_pis, sc.saldo_credito_cofins
    FROM arquivos a
    LEFT JOIN raw_contrib_m200 p ON p.arquivo_id = a.arquivo_id
    LEFT JOIN raw_contrib_m600 c ON c.arquivo_id = a.arquivo_id
    LEFT JOIN m ON m.arquivo_id = a.arquivo_id LEFT JOIN mc ON mc.arquivo_id = a.arquivo_id
    LEFT JOIN nt ON nt.arquivo_id = a.arquivo_id LEFT JOIN ntc ON ntc.arquivo_id = a.arquivo_id
    LEFT JOIN cp ON cp.arquivo_id = a.arquivo_id LEFT JOIN cc ON cc.arquivo_id = a.arquivo_id
    LEFT JOIN sp ON sp.arquivo_id = a.arquivo_id LEFT JOIN sc ON sc.arquivo_id = a.arquivo_id
    WHERE a.ativo AND a.tipo = 'CONTRIB'
    """),
]


# Visoes pesadas viram TABELAS (materializadas) apos a carga/alteracao de parametros:
# as telas leem tabelas prontas em vez de recalcular a cadeia de visoes a cada clique.
MATERIALIZAR = ["v_estabelecimentos", "v_participantes", "v_participantes_contrib", "v_docs", "v_doc_par",
                "v_saidas_doc", "v_saidas_item", "v_saidas_dest", "v_entradas_linhas", "v_entradas_pc",
                "v_entradas_item",
                "v_entradas_servicos", "v_base_operacoes", "v_cenarios"]
VERSAO_CODIGO = "8"  # mudar quando o SQL das visoes mudar (forca reconstrucao)


def criar(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela de UFs, as tabelas de parametros e as visoes (sem materializar)."""
    con.execute("CREATE TABLE IF NOT EXISTS ref_uf (cod VARCHAR, uf VARCHAR, regiao VARCHAR)")
    if con.execute("SELECT count(*) FROM ref_uf").fetchall()[0][0] == 0:
        con.executemany("INSERT INTO ref_uf VALUES (?, ?, ?)",
                        [[k, v[0], v[1]] for k, v in UFS.items()])
    params.criar_tabelas_vazias(con)
    _remover(con, [n for n, _ in VIEWS])
    for nome, sql in VIEWS:
        con.execute(f"CREATE VIEW {nome} AS {sql}")


def _remover(con: duckdb.DuckDBPyConnection, nomes: list[str]) -> None:
    tipos = dict(con.execute("""SELECT table_name, table_type FROM information_schema.tables
                                WHERE table_schema = 'main'""").fetchall())
    for n in nomes:
        t = tipos.get(n)
        if t == "VIEW":
            con.execute(f"DROP VIEW {n}")
        elif t:
            con.execute(f"DROP TABLE {n}")


def _materializar(con: duckdb.DuckDBPyConnection) -> None:
    for nome in MATERIALIZAR:
        con.execute("DROP TABLE IF EXISTS _tmp_mat")
        con.execute(f"CREATE TABLE _tmp_mat AS SELECT * FROM {nome}")
        con.execute(f"DROP VIEW {nome}")
        con.execute(f"ALTER TABLE _tmp_mat RENAME TO {nome}")


def versao_dados(con: duckdb.DuckDBPyConnection) -> str:
    """Muda quando arquivos sao carregados/substituidos/apagados ou um parametro e salvo."""
    import hashlib
    a = con.execute("""SELECT count(*), coalesce(max(arquivo_id), 0),
                              coalesce(sum(arquivo_id) FILTER (WHERE ativo), 0) FROM arquivos""").fetchall()[0]
    h = hashlib.sha256()
    for p in sorted(params.pasta_params().glob("*.csv")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return f"{VERSAO_CODIGO}|{a[0]}|{a[1]}|{a[2]}|{h.hexdigest()[:16]}"


def _estado_ok(con: duckdb.DuckDBPyConnection) -> bool:
    nomes = {r[0] for r in con.execute("""SELECT table_name FROM information_schema.tables
                                           WHERE table_schema = 'main'""").fetchall()}
    if "_meta" not in nomes or any(n not in nomes for n, _ in VIEWS):
        return False
    return params.esquema_ok(con)


def preparar(con: duckdb.DuckDBPyConnection, forcar: bool = False) -> bool:
    """Sincroniza parametros, recria as visoes e materializa as pesadas, SO se os dados ou os
    parametros mudaram desde a ultima vez. Retorna True se reconstruiu."""
    con.execute("CREATE TABLE IF NOT EXISTS _meta (chave VARCHAR PRIMARY KEY, valor VARCHAR)")
    v = versao_dados(con)
    if not forcar and _estado_ok(con):
        r = con.execute("SELECT valor FROM _meta WHERE chave = 'versao'").fetchall()
        if r and r[0][0] == v:
            return False
    criar(con)
    params.sincronizar(con)
    _materializar(con)
    v = versao_dados(con)  # sincronizar pode ter criado CSV a partir dos modelos
    con.execute("INSERT OR REPLACE INTO _meta VALUES ('versao', ?)", [v])
    return True
