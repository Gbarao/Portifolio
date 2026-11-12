"""Auditoria automática de divergências SPED Fiscal x EFD-Contribuições."""
from __future__ import annotations

import polars as pl

from app import config
from app.database.filter_builder import FATO, global_filters_sql

_CRED = ", ".join(f"'{c}'" for c in config.CST_PIS_COFINS_CREDITO)
_IPI = ", ".join(f"'{c}'" for c in config.CST_IPI_CREDITO)
_INSUMO = ", ".join(f"'{c}'" for c in config.TIPO_ITEM_INSUMO_REVENDA)

CHECKS = {
    "valor_documento": "Notas com diferença de Valor do Documento / Mercadoria (C100 SF x C100 EFD)",
    "valor_item": "Itens com diferença de Valor do Item (C170 SF x C170 EFD, mesmo NUM_ITEM)",
    "credito_icms_sem_pis": "Insumo/revenda com crédito de ICMS/IPI e sem crédito de PIS/COFINS",
    "credito_pis_sem_icms": "Insumo/revenda com crédito de PIS/COFINS e sem crédito de ICMS/IPI",
    "cst_divergente_filiais": "Mesmo item + CFOP com CST diferente entre filiais",
    "ec_sem_sf": "NF de entrada na EFD-Contribuições ausente no SPED Fiscal",
    "item_sem_c190": "Itens C170 sem registro analítico C190 correspondente (CST/CFOP/alíquota)",
}


def _scope_where(gf: dict | None, params: list, alias: str = "") -> str:
    """Aplica período e filiais dos filtros globais às consultas sobre tabelas brutas."""
    gf = gf or {}
    conds = []
    a = f"{alias}." if alias else ""
    if gf.get("comp_ini"):
        params.append(gf["comp_ini"])
        conds.append(f"{a}competencia >= ${len(params)}")
    if gf.get("comp_fim"):
        params.append(gf["comp_fim"])
        conds.append(f"{a}competencia <= ${len(params)}")
    if gf.get("competencias"):
        params.append(list(gf["competencias"]))
        conds.append(f"{a}competencia IN (SELECT unnest(${len(params)}))")
    if gf.get("filiais"):
        params.append(list(gf["filiais"]))
        conds.append(f"{a}cnpj_filial IN (SELECT unnest(${len(params)}))")
    return " AND ".join(conds) if conds else "TRUE"


def run_check(db, check: str, gf: dict | None = None, tol: float = config.TOLERANCIA_DIVERGENCIA,
              limit: int = 20_000) -> pl.DataFrame:
    params: list = []
    if check == "valor_documento":
        w = _scope_where(gf, params, "s")
        params.append(tol)
        t = f"${len(params)}"
        sql = f"""
            WITH s AS (
                SELECT a.competencia, a.cnpj AS cnpj_filial, d.chave, d.num_doc, d.ser, d.dt_doc, d.cod_part,
                       sum(d.vl_doc) AS vl_doc, sum(d.vl_merc) AS vl_merc
                FROM sf_doc d JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo
                WHERE d.reg = 'C100' AND d.chave IS NOT NULL AND coalesce(d.cod_sit, '00') NOT IN ('02','03','04','05')
                GROUP BY ALL
            ), e AS (
                SELECT d.cnpj_filial, d.chave, a.competencia AS comp_efd, sum(d.vl_doc) AS vl_doc, sum(d.vl_merc) AS vl_merc
                FROM ec_doc d JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo
                WHERE d.reg = 'C100' AND d.chave IS NOT NULL GROUP BY ALL
            )
            SELECT s.competencia, s.cnpj_filial, s.num_doc, s.ser AS serie, s.dt_doc, s.chave, e.comp_efd,
                   CAST(s.vl_doc AS DOUBLE) AS vl_doc_sf, CAST(e.vl_doc AS DOUBLE) AS vl_doc_efd,
                   CAST(coalesce(s.vl_doc, 0) - coalesce(e.vl_doc, 0) AS DOUBLE) AS dif_vl_doc,
                   CAST(s.vl_merc AS DOUBLE) AS vl_merc_sf, CAST(e.vl_merc AS DOUBLE) AS vl_merc_efd,
                   CAST(coalesce(s.vl_merc, 0) - coalesce(e.vl_merc, 0) AS DOUBLE) AS dif_vl_merc
            FROM s JOIN e ON e.cnpj_filial = s.cnpj_filial AND e.chave = s.chave
            WHERE {w} AND (abs(coalesce(s.vl_doc, 0) - coalesce(e.vl_doc, 0)) > {t}
                       OR abs(coalesce(s.vl_merc, 0) - coalesce(e.vl_merc, 0)) > {t})
            ORDER BY abs(coalesce(s.vl_doc, 0) - coalesce(e.vl_doc, 0)) DESC"""
    elif check == "valor_item":
        w = _scope_where(gf, params, "s")
        params.append(tol)
        t = f"${len(params)}"
        sql = f"""
            WITH s AS (
                SELECT a.competencia, a.cnpj AS cnpj_filial, d.chave, d.num_doc, i.num_item, i.cod_item, i.cfop,
                       i.vl_item, i.vl_desc, i.qtd
                FROM sf_c170 i JOIN sf_doc d ON d.file_id = i.file_id AND d.doc_id = i.doc_id
                JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo
                WHERE d.chave IS NOT NULL AND coalesce(d.cod_sit, '00') NOT IN ('02','03','04','05')
            ), e AS (
                SELECT d.cnpj_filial, d.chave, i.num_item, i.cod_item, i.cfop, i.vl_item, i.vl_desc, i.qtd
                FROM ec_item i JOIN ec_doc d ON d.file_id = i.file_id AND d.doc_id = i.doc_id
                JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo
                WHERE i.reg = 'C170' AND d.chave IS NOT NULL
            )
            SELECT s.competencia, s.cnpj_filial, s.num_doc, s.chave, s.num_item, s.cod_item AS cod_item_sf,
                   e.cod_item AS cod_item_efd, s.cfop AS cfop_sf, e.cfop AS cfop_efd,
                   CAST(s.qtd AS DOUBLE) AS qtd_sf, CAST(e.qtd AS DOUBLE) AS qtd_efd,
                   CAST(s.vl_item AS DOUBLE) AS vl_item_sf, CAST(e.vl_item AS DOUBLE) AS vl_item_efd,
                   CAST(coalesce(s.vl_item, 0) - coalesce(e.vl_item, 0) AS DOUBLE) AS dif_vl_item
            FROM s JOIN e ON e.cnpj_filial = s.cnpj_filial AND e.chave = s.chave AND e.num_item = s.num_item
            WHERE {w} AND (abs(coalesce(s.vl_item, 0) - coalesce(e.vl_item, 0)) > {t}
                       OR coalesce(s.cfop, '') <> coalesce(e.cfop, '') OR coalesce(s.cod_item, '') <> coalesce(e.cod_item, ''))
            ORDER BY abs(coalesce(s.vl_item, 0) - coalesce(e.vl_item, 0)) DESC"""
    elif check in ("credito_icms_sem_pis", "credito_pis_sem_icms"):
        w = global_filters_sql(gf, params)
        icms_cred = f"(coalesce(vl_icms, 0) > 0 OR (cst_ipi IN ({_IPI}) AND coalesce(vl_ipi, 0) > 0))"
        pis_cred = f"(cst_pis IN ({_CRED}) AND coalesce(vl_pis, 0) + coalesce(vl_cofins, 0) > 0)"
        cond = f"{icms_cred} AND NOT {pis_cred}" if check == "credito_icms_sem_pis" else f"{pis_cred} AND NOT {icms_cred}"
        sql = f"""
            SELECT competencia, cnpj_filial, nome_filial, num_doc, serie, dt_e_s, chave, cnpj_cpf_fornecedor,
                   razao_social_fornecedor, cod_item, descr_item, tipo_item, cfop, cst_icms, cst_ipi, cst_pis, cst_cofins,
                   CAST(vl_contabil AS DOUBLE) AS vl_contabil, CAST(vl_icms AS DOUBLE) AS vl_icms,
                   CAST(vl_ipi AS DOUBLE) AS vl_ipi, CAST(vl_pis AS DOUBLE) AS vl_pis,
                   CAST(vl_cofins AS DOUBLE) AS vl_cofins, status_efd, nivel_cruzamento_efd
            FROM {FATO}
            WHERE {w} AND tipo_item IN ({_INSUMO}) AND origem NOT LIKE 'EC_%' AND {cond}
            ORDER BY vl_contabil DESC"""
    elif check == "cst_divergente_filiais":
        w = global_filters_sql(gf, params)
        sql = f"""
            WITH b AS (
                SELECT cod_item_unificado, max(descr_item) AS descr_item, cfop, cnpj_filial, max(nome_filial) AS nome_filial,
                       string_agg(DISTINCT cst_icms, '/' ORDER BY cst_icms) AS cst_icms,
                       string_agg(DISTINCT cst_pis, '/' ORDER BY cst_pis) AS cst_pis,
                       string_agg(DISTINCT cst_cofins, '/' ORDER BY cst_cofins) AS cst_cofins,
                       CAST(sum(vl_contabil) AS DOUBLE) AS vl_contabil
                FROM {FATO} WHERE {w} AND NOT flag_item_sintetico AND origem NOT LIKE 'EC_%'
                GROUP BY cod_item_unificado, cfop, cnpj_filial
            ), d AS (
                SELECT cod_item_unificado, cfop FROM b GROUP BY ALL
                HAVING count(DISTINCT cnpj_filial) > 1
                   AND (count(DISTINCT coalesce(cst_icms, '-')) > 1 OR count(DISTINCT coalesce(cst_pis, '-')) > 1
                        OR count(DISTINCT coalesce(cst_cofins, '-')) > 1)
            )
            SELECT b.* FROM b JOIN d USING (cod_item_unificado, cfop)
            ORDER BY b.cod_item_unificado, b.cfop, b.cnpj_filial"""
    elif check == "ec_sem_sf":
        w = _scope_where(gf, params, "e")
        sql = f"""
            WITH e AS (
                SELECT a.competencia, d.cnpj_filial, d.chave, d.num_doc, d.ser, d.dt_doc, d.cod_part,
                       CAST(d.vl_doc AS DOUBLE) AS vl_doc, CAST(d.vl_pis AS DOUBLE) AS vl_pis,
                       CAST(d.vl_cofins AS DOUBLE) AS vl_cofins
                FROM ec_doc d JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo
                WHERE d.reg = 'C100' AND d.chave IS NOT NULL
            ), sfk AS (
                SELECT DISTINCT a.cnpj AS cnpj_filial, d.chave FROM sf_doc d
                JOIN sys_arquivos_importados a ON a.id_arquivo = d.file_id AND a.ativo WHERE d.reg = 'C100'
            ), cov AS (
                SELECT DISTINCT cnpj, competencia FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'ICMS_IPI'
            )
            SELECT e.* FROM e
            JOIN cov ON cov.cnpj = e.cnpj_filial AND cov.competencia = e.competencia
            WHERE {w} AND NOT EXISTS (SELECT 1 FROM sfk WHERE sfk.cnpj_filial = e.cnpj_filial AND sfk.chave = e.chave)
            ORDER BY e.vl_doc DESC"""
    elif check == "item_sem_c190":
        w = global_filters_sql(gf, params)
        sql = f"""
            SELECT competencia, cnpj_filial, num_doc, chave, num_item, cod_item, cfop, cst_icms,
                   CAST(aliq_icms AS DOUBLE) AS aliq_icms, CAST(vl_item AS DOUBLE) AS vl_item,
                   CAST(vl_contabil AS DOUBLE) AS vl_contabil
            FROM {FATO} WHERE {w} AND flag_sem_c190 ORDER BY vl_item DESC"""
    else:
        raise ValueError(f"Verificação desconhecida: {check}")
    return db.query(sql + f" LIMIT {int(limit)}", params)


def summary(db, gf: dict | None = None) -> list[dict]:
    out = []
    for k, label in CHECKS.items():
        try:
            n = run_check(db, k, gf, limit=100_000).height
        except Exception as e:  # noqa: BLE001
            n = f"erro: {e}"
        out.append({"verificacao": k, "descricao": label, "ocorrencias": n})
    return out
