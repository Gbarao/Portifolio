"""Cruzamento SPED Fiscal (EFD ICMS/IPI) × EFD Contribuicoes — mecanica do sped_analytics_app
(branch claude/wonderful-rubin-5qi5sj, app/database/queries_join.sql), adaptada as entradas e
saidas da analise ZFM.

1. Vinculo de documentos, estritamente 1:1 (v_doc_par):
   1o) chave do documento eletronico (44 posicoes), em qualquer competencia;
   2o) sem chave em um dos lados: estabelecimento + competencia + entrada/saida + fornecedor (CNPJ/CPF do
       0150) + modelo + serie + numero (o k-esimo de um lado casa com o k-esimo do outro).
2. Linhas de entrada do SPED Fiscal (v_entradas_linhas): C170; sem C170 (Excecao 2), os itens do C170
   da EFD Contribuicoes do documento vinculado, com valor, ICMS e IPI rateados ao C190 do mesmo CFOP;
   sem itens em nenhum dos dois, o C190.
3. PIS/COFINS das entradas vem SEMPRE da EFD Contribuicoes (v_entradas_pc), por nivel:
   N1_ITEM            mesma posicao (NUM_ITEM) + mesmo COD_ITEM + mesmo VL_ITEM (tolerancia 0,01);
   N1V_POSICAO_VALOR  mesma posicao + mesmo valor + mesmo CFOP, codigo do item diferente;
   N2_ITEM_CFOP       COD_ITEM + CFOP dentro do documento vinculado (saldo rateado pelo VL_ITEM);
   N3_CONSOLIDADO_C190  escrituracao consolidada (C190/C191/C195): estabelecimento + competencia +
                      CNPJ do fornecedor + CFOP + COD_ITEM;
   EC_EXCLUSIVO       so na EFD (estabelecimento/mes sem SPED Fiscal carregado): entra com o valor;
   EC_SEM_PAR         ha SPED Fiscal, mas o item/consolidacao da EFD nao achou par: entra com valor
                      zero e com todo o PIS/COFINS (nada some, nada duplica).
   Linha do SPED Fiscal sem nivel = "Sem credito / nao escriturado na EFD Contribuicoes".
"""
from __future__ import annotations

CANC = "('02','03','04','05')"
TOL_ITEM = 0.01

_FORN = """coalesce(nullif(regexp_replace(coalesce({p}.cnpj_part, ''), '[^0-9A-Za-z]', '', 'g'), ''),
                    nullif(regexp_replace(coalesce({p}.cpf_part, ''), '[^0-9]', '', 'g'), ''),
                    CASE WHEN {p}.cod_part IS NOT NULL THEN 'EXT:' || upper(trim(coalesce({p}.nome_part, {p}.cod_part))) END,
                    'PART:' || coalesce({d}.COD_PART, '?'))"""

V_DOC_PAR = f"""
WITH pf AS (SELECT DISTINCT ON (arquivo_id, cod_part) * FROM v_participantes ORDER BY arquivo_id, cod_part),
pc AS (SELECT DISTINCT ON (arquivo_id, cnpj_estab, cod_part) * FROM v_participantes_contrib
       ORDER BY arquivo_id, cnpj_estab, cod_part),
pa AS (SELECT DISTINCT ON (arquivo_id, cod_part) * FROM v_participantes_contrib ORDER BY arquivo_id, cod_part),
sf AS (
    SELECT d.arquivo_id, d.linha_num, a.cnpj AS cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END AS sentido, coalesce(d.COD_MOD, '') AS cod_mod,
           ltrim(coalesce(d.SER, ''), '0') AS sr, ltrim(coalesce(d.NUM_DOC, ''), '0') AS nd,
           CASE WHEN regexp_full_match(upper(coalesce(d.CHV_NFE, '')), '[0-9A-Z]{{44}}') THEN upper(d.CHV_NFE) END AS chave,
           {_FORN.format(p='p', d='d')} AS forn
    FROM raw_icms_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN pf p ON p.arquivo_id = d.arquivo_id AND p.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANC}),
ec AS (
    SELECT d.arquivo_id, d.linha_num, d.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes,
           CASE d.IND_OPER WHEN '0' THEN 'entrada' ELSE 'saida' END AS sentido, coalesce(d.COD_MOD, '') AS cod_mod,
           ltrim(coalesce(d.SER, ''), '0') AS sr, ltrim(coalesce(d.NUM_DOC, ''), '0') AS nd,
           CASE WHEN regexp_full_match(upper(coalesce(d.CHV_NFE, '')), '[0-9A-Z]{{44}}') THEN upper(d.CHV_NFE) END AS chave,
           coalesce(nullif(regexp_replace(coalesce(p.cnpj_part, q.cnpj_part, ''), '[^0-9A-Za-z]', '', 'g'), ''),
                    nullif(regexp_replace(coalesce(p.cpf_part, q.cpf_part, ''), '[^0-9]', '', 'g'), ''),
                    CASE WHEN coalesce(p.cod_part, q.cod_part) IS NOT NULL
                         THEN 'EXT:' || upper(trim(coalesce(p.nome_part, q.nome_part, d.COD_PART))) END,
                    'PART:' || coalesce(d.COD_PART, '?')) AS forn
    FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
    LEFT JOIN pc p ON p.arquivo_id = d.arquivo_id AND p.cnpj_estab = d.cnpj_estab AND p.cod_part = d.COD_PART
    LEFT JOIN pa q ON q.arquivo_id = d.arquivo_id AND q.cod_part = d.COD_PART
    WHERE a.ativo AND coalesce(d.COD_SIT, '00') NOT IN {CANC}),
sfr AS (SELECT *, row_number() OVER (PARTITION BY cnpj_estab, sentido, chave ORDER BY ano, mes, arquivo_id, linha_num) AS rn
        FROM sf),
ecr AS (SELECT *, row_number() OVER (PARTITION BY cnpj_estab, sentido, chave
                                     ORDER BY ano DESC, mes DESC, arquivo_id DESC, linha_num) AS rn FROM ec),
m1 AS (SELECT s.arquivo_id AS sf_arquivo_id, s.linha_num AS sf_linha, e.arquivo_id AS ec_arquivo_id,
              e.linha_num AS ec_linha, 'CHAVE' AS via
       FROM sfr s JOIN ecr e ON e.cnpj_estab = s.cnpj_estab AND e.sentido = s.sentido AND e.chave = s.chave
       WHERE s.chave IS NOT NULL AND s.rn = 1 AND e.rn = 1),
s2 AS (SELECT s.*, row_number() OVER (PARTITION BY cnpj_estab, ano, mes, sentido, forn, cod_mod, nd, sr
                                      ORDER BY arquivo_id, linha_num) AS rn2
       FROM sf s WHERE nd <> '' AND NOT EXISTS (SELECT 1 FROM m1 WHERE m1.sf_arquivo_id = s.arquivo_id
                                                                    AND m1.sf_linha = s.linha_num)),
e2 AS (SELECT e.*, row_number() OVER (PARTITION BY cnpj_estab, ano, mes, sentido, forn, cod_mod, nd, sr
                                      ORDER BY arquivo_id, linha_num) AS rn2
       FROM ec e WHERE nd <> '' AND NOT EXISTS (SELECT 1 FROM m1 WHERE m1.ec_arquivo_id = e.arquivo_id
                                                                    AND m1.ec_linha = e.linha_num)),
m2 AS (SELECT s.arquivo_id, s.linha_num, e.arquivo_id, e.linha_num, 'NUMERO'
       FROM s2 s JOIN e2 e ON e.cnpj_estab = s.cnpj_estab AND e.ano = s.ano AND e.mes = s.mes AND e.sentido = s.sentido
            AND e.forn = s.forn AND e.cod_mod = s.cod_mod AND e.nd = s.nd AND e.sr = s.sr AND e.rn2 = s.rn2
       WHERE s.chave IS NULL OR e.chave IS NULL)
SELECT * FROM m1 UNION ALL SELECT * FROM m2
"""

V_ENTRADAS_LINHAS = f"""
WITH docs AS (SELECT arquivo_id, doc_linha FROM v_docs WHERE sentido = 'entrada' AND NOT cancelado AND uf_estab = 'AM'),
sf170 AS (
    SELECT i.arquivo_id, i.linha_num, 'C170' AS reg_origem, i.pai_linha AS doc_linha,
           CAST(NULL AS BIGINT) AS ec_arquivo_id, i.NUM_ITEM AS num_item, i.COD_ITEM AS cod_item, i.CFOP AS cfop,
           CAST(i.VL_ITEM AS DOUBLE) AS vl_item, CAST(coalesce(i.VL_DESC, 0) AS DOUBLE) AS vl_desc,
           i.CST_ICMS AS cst_icms, CAST(i.VL_ICMS AS DOUBLE) AS vl_icms, i.CST_IPI AS cst_ipi,
           CAST(i.VL_IPI AS DOUBLE) AS vl_ipi, CAST(i.VL_ITEM - coalesce(i.VL_DESC, 0) AS DOUBLE) AS valor
    FROM raw_icms_c170 i JOIN docs d ON d.arquivo_id = i.arquivo_id AND d.doc_linha = i.pai_linha),
sem170 AS (SELECT d.* FROM docs d WHERE NOT EXISTS (SELECT 1 FROM raw_icms_c170 x
                                                    WHERE x.arquivo_id = d.arquivo_id AND x.pai_linha = d.doc_linha)),
c190 AS (
    SELECT c.arquivo_id, c.linha_num, c.pai_linha AS doc_linha, c.CFOP AS cfop, c.CST_ICMS AS cst_icms,
           CAST(c.VL_OPR - coalesce(c.VL_IPI, 0) - coalesce(c.VL_ICMS_ST, 0) AS DOUBLE) AS valor,
           CAST(c.VL_ICMS AS DOUBLE) AS vl_icms, CAST(c.VL_IPI AS DOUBLE) AS vl_ipi
    FROM raw_icms_c190 c JOIN sem170 s ON s.arquivo_id = c.arquivo_id AND s.doc_linha = c.pai_linha),
c190c AS (SELECT arquivo_id, doc_linha, cfop, sum(valor) AS valor, sum(vl_icms) AS vl_icms, sum(vl_ipi) AS vl_ipi
          FROM c190 GROUP BY ALL),
ex AS (  -- Excecao 2: itens do C170 da EFD Contribuicoes do documento vinculado
    SELECT s.arquivo_id, s.doc_linha, e.arquivo_id AS ec_arquivo_id, e.linha_num, e.NUM_ITEM AS num_item,
           e.COD_ITEM AS cod_item, e.CFOP AS cfop, CAST(e.VL_ITEM AS DOUBLE) AS vl_item,
           CAST(coalesce(e.VL_DESC, 0) AS DOUBLE) AS vl_desc, e.CST_ICMS AS cst_icms, e.CST_IPI AS cst_ipi,
           CAST(e.VL_ITEM - coalesce(e.VL_DESC, 0) AS DOUBLE) AS v0, CAST(e.VL_ICMS AS DOUBLE) AS icms0,
           CAST(e.VL_IPI AS DOUBLE) AS ipi0
    FROM sem170 s JOIN v_doc_par m ON m.sf_arquivo_id = s.arquivo_id AND m.sf_linha = s.doc_linha
    JOIN raw_contrib_c170 e ON e.arquivo_id = m.ec_arquivo_id AND e.pai_linha = m.ec_linha),
exr AS (SELECT ex.*, c.valor AS alvo, c.vl_icms AS icms_c190, c.vl_ipi AS ipi_c190,
               sum(ex.v0) OVER (PARTITION BY ex.arquivo_id, ex.doc_linha, ex.cfop) AS soma_v,
               count(*) OVER (PARTITION BY ex.arquivo_id, ex.doc_linha, ex.cfop) AS n
        FROM ex LEFT JOIN c190c c ON c.arquivo_id = ex.arquivo_id AND c.doc_linha = ex.doc_linha AND c.cfop = ex.cfop),
exl AS (
    SELECT arquivo_id, linha_num, 'C170 (EFD Contribuições)' AS reg_origem, doc_linha, ec_arquivo_id, num_item,
           cod_item, cfop, vl_item, vl_desc, cst_icms,
           CASE WHEN alvo IS NULL THEN icms0 ELSE icms_c190 * coalesce(v0 / nullif(soma_v, 0), 1.0 / n) END AS vl_icms,
           cst_ipi,
           CASE WHEN alvo IS NULL THEN ipi0 ELSE ipi_c190 * coalesce(v0 / nullif(soma_v, 0), 1.0 / n) END AS vl_ipi,
           CASE WHEN alvo IS NULL THEN v0 ELSE alvo * coalesce(v0 / nullif(soma_v, 0), 1.0 / n) END AS valor
    FROM exr),
c190l AS (
    SELECT c.arquivo_id, c.linha_num, 'C190' AS reg_origem, c.doc_linha, CAST(NULL AS BIGINT) AS ec_arquivo_id,
           CAST(NULL AS VARCHAR) AS num_item, CAST(NULL AS VARCHAR) AS cod_item, c.cfop, c.valor AS vl_item,
           0.0 AS vl_desc, c.cst_icms, c.vl_icms, CAST(NULL AS VARCHAR) AS cst_ipi, c.vl_ipi, c.valor
    FROM c190 c WHERE NOT EXISTS (SELECT 1 FROM ex WHERE ex.arquivo_id = c.arquivo_id AND ex.doc_linha = c.doc_linha
                                                     AND ex.cfop = c.cfop))
SELECT *, reg_origem || '|' || arquivo_id || '|' || linha_num || '|' || coalesce(ec_arquivo_id, 0) AS lk
FROM (SELECT * FROM sf170 UNION ALL BY NAME SELECT * FROM exl UNION ALL BY NAME SELECT * FROM c190l)
"""

# PIS/COFINS das entradas a partir da EFD Contribuicoes, por nivel; inclui as linhas "so na EFD"
V_ENTRADAS_PC = f"""
WITH l AS (SELECT l.*, d.cnpj_estab, d.ano, d.mes,
                  regexp_replace(coalesce(d.cnpj_part, ''), '[^0-9A-Za-z]', '', 'g') AS forn
           FROM v_entradas_linhas l JOIN v_docs d ON d.arquivo_id = l.arquivo_id AND d.doc_linha = l.doc_linha),
ecd AS (SELECT d.arquivo_id, d.linha_num, d.cnpj_estab, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, a.raiz
        FROM raw_contrib_c100 d JOIN arquivos a USING (arquivo_id)
        WHERE a.ativo AND d.IND_OPER = '0' AND coalesce(d.COD_SIT, '00') NOT IN {CANC}),
eci AS (SELECT e.arquivo_id AS ec_arquivo_id, e.linha_num AS ec_linha, e.pai_linha AS ec_doc, d.cnpj_estab, d.raiz,
               d.ano, d.mes, m.sf_arquivo_id, m.sf_linha, e.NUM_ITEM AS num_item, e.COD_ITEM AS cod_item,
               coalesce(e.CFOP, '') AS cfop, CAST(e.VL_ITEM AS DOUBLE) AS vl_item,
               CAST(coalesce(e.VL_DESC, 0) AS DOUBLE) AS vl_desc, CAST(e.VL_ICMS AS DOUBLE) AS vl_icms,
               CAST(e.VL_IPI AS DOUBLE) AS vl_ipi,
               e.CST_PIS AS cst_pis, CAST(e.ALIQ_PIS AS DOUBLE) AS aliq_pis, CAST(e.VL_PIS AS DOUBLE) AS vl_pis,
               e.CST_COFINS AS cst_cofins, CAST(e.ALIQ_COFINS AS DOUBLE) AS aliq_cofins,
               CAST(e.VL_COFINS AS DOUBLE) AS vl_cofins,
               row_number() OVER (PARTITION BY e.arquivo_id, e.pai_linha, e.NUM_ITEM ORDER BY e.COD_ITEM, e.linha_num) AS dup
        FROM raw_contrib_c170 e JOIN ecd d ON d.arquivo_id = e.arquivo_id AND d.linha_num = e.pai_linha
        LEFT JOIN v_doc_par m ON m.ec_arquivo_id = e.arquivo_id AND m.ec_linha = e.pai_linha),
p_ex AS (SELECT l.lk, 'N1_ITEM' AS nivel, i.ec_arquivo_id, i.ec_linha FROM l
         JOIN eci i ON i.ec_arquivo_id = l.ec_arquivo_id AND i.ec_linha = l.linha_num
         WHERE l.ec_arquivo_id IS NOT NULL),
sfl AS (SELECT l.*, row_number() OVER (PARTITION BY arquivo_id, doc_linha, num_item ORDER BY linha_num) AS rn
        FROM l WHERE reg_origem = 'C170'),
cand AS (SELECT s.lk, i.ec_arquivo_id, i.ec_linha,
                CASE WHEN i.cod_item = s.cod_item THEN 'N1_ITEM'
                     WHEN i.cfop = coalesce(s.cfop, '') AND coalesce(s.vl_item, 0) <> 0 THEN 'N1V_POSICAO_VALOR' END AS nivel
         FROM sfl s JOIN eci i ON i.sf_arquivo_id = s.arquivo_id AND i.sf_linha = s.doc_linha AND i.num_item = s.num_item
         WHERE s.rn = 1 AND i.dup = 1 AND abs(coalesce(i.vl_item, 0) - coalesce(s.vl_item, 0)) <= {TOL_ITEM}),
n1 AS (SELECT lk, nivel, ec_arquivo_id, ec_linha FROM cand WHERE nivel IS NOT NULL
       UNION ALL SELECT * FROM p_ex),
v1 AS (SELECT n1.lk, n1.nivel, i.cst_pis, i.aliq_pis, i.vl_pis, i.cst_cofins, i.aliq_cofins, i.vl_cofins
       FROM n1 JOIN eci i ON i.ec_arquivo_id = n1.ec_arquivo_id AND i.ec_linha = n1.ec_linha),
rest AS (SELECT i.* FROM eci i WHERE i.sf_arquivo_id IS NOT NULL AND NOT EXISTS (
             SELECT 1 FROM n1 WHERE n1.ec_arquivo_id = i.ec_arquivo_id AND n1.ec_linha = i.ec_linha)),
pool2 AS (SELECT sf_arquivo_id, sf_linha, cod_item, cfop,
                 arg_max(cst_pis, vl_item) AS cst_pis, arg_max(aliq_pis, vl_item) AS aliq_pis, sum(vl_pis) AS vl_pis,
                 arg_max(cst_cofins, vl_item) AS cst_cofins, arg_max(aliq_cofins, vl_item) AS aliq_cofins,
                 sum(vl_cofins) AS vl_cofins
          FROM rest GROUP BY sf_arquivo_id, sf_linha, cod_item, cfop),
cand2 AS (SELECT l.lk, l.arquivo_id, l.doc_linha, l.cod_item, coalesce(l.cfop, '') AS cfop, abs(coalesce(l.vl_item, 0)) AS w
          FROM l WHERE l.reg_origem = 'C170' AND l.lk NOT IN (SELECT lk FROM n1)),
a2 AS (SELECT c.lk, 'N2_ITEM_CFOP' AS nivel, p.sf_arquivo_id, p.sf_linha, p.cod_item, p.cfop,
              p.cst_pis, p.aliq_pis, p.cst_cofins, p.aliq_cofins,
              coalesce(c.w / nullif(sum(c.w) OVER k, 0), 1.0 / count(*) OVER k) AS share, p.vl_pis, p.vl_cofins
       FROM cand2 c JOIN pool2 p ON p.sf_arquivo_id = c.arquivo_id AND p.sf_linha = c.doc_linha
            AND p.cod_item = c.cod_item AND p.cfop = c.cfop
       WINDOW k AS (PARTITION BY p.sf_arquivo_id, p.sf_linha, p.cod_item, p.cfop)),
c19 AS (SELECT h.arquivo_id, h.cnpj_estab, a.raiz, year(a.dt_ini) AS ano, month(a.dt_ini) AS mes, h.COD_ITEM AS cod_item,
               x.*
        FROM raw_contrib_c190 h JOIN arquivos a USING (arquivo_id)
        JOIN (SELECT arquivo_id, pai_linha, CNPJ_CPF_PART AS part, coalesce(CFOP, '') AS cfop, 'PIS' AS trib,
                     CST_PIS AS cst, CAST(ALIQ_PIS AS DOUBLE) AS aliq, CAST(VL_PIS AS DOUBLE) AS vl,
                     CAST(VL_ITEM - coalesce(VL_DESC, 0) AS DOUBLE) AS v
              FROM raw_contrib_c191
              UNION ALL
              SELECT arquivo_id, pai_linha, CNPJ_CPF_PART, coalesce(CFOP, ''), 'COFINS', CST_COFINS,
                     CAST(ALIQ_COFINS AS DOUBLE), CAST(VL_COFINS AS DOUBLE), CAST(VL_ITEM - coalesce(VL_DESC, 0) AS DOUBLE)
              FROM raw_contrib_c195) x ON x.arquivo_id = h.arquivo_id AND x.pai_linha = h.linha_num
        WHERE a.ativo),
pool3 AS (SELECT cnpj_estab, raiz, ano, mes, regexp_replace(coalesce(part, ''), '[^0-9A-Za-z]', '', 'g') AS forn, cfop,
                 cod_item, min(arquivo_id) AS ec_arquivo_id,
                 arg_max(cst, v) FILTER (WHERE trib = 'PIS') AS cst_pis, arg_max(aliq, v) FILTER (WHERE trib = 'PIS') AS aliq_pis,
                 sum(vl) FILTER (WHERE trib = 'PIS') AS vl_pis,
                 arg_max(cst, v) FILTER (WHERE trib = 'COFINS') AS cst_cofins,
                 arg_max(aliq, v) FILTER (WHERE trib = 'COFINS') AS aliq_cofins,
                 sum(vl) FILTER (WHERE trib = 'COFINS') AS vl_cofins,
                 coalesce(sum(v) FILTER (WHERE trib = 'PIS'), sum(v) FILTER (WHERE trib = 'COFINS')) AS v
          FROM c19 GROUP BY cnpj_estab, raiz, ano, mes, forn, cfop, cod_item),
cand3 AS (SELECT l.lk, l.cnpj_estab, l.ano, l.mes, l.forn, coalesce(l.cfop, '') AS cfop, l.cod_item,
                 abs(coalesce(l.vl_item, 0)) AS w
          FROM l WHERE l.reg_origem = 'C170' AND l.lk NOT IN (SELECT lk FROM n1) AND l.lk NOT IN (SELECT lk FROM a2)),
a3 AS (SELECT c.lk, 'N3_CONSOLIDADO_C190' AS nivel, p.cnpj_estab, p.ano, p.mes, p.forn, p.cfop, p.cod_item,
              p.cst_pis, p.aliq_pis, p.cst_cofins, p.aliq_cofins,
              coalesce(c.w / nullif(sum(c.w) OVER k, 0), 1.0 / count(*) OVER k) AS share, p.vl_pis, p.vl_cofins
       FROM cand3 c JOIN pool3 p ON p.cnpj_estab = c.cnpj_estab AND p.ano = c.ano AND p.mes = c.mes
            AND p.forn = c.forn AND p.cfop = c.cfop AND p.cod_item = c.cod_item
       WINDOW k AS (PARTITION BY p.cnpj_estab, p.ano, p.mes, p.forn, p.cfop, p.cod_item)),
sf_cov AS (SELECT DISTINCT cnpj, year(dt_ini) AS ano, month(dt_ini) AS mes FROM arquivos WHERE ativo AND tipo = 'ICMS_IPI'),
-- linhas que so existem na EFD Contribuicoes
so_c170 AS (
    SELECT i.raiz, i.cnpj_estab, i.ano, i.mes, i.ec_arquivo_id, i.ec_linha, i.ec_doc, i.cod_item, i.cfop, i.num_item,
           i.vl_item, i.vl_desc, i.vl_icms, i.vl_ipi, i.cst_pis, i.aliq_pis, i.vl_pis, i.cst_cofins, i.aliq_cofins,
           i.vl_cofins, c.cnpj IS NULL AS exclusivo, CAST(NULL AS VARCHAR) AS forn, 'C170' AS reg
    FROM eci i LEFT JOIN sf_cov c ON c.cnpj = i.cnpj_estab AND c.ano = i.ano AND c.mes = i.mes
    WHERE NOT EXISTS (SELECT 1 FROM n1 WHERE n1.ec_arquivo_id = i.ec_arquivo_id AND n1.ec_linha = i.ec_linha)
      AND NOT EXISTS (SELECT 1 FROM a2 WHERE a2.sf_arquivo_id = i.sf_arquivo_id AND a2.sf_linha = i.sf_linha
                                       AND a2.cod_item = i.cod_item AND a2.cfop = i.cfop)),
so_c190 AS (
    SELECT p.raiz, p.cnpj_estab, p.ano, p.mes, p.ec_arquivo_id, CAST(NULL AS BIGINT) AS ec_linha,
           CAST(NULL AS BIGINT) AS ec_doc, p.cod_item, p.cfop, CAST(NULL AS VARCHAR) AS num_item, p.v AS vl_item,
           0.0 AS vl_desc, 0.0 AS vl_icms, 0.0 AS vl_ipi, p.cst_pis, p.aliq_pis, p.vl_pis, p.cst_cofins, p.aliq_cofins,
           p.vl_cofins, c.cnpj IS NULL AS exclusivo, p.forn, 'C190/C191/C195' AS reg
    FROM pool3 p LEFT JOIN sf_cov c ON c.cnpj = p.cnpj_estab AND c.ano = p.ano AND c.mes = p.mes
    WHERE NOT EXISTS (SELECT 1 FROM a3 WHERE a3.cnpj_estab = p.cnpj_estab AND a3.ano = p.ano AND a3.mes = p.mes
                                       AND a3.forn = p.forn AND a3.cfop = p.cfop AND a3.cod_item = p.cod_item))
SELECT 'linha' AS tipo, lk, nivel, cst_pis, aliq_pis, vl_pis, cst_cofins, aliq_cofins, vl_cofins,
       NULL::VARCHAR AS raiz, NULL::VARCHAR AS cnpj_estab, NULL::BIGINT AS ano, NULL::BIGINT AS mes,
       NULL::BIGINT AS ec_arquivo_id, NULL::BIGINT AS ec_linha, NULL::BIGINT AS ec_doc, NULL::VARCHAR AS cod_item,
       NULL::VARCHAR AS cfop, NULL::VARCHAR AS num_item, NULL::DOUBLE AS vl_item, NULL::DOUBLE AS vl_desc,
       NULL::DOUBLE AS vl_icms, NULL::DOUBLE AS vl_ipi, NULL::VARCHAR AS forn, NULL::VARCHAR AS reg
FROM v1
UNION ALL
SELECT 'linha', lk, nivel, cst_pis, aliq_pis, vl_pis * share, cst_cofins, aliq_cofins, vl_cofins * share,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM a2
UNION ALL
SELECT 'linha', lk, nivel, cst_pis, aliq_pis, vl_pis * share, cst_cofins, aliq_cofins, vl_cofins * share,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM a3
UNION ALL
SELECT 'so_efd', NULL, CASE WHEN exclusivo THEN 'EC_EXCLUSIVO' ELSE 'EC_SEM_PAR' END, cst_pis, aliq_pis, vl_pis,
       cst_cofins, aliq_cofins, vl_cofins, raiz, cnpj_estab, ano, mes, ec_arquivo_id, ec_linha, ec_doc, cod_item, cfop,
       num_item, vl_item, vl_desc, vl_icms, vl_ipi, forn, reg
FROM (SELECT * FROM so_c170 UNION ALL BY NAME SELECT * FROM so_c190)
"""

NIVEIS = {
    "N1_ITEM": "Item a item (posição + código + valor)",
    "N1V_POSICAO_VALOR": "Mesma posição, valor e CFOP (código do item diferente)",
    "N2_ITEM_CFOP": "Código do item + CFOP no documento (rateio)",
    "N3_CONSOLIDADO_C190": "Consolidado C190/C191/C195 (estabelecimento + mês + fornecedor + CFOP + item)",
    "EC_EXCLUSIVO": "Só na EFD Contribuições (sem SPED Fiscal do mês): entra com o valor",
    "EC_SEM_PAR": "Só na EFD Contribuições, sem par no SPED Fiscal: valor zero, todo o PIS/COFINS",
    "SEM_CREDITO": "Sem crédito / não escriturado na EFD Contribuições",
}
