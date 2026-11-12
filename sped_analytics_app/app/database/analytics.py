"""Consultas analíticas da tela principal: agregação multinível, visão mês a mês e drill-down até a NF."""
from __future__ import annotations

from typing import Any

import polars as pl

from app import config
from app.database.filter_builder import FATO, where_clause

# Dimensões de agrupamento: chave -> (rótulo, expressão-chave, expressão-descrição)
DIMENSIONS: dict[str, tuple[str, str, str | None]] = {
    "filial": ("Empresa/Filial", "cnpj_filial", "max(nome_filial)"),
    "fornecedor": ("Fornecedor", "cnpj_cpf_fornecedor", "max(razao_social_fornecedor)"),
    "cfop": ("CFOP", "cfop", None),
    "item": ("Item", "cod_item_unificado", "max(descr_item)"),
    "competencia": ("Competência", "competencia", None),
    "ano": ("Ano", "left(competencia, 4)", None),
    "uf_filial": ("UF Filial", "uf_filial", None),
    "raiz_fornecedor": ("Raiz CNPJ Fornecedor", "raiz_cnpj_fornecedor", "max(razao_social_fornecedor)"),
    "uf_fornecedor": ("UF Fornecedor", "uf_fornecedor", None),
    "ncm": ("NCM", "cod_ncm", None),
    "tipo_item": ("Tipo Item", "tipo_item", None),
    "item_global": ("Item Global (NCM|Código)", "chave_item_global", "max(descr_item)"),
    "cst_icms": ("CST ICMS", "cst_icms", None),
    "cst_pis": ("CST PIS", "cst_pis", None),
    "cst_cofins": ("CST COFINS", "cst_cofins", None),
    "nat_bc_cred": ("Nat. BC Crédito", "nat_bc_cred", None),
    "cod_cta": ("Conta Contábil", "cod_cta", None),
    "origem": ("Origem da Linha", "origem", None),
    "status_efd": ("Status EFD-Contribuições", "status_efd", None),
    "nivel": ("Nível Cruzamento", "nivel_cruzamento_efd", None),
}
DEFAULT_HIERARCHY = ["filial", "fornecedor", "cfop", "item"]

# Métricas: chave -> (rótulo, expressão agregada, tipo)  tipo: money|qty|text|int
METRICS: dict[str, tuple[str, str, str]] = {
    "qtd": ("Qtd. Comprada", "sum(qtd)", "qty"),
    "unid": ("Unid.", "CASE WHEN count(DISTINCT unid) <= 1 THEN max(unid) ELSE 'DIVERSAS' END", "text"),
    "preco_medio": ("Preço Médio Unit.", "sum(vl_item) / nullif(sum(qtd), 0)", "price"),
    "vl_item": ("Valor Bruto Mercadoria", "sum(vl_item)", "money"),
    "vl_desc": ("Descontos", "sum(vl_desc)", "money"),
    "vl_contabil": ("Valor Contábil", "sum(vl_contabil)", "money"),
    "vl_bc_icms": ("BC ICMS", "sum(vl_bc_icms)", "money"),
    "vl_icms": ("ICMS", "sum(vl_icms)", "money"),
    "vl_bc_icms_st": ("BC ICMS-ST", "sum(vl_bc_icms_st)", "money"),
    "vl_icms_st_fcp": ("ICMS-ST + FCP", "sum(coalesce(vl_icms_st, 0) + coalesce(vl_fcp, 0) + coalesce(vl_fcp_st, 0))",
                       "money"),
    "vl_bc_ipi": ("BC IPI", "sum(vl_bc_ipi)", "money"),
    "vl_ipi": ("IPI", "sum(vl_ipi)", "money"),
    "cst_pis": ("CST PIS", "string_agg(DISTINCT cst_pis, ',' ORDER BY cst_pis)", "text"),
    "vl_bc_pis": ("BC PIS", "sum(vl_bc_pis)", "money"),
    "vl_pis": ("PIS", "sum(vl_pis)", "money"),
    "cst_cofins": ("CST COFINS", "string_agg(DISTINCT cst_cofins, ',' ORDER BY cst_cofins)", "text"),
    "vl_bc_cofins": ("BC COFINS", "sum(vl_bc_cofins)", "money"),
    "vl_cofins": ("COFINS", "sum(vl_cofins)", "money"),
    "vl_trib_recuperaveis": ("Tributos Recuperáveis", "sum(vl_trib_recuperaveis)", "money"),
    "vl_custo_liquido": ("Custo Líquido de Entrada", "sum(vl_custo_liquido)", "money"),
    "n_docs": ("Qtd. Documentos", "count(DISTINCT coalesce(file_id_sf, file_id_ec) || '-' || coalesce(doc_id, 0) "
                                  "|| '-' || origem)", "int"),
    "n_linhas": ("Qtd. Linhas", "count(*)", "int"),
}
DEFAULT_METRICS = ["qtd", "unid", "preco_medio", "vl_item", "vl_desc", "vl_contabil", "vl_bc_icms", "vl_icms",
                   "vl_bc_icms_st", "vl_icms_st_fcp", "vl_bc_ipi", "vl_ipi", "cst_pis", "vl_bc_pis", "vl_pis",
                   "cst_cofins", "vl_bc_cofins", "vl_cofins", "vl_trib_recuperaveis", "vl_custo_liquido", "n_docs"]


def _metric_sql(keys: list[str]) -> str:
    out = []
    for k in keys:
        _, expr, typ = METRICS[k]
        if typ in ("money",):
            expr = f"CAST(coalesce({expr}, 0) AS DOUBLE)"
        elif typ in ("qty", "price"):
            expr = f"CAST({expr} AS DOUBLE)"
        out.append(f"{expr} AS \"{k}\"")
    return ", ".join(out)


def _path_extra(path: list[tuple[str, Any]] | None) -> list[tuple[str, Any]]:
    return [(DIMENSIONS[d][1], v) for d, v in (path or [])]


def aggregate(db, gf: dict | None, rules: dict | None, dims: list[str], metrics: list[str] | None = None,
              path: list[tuple[str, Any]] | None = None, limit: int = config.UI_MAX_GRID_ROWS,
              order_by: str = "vl_contabil") -> pl.DataFrame:
    """Agrega a fato pelas dimensões `dims` (podem ser várias = visão plana multinível),
    restrita pelo caminho de drill `path` [(dim, valor), ...]."""
    metrics = metrics or DEFAULT_METRICS
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    sel, grp = [], []
    for d in dims:
        _, key, desc = DIMENSIONS[d]
        sel.append(f"{key} AS \"{d}\"")
        grp.append(key)
        if desc:
            sel.append(f"{desc} AS \"{d}__desc\"")
    msql = _metric_sql(metrics)
    order = f'"{order_by}" DESC NULLS LAST' if order_by in metrics else "1"
    sql = (f"SELECT {', '.join(sel + [msql]) if sel else msql} FROM {FATO} WHERE {where}"
           + (f" GROUP BY {', '.join(grp)}" if grp else "") + f" ORDER BY {order} LIMIT {int(limit)}")
    return db.query(sql, params)


def totals(db, gf: dict | None, rules: dict | None, metrics: list[str] | None = None,
           path: list[tuple[str, Any]] | None = None) -> dict:
    df = aggregate(db, gf, rules, [], metrics, path, limit=1)
    return df.to_dicts()[0] if df.height else {}


def monthly_pivot(db, gf: dict | None, rules: dict | None, dims: list[str], metric: str = "vl_contabil",
                  path: list[tuple[str, Any]] | None = None, limit: int = config.UI_MAX_GRID_ROWS) -> pl.DataFrame:
    """Visão mês a mês: linhas = dims, colunas = competências, valores = métrica escolhida + total."""
    df = aggregate(db, gf, rules, dims + ["competencia"], [metric], path, limit=10_000_000)
    if df.height == 0:
        return df
    keys = [c for c in df.columns if c not in ("competencia", metric)]
    descs = [c for c in keys if c.endswith("__desc")]
    base_keys = [c for c in keys if c not in descs]
    if descs:
        dmap = df.group_by(base_keys).agg([pl.col(c).max() for c in descs])
    piv = df.select(base_keys + ["competencia", metric]).pivot(
        on="competencia", index=base_keys or None, values=metric, aggregate_function="sum") if base_keys else \
        df.select(["competencia", metric]).with_columns(pl.lit("TOTAL").alias("_t")).pivot(
            on="competencia", index="_t", values=metric, aggregate_function="sum")
    comps = sorted(c for c in piv.columns if c not in base_keys and c != "_t")
    piv = piv.with_columns(pl.sum_horizontal([pl.col(c).fill_null(0) for c in comps]).alias("TOTAL"))
    if descs:
        piv = piv.join(dmap, on=base_keys, how="left")
    ordered = []
    for k in base_keys:
        ordered.append(k)
        if f"{k}__desc" in piv.columns:
            ordered.append(f"{k}__desc")
    piv = piv.select(ordered + comps + ["TOTAL"]).sort("TOTAL", descending=True)
    return piv.head(limit)


def documents(db, gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None,
              limit: int = config.UI_MAX_DRILL_ROWS) -> pl.DataFrame:
    """Drill-down: notas fiscais/documentos que compõem a linha consolidada selecionada."""
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    sql = f"""
        SELECT competencia, cnpj_filial, max(nome_filial) AS nome_filial, reg_doc, cod_mod, num_doc, serie,
               dt_doc, dt_e_s, chave, cnpj_cpf_fornecedor, max(razao_social_fornecedor) AS razao_social_fornecedor,
               string_agg(DISTINCT cfop, ',' ORDER BY cfop) AS cfops, count(*) AS linhas,
               CAST(sum(qtd) AS DOUBLE) AS qtd, CAST(sum(vl_item) AS DOUBLE) AS vl_item,
               CAST(sum(vl_contabil) AS DOUBLE) AS vl_contabil, CAST(sum(vl_icms) AS DOUBLE) AS vl_icms,
               CAST(sum(coalesce(vl_icms_st, 0) + coalesce(vl_fcp, 0) + coalesce(vl_fcp_st, 0)) AS DOUBLE) AS vl_icms_st_fcp,
               CAST(sum(vl_ipi) AS DOUBLE) AS vl_ipi, CAST(sum(vl_pis) AS DOUBLE) AS vl_pis,
               CAST(sum(vl_cofins) AS DOUBLE) AS vl_cofins, max(status_efd) AS status_efd,
               string_agg(DISTINCT origem, ',') AS origem, coalesce(file_id_sf, file_id_ec) AS file_id, doc_id
        FROM {FATO} WHERE {where}
        GROUP BY competencia, cnpj_filial, reg_doc, cod_mod, num_doc, serie, dt_doc, dt_e_s, chave,
                 cnpj_cpf_fornecedor, coalesce(file_id_sf, file_id_ec), doc_id
        ORDER BY dt_e_s NULLS LAST, num_doc LIMIT {int(limit)}"""
    return db.query(sql, params)


def lines(db, gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None,
          limit: int | None = config.UI_MAX_DRILL_ROWS, columns: list[str] | None = None) -> pl.DataFrame:
    """Linhas detalhadas da tabela fato (itens), para conferência e exportação."""
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    lim = f" LIMIT {int(limit)}" if limit else ""
    return db.query(f"SELECT {cols} FROM {FATO} WHERE {where} ORDER BY competencia, cnpj_filial, dt_e_s, num_doc, "
                    f"num_item{lim}", params)


def lines_sql(gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None) -> tuple[str, list]:
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    return (f"SELECT * FROM {FATO} WHERE {where} ORDER BY competencia, cnpj_filial, dt_e_s, num_doc, num_item",
            params)


def distinct_values(db, column: str, search: str = "", limit: int = 300) -> list[dict]:
    """Opções para os seletores dos filtros globais (com descrição e busca instantânea)."""
    spec = {
        "competencia": ("competencia", "competencia"),
        "filial": ("cnpj_filial", "max(nome_filial) || ' — ' || max(uf_filial)"),
        "uf_filial": ("uf_filial", "uf_filial"),
        "fornecedor": ("cnpj_cpf_fornecedor", "max(razao_social_fornecedor)"),
        "raiz_fornecedor": ("raiz_cnpj_fornecedor", "max(razao_social_fornecedor)"),
        "cfop": ("cfop", "cfop"),
        "item": ("cod_item_unificado", "max(descr_item)"),
        "ncm": ("cod_ncm", "cod_ncm"),
    }[column]
    key, label = spec
    params: list = []
    where = "TRUE"
    if search:
        params.append(search.lower())
        where = f"contains(lower(coalesce({key}, '') || ' ' || coalesce(CAST({label.replace('max(', '(')} AS VARCHAR), '')), $1)"
    rows = db.query(f"SELECT {key} AS v, {label} AS l, CAST(sum(vl_contabil) AS DOUBLE) AS t FROM {FATO} "
                    f"WHERE {key} IS NOT NULL AND {where} GROUP BY {key} ORDER BY "
                    f"{'v' if column == 'competencia' else 't DESC'} LIMIT {int(limit)}", params)
    return rows.to_dicts()
