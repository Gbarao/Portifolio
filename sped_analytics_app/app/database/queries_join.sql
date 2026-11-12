-- =====================================================================================
-- MOTOR DE CONSOLIDAÇÃO FISCAL — SPED Fiscal (base mestre) LEFT JOIN EFD-Contribuições
--
-- Executado por app/database/engine.py em ordem, bloco a bloco (marcadores "-- @step").
-- Pré-requisito: tabela temporária _scope(competencia) com as competências a (re)consolidar.
-- Placeholders {{...}} são constantes de config.py (nunca entrada do usuário).
-- O bloco "-- @template alocar" é instanciado para cada nível de cruzamento por rateio.
-- =====================================================================================

-- @step dim_filial
DELETE FROM dim_filial;
INSERT INTO dim_filial
SELECT cnpj_filial, arg_max(nome, prio_comp) AS nome_filial, arg_max(uf, prio_comp) AS uf_filial,
       left(cnpj_filial, 8) AS raiz_cnpj, arg_max(fonte, prio_comp) AS fonte
FROM (
    SELECT cnpj AS cnpj_filial, nome, uf, '1|' || competencia AS prio_comp, 'SPED_FISCAL_0000' AS fonte
    FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'ICMS_IPI'
    UNION ALL
    SELECT e.cnpj, e.nome, e.uf, '0|' || a.competencia, 'EFD_CONTRIB_0140'
    FROM ec_estab e JOIN sys_arquivos_importados a ON a.id_arquivo = e.file_id AND a.ativo
    UNION ALL
    SELECT cnpj, nome, uf, '0|' || competencia, 'EFD_CONTRIB_0000'
    FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'CONTRIB'
) WHERE cnpj_filial IS NOT NULL
GROUP BY cnpj_filial;

-- @step dim_fornecedor
DELETE FROM dim_fornecedor;
INSERT INTO dim_fornecedor
WITH p AS (
    SELECT p.*, a.competencia FROM sf_part p JOIN sys_arquivos_importados a ON a.id_arquivo = p.file_id AND a.ativo
    UNION ALL BY NAME
    SELECT p.*, a.competencia FROM ec_part p JOIN sys_arquivos_importados a ON a.id_arquivo = p.file_id AND a.ativo
), k AS (
    SELECT COALESCE(NULLIF(regexp_replace(coalesce(cnpj, ''), '\D', '', 'g'), ''),
                    NULLIF(regexp_replace(coalesce(cpf, ''), '\D', '', 'g'), ''),
                    'EXT:' || upper(trim(coalesce(nome, cod_part)))) AS cnpj_cpf,
           nome, cod_mun, cod_pais, competencia
    FROM p
)
SELECT k.cnpj_cpf, arg_max(k.nome, k.competencia),
       arg_max(CASE WHEN coalesce(k.cod_pais, '1058') NOT IN ('1058', '01058', '') THEN 'EX' ELSE u.uf END, k.competencia),
       arg_max(k.cod_pais, k.competencia), max(k.competencia)
FROM k LEFT JOIN ref_uf_ibge u ON u.cod = left(k.cod_mun, 2)
GROUP BY k.cnpj_cpf;

-- @step dim_item_depara
DELETE FROM dim_item_depara;
INSERT INTO dim_item_depara
WITH src AS (
    SELECT a.cnpj AS cnpj_filial, h.cod_ant_item AS cod_ant, h.cod_item AS cod_atual, a.competencia
    FROM sf_item_hist h JOIN sys_arquivos_importados a ON a.id_arquivo = h.file_id AND a.ativo
    UNION ALL
    SELECT a.cnpj, c.cod_ant_item, c.cod_item, a.competencia
    FROM sf_item_cad c JOIN sys_arquivos_importados a ON a.id_arquivo = c.file_id AND a.ativo
    UNION ALL
    SELECT h.cnpj_filial, h.cod_ant_item, h.cod_item, a.competencia
    FROM ec_item_hist h JOIN sys_arquivos_importados a ON a.id_arquivo = h.file_id AND a.ativo
)
SELECT DISTINCT ON (cnpj_filial, cod_ant) cnpj_filial, cod_ant, cod_atual, competencia
FROM src
WHERE cod_ant IS NOT NULL AND cod_atual IS NOT NULL AND cod_ant <> cod_atual
ORDER BY cnpj_filial, cod_ant, competencia DESC;

-- @step t_doc
-- Documentos de entrada do SPED Fiscal (C100/C500/D100/D500/D700) no escopo, com fornecedor unificado
CREATE OR REPLACE TEMP TABLE t_doc AS
WITH part AS (
    SELECT DISTINCT ON (file_id, cod_part) * FROM sf_part ORDER BY file_id, cod_part
), d0 AS (
    SELECT a.competencia, a.cnpj AS cnpj_filial, d.*,
           COALESCE(NULLIF(regexp_replace(coalesce(p.cnpj, ''), '\D', '', 'g'), ''),
                    NULLIF(regexp_replace(coalesce(p.cpf, ''), '\D', '', 'g'), ''),
                    CASE WHEN p.cod_part IS NOT NULL THEN 'EXT:' || upper(trim(coalesce(p.nome, p.cod_part))) END,
                    'PART:' || coalesce(d.cod_part, '?')) AS cnpj_cpf_forn,
           p.nome AS nome_part
    FROM sf_doc d
    JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo AND a.tipo_sped = 'ICMS_IPI'
    JOIN _scope s ON s.competencia = a.competencia
    LEFT JOIN part p ON p.file_id = d.file_id AND p.cod_part = d.cod_part
    WHERE coalesce(d.cod_sit, '00') NOT IN ({{COD_SIT_EXCL}})
), hist AS (   -- 0175: nome vigente na data do documento (alteração posterior à data => vale o conteúdo anterior)
    SELECT d0.file_id, d0.doc_id, arg_min(h.cont_ant, h.dt_alt) AS nome_ant
    FROM d0 JOIN sf_part_hist h
      ON h.file_id = d0.file_id AND h.cod_part = d0.cod_part AND ltrim(h.nr_campo, '0') = '3'
     AND h.dt_alt > coalesce(d0.dt_e_s, d0.dt_doc)
    GROUP BY d0.file_id, d0.doc_id
)
SELECT d0.*, coalesce(hist.nome_ant, d0.nome_part) AS nome_part_na_data
FROM d0 LEFT JOIN hist ON hist.file_id = d0.file_id AND hist.doc_id = d0.doc_id;

-- @step t_ec_doc
-- Documentos da EFD-Contribuições ativos (todas as competências: a nota pode ser escriturada em outro período)
CREATE OR REPLACE TEMP TABLE t_ec_doc AS
WITH part AS (
    SELECT DISTINCT ON (file_id, cnpj_filial, cod_part) * FROM ec_part ORDER BY file_id, cnpj_filial, cod_part
), part_any AS (
    SELECT DISTINCT ON (file_id, cod_part) * FROM ec_part ORDER BY file_id, cod_part
)
SELECT a.competencia, d.*,
       COALESCE(NULLIF(regexp_replace(coalesce(p.cnpj, pa.cnpj, ''), '\D', '', 'g'), ''),
                NULLIF(regexp_replace(coalesce(p.cpf, pa.cpf, ''), '\D', '', 'g'), ''),
                CASE WHEN coalesce(p.cod_part, pa.cod_part) IS NOT NULL
                     THEN 'EXT:' || upper(trim(coalesce(p.nome, pa.nome, d.cod_part))) END,
                'PART:' || coalesce(d.cod_part, '?')) AS cnpj_cpf_forn,
       ltrim(coalesce(d.num_doc, ''), '0') AS nd, ltrim(coalesce(d.ser, ''), '0') AS sr
FROM ec_doc d
JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo AND a.tipo_sped = 'CONTRIB'
LEFT JOIN part p ON p.file_id = d.file_id AND p.cnpj_filial = d.cnpj_filial AND p.cod_part = d.cod_part
LEFT JOIN part_any pa ON pa.file_id = d.file_id AND pa.cod_part = d.cod_part
WHERE coalesce(d.cod_sit, '00') NOT IN ({{COD_SIT_EXCL}});

CREATE OR REPLACE TEMP TABLE t_ec_c100 AS
SELECT DISTINCT ON (cnpj_filial, chave) file_id AS ec_file_id, doc_id AS ec_doc_id, cnpj_filial, chave, competencia
FROM t_ec_doc WHERE reg = 'C100' AND chave IS NOT NULL
ORDER BY cnpj_filial, chave, competencia DESC, file_id DESC;

-- @step t_item
-- Itens candidatos das NF (C100): C170 do SPED Fiscal; na ausência (Exceção 2 — emissão própria),
-- C170 da EFD-Contribuições localizado pela chave da NF-e.
CREATE OR REPLACE TEMP TABLE t_item AS
SELECT i.file_id, i.doc_id, 'SF_C170' AS origem, i.num_item, i.cod_item, i.descr_compl, i.qtd, i.unid,
       i.vl_item, i.vl_desc, i.cst_icms, i.cfop, i.cod_nat, i.aliq_icms, i.vl_bc_icms, i.vl_icms,
       i.vl_bc_icms_st, i.vl_icms_st, i.cst_ipi, i.aliq_ipi, i.vl_bc_ipi, i.vl_ipi, i.cod_cta
FROM t_doc d JOIN sf_c170 i ON i.file_id = d.file_id AND i.doc_id = d.doc_id
WHERE d.reg = 'C100'
UNION ALL BY NAME
SELECT d.file_id, d.doc_id, 'EC_C170_VIA_CHAVE' AS origem, e.num_item, e.cod_item, e.descr_compl, e.qtd, e.unid,
       e.vl_item, e.vl_desc, e.cst_icms, e.cfop, NULL AS cod_nat, e.aliq_icms, e.vl_bc_icms, e.vl_icms,
       NULL AS vl_bc_icms_st, e.vl_icms_st, NULL AS cst_ipi, NULL AS aliq_ipi, NULL AS vl_bc_ipi, e.vl_ipi, e.cod_cta,
       ec.ec_file_id, ec.ec_doc_id, e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis,
       e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins
FROM t_doc d
JOIN t_ec_c100 ec ON ec.cnpj_filial = d.cnpj_filial AND ec.chave = d.chave
JOIN ec_item e ON e.file_id = ec.ec_file_id AND e.doc_id = ec.ec_doc_id AND e.reg = 'C170'
WHERE d.reg = 'C100'
  AND NOT EXISTS (SELECT 1 FROM sf_c170 x WHERE x.file_id = d.file_id AND x.doc_id = d.doc_id);

-- @step t_anal_k
-- Registros analíticos (C190/C590/D190/D590/D730) agregados por CST+CFOP+alíquota, com FCP do C191
CREATE OR REPLACE TEMP TABLE t_anal_k AS
WITH fcp AS (
    SELECT file_id, anal_id, sum(vl_fcp_op) AS fcp_op, sum(vl_fcp_st) AS fcp_st FROM sf_c191 GROUP BY ALL
)
SELECT a.file_id, a.doc_id, a.reg,
       coalesce(a.cst_icms, '') AS cst_k, coalesce(a.cfop, '') AS cfop_k, round(coalesce(a.aliq_icms, 0), 2) AS aliq_k,
       min(a.anal_id) AS anal_id, max(a.cst_icms) AS cst_icms, max(a.cfop) AS cfop, max(a.aliq_icms) AS aliq_icms,
       sum(a.vl_opr) AS vl_opr, sum(a.vl_bc_icms) AS vl_bc_icms, sum(a.vl_icms) AS vl_icms,
       sum(a.vl_bc_icms_st) AS vl_bc_icms_st, sum(a.vl_icms_st) AS vl_icms_st, sum(a.vl_ipi) AS vl_ipi,
       sum(f.fcp_op) AS fcp_op, sum(f.fcp_st) AS fcp_st
FROM sf_anal a
JOIN t_doc d ON d.file_id = a.file_id AND d.doc_id = a.doc_id
LEFT JOIN fcp f ON f.file_id = a.file_id AND f.anal_id = a.anal_id
GROUP BY a.file_id, a.doc_id, a.reg, cst_k, cfop_k, aliq_k;

-- @step t_item_r
-- Rateio: diferença entre VL_OPR (C190) e a soma dos itens (VL_ITEM - VL_DESC + ST + IPI) é distribuída
-- proporcionalmente ao VL_ITEM; o resíduo de arredondamento vai ao maior item => soma fecha 100% com o C190.
CREATE OR REPLACE TEMP TABLE t_item_r AS
WITH b AS (
    SELECT i.*, coalesce(i.cst_icms, '') AS cst_k, coalesce(i.cfop, '') AS cfop_k,
           round(coalesce(i.aliq_icms, 0), 2) AS aliq_k,
           CAST(coalesce(i.vl_item, 0) - coalesce(i.vl_desc, 0) + coalesce(i.vl_icms_st, 0) + coalesce(i.vl_ipi, 0)
                AS DECIMAL(18,2)) AS base,
           abs(coalesce(i.vl_item, 0)) AS w
    FROM t_item i
), g AS (
    SELECT b.*, a.anal_id, a.vl_opr, a.fcp_op, a.fcp_st,
           sum(b.base) OVER k AS sum_base, sum(b.w) OVER k AS sum_w, count(*) OVER k AS n_k,
           row_number() OVER (PARTITION BY b.file_id, b.doc_id, b.cst_k, b.cfop_k, b.aliq_k
                              ORDER BY b.w DESC, b.num_item) AS rn
    FROM b
    LEFT JOIN t_anal_k a ON a.reg = 'C190' AND a.file_id = b.file_id AND a.doc_id = b.doc_id
                        AND a.cst_k = b.cst_k AND a.cfop_k = b.cfop_k AND a.aliq_k = b.aliq_k
    WINDOW k AS (PARTITION BY b.file_id, b.doc_id, b.cst_k, b.cfop_k, b.aliq_k)
), s AS (
    SELECT g.*, CASE WHEN sum_w > 0 THEN w / sum_w ELSE 1.0 / n_k END AS share,
           CAST(coalesce(vl_opr, 0) - sum_base AS DECIMAL(18,2)) AS diff
    FROM g
), r AS (
    SELECT s.*,
           CAST(round(diff * share, 2) AS DECIMAL(18,2)) AS a_diff,
           CAST(round(coalesce(fcp_op, 0) * share, 2) AS DECIMAL(18,2)) AS a_fcp,
           CAST(round(coalesce(fcp_st, 0) * share, 2) AS DECIMAL(18,2)) AS a_fcpst
    FROM s
)
SELECT r.*,
       CASE WHEN anal_id IS NULL THEN 0
            ELSE a_diff + CASE WHEN rn = 1 THEN diff - sum(a_diff) OVER k2 ELSE 0 END END AS vl_rateio,
       CASE WHEN anal_id IS NULL OR fcp_op IS NULL THEN NULL
            ELSE a_fcp + CASE WHEN rn = 1 THEN fcp_op - sum(a_fcp) OVER k2 ELSE 0 END END AS vl_fcp,
       CASE WHEN anal_id IS NULL OR fcp_st IS NULL THEN NULL
            ELSE a_fcpst + CASE WHEN rn = 1 THEN fcp_st - sum(a_fcpst) OVER k2 ELSE 0 END END AS vl_fcp_st
FROM r
WINDOW k2 AS (PARTITION BY file_id, doc_id, cst_k, cfop_k, aliq_k);

-- @step t_lin
-- Linhas do SPED Fiscal: itens rateados + itens sintéticos (C190 sem item, energia, água, gás, telecom, frete)
CREATE OR REPLACE TEMP TABLE t_lin AS
SELECT row_number() OVER () AS lid, u.* FROM (
    SELECT d.competencia, d.cnpj_filial, d.file_id, d.doc_id, d.reg AS reg_doc, d.cod_part, d.cnpj_cpf_forn,
           d.nome_part_na_data, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
           r.origem, r.num_item, r.cod_item, r.descr_compl, r.qtd, r.unid, r.vl_item, r.vl_desc,
           r.vl_rateio AS vl_rateio_c190, r.base + r.vl_rateio AS vl_contabil,
           r.cst_icms, r.cfop, r.cod_nat, r.aliq_icms, r.vl_bc_icms, r.vl_icms, r.vl_bc_icms_st, r.vl_icms_st,
           r.vl_fcp, r.vl_fcp_st, r.cst_ipi, r.aliq_ipi, r.vl_bc_ipi, r.vl_ipi, r.cod_cta,
           r.ec_file_id, r.ec_doc_id, r.cst_pis, r.aliq_pis, r.vl_bc_pis, r.vl_pis,
           r.cst_cofins, r.aliq_cofins, r.vl_bc_cofins, r.vl_cofins, NULL::VARCHAR AS nat_bc_cred,
           FALSE AS flag_item_sintetico, r.anal_id IS NULL AS flag_sem_c190
    FROM t_item_r r JOIN t_doc d ON d.file_id = r.file_id AND d.doc_id = r.doc_id
    UNION ALL BY NAME
    SELECT d.competencia, d.cnpj_filial, d.file_id, d.doc_id, d.reg AS reg_doc, d.cod_part, d.cnpj_cpf_forn,
           d.nome_part_na_data, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
           'SF_' || a.reg || '_SINTETICO' AS origem, NULL::BIGINT AS num_item,
           CASE WHEN a.reg = 'C190' THEN '{{ITEM_SINT_C190}}'
                ELSE coalesce(m.cod_item, '_SERVICO_' || d.reg || '_') END AS cod_item,
           CAST(a.vl_opr AS DECIMAL(18,2)) AS vl_item, 0 AS vl_desc, 0 AS vl_rateio_c190,
           CAST(a.vl_opr AS DECIMAL(18,2)) AS vl_contabil,
           a.cst_icms, a.cfop, a.aliq_icms, a.vl_bc_icms, a.vl_icms, a.vl_bc_icms_st, a.vl_icms_st,
           a.fcp_op AS vl_fcp, a.fcp_st AS vl_fcp_st, a.vl_ipi,
           TRUE AS flag_item_sintetico, FALSE AS flag_sem_c190
    FROM t_anal_k a
    JOIN t_doc d ON d.file_id = a.file_id AND d.doc_id = a.doc_id
    LEFT JOIN ref_item_sintetico m ON m.cod_mod = d.cod_mod
    WHERE a.reg <> 'C190'
       OR NOT EXISTS (SELECT 1 FROM t_item_r r
                      WHERE r.file_id = a.file_id AND r.doc_id = a.doc_id AND r.anal_id = a.anal_id)
) u;

-- @step n0_n1
-- N0: itens vindos do C170 da EFD-Contribuições (já trazem PIS/COFINS próprios)
-- N1: item a item — CNPJ_Filial + CHV_NFE + NUM_ITEM
CREATE OR REPLACE TEMP TABLE t_ec_it AS
SELECT ec.cnpj_filial, ec.chave, e.file_id AS ec_file_id, e.doc_id AS ec_doc_id, e.num_item, e.cod_item, e.cfop,
       e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis, e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins,
       row_number() OVER (PARTITION BY e.file_id, e.doc_id, e.num_item ORDER BY e.cod_item) AS dup
FROM t_ec_c100 ec
JOIN ec_item e ON e.file_id = ec.ec_file_id AND e.doc_id = ec.ec_doc_id AND e.reg = 'C170';

CREATE OR REPLACE TEMP TABLE t_pc AS
SELECT lid, 'N1_ITEM' AS nivel, ec_file_id, ec_doc_id, NULL::BIGINT AS ec_num_item,
       cst_pis, aliq_pis, vl_bc_pis, vl_pis, cst_cofins, aliq_cofins, vl_bc_cofins, vl_cofins, NULL::VARCHAR AS nat_bc_cred
FROM t_lin WHERE origem = 'EC_C170_VIA_CHAVE'
UNION ALL
SELECT l.lid, 'N1_ITEM', e.ec_file_id, e.ec_doc_id, e.num_item,
       e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis, e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins, NULL
FROM t_lin l
JOIN t_ec_it e ON e.cnpj_filial = l.cnpj_filial AND e.chave = l.chave AND e.num_item = l.num_item AND e.dup = 1
WHERE l.origem = 'SF_C170';

-- @step pool_n2
-- N2: agrupamento dentro da nota — CNPJ_Filial + CHV_NFE + COD_ITEM + CFOP (itens EFD não usados no N1)
CREATE OR REPLACE TEMP TABLE t_pool_N2 AS
SELECT row_number() OVER () AS pool_id, 'N2_ITEM_CFOP' AS nivel, e.cnpj_filial, e.chave, e.cod_item, e.cfop,
       min(e.ec_file_id) AS ec_file_id, min(e.ec_doc_id) AS ec_doc_id,
       arg_max(e.cst_pis, coalesce(e.vl_bc_pis, 0)) AS cst_pis, arg_max(e.aliq_pis, coalesce(e.vl_bc_pis, 0)) AS aliq_pis,
       sum(e.vl_bc_pis) AS vl_bc_pis, sum(e.vl_pis) AS vl_pis,
       arg_max(e.cst_cofins, coalesce(e.vl_bc_cofins, 0)) AS cst_cofins,
       arg_max(e.aliq_cofins, coalesce(e.vl_bc_cofins, 0)) AS aliq_cofins,
       sum(e.vl_bc_cofins) AS vl_bc_cofins, sum(e.vl_cofins) AS vl_cofins, NULL::VARCHAR AS nat_bc_cred
FROM t_ec_it e
WHERE NOT (e.dup = 1 AND EXISTS (SELECT 1 FROM t_pc p WHERE p.ec_file_id = e.ec_file_id
                                 AND p.ec_doc_id = e.ec_doc_id AND p.ec_num_item = e.num_item))
GROUP BY e.cnpj_filial, e.chave, e.cod_item, e.cfop;

CREATE OR REPLACE TEMP TABLE t_cand_N2 AS
SELECT l.lid, abs(coalesce(l.vl_item, 0)) AS w, l.cnpj_filial, l.chave, l.cod_item, l.cfop
FROM t_lin l
WHERE l.origem = 'SF_C170' AND NOT EXISTS (SELECT 1 FROM t_pc p WHERE p.lid = l.lid);

-- @alloc N2: c.cnpj_filial = p.cnpj_filial AND c.chave = p.chave AND c.cod_item = p.cod_item AND c.cfop = p.cfop

-- @step pool_n3
-- N3: escrituração consolidada (C190 + C191/C195) — CNPJ_Filial + Período + CNPJ Fornecedor + CFOP + COD_ITEM
CREATE OR REPLACE TEMP TABLE t_pool_N3 AS
SELECT row_number() OVER () AS pool_id, 'N3_CONSOLIDADO_C190' AS nivel, c.cnpj_filial, a.competencia,
       regexp_replace(coalesce(x.cnpj_cpf_part, ''), '\D', '', 'g') AS cnpj_cpf_forn, x.cfop, c.cod_item,
       min(c.file_id) AS ec_file_id, NULL::BIGINT AS ec_doc_id,
       arg_max(x.cst, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'PIS') AS cst_pis,
       arg_max(x.aliq, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'PIS') AS aliq_pis,
       sum(x.vl_bc) FILTER (WHERE x.tributo = 'PIS') AS vl_bc_pis,
       sum(x.vl) FILTER (WHERE x.tributo = 'PIS') AS vl_pis,
       arg_max(x.cst, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'COFINS') AS cst_cofins,
       arg_max(x.aliq, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'COFINS') AS aliq_cofins,
       sum(x.vl_bc) FILTER (WHERE x.tributo = 'COFINS') AS vl_bc_cofins,
       sum(x.vl) FILTER (WHERE x.tributo = 'COFINS') AS vl_cofins,
       NULL::VARCHAR AS nat_bc_cred
FROM ec_c190 c
JOIN sys_arquivos_importados a ON a.id_arquivo = c.file_id AND a.ativo
JOIN _scope s ON s.competencia = a.competencia
JOIN ec_c191_195 x ON x.file_id = c.file_id AND x.c190_id = c.c190_id
GROUP BY c.cnpj_filial, a.competencia, regexp_replace(coalesce(x.cnpj_cpf_part, ''), '\D', '', 'g'), x.cfop, c.cod_item;

CREATE OR REPLACE TEMP TABLE t_cand_N3 AS
SELECT l.lid, abs(coalesce(l.vl_item, 0)) AS w, l.cnpj_filial, l.competencia, l.cnpj_cpf_forn, l.cfop, l.cod_item
FROM t_lin l
WHERE l.reg_doc = 'C100'
  AND NOT EXISTS (SELECT 1 FROM t_pc p WHERE p.lid = l.lid)
  AND NOT EXISTS (SELECT 1 FROM t_alloc_N2 p WHERE p.lid = l.lid);

-- @alloc N3: c.cnpj_filial = p.cnpj_filial AND c.competencia = p.competencia AND c.cnpj_cpf_forn = p.cnpj_cpf_forn AND c.cfop = p.cfop AND c.cod_item = p.cod_item

-- @step pool_doc
-- Energia/água/gás (C500), frete CT-e (D100), telecom (D500/D700): vínculo pela chave do documento eletrônico;
-- na ausência de chave, por Filial + Fornecedor + Número + Série. PIS/COFINS dos C501/C505, D101/D105, D501/D505.
CREATE OR REPLACE TEMP TABLE t_docmatch AS
WITH sfd AS (
    SELECT file_id, doc_id, cnpj_filial, competencia, chave, cnpj_cpf_forn,
           ltrim(coalesce(num_doc, ''), '0') AS nd, ltrim(coalesce(ser, ''), '0') AS sr,
           CASE reg WHEN 'D700' THEN 'D500' ELSE reg END AS fam
    FROM t_doc WHERE reg IN ('C500', 'D100', 'D500', 'D700')
), ec1 AS (
    SELECT DISTINCT ON (cnpj_filial, reg, chave) cnpj_filial, reg, chave, file_id AS ec_file_id, doc_id AS ec_doc_id
    FROM t_ec_doc WHERE chave IS NOT NULL AND reg IN ('C500', 'D100', 'D500')
    ORDER BY cnpj_filial, reg, chave, competencia DESC, file_id DESC
), ec2 AS (
    SELECT DISTINCT ON (cnpj_filial, competencia, reg, cnpj_cpf_forn, nd, sr) cnpj_filial, competencia, reg,
           cnpj_cpf_forn, nd, sr, file_id AS ec_file_id, doc_id AS ec_doc_id
    FROM t_ec_doc WHERE reg IN ('C500', 'D100', 'D500')
    ORDER BY cnpj_filial, competencia, reg, cnpj_cpf_forn, nd, sr, file_id DESC
)
SELECT s.file_id, s.doc_id,
       coalesce(e1.ec_file_id, e2.ec_file_id) AS ec_file_id, coalesce(e1.ec_doc_id, e2.ec_doc_id) AS ec_doc_id,
       CASE WHEN e1.ec_doc_id IS NOT NULL THEN 'DOC_CHAVE' ELSE 'DOC_NUMERO' END AS nivel
FROM sfd s
LEFT JOIN ec1 e1 ON e1.cnpj_filial = s.cnpj_filial AND e1.reg = s.fam AND e1.chave = s.chave
-- sem chave: número/série/fornecedor somente na mesma competência (evita falso vínculo entre faturas mensais)
LEFT JOIN ec2 e2 ON e2.cnpj_filial = s.cnpj_filial AND e2.competencia = s.competencia AND e2.reg = s.fam
                AND e2.cnpj_cpf_forn = s.cnpj_cpf_forn
                AND e2.nd = s.nd AND e2.sr = s.sr AND s.nd <> ''
WHERE coalesce(e1.ec_doc_id, e2.ec_doc_id) IS NOT NULL;

CREATE OR REPLACE TEMP TABLE t_pool_DOC AS
WITH tr AS (
    SELECT file_id, doc_id,
           arg_max(cst, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'PIS') AS cst_pis,
           arg_max(aliq, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'PIS') AS aliq_pis,
           sum(vl_bc) FILTER (WHERE tributo = 'PIS') AS vl_bc_pis,
           sum(vl) FILTER (WHERE tributo = 'PIS') AS vl_pis,
           arg_max(cst, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'COFINS') AS cst_cofins,
           arg_max(aliq, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'COFINS') AS aliq_cofins,
           sum(vl_bc) FILTER (WHERE tributo = 'COFINS') AS vl_bc_cofins,
           sum(vl) FILTER (WHERE tributo = 'COFINS') AS vl_cofins,
           arg_max(nat_bc_cred, coalesce(vl_bc, 0)) AS nat_bc_cred
    FROM ec_doc_trib GROUP BY file_id, doc_id
)
SELECT row_number() OVER () AS pool_id, m.nivel, m.file_id, m.doc_id, m.ec_file_id, m.ec_doc_id,
       tr.cst_pis, tr.aliq_pis, tr.vl_bc_pis, tr.vl_pis, tr.cst_cofins, tr.aliq_cofins, tr.vl_bc_cofins, tr.vl_cofins,
       tr.nat_bc_cred
FROM t_docmatch m LEFT JOIN tr ON tr.file_id = m.ec_file_id AND tr.doc_id = m.ec_doc_id;

CREATE OR REPLACE TEMP TABLE t_cand_DOC AS
SELECT l.lid, abs(coalesce(l.vl_contabil, 0)) AS w, l.file_id, l.doc_id
FROM t_lin l WHERE l.reg_doc IN ('C500', 'D100', 'D500', 'D700');

-- @alloc DOC: c.file_id = p.file_id AND c.doc_id = p.doc_id

-- @template alocar
-- Rateio genérico de um "pool" de PIS/COFINS sobre as linhas candidatas com a mesma chave (proporcional ao peso,
-- resíduo de centavos no maior peso). Resultado: uma linha por lid.
CREATE OR REPLACE TEMP TABLE t_alloc_{{LEVEL}} AS
WITH j AS (
    SELECT c.lid, c.w, p.pool_id, p.nivel, p.ec_file_id, p.ec_doc_id, p.cst_pis, p.aliq_pis, p.cst_cofins,
           p.aliq_cofins, p.nat_bc_cred, p.vl_bc_pis, p.vl_pis, p.vl_bc_cofins, p.vl_cofins,
           sum(c.w) OVER (PARTITION BY p.pool_id) AS sum_w,
           count(*) OVER (PARTITION BY p.pool_id) AS n_k,
           row_number() OVER (PARTITION BY p.pool_id ORDER BY c.w DESC, c.lid) AS rn
    FROM t_cand_{{LEVEL}} c JOIN t_pool_{{LEVEL}} p ON {{JOIN}}
), s AS (
    SELECT j.*, CASE WHEN sum_w > 0 THEN w / sum_w ELSE 1.0 / n_k END AS share FROM j
), a AS (
    SELECT s.*,
           CAST(round(coalesce(vl_bc_pis, 0) * share, 2) AS DECIMAL(18,2)) AS a1,
           CAST(round(coalesce(vl_pis, 0) * share, 2) AS DECIMAL(18,2)) AS a2,
           CAST(round(coalesce(vl_bc_cofins, 0) * share, 2) AS DECIMAL(18,2)) AS a3,
           CAST(round(coalesce(vl_cofins, 0) * share, 2) AS DECIMAL(18,2)) AS a4
    FROM s
)
SELECT lid, nivel, ec_file_id, ec_doc_id, NULL::BIGINT AS ec_num_item,
       cst_pis, aliq_pis,
       a1 + CASE WHEN rn = 1 THEN coalesce(vl_bc_pis, 0) - sum(a1) OVER (PARTITION BY pool_id) ELSE 0 END AS vl_bc_pis,
       a2 + CASE WHEN rn = 1 THEN coalesce(vl_pis, 0) - sum(a2) OVER (PARTITION BY pool_id) ELSE 0 END AS vl_pis,
       cst_cofins, aliq_cofins,
       a3 + CASE WHEN rn = 1 THEN coalesce(vl_bc_cofins, 0) - sum(a3) OVER (PARTITION BY pool_id) ELSE 0 END AS vl_bc_cofins,
       a4 + CASE WHEN rn = 1 THEN coalesce(vl_cofins, 0) - sum(a4) OVER (PARTITION BY pool_id) ELSE 0 END AS vl_cofins,
       nat_bc_cred
FROM a;
-- @endtemplate

-- @step t_pc_final
CREATE OR REPLACE TEMP TABLE t_pc_all AS
SELECT lid, nivel, ec_file_id, cst_pis, aliq_pis, vl_bc_pis, vl_pis, cst_cofins, aliq_cofins, vl_bc_cofins,
       vl_cofins, nat_bc_cred FROM t_pc
UNION ALL BY NAME SELECT * EXCLUDE (ec_doc_id, ec_num_item) FROM t_alloc_N2
UNION ALL BY NAME SELECT * EXCLUDE (ec_doc_id, ec_num_item) FROM t_alloc_N3
UNION ALL BY NAME SELECT * EXCLUDE (ec_doc_id, ec_num_item) FROM t_alloc_DOC;

-- @step t_lin_ec
-- Operações exclusivas da EFD-Contribuições (serviços A100/A170, F100, F120/F130) e documentos de
-- filiais/competências sem SPED Fiscal carregado (ex.: estabelecimento não contribuinte do ICMS).
CREATE OR REPLACE TEMP TABLE t_lin_ec AS
WITH sf_cov AS (
    SELECT DISTINCT cnpj, competencia FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'ICMS_IPI'
), docs AS (
    SELECT d.* FROM t_ec_doc d JOIN _scope s ON s.competencia = d.competencia
), tr AS (
    SELECT file_id, doc_id,
           arg_max(cst, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'PIS') AS cst_pis,
           arg_max(aliq, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'PIS') AS aliq_pis,
           sum(vl_bc) FILTER (WHERE tributo = 'PIS') AS vl_bc_pis, sum(vl) FILTER (WHERE tributo = 'PIS') AS vl_pis,
           arg_max(cst, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'COFINS') AS cst_cofins,
           arg_max(aliq, coalesce(vl_bc, 0)) FILTER (WHERE tributo = 'COFINS') AS aliq_cofins,
           sum(vl_bc) FILTER (WHERE tributo = 'COFINS') AS vl_bc_cofins,
           sum(vl) FILTER (WHERE tributo = 'COFINS') AS vl_cofins,
           arg_max(nat_bc_cred, coalesce(vl_bc, 0)) AS nat_bc_cred
    FROM ec_doc_trib GROUP BY file_id, doc_id
), part AS (
    SELECT DISTINCT ON (file_id, cod_part) * FROM ec_part ORDER BY file_id, cod_part
)
-- A100/A170 serviços tomados
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       'EC_A170_SERVICO' AS origem, i.num_item, i.cod_item, i.descr_compl,
       CAST(coalesce(i.vl_item, 0) - coalesce(i.vl_desc, 0) AS DECIMAL(18,2)) AS vl_contabil,
       i.vl_item, i.vl_desc, 'SERV' AS cfop, i.cod_cta, i.nat_bc_cred,
       i.cst_pis, i.aliq_pis, i.vl_bc_pis, i.vl_pis, i.cst_cofins, i.aliq_cofins, i.vl_bc_cofins, i.vl_cofins,
       FALSE AS flag_item_sintetico
FROM docs d JOIN ec_item i ON i.file_id = d.file_id AND i.doc_id = d.doc_id AND i.reg = 'A170'
WHERE d.reg = 'A100'
UNION ALL BY NAME
-- C100/C170 sem SPED Fiscal da filial na competência
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       'EC_C170_SEM_SPED_FISCAL' AS origem, i.num_item, i.cod_item, i.descr_compl, i.qtd, i.unid,
       CAST(coalesce(i.vl_item, 0) - coalesce(i.vl_desc, 0) + coalesce(i.vl_icms_st, 0) + coalesce(i.vl_ipi, 0)
            AS DECIMAL(18,2)) AS vl_contabil,
       i.vl_item, i.vl_desc, i.cfop, i.cod_cta,
       i.cst_pis, i.aliq_pis, i.vl_bc_pis, i.vl_pis, i.cst_cofins, i.aliq_cofins, i.vl_bc_cofins, i.vl_cofins,
       FALSE AS flag_item_sintetico,
       i.cst_icms, i.aliq_icms, i.vl_bc_icms, i.vl_icms, i.vl_icms_st, i.vl_ipi
FROM docs d JOIN ec_item i ON i.file_id = d.file_id AND i.doc_id = d.doc_id AND i.reg = 'C170'
WHERE d.reg = 'C100'
  AND NOT EXISTS (SELECT 1 FROM sf_cov c WHERE c.cnpj = d.cnpj_filial AND c.competencia = d.competencia)
UNION ALL BY NAME
-- C500/D100/D500 sem SPED Fiscal da filial na competência
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       'EC_' || d.reg || '_SEM_SPED_FISCAL' AS origem,
       coalesce(m.cod_item, '_SERVICO_' || d.reg || '_') AS cod_item,
       CAST(d.vl_doc AS DECIMAL(18,2)) AS vl_item, d.vl_desc, CAST(d.vl_doc AS DECIMAL(18,2)) AS vl_contabil,
       'N/D' AS cfop, tr.nat_bc_cred,
       tr.cst_pis, tr.aliq_pis, tr.vl_bc_pis, tr.vl_pis, tr.cst_cofins, tr.aliq_cofins, tr.vl_bc_cofins, tr.vl_cofins,
       TRUE AS flag_item_sintetico, d.vl_icms
FROM docs d
LEFT JOIN tr ON tr.file_id = d.file_id AND tr.doc_id = d.doc_id
LEFT JOIN ref_item_sintetico m ON m.cod_mod = d.cod_mod
WHERE d.reg IN ('C500', 'D100', 'D500')
  AND NOT EXISTS (SELECT 1 FROM sf_cov c WHERE c.cnpj = d.cnpj_filial AND c.competencia = d.competencia)
UNION ALL BY NAME
-- F100 (demais operações com crédito) e F120/F130 (ativo imobilizado: crédito sobre depreciação/aquisição)
SELECT a.competencia, f.cnpj_filial, f.file_id AS ec_file_id, f.reg AS reg_doc, f.cod_part,
       COALESCE(NULLIF(regexp_replace(coalesce(p.cnpj, ''), '\D', '', 'g'), ''),
                NULLIF(regexp_replace(coalesce(p.cpf, ''), '\D', '', 'g'), ''),
                CASE WHEN f.cod_part IS NOT NULL THEN 'PART:' || f.cod_part END) AS cnpj_cpf_forn,
       f.dt_oper AS dt_doc, f.dt_oper AS dt_e_s, 'EC_' || f.reg AS origem,
       CASE WHEN f.reg = 'F100' THEN coalesce(f.cod_item, '_OUTRAS_OPERACOES_')
            ELSE '_ATIVO_IMOB_' || coalesce(f.cod_item, '') END AS cod_item,
       f.descr AS descr_compl,
       CASE WHEN f.reg = 'F100' THEN CAST(f.vl_oper AS DECIMAL(18,2)) ELSE 0 END AS vl_item,
       CASE WHEN f.reg = 'F100' THEN CAST(f.vl_oper AS DECIMAL(18,2)) ELSE 0 END AS vl_contabil,
       'OUTROS' AS cfop, f.cod_cta, f.nat_bc_cred,
       f.cst_pis, f.aliq_pis, f.vl_bc_pis, f.vl_pis, f.cst_cofins, f.aliq_cofins, f.vl_bc_cofins, f.vl_cofins,
       f.reg <> 'F100' AS flag_item_sintetico
FROM ec_f f
JOIN sys_arquivos_importados a ON a.id_arquivo = f.file_id AND a.ativo
JOIN _scope s ON s.competencia = a.competencia
LEFT JOIN part p ON p.file_id = f.file_id AND p.cod_part = f.cod_part;

-- @step fato_delete
DELETE FROM fato_entradas_consolidadas WHERE competencia IN (SELECT competencia FROM _scope);

-- @step fato_insert_sf
INSERT INTO fato_entradas_consolidadas BY NAME
WITH cat AS (
    SELECT DISTINCT ON (file_id, cod_item) file_id, cod_item, descr_item, tipo_item, cod_ncm, cest, cod_barra, unid_inv
    FROM sf_item_cad ORDER BY file_id, cod_item
), ecat AS (
    SELECT DISTINCT ON (file_id, cnpj_filial, cod_item) file_id, cnpj_filial, cod_item, descr_item, tipo_item, cod_ncm,
           cod_barra, unid_inv
    FROM ec_item_cad ORDER BY file_id, cnpj_filial, cod_item
), x AS (
    SELECT l.*, pc.nivel, pc.ec_file_id AS pc_ec_file_id,
           coalesce(l.cst_pis, pc.cst_pis) AS f_cst_pis, coalesce(l.aliq_pis, pc.aliq_pis) AS f_aliq_pis,
           CASE WHEN l.origem = 'EC_C170_VIA_CHAVE' THEN l.vl_bc_pis ELSE pc.vl_bc_pis END AS f_vl_bc_pis,
           CASE WHEN l.origem = 'EC_C170_VIA_CHAVE' THEN l.vl_pis ELSE pc.vl_pis END AS f_vl_pis,
           coalesce(l.cst_cofins, pc.cst_cofins) AS f_cst_cofins, coalesce(l.aliq_cofins, pc.aliq_cofins) AS f_aliq_cofins,
           CASE WHEN l.origem = 'EC_C170_VIA_CHAVE' THEN l.vl_bc_cofins ELSE pc.vl_bc_cofins END AS f_vl_bc_cofins,
           CASE WHEN l.origem = 'EC_C170_VIA_CHAVE' THEN l.vl_cofins ELSE pc.vl_cofins END AS f_vl_cofins,
           pc.nat_bc_cred AS f_nat
    FROM t_lin l LEFT JOIN t_pc_all pc ON pc.lid = l.lid
)
SELECT x.competencia, x.cnpj_filial, df.nome_filial, df.uf_filial, df.raiz_cnpj AS raiz_cnpj_filial,
       x.origem, x.reg_doc, x.file_id AS file_id_sf, coalesce(x.ec_file_id, x.pc_ec_file_id) AS file_id_ec, x.doc_id,
       x.cod_part, x.cnpj_cpf_forn AS cnpj_cpf_fornecedor,
       CASE WHEN length(x.cnpj_cpf_forn) = 14 THEN left(x.cnpj_cpf_forn, 8) ELSE x.cnpj_cpf_forn END AS raiz_cnpj_fornecedor,
       coalesce(fo.razao_social, x.nome_part_na_data) AS razao_social_fornecedor, x.nome_part_na_data,
       fo.uf AS uf_fornecedor, x.cod_mod, x.cod_sit, x.ind_emit, x.ser AS serie, x.num_doc, x.chave, x.dt_doc, x.dt_e_s,
       x.num_item, x.cod_item, coalesce(dp.cod_atual, x.cod_item) AS cod_item_unificado,
       coalesce(coalesce(c.cod_ncm, ec.cod_ncm), '') || '|' || coalesce(dp.cod_atual, x.cod_item) AS chave_item_global,
       coalesce(c.descr_item, ec.descr_item, CASE WHEN x.flag_item_sintetico THEN x.cod_item END) AS descr_item,
       x.descr_compl, coalesce(c.tipo_item, ec.tipo_item) AS tipo_item, coalesce(c.cod_ncm, ec.cod_ncm) AS cod_ncm,
       c.cest, coalesce(c.cod_barra, ec.cod_barra) AS cod_barra, coalesce(x.unid, c.unid_inv, ec.unid_inv) AS unid,
       x.cfop, x.cod_nat, x.cst_icms, x.aliq_icms, x.cst_ipi, x.aliq_ipi,
       x.f_cst_pis AS cst_pis, x.f_aliq_pis AS aliq_pis, x.f_cst_cofins AS cst_cofins, x.f_aliq_cofins AS aliq_cofins,
       coalesce(x.f_nat, CASE WHEN x.f_cst_pis IN ({{CST_CRED}}) THEN coalesce(n.nat_bc_cred, '13') END) AS nat_bc_cred,
       CASE WHEN x.f_nat IS NOT NULL THEN 'INFORMADO'
            WHEN x.f_cst_pis IN ({{CST_CRED}}) THEN 'DERIVADO_CFOP' END AS nat_bc_cred_origem,
       x.cod_cta, x.qtd, x.vl_item, x.vl_desc, x.vl_rateio_c190, x.vl_contabil,
       x.vl_bc_icms, x.vl_icms, x.vl_bc_icms_st, x.vl_icms_st, x.vl_fcp, x.vl_fcp_st, x.vl_bc_ipi, x.vl_ipi,
       x.f_vl_bc_pis AS vl_bc_pis, x.f_vl_pis AS vl_pis, x.f_vl_bc_cofins AS vl_bc_cofins, x.f_vl_cofins AS vl_cofins,
       NULL AS vl_trib_recuperaveis, NULL AS vl_custo_liquido,
       x.nivel AS nivel_cruzamento_efd, x.flag_item_sintetico, x.flag_sem_c190
FROM x
LEFT JOIN dim_filial df ON df.cnpj_filial = x.cnpj_filial
LEFT JOIN dim_fornecedor fo ON fo.cnpj_cpf = x.cnpj_cpf_forn
LEFT JOIN cat c ON NOT starts_with(x.origem, 'EC_') AND c.file_id = x.file_id AND c.cod_item = x.cod_item
LEFT JOIN ecat ec ON starts_with(x.origem, 'EC_') AND ec.file_id = x.ec_file_id AND ec.cnpj_filial = x.cnpj_filial
                 AND ec.cod_item = x.cod_item
LEFT JOIN dim_item_depara dp ON dp.cnpj_filial = x.cnpj_filial AND dp.cod_ant = x.cod_item
LEFT JOIN ref_cfop_nat_bc_cred n ON n.cfop = x.cfop;

-- @step fato_insert_ec
INSERT INTO fato_entradas_consolidadas BY NAME
WITH ecat AS (
    SELECT DISTINCT ON (file_id, cnpj_filial, cod_item) file_id, cnpj_filial, cod_item, descr_item, tipo_item, cod_ncm,
           cod_barra, unid_inv
    FROM ec_item_cad ORDER BY file_id, cnpj_filial, cod_item
)
SELECT x.competencia, x.cnpj_filial, df.nome_filial, df.uf_filial, df.raiz_cnpj AS raiz_cnpj_filial,
       x.origem, x.reg_doc, x.ec_file_id AS file_id_ec, x.doc_id,
       x.cod_part, x.cnpj_cpf_forn AS cnpj_cpf_fornecedor,
       CASE WHEN length(x.cnpj_cpf_forn) = 14 THEN left(x.cnpj_cpf_forn, 8) ELSE x.cnpj_cpf_forn END AS raiz_cnpj_fornecedor,
       fo.razao_social AS razao_social_fornecedor, fo.razao_social AS nome_part_na_data, fo.uf AS uf_fornecedor,
       x.cod_mod, x.cod_sit, x.ind_emit, x.ser AS serie, x.num_doc, x.chave, x.dt_doc, x.dt_e_s,
       x.num_item, x.cod_item, coalesce(dp.cod_atual, x.cod_item) AS cod_item_unificado,
       coalesce(ec.cod_ncm, '') || '|' || coalesce(dp.cod_atual, x.cod_item) AS chave_item_global,
       coalesce(ec.descr_item, x.descr_compl, x.cod_item) AS descr_item, x.descr_compl,
       ec.tipo_item, ec.cod_ncm, ec.cod_barra, coalesce(x.unid, ec.unid_inv) AS unid,
       x.cfop, x.cst_icms, x.aliq_icms,
       x.cst_pis, x.aliq_pis, x.cst_cofins, x.aliq_cofins,
       coalesce(x.nat_bc_cred, CASE WHEN x.cst_pis IN ({{CST_CRED}}) THEN coalesce(n.nat_bc_cred, '13') END) AS nat_bc_cred,
       CASE WHEN x.nat_bc_cred IS NOT NULL THEN 'INFORMADO'
            WHEN x.cst_pis IN ({{CST_CRED}}) THEN 'DERIVADO_CFOP' END AS nat_bc_cred_origem,
       x.cod_cta, x.qtd, x.vl_item, x.vl_desc, 0 AS vl_rateio_c190, x.vl_contabil,
       x.vl_bc_icms, x.vl_icms, x.vl_icms_st, x.vl_ipi,
       x.vl_bc_pis, x.vl_pis, x.vl_bc_cofins, x.vl_cofins,
       'EC_EXCLUSIVO' AS nivel_cruzamento_efd, x.flag_item_sintetico, FALSE AS flag_sem_c190
FROM t_lin_ec x
LEFT JOIN dim_filial df ON df.cnpj_filial = x.cnpj_filial
LEFT JOIN dim_fornecedor fo ON fo.cnpj_cpf = x.cnpj_cpf_forn
LEFT JOIN ecat ec ON ec.file_id = x.ec_file_id AND ec.cnpj_filial = x.cnpj_filial AND ec.cod_item = x.cod_item
LEFT JOIN dim_item_depara dp ON dp.cnpj_filial = x.cnpj_filial AND dp.cod_ant = x.cod_item
LEFT JOIN ref_cfop_nat_bc_cred n ON n.cfop = x.cfop;

-- @step fato_metricas
UPDATE fato_entradas_consolidadas SET
    vl_trib_recuperaveis = coalesce(vl_icms, 0)
        + CASE WHEN cst_ipi IN ({{CST_IPI_CRED}}) THEN coalesce(vl_ipi, 0) ELSE 0 END
        + CASE WHEN cst_pis IN ({{CST_CRED}}) THEN coalesce(vl_pis, 0) ELSE 0 END
        + CASE WHEN cst_cofins IN ({{CST_CRED}}) THEN coalesce(vl_cofins, 0) ELSE 0 END,
    status_efd = CASE WHEN nivel_cruzamento_efd IS NULL THEN 'Sem Crédito / Não Escriturado na EFD-Contribuições'
                      WHEN nivel_cruzamento_efd = 'EC_EXCLUSIVO' THEN 'Exclusivo EFD-Contribuições'
                      ELSE 'Escriturado na EFD-Contribuições' END
WHERE competencia IN (SELECT competencia FROM _scope);

UPDATE fato_entradas_consolidadas SET vl_custo_liquido = coalesce(vl_contabil, 0) - vl_trib_recuperaveis
WHERE competencia IN (SELECT competencia FROM _scope);
