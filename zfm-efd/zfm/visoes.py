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

from . import params
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
            AND nullif(p.SUFRAMA, '') IS NOT NULL AND nullif(p.CNPJ, '') IS NOT NULL) AS eh_zfm,
           (nullif(p.CNPJ, '') IS NOT NULL AND (substr(p.CNPJ, 1, 8) IN (SELECT raiz_cnpj FROM param_empresas)
             OR substr(p.CNPJ, 1, 8) IN (SELECT raiz FROM arquivos))) AS eh_grupo
    FROM {tabela} p JOIN arquivos a USING (arquivo_id)
    LEFT JOIN ref_uf u ON u.cod = substr(p.COD_MUN, 1, 2)
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
           coalesce(p.eh_grupo, FALSE) AS eh_grupo
    FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN v_participantes p ON p.arquivo_id = d.arquivo_id AND p.cod_part = d.COD_PART
    WHERE a.ativo
    """),
    ("v_saidas_doc", """
    SELECT v.*, c.linha_num, c.CFOP AS cfop, c.CST_ICMS AS cst_icms, c.ALIQ_ICMS AS aliq_icms,
           c.VL_OPR AS vl_opr, c.VL_BC_ICMS AS vl_bc_icms_c190, c.VL_ICMS AS vl_icms_c190,
           c.VL_IPI AS vl_ipi_c190, coalesce(pc.categoria, 'outros') AS categoria_cfop,
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
               d.COD_PART AS cod_part, CAST(NULL AS VARCHAR) AS ncm_c180
        FROM raw_contrib_c170 i
        JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
        WHERE d.IND_OPER = '1' AND coalesce(d.COD_SIT, '00') NOT IN {_COD_SIT_CANCELADO}
    ),
    c181 AS (SELECT *, row_number() OVER (PARTITION BY arquivo_id, pai_linha, CFOP, VL_ITEM,
                       coalesce(VL_DESC, 0) ORDER BY linha_num) AS rn FROM raw_contrib_c181),
    c185 AS (SELECT *, row_number() OVER (PARTITION BY arquivo_id, pai_linha, CFOP, VL_ITEM,
                       coalesce(VL_DESC, 0) ORDER BY linha_num) AS rn FROM raw_contrib_c185),
    cons AS (
        SELECT coalesce(a.arquivo_id, b.arquivo_id) AS arquivo_id,
               coalesce(a.linha_num, b.linha_num) AS linha_num, 'C181/C185' AS reg_origem,
               h.cnpj_estab, h.COD_ITEM AS cod_item, coalesce(a.CFOP, b.CFOP) AS cfop,
               coalesce(a.VL_ITEM, b.VL_ITEM) AS vl_item, coalesce(a.VL_DESC, b.VL_DESC, 0) AS vl_desc,
               a.CST_PIS AS cst_pis, a.ALIQ_PIS AS aliq_pis, a.VL_PIS AS vl_pis,
               b.CST_COFINS AS cst_cofins, b.ALIQ_COFINS AS aliq_cofins, b.VL_COFINS AS vl_cofins,
               CAST(NULL AS VARCHAR) AS cst_ipi, CAST(NULL AS DECIMAL(18,2)) AS vl_icms,
               CAST(NULL AS DECIMAL(18,2)) AS vl_ipi, CAST(NULL AS VARCHAR) AS cod_part,
               h.COD_NCM AS ncm_c180
        FROM c181 a
        FULL OUTER JOIN c185 b ON a.arquivo_id = b.arquivo_id AND a.pai_linha = b.pai_linha
             AND a.CFOP = b.CFOP AND a.VL_ITEM = b.VL_ITEM
             AND coalesce(a.VL_DESC, 0) = coalesce(b.VL_DESC, 0) AND a.rn = b.rn
        JOIN raw_contrib_c180 h ON h.arquivo_id = coalesce(a.arquivo_id, b.arquivo_id)
             AND h.linha_num = coalesce(a.pai_linha, b.pai_linha)
    ),
    u AS (SELECT * FROM c170 UNION ALL BY NAME SELECT * FROM cons)
    SELECT u.arquivo_id, u.linha_num, u.reg_origem, a.raiz, u.cnpj_estab,
           year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, u.cod_item,
           coalesce(nullif(u.ncm_c180, ''), pp.ncm) AS ncm, u.cfop,
           u.vl_item, u.vl_desc, u.vl_item - u.vl_desc AS receita,
           u.cst_pis, u.aliq_pis, u.vl_pis, u.cst_cofins, u.aliq_cofins, u.vl_cofins,
           u.cst_ipi, u.vl_icms, u.vl_ipi,
           coalesce(pc.categoria, 'outros') AS categoria_cfop, coalesce(pc.eh_receita, FALSE) AS eh_receita,
           CASE WHEN u.cod_part IS NULL THEN NULL
                WHEN u.cfop LIKE '7%' OR p.exterior THEN 'exportacao'
                WHEN u.cfop LIKE '6%' THEN 'interestadual'
                WHEN p.eh_zfm THEN 'zfm_interna' ELSE 'interna' END AS tipo_operacao_exato,
           CASE WHEN u.cod_part IS NULL THEN NULL ELSE coalesce(p.eh_grupo, FALSE) END AS eh_grupo_exato,
           p.uf AS uf_dest_exato,
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
        SELECT cnpj_estab, mes, cfop, tipo_operacao, eh_grupo, uf AS uf_dest, sum(vl_opr) AS v
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
           CASE WHEN vl_icms IS NOT NULL THEN CAST(vl_icms AS DOUBLE)
                ELSE CAST(receita AS DOUBLE) * r_icms END * fator_rateio AS icms_est_r,
           (vl_icms IS NULL) AS icms_estimado
    FROM base
    """),
    ("v_entradas_item", f"""
    WITH it AS (
        SELECT i.arquivo_id, i.linha_num, 'C170' AS reg_origem, i.pai_linha AS doc_linha,
               i.COD_ITEM AS cod_item, i.CFOP AS cfop, i.VL_ITEM AS vl_item,
               coalesce(i.VL_DESC, 0) AS vl_desc, i.CST_ICMS AS cst_icms, i.VL_ICMS AS vl_icms,
               i.CST_IPI AS cst_ipi, i.VL_IPI AS vl_ipi, i.CST_PIS AS cst_pis, i.VL_PIS AS vl_pis,
               i.CST_COFINS AS cst_cofins, i.VL_COFINS AS vl_cofins
        FROM raw_icms_c170 i
        UNION ALL
        SELECT c.arquivo_id, c.linha_num, 'C190', c.pai_linha, NULL, c.CFOP,
               c.VL_OPR - coalesce(c.VL_IPI, 0) - coalesce(c.VL_ICMS_ST, 0), 0, c.CST_ICMS,
               c.VL_ICMS, NULL, c.VL_IPI, NULL, NULL, NULL, NULL
        FROM raw_icms_c190 c
        WHERE NOT EXISTS (SELECT 1 FROM raw_icms_c170 x
                          WHERE x.arquivo_id = c.arquivo_id AND x.pai_linha = c.pai_linha)
    )
    SELECT it.*, v.raiz, v.cnpj_estab, v.ano, v.mes, v.cod_part, v.nome_part, v.cnpj_part, v.chv_nfe,
           v.uf, v.regiao, v.exterior, v.eh_zfm, v.eh_grupo,
           it.vl_item - it.vl_desc AS valor,
           coalesce(pc.categoria, 'outros') AS categoria_cfop,
           CASE WHEN it.cfop LIKE '3%' OR v.exterior THEN 'importacao'
                WHEN v.eh_zfm THEN 'zfm'
                WHEN v.uf = 'AM' THEN 'am_fora_zfm'
                ELSE 'nacional_fora_zfm' END AS origem,
           CASE WHEN it.cfop LIKE '3%' OR v.exterior THEN 'Importação'
                WHEN v.eh_zfm THEN 'ZFM'
                WHEN v.uf IN {SUL_SUDESTE_EXCETO_ES} THEN 'Sul/Sudeste exceto ES'
                WHEN v.uf = 'AM' THEN 'Amazonas fora da ZFM'
                ELSE 'Norte, Nordeste, Centro-Oeste e ES' END AS regiao_origem,
           (v.uf IN {SUL_SUDESTE_EXCETO_ES}) AS sul_sudeste_exceto_es
    FROM it JOIN v_docs v ON v.arquivo_id = it.arquivo_id AND v.doc_linha = it.doc_linha
    LEFT JOIN param_cfops pc ON pc.cfop = it.cfop
    WHERE v.sentido = 'entrada' AND NOT v.cancelado AND v.uf_estab = 'AM'
    """),
    ("v_entradas_servicos", """
    SELECT a.raiz, i.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, i.arquivo_id,
           i.linha_num, 'A170' AS reg_origem, i.VL_ITEM - coalesce(i.VL_DESC, 0) AS valor
    FROM raw_contrib_a170 i JOIN raw_contrib_a100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
    JOIN arquivos a ON a.arquivo_id = i.arquivo_id
    WHERE a.ativo AND d.IND_OPER = '0'
    UNION ALL
    SELECT a.raiz, f.cnpj_estab, year(a.dt_ini), month(a.dt_ini), f.arquivo_id, f.linha_num, 'F100',
           f.VL_OPER
    FROM raw_contrib_f100 f JOIN arquivos a USING (arquivo_id)
    WHERE a.ativo AND f.IND_OPER = '0'
    """),
    ("v_ajustes_icms", """
    SELECT a.arquivo_id, a.cnpj AS cnpj_estab, a.raiz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           'E111' AS registro, e.COD_AJ_APUR AS codigo, e.DESCR_COMPL_AJ AS descricao,
           e.VL_AJ_APUR AS valor, coalesce(pc.classe, 'outros') AS classe,
           (pc.codigo IS NULL) AS nao_classificado, e.linha_num
    FROM raw_icms_e111 e JOIN arquivos a USING (arquivo_id)
    LEFT JOIN param_codigos_ajuste_icms pc ON pc.codigo = e.COD_AJ_APUR AND pc.registro = 'E111'
    WHERE a.ativo
    UNION ALL
    SELECT a.arquivo_id, a.cnpj, a.raiz, year(a.dt_ini), month(a.dt_ini), 'E116',
           coalesce(e.COD_REC, e.COD_OR), e.TXT_COMPL, e.VL_OR, coalesce(pc.classe, 'outros'),
           (pc.codigo IS NULL), e.linha_num
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


def criar(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela de UFs, as tabelas de parametros e as visoes."""
    con.execute("CREATE TABLE IF NOT EXISTS ref_uf (cod VARCHAR, uf VARCHAR, regiao VARCHAR)")
    if con.execute("SELECT count(*) FROM ref_uf").fetchall()[0][0] == 0:
        con.executemany("INSERT INTO ref_uf VALUES (?, ?, ?)",
                        [[k, v[0], v[1]] for k, v in UFS.items()])
    params.criar_tabelas_vazias(con)
    for nome, sql in VIEWS:
        con.execute(f"CREATE OR REPLACE VIEW {nome} AS {sql}")


def preparar(con: duckdb.DuckDBPyConnection) -> None:
    """Sincroniza parametros e (re)cria as visoes. Chamar antes das analises."""
    criar(con)
    params.sincronizar(con)
