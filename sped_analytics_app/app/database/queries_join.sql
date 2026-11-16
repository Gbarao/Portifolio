-- =====================================================================================
-- MOTOR DE CONSOLIDAÇÃO FISCAL — SPED Fiscal (base mestre) LEFT JOIN EFD-Contribuições
--
-- Executado por app/database/engine.py em ordem, bloco a bloco (marcadores "-- @step").
-- Pré-requisito: tabela temporária _scope(competencia) com as competências a (re)consolidar.
-- Placeholders {{...}} são constantes de config.py (nunca entrada do usuário).
-- O bloco "-- @template alocar" é instanciado para cada nível de cruzamento por rateio.
--
-- Garantias do cruzamento:
--   * vínculo de documentos 1:1 (um documento da EFD nunca alimenta dois do SPED Fiscal e vice-versa);
--   * item a item só com identidade comprovada (posição + código + valor);
--   * todo PIS/COFINS da EFD-Contribuições termina em exatamente uma linha da fato — o que não encontra
--     par no SPED Fiscal entra como linha "Somente EFD" (nada some, nada duplica).
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
           p.nome AS nome_part,
           ltrim(coalesce(d.num_doc, ''), '0') AS nd, ltrim(coalesce(d.ser, ''), '0') AS sr,
           CASE d.reg WHEN 'D700' THEN 'D500' ELSE d.reg END AS fam
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
-- Documentos da EFD-Contribuições no escopo. O escopo já vem "fechado" pelo engine: competências ligadas
-- pela chave do documento (nota escriturada em meses diferentes nos dois arquivos) são reconsolidadas juntas.
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
JOIN _scope s ON s.competencia = a.competencia
LEFT JOIN part p ON p.file_id = d.file_id AND p.cnpj_filial = d.cnpj_filial AND p.cod_part = d.cod_part
LEFT JOIN part_any pa ON pa.file_id = d.file_id AND pa.cod_part = d.cod_part
WHERE coalesce(d.cod_sit, '00') NOT IN ({{COD_SIT_EXCL}});

-- @step t_docmatch
-- Vínculo de documentos SPED Fiscal x EFD-Contribuições, estritamente 1:1.
--   1º) pela chave do documento eletrônico (CHV_NFE / CHV_CTE / CHV_DOCe), em qualquer competência do escopo;
--   2º) sem chave em um dos lados: Filial + competência + CNPJ fornecedor + modelo + série + número
--       (o k-ésimo documento de um lado casa com o k-ésimo do outro; nunca um para muitos).
CREATE OR REPLACE TEMP TABLE t_docmatch AS
WITH sfd AS (
    SELECT file_id, doc_id, cnpj_filial, competencia, fam, chave, cnpj_cpf_forn, coalesce(cod_mod, '') AS cod_mod,
           nd, sr,
           row_number() OVER (PARTITION BY cnpj_filial, fam, chave ORDER BY file_id, doc_id) AS rn_ch
    FROM t_doc
), ecd AS (
    SELECT file_id AS ec_file_id, doc_id AS ec_doc_id, cnpj_filial, competencia, reg AS fam, chave, cnpj_cpf_forn,
           coalesce(cod_mod, '') AS cod_mod, nd, sr,
           row_number() OVER (PARTITION BY cnpj_filial, reg, chave
                              ORDER BY competencia DESC, file_id DESC, doc_id) AS rn_ch
    FROM t_ec_doc WHERE reg IN ('C100', 'C500', 'D100', 'D500')
), m1 AS (
    SELECT s.file_id, s.doc_id, e.ec_file_id, e.ec_doc_id, 'CHAVE' AS via
    FROM sfd s JOIN ecd e ON e.cnpj_filial = s.cnpj_filial AND e.fam = s.fam AND e.chave = s.chave
    WHERE s.rn_ch = 1 AND e.rn_ch = 1
), s2 AS (
    SELECT s.*, row_number() OVER (PARTITION BY cnpj_filial, competencia, fam, cnpj_cpf_forn, cod_mod, nd, sr
                                   ORDER BY file_id, doc_id) AS rn2
    FROM sfd s
    WHERE s.nd <> '' AND NOT EXISTS (SELECT 1 FROM m1 WHERE m1.file_id = s.file_id AND m1.doc_id = s.doc_id)
), e2 AS (
    SELECT e.*, row_number() OVER (PARTITION BY cnpj_filial, competencia, fam, cnpj_cpf_forn, cod_mod, nd, sr
                                   ORDER BY ec_file_id, ec_doc_id) AS rn2
    FROM ecd e
    WHERE e.nd <> '' AND NOT EXISTS (SELECT 1 FROM m1 WHERE m1.ec_file_id = e.ec_file_id AND m1.ec_doc_id = e.ec_doc_id)
), m2 AS (
    SELECT s.file_id, s.doc_id, e.ec_file_id, e.ec_doc_id, 'NUMERO' AS via
    FROM s2 s JOIN e2 e
      ON e.cnpj_filial = s.cnpj_filial AND e.competencia = s.competencia AND e.fam = s.fam
     AND e.cnpj_cpf_forn = s.cnpj_cpf_forn AND e.cod_mod = s.cod_mod AND e.nd = s.nd AND e.sr = s.sr AND e.rn2 = s.rn2
    WHERE s.chave IS NULL OR e.chave IS NULL
)
SELECT * FROM m1 UNION ALL SELECT * FROM m2;

-- @step t_ec_it
-- Itens C170 da EFD-Contribuições (entradas do escopo), cada um com identificador próprio (eid) e o documento
-- do SPED Fiscal vinculado (quando houver). O eid permite provar que cada item foi consumido no máximo uma vez.
CREATE OR REPLACE TEMP TABLE t_ec_it AS
SELECT row_number() OVER () AS eid, e.file_id AS ec_file_id, e.doc_id AS ec_doc_id,
       m.file_id AS sf_file_id, m.doc_id AS sf_doc_id,
       e.num_item, e.cod_item, e.descr_compl, e.qtd, e.unid, e.vl_item, e.vl_desc, e.cst_icms, e.cfop, e.aliq_icms,
       e.vl_bc_icms, e.vl_icms, e.vl_icms_st, e.vl_ipi, e.cod_cta,
       e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis, e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins,
       row_number() OVER (PARTITION BY e.file_id, e.doc_id, e.num_item ORDER BY e.cod_item) AS dup
FROM t_ec_doc d
JOIN ec_item e ON e.file_id = d.file_id AND e.doc_id = d.doc_id AND e.reg = 'C170'
LEFT JOIN t_docmatch m ON m.ec_file_id = d.file_id AND m.ec_doc_id = d.doc_id
WHERE d.reg = 'C100';

-- @step t_item
-- Itens candidatos das NF (C100): C170 do SPED Fiscal; na ausência (Exceção 2 — emissão própria),
-- C170 da EFD-Contribuições do documento vinculado.
CREATE OR REPLACE TEMP TABLE t_item AS
SELECT i.file_id, i.doc_id, 'SF_C170' AS origem, i.num_item, i.cod_item, i.descr_compl, i.qtd, i.unid,
       i.vl_item, i.vl_desc, i.cst_icms, i.cfop, i.cod_nat, i.aliq_icms, i.vl_bc_icms, i.vl_icms,
       i.vl_bc_icms_st, i.vl_icms_st, i.cst_ipi, i.aliq_ipi, i.vl_bc_ipi, i.vl_ipi, i.cod_cta
FROM t_doc d JOIN sf_c170 i ON i.file_id = d.file_id AND i.doc_id = d.doc_id
WHERE d.reg = 'C100'
UNION ALL BY NAME
SELECT e.sf_file_id AS file_id, e.sf_doc_id AS doc_id, 'EC_C170_VIA_CHAVE' AS origem, e.num_item, e.cod_item,
       e.descr_compl, e.qtd, e.unid, e.vl_item, e.vl_desc, e.cst_icms, e.cfop, NULL AS cod_nat, e.aliq_icms,
       e.vl_bc_icms, e.vl_icms, NULL AS vl_bc_icms_st, e.vl_icms_st, NULL AS cst_ipi, NULL AS aliq_ipi,
       NULL AS vl_bc_ipi, e.vl_ipi, e.cod_cta, e.eid, e.ec_file_id
FROM t_ec_it e
WHERE e.sf_file_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM sf_c170 x WHERE x.file_id = e.sf_file_id AND x.doc_id = e.sf_doc_id);

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
           r.eid, r.ec_file_id,
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

-- @step n1
-- Cruzamento item a item dentro do documento vinculado (cada item da EFD usado no máximo uma vez):
--   N1_ITEM            posição (NUM_ITEM) + mesmo COD_ITEM + mesmo VL_ITEM  -> identidade comprovada
--   N1V_POSICAO_VALOR  posição + mesmo VL_ITEM + mesmo CFOP, com código de item diferente entre os arquivos
-- Itens vindos do próprio C170 da EFD (Exceção 2) já carregam seu PIS/COFINS (N1_ITEM).
-- Quem não passa aqui segue para o N2 (COD_ITEM + CFOP) — nunca recebe o crédito de outro item por posição.
CREATE OR REPLACE TEMP TABLE t_pc AS
WITH sfl AS (
    SELECT l.lid, l.file_id, l.doc_id, l.num_item, l.cod_item, l.cfop, l.vl_item,
           row_number() OVER (PARTITION BY l.file_id, l.doc_id, l.num_item ORDER BY l.lid) AS rn
    FROM t_lin l WHERE l.origem = 'SF_C170'
), cand AS (
    SELECT s.lid, e.eid,
           CASE WHEN e.cod_item = s.cod_item THEN 'N1_ITEM'
                WHEN coalesce(e.cfop, '') = coalesce(s.cfop, '') AND coalesce(s.vl_item, 0) <> 0
                THEN 'N1V_POSICAO_VALOR' END AS nivel
    FROM sfl s
    JOIN t_ec_it e ON e.sf_file_id = s.file_id AND e.sf_doc_id = s.doc_id AND e.num_item = s.num_item
    WHERE s.rn = 1 AND e.dup = 1
      AND abs(coalesce(e.vl_item, 0) - coalesce(s.vl_item, 0)) <= {{TOL_ITEM}}
), m AS (
    SELECT lid, eid, 'N1_ITEM' AS nivel FROM t_lin WHERE origem = 'EC_C170_VIA_CHAVE'
    UNION ALL
    SELECT lid, eid, nivel FROM cand WHERE nivel IS NOT NULL
)
SELECT m.lid, m.nivel, m.eid, e.ec_file_id, e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis,
       e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins, NULL::VARCHAR AS nat_bc_cred
FROM m JOIN t_ec_it e ON e.eid = m.eid;

-- @step pool_n2
-- N2: dentro do documento vinculado, por COD_ITEM + CFOP. Os itens da EFD ainda não consumidos formam um
-- "pool" por chave, rateado entre as linhas do SPED Fiscal da mesma chave (proporcional ao VL_ITEM).
CREATE OR REPLACE TEMP TABLE t_ec_rest AS
SELECT e.*, dense_rank() OVER (ORDER BY e.sf_file_id, e.sf_doc_id, e.cod_item, e.cfop) AS pool_id
FROM t_ec_it e
WHERE e.sf_file_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM t_pc p WHERE p.eid = e.eid);

CREATE OR REPLACE TEMP TABLE t_pool_N2 AS
SELECT pool_id, 'N2_ITEM_CFOP' AS nivel, any_value(sf_file_id) AS file_id, any_value(sf_doc_id) AS doc_id,
       any_value(cod_item) AS cod_item, any_value(cfop) AS cfop, min(ec_file_id) AS ec_file_id,
       arg_max(cst_pis, coalesce(vl_bc_pis, 0)) AS cst_pis, arg_max(aliq_pis, coalesce(vl_bc_pis, 0)) AS aliq_pis,
       sum(vl_bc_pis) AS vl_bc_pis, sum(vl_pis) AS vl_pis,
       arg_max(cst_cofins, coalesce(vl_bc_cofins, 0)) AS cst_cofins,
       arg_max(aliq_cofins, coalesce(vl_bc_cofins, 0)) AS aliq_cofins,
       sum(vl_bc_cofins) AS vl_bc_cofins, sum(vl_cofins) AS vl_cofins, NULL::VARCHAR AS nat_bc_cred
FROM t_ec_rest GROUP BY pool_id;

CREATE OR REPLACE TEMP TABLE t_cand_N2 AS
SELECT l.lid, abs(coalesce(l.vl_item, 0)) AS w, l.file_id, l.doc_id, l.cod_item, l.cfop
FROM t_lin l
WHERE l.origem = 'SF_C170' AND NOT EXISTS (SELECT 1 FROM t_pc p WHERE p.lid = l.lid);

-- @alloc N2: c.file_id = p.file_id AND c.doc_id = p.doc_id AND c.cod_item = p.cod_item AND coalesce(c.cfop, '') = coalesce(p.cfop, '')

-- @step pool_n3
-- N3: escrituração consolidada (C190 + C191/C195) — CNPJ_Filial + Período + CNPJ Fornecedor + CFOP + COD_ITEM
CREATE OR REPLACE TEMP TABLE t_pool_N3 AS
SELECT row_number() OVER () AS pool_id, 'N3_CONSOLIDADO_C190' AS nivel, c.cnpj_filial, a.competencia,
       regexp_replace(coalesce(x.cnpj_cpf_part, ''), '\D', '', 'g') AS cnpj_cpf_forn, x.cfop, c.cod_item,
       min(c.file_id) AS ec_file_id,
       arg_max(x.cst, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'PIS') AS cst_pis,
       arg_max(x.aliq, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'PIS') AS aliq_pis,
       sum(x.vl_bc) FILTER (WHERE x.tributo = 'PIS') AS vl_bc_pis,
       sum(x.vl) FILTER (WHERE x.tributo = 'PIS') AS vl_pis,
       arg_max(x.cst, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'COFINS') AS cst_cofins,
       arg_max(x.aliq, coalesce(x.vl_bc, 0)) FILTER (WHERE x.tributo = 'COFINS') AS aliq_cofins,
       sum(x.vl_bc) FILTER (WHERE x.tributo = 'COFINS') AS vl_bc_cofins,
       sum(x.vl) FILTER (WHERE x.tributo = 'COFINS') AS vl_cofins,
       NULL::VARCHAR AS nat_bc_cred,
       coalesce(sum(coalesce(x.vl_item, 0) - coalesce(x.vl_desc, 0)) FILTER (WHERE x.tributo = 'PIS'),
                sum(coalesce(x.vl_item, 0) - coalesce(x.vl_desc, 0)) FILTER (WHERE x.tributo = 'COFINS')) AS vl_item_pool
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
-- Energia/água/gás (C500), frete CT-e (D100), telecom (D500/D700): PIS/COFINS dos C501/C505, D101/D105,
-- D501/D505 do documento vinculado, rateado entre as linhas analíticas do SPED Fiscal (C590/D190/D590/D730).
CREATE OR REPLACE TEMP TABLE t_ec_trib AS
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
FROM ec_doc_trib t
WHERE EXISTS (SELECT 1 FROM t_ec_doc d WHERE d.file_id = t.file_id AND d.doc_id = t.doc_id)
GROUP BY file_id, doc_id;

CREATE OR REPLACE TEMP TABLE t_pool_DOC AS
SELECT row_number() OVER () AS pool_id, 'DOC_' || m.via AS nivel, m.file_id, m.doc_id, m.ec_file_id, m.ec_doc_id,
       tr.cst_pis, tr.aliq_pis, tr.vl_bc_pis, tr.vl_pis, tr.cst_cofins, tr.aliq_cofins, tr.vl_bc_cofins, tr.vl_cofins,
       tr.nat_bc_cred
FROM t_docmatch m
JOIN t_ec_doc d ON d.file_id = m.ec_file_id AND d.doc_id = m.ec_doc_id AND d.reg IN ('C500', 'D100', 'D500')
LEFT JOIN t_ec_trib tr ON tr.file_id = m.ec_file_id AND tr.doc_id = m.ec_doc_id;

CREATE OR REPLACE TEMP TABLE t_cand_DOC AS
SELECT l.lid, abs(coalesce(l.vl_contabil, 0)) AS w, l.file_id, l.doc_id
FROM t_lin l WHERE l.reg_doc IN ('C500', 'D100', 'D500', 'D700');

-- @alloc DOC: c.file_id = p.file_id AND c.doc_id = p.doc_id

-- @template alocar
-- Rateio genérico de um "pool" de PIS/COFINS sobre as linhas candidatas com a mesma chave (proporcional ao peso,
-- resíduo de centavos no maior peso). Resultado: uma linha por lid; a soma por pool é exatamente o valor do pool.
CREATE OR REPLACE TEMP TABLE t_alloc_{{LEVEL}} AS
WITH j AS (
    SELECT c.lid, c.w, p.pool_id, p.nivel, p.ec_file_id, p.cst_pis, p.aliq_pis, p.cst_cofins,
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
SELECT lid, pool_id, nivel, ec_file_id, cst_pis, aliq_pis,
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
UNION ALL BY NAME SELECT * EXCLUDE (pool_id) FROM t_alloc_N2
UNION ALL BY NAME SELECT * EXCLUDE (pool_id) FROM t_alloc_N3
UNION ALL BY NAME SELECT * EXCLUDE (pool_id) FROM t_alloc_DOC;

-- Itens da EFD efetivamente consumidos (N1/N1V/Exceção 2 + pools N2 que encontraram linha no SPED Fiscal)
CREATE OR REPLACE TEMP TABLE t_ec_used AS
SELECT eid FROM t_pc WHERE eid IS NOT NULL
UNION
SELECT r.eid FROM t_ec_rest r WHERE r.pool_id IN (SELECT pool_id FROM t_alloc_N2);

-- @step t_lin_ec
-- Linhas que existem somente na EFD-Contribuições:
--   * operações exclusivas por natureza: serviços (A100/A170), F100, F120/F130;
--   * SEM_SPED_FISCAL: filial/competência sem SPED Fiscal carregado (a EFD é a única fonte; leva o valor);
--   * SEM_PAR: há SPED Fiscal da filial no período, mas o item/documento/consolidação da EFD não encontrou
--     correspondência. Entra com valor contábil zero (o SPED Fiscal é a fonte do valor) e com todo o
--     PIS/COFINS, para que nenhum crédito desapareça do totalizador.
CREATE OR REPLACE TEMP TABLE t_lin_ec AS
WITH sf_cov AS (
    SELECT DISTINCT cnpj, competencia FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'ICMS_IPI'
), part AS (
    SELECT DISTINCT ON (file_id, cod_part) * FROM ec_part ORDER BY file_id, cod_part
)
-- A100/A170 serviços tomados
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       'EC_A170_SERVICO' AS origem, 'EC_EXCLUSIVO' AS nivel, i.num_item, i.cod_item, i.descr_compl,
       CAST(coalesce(i.vl_item, 0) - coalesce(i.vl_desc, 0) AS DECIMAL(18,2)) AS vl_contabil,
       i.vl_item, i.vl_desc, 'SERV' AS cfop, i.cod_cta, i.nat_bc_cred,
       i.cst_pis, i.aliq_pis, i.vl_bc_pis, i.vl_pis, i.cst_cofins, i.aliq_cofins, i.vl_bc_cofins, i.vl_cofins,
       FALSE AS flag_item_sintetico
FROM t_ec_doc d JOIN ec_item i ON i.file_id = d.file_id AND i.doc_id = d.doc_id AND i.reg = 'A170'
WHERE d.reg = 'A100'
UNION ALL BY NAME
-- C170 da EFD não consumido por nenhuma linha do SPED Fiscal
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       CASE WHEN c.cnpj IS NULL THEN 'EC_C170_SEM_SPED_FISCAL' ELSE 'EC_C170_SEM_PAR' END AS origem,
       CASE WHEN c.cnpj IS NULL THEN 'EC_EXCLUSIVO' ELSE 'EC_SEM_PAR' END AS nivel,
       e.num_item, e.cod_item, e.descr_compl, e.unid, e.cfop, e.cod_cta,
       CASE WHEN c.cnpj IS NULL THEN e.qtd END AS qtd,
       CASE WHEN c.cnpj IS NULL THEN e.vl_item ELSE 0 END AS vl_item,
       CASE WHEN c.cnpj IS NULL THEN e.vl_desc ELSE 0 END AS vl_desc,
       CASE WHEN c.cnpj IS NULL
            THEN CAST(coalesce(e.vl_item, 0) - coalesce(e.vl_desc, 0) + coalesce(e.vl_icms_st, 0)
                      + coalesce(e.vl_ipi, 0) AS DECIMAL(18,2)) ELSE 0 END AS vl_contabil,
       e.cst_pis, e.aliq_pis, e.vl_bc_pis, e.vl_pis, e.cst_cofins, e.aliq_cofins, e.vl_bc_cofins, e.vl_cofins,
       FALSE AS flag_item_sintetico,
       CASE WHEN c.cnpj IS NULL THEN e.cst_icms END AS cst_icms,
       CASE WHEN c.cnpj IS NULL THEN e.aliq_icms END AS aliq_icms,
       CASE WHEN c.cnpj IS NULL THEN e.vl_bc_icms END AS vl_bc_icms,
       CASE WHEN c.cnpj IS NULL THEN e.vl_icms END AS vl_icms,
       CASE WHEN c.cnpj IS NULL THEN e.vl_icms_st END AS vl_icms_st,
       CASE WHEN c.cnpj IS NULL THEN e.vl_ipi END AS vl_ipi
FROM t_ec_it e
JOIN t_ec_doc d ON d.file_id = e.ec_file_id AND d.doc_id = e.ec_doc_id
LEFT JOIN sf_cov c ON c.cnpj = d.cnpj_filial AND c.competencia = d.competencia
WHERE NOT EXISTS (SELECT 1 FROM t_ec_used u WHERE u.eid = e.eid)
UNION ALL BY NAME
-- Consolidação C190/C191/C195 sem linha correspondente no SPED Fiscal
SELECT p.competencia, p.cnpj_filial, p.ec_file_id, -(1000000000 + p.pool_id) AS doc_id, 'C190' AS reg_doc,
       NULLIF(p.cnpj_cpf_forn, '') AS cnpj_cpf_forn,
       CASE WHEN c.cnpj IS NULL THEN 'EC_C190_SEM_SPED_FISCAL' ELSE 'EC_C190_SEM_PAR' END AS origem,
       CASE WHEN c.cnpj IS NULL THEN 'EC_EXCLUSIVO' ELSE 'EC_SEM_PAR' END AS nivel,
       p.cod_item, p.cfop,
       CASE WHEN c.cnpj IS NULL THEN CAST(p.vl_item_pool AS DECIMAL(18,2)) ELSE 0 END AS vl_item,
       CASE WHEN c.cnpj IS NULL THEN CAST(p.vl_item_pool AS DECIMAL(18,2)) ELSE 0 END AS vl_contabil,
       p.cst_pis, p.aliq_pis, p.vl_bc_pis, p.vl_pis, p.cst_cofins, p.aliq_cofins, p.vl_bc_cofins, p.vl_cofins,
       FALSE AS flag_item_sintetico
FROM t_pool_N3 p
LEFT JOIN sf_cov c ON c.cnpj = p.cnpj_filial AND c.competencia = p.competencia
WHERE p.pool_id NOT IN (SELECT pool_id FROM t_alloc_N3)
UNION ALL BY NAME
-- C500/D100/D500 da EFD sem documento (ou sem linha analítica) correspondente no SPED Fiscal
SELECT d.competencia, d.cnpj_filial, d.file_id AS ec_file_id, d.doc_id, d.reg AS reg_doc, d.cod_part,
       d.cnpj_cpf_forn, d.cod_mod, d.cod_sit, d.ind_emit, d.ser, d.num_doc, d.chave, d.dt_doc, d.dt_e_s,
       'EC_' || d.reg || CASE WHEN c.cnpj IS NULL THEN '_SEM_SPED_FISCAL' ELSE '_SEM_PAR' END AS origem,
       CASE WHEN c.cnpj IS NULL THEN 'EC_EXCLUSIVO' ELSE 'EC_SEM_PAR' END AS nivel,
       coalesce(m.cod_item, '_SERVICO_' || d.reg || '_') AS cod_item,
       CASE WHEN c.cnpj IS NULL THEN CAST(d.vl_doc AS DECIMAL(18,2)) ELSE 0 END AS vl_item,
       CASE WHEN c.cnpj IS NULL THEN d.vl_desc ELSE 0 END AS vl_desc,
       CASE WHEN c.cnpj IS NULL THEN CAST(d.vl_doc AS DECIMAL(18,2)) ELSE 0 END AS vl_contabil,
       'N/D' AS cfop, tr.nat_bc_cred,
       tr.cst_pis, tr.aliq_pis, tr.vl_bc_pis, tr.vl_pis, tr.cst_cofins, tr.aliq_cofins, tr.vl_bc_cofins, tr.vl_cofins,
       TRUE AS flag_item_sintetico, CASE WHEN c.cnpj IS NULL THEN d.vl_icms END AS vl_icms
FROM t_ec_doc d
LEFT JOIN t_ec_trib tr ON tr.file_id = d.file_id AND tr.doc_id = d.doc_id
LEFT JOIN ref_item_sintetico m ON m.cod_mod = d.cod_mod
LEFT JOIN sf_cov c ON c.cnpj = d.cnpj_filial AND c.competencia = d.competencia
WHERE d.reg IN ('C500', 'D100', 'D500')
  AND NOT EXISTS (SELECT 1 FROM t_pool_DOC p
                  WHERE p.ec_file_id = d.file_id AND p.ec_doc_id = d.doc_id
                    AND p.pool_id IN (SELECT pool_id FROM t_alloc_DOC))
UNION ALL BY NAME
-- F100 (demais operações com crédito) e F120/F130 (ativo imobilizado: crédito sobre depreciação/aquisição)
SELECT a.competencia, f.cnpj_filial, f.file_id AS ec_file_id, -(row_number() OVER ()) AS doc_id, f.reg AS reg_doc,
       f.cod_part,
       COALESCE(NULLIF(regexp_replace(coalesce(p.cnpj, ''), '\D', '', 'g'), ''),
                NULLIF(regexp_replace(coalesce(p.cpf, ''), '\D', '', 'g'), ''),
                CASE WHEN f.cod_part IS NOT NULL THEN 'PART:' || f.cod_part END) AS cnpj_cpf_forn,
       f.dt_oper AS dt_doc, f.dt_oper AS dt_e_s, 'EC_' || f.reg AS origem, 'EC_EXCLUSIVO' AS nivel,
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

-- @step fato_stage
-- Monta as linhas finais (SPED Fiscal + somente-EFD) com dimensões resolvidas
CREATE OR REPLACE TEMP TABLE t_fato_new AS
WITH cat AS (
    SELECT DISTINCT ON (file_id, cod_item) file_id, cod_item, descr_item, tipo_item, cod_ncm, cest, cod_barra, unid_inv
    FROM sf_item_cad ORDER BY file_id, cod_item
), ecat AS (
    SELECT DISTINCT ON (file_id, cnpj_filial, cod_item) file_id, cnpj_filial, cod_item, descr_item, tipo_item, cod_ncm,
           cod_barra, unid_inv
    FROM ec_item_cad ORDER BY file_id, cnpj_filial, cod_item
), x AS (
    SELECT l.*, pc.nivel, pc.ec_file_id AS pc_ec_file_id, pc.cst_pis, pc.aliq_pis, pc.vl_bc_pis, pc.vl_pis,
           pc.cst_cofins, pc.aliq_cofins, pc.vl_bc_cofins, pc.vl_cofins, pc.nat_bc_cred
    FROM t_lin l LEFT JOIN t_pc_all pc ON pc.lid = l.lid
)
SELECT x.competencia, x.cnpj_filial, x.origem, x.reg_doc, x.file_id AS file_id_sf,
       coalesce(x.ec_file_id, x.pc_ec_file_id) AS file_id_ec, x.doc_id,
       x.cod_part, x.cnpj_cpf_forn AS cnpj_cpf_fornecedor, x.nome_part_na_data,
       x.cod_mod, x.cod_sit, x.ind_emit, x.ser AS serie, x.num_doc, x.chave, x.dt_doc, x.dt_e_s,
       x.num_item, x.cod_item,
       coalesce(c.descr_item, ec.descr_item, CASE WHEN x.flag_item_sintetico THEN x.cod_item END) AS descr_item,
       x.descr_compl, coalesce(c.tipo_item, ec.tipo_item) AS tipo_item, coalesce(c.cod_ncm, ec.cod_ncm) AS cod_ncm,
       c.cest, coalesce(c.cod_barra, ec.cod_barra) AS cod_barra, coalesce(x.unid, c.unid_inv, ec.unid_inv) AS unid,
       x.cfop, x.cod_nat, x.cst_icms, x.aliq_icms, x.cst_ipi, x.aliq_ipi,
       x.cst_pis, x.aliq_pis, x.cst_cofins, x.aliq_cofins, x.nat_bc_cred AS nat_informada,
       x.cod_cta, x.qtd, x.vl_item, x.vl_desc, x.vl_rateio_c190, x.vl_contabil,
       x.vl_bc_icms, x.vl_icms, x.vl_bc_icms_st, x.vl_icms_st, x.vl_fcp, x.vl_fcp_st, x.vl_bc_ipi, x.vl_ipi,
       x.vl_bc_pis, x.vl_pis, x.vl_bc_cofins, x.vl_cofins,
       x.nivel AS nivel_cruzamento_efd, x.flag_item_sintetico, x.flag_sem_c190
FROM x
LEFT JOIN cat c ON NOT starts_with(x.origem, 'EC_') AND c.file_id = x.file_id AND c.cod_item = x.cod_item
LEFT JOIN ecat ec ON starts_with(x.origem, 'EC_') AND ec.file_id = x.ec_file_id AND ec.cnpj_filial = x.cnpj_filial
                 AND ec.cod_item = x.cod_item
UNION ALL BY NAME
SELECT x.competencia, x.cnpj_filial, x.origem, x.reg_doc, x.ec_file_id AS file_id_ec, x.doc_id,
       x.cod_part, x.cnpj_cpf_forn AS cnpj_cpf_fornecedor,
       x.cod_mod, x.cod_sit, x.ind_emit, x.ser AS serie, x.num_doc, x.chave, x.dt_doc, x.dt_e_s,
       x.num_item, x.cod_item, coalesce(ec.descr_item, x.descr_compl, x.cod_item) AS descr_item, x.descr_compl,
       ec.tipo_item, ec.cod_ncm, ec.cod_barra, coalesce(x.unid, ec.unid_inv) AS unid,
       x.cfop, x.cst_icms, x.aliq_icms,
       x.cst_pis, x.aliq_pis, x.cst_cofins, x.aliq_cofins, x.nat_bc_cred AS nat_informada,
       x.cod_cta, x.qtd, x.vl_item, x.vl_desc, 0 AS vl_rateio_c190, x.vl_contabil,
       x.vl_bc_icms, x.vl_icms, x.vl_icms_st, x.vl_ipi,
       x.vl_bc_pis, x.vl_pis, x.vl_bc_cofins, x.vl_cofins,
       x.nivel AS nivel_cruzamento_efd, x.flag_item_sintetico, FALSE AS flag_sem_c190
FROM t_lin_ec x
LEFT JOIN ecat ec ON ec.file_id = x.ec_file_id AND ec.cnpj_filial = x.cnpj_filial AND ec.cod_item = x.cod_item;

-- @step fato_insert
-- Carga final já com métricas derivadas (sem UPDATE posterior) e ordenada por Filial/Fornecedor/Item:
-- o agrupamento físico permite ao DuckDB descartar blocos inteiros nos filtros e no drill-down.
INSERT INTO fato_entradas_consolidadas BY NAME
SELECT n.* EXCLUDE (nat_informada),
       df.nome_filial, df.uf_filial, df.raiz_cnpj AS raiz_cnpj_filial,
       CASE WHEN length(n.cnpj_cpf_fornecedor) = 14 THEN left(n.cnpj_cpf_fornecedor, 8)
            ELSE n.cnpj_cpf_fornecedor END AS raiz_cnpj_fornecedor,
       coalesce(fo.razao_social, n.nome_part_na_data) AS razao_social_fornecedor, fo.uf AS uf_fornecedor,
       coalesce(dp.cod_atual, n.cod_item) AS cod_item_unificado,
       coalesce(n.cod_ncm, '') || '|' || coalesce(dp.cod_atual, n.cod_item) AS chave_item_global,
       coalesce(n.nat_informada,
                CASE WHEN n.cst_pis IN ({{CST_CRED}}) THEN coalesce(nt.nat_bc_cred, '13') END) AS nat_bc_cred,
       CASE WHEN n.nat_informada IS NOT NULL THEN 'INFORMADO'
            WHEN n.cst_pis IN ({{CST_CRED}}) THEN 'DERIVADO_CFOP' END AS nat_bc_cred_origem,
       CAST(coalesce(n.vl_icms, 0)
            + CASE WHEN n.cst_ipi IN ({{CST_IPI_CRED}}) THEN coalesce(n.vl_ipi, 0) ELSE 0 END
            + CASE WHEN n.cst_pis IN ({{CST_CRED}}) THEN coalesce(n.vl_pis, 0) ELSE 0 END
            + CASE WHEN n.cst_cofins IN ({{CST_CRED}}) THEN coalesce(n.vl_cofins, 0) ELSE 0 END
            AS DECIMAL(18,2)) AS vl_trib_recuperaveis,
       CAST(coalesce(n.vl_contabil, 0)
            - (coalesce(n.vl_icms, 0)
               + CASE WHEN n.cst_ipi IN ({{CST_IPI_CRED}}) THEN coalesce(n.vl_ipi, 0) ELSE 0 END
               + CASE WHEN n.cst_pis IN ({{CST_CRED}}) THEN coalesce(n.vl_pis, 0) ELSE 0 END
               + CASE WHEN n.cst_cofins IN ({{CST_CRED}}) THEN coalesce(n.vl_cofins, 0) ELSE 0 END)
            AS DECIMAL(18,2)) AS vl_custo_liquido,
       CASE WHEN n.nivel_cruzamento_efd IS NULL THEN 'Sem Crédito / Não Escriturado na EFD-Contribuições'
            WHEN n.nivel_cruzamento_efd = 'EC_SEM_PAR' THEN 'Somente EFD — sem correspondência no SPED Fiscal'
            WHEN n.nivel_cruzamento_efd = 'EC_EXCLUSIVO' THEN 'Exclusivo EFD-Contribuições'
            ELSE 'Escriturado na EFD-Contribuições' END AS status_efd,
       coalesce(n.file_id_sf, n.file_id_ec) * 4294967296 + coalesce(n.doc_id, 0) AS doc_key
FROM t_fato_new n
LEFT JOIN dim_filial df ON df.cnpj_filial = n.cnpj_filial
LEFT JOIN dim_fornecedor fo ON fo.cnpj_cpf = n.cnpj_cpf_fornecedor
LEFT JOIN dim_item_depara dp ON dp.cnpj_filial = n.cnpj_filial AND dp.cod_ant = n.cod_item
LEFT JOIN ref_cfop_nat_bc_cred nt ON nt.cfop = n.cfop
ORDER BY n.competencia, n.cnpj_filial, n.cnpj_cpf_fornecedor, n.cod_item;
