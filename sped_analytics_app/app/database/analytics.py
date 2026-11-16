"""Consultas analíticas da tela principal: agregação multinível, visão mês a mês e drill-down até a NF.

Desempenho: toda consulta passa por `aggregates.pick_source`, que escolhe a menor tabela pré-somada capaz de
respondê-la (agg_filial < agg_fornecedor < agg_item < fato). A fato linha a linha só é lida quando a pergunta
exige o documento (drill-down, contagem de notas) ou um filtro sobre valores de linha (ex.: VL_ICMS > 0).
"""
from __future__ import annotations

from typing import Any

import polars as pl

from app import config
from app.database.aggregates import FATO, pick_source
from app.database.filter_builder import columns_used, where_clause

# Dimensões de agrupamento: chave -> (rótulo, coluna-chave, expressão-descrição, coluna da descrição)
DIMENSIONS: dict[str, tuple[str, str, str | None, str | None]] = {
    "filial": ("Empresa/Filial", "cnpj_filial", "max(nome_filial)", "nome_filial"),
    "fornecedor": ("Fornecedor", "cnpj_cpf_fornecedor", "max(razao_social_fornecedor)", "razao_social_fornecedor"),
    "cfop": ("CFOP", "cfop", None, None),
    "item": ("Item", "cod_item_unificado", "max(descr_item)", "descr_item"),
    "competencia": ("Competência", "competencia", None, None),
    "ano": ("Ano", "left(competencia, 4)", None, None),
    "uf_filial": ("UF Filial", "uf_filial", None, None),
    "raiz_fornecedor": ("Raiz CNPJ Fornecedor", "raiz_cnpj_fornecedor", "max(razao_social_fornecedor)",
                        "razao_social_fornecedor"),
    "uf_fornecedor": ("UF Fornecedor", "uf_fornecedor", None, None),
    "ncm": ("NCM", "cod_ncm", None, None),
    "tipo_item": ("Tipo Item", "tipo_item", None, None),
    "item_global": ("Item Global (NCM|Código)", "chave_item_global", "max(descr_item)", "descr_item"),
    "cst_icms": ("CST ICMS", "cst_icms", None, None),
    "cst_pis": ("CST PIS", "cst_pis", None, None),
    "cst_cofins": ("CST COFINS", "cst_cofins", None, None),
    "nat_bc_cred": ("Nat. BC Crédito", "nat_bc_cred", None, None),
    "cod_cta": ("Conta Contábil", "cod_cta", None, None),
    "origem": ("Origem da Linha", "origem", None, None),
    "status_efd": ("Status EFD-Contribuições", "status_efd", None, None),
    "nivel": ("Nível Cruzamento", "nivel_cruzamento_efd", None, None),
}
_DIM_COLS = {"ano": {"competencia"}}
DEFAULT_HIERARCHY = ["filial", "fornecedor", "cfop", "item"]


def dim_columns(dim: str) -> set[str]:
    _, key, _, desc_col = DIMENSIONS[dim]
    cols = set(_DIM_COLS.get(dim, {key}))
    if desc_col:
        cols.add(desc_col)
    return cols


# Métricas: chave -> (rótulo, expressão agregada, tipo, colunas usadas)   tipo: money|qty|price|text|int
# A mesma expressão vale para a fato e para as agregadas (soma de somas), exceto n_linhas e n_docs.
METRICS: dict[str, tuple[str, str, str, set[str]]] = {
    "qtd": ("Qtd. Comprada", "sum(qtd)", "qty", {"qtd"}),
    "unid": ("Unid.", "CASE WHEN min(unid) IS NOT DISTINCT FROM max(unid) THEN min(unid) ELSE 'DIVERSAS' END",
             "text", {"unid"}),
    "preco_medio": ("Preço Médio Unit.", "sum(vl_item) / nullif(sum(qtd), 0)", "price", {"vl_item", "qtd"}),
    "vl_item": ("Valor Bruto Mercadoria", "sum(vl_item)", "money", {"vl_item"}),
    "vl_desc": ("Descontos", "sum(vl_desc)", "money", {"vl_desc"}),
    "vl_contabil": ("Valor Contábil", "sum(vl_contabil)", "money", {"vl_contabil"}),
    "vl_bc_icms": ("BC ICMS", "sum(vl_bc_icms)", "money", {"vl_bc_icms"}),
    "vl_icms": ("ICMS", "sum(vl_icms)", "money", {"vl_icms"}),
    "vl_bc_icms_st": ("BC ICMS-ST", "sum(vl_bc_icms_st)", "money", {"vl_bc_icms_st"}),
    "vl_icms_st_fcp": ("ICMS-ST + FCP",
                       "sum(coalesce(vl_icms_st, 0) + coalesce(vl_fcp, 0) + coalesce(vl_fcp_st, 0))", "money",
                       {"vl_icms_st", "vl_fcp", "vl_fcp_st"}),
    "vl_bc_ipi": ("BC IPI", "sum(vl_bc_ipi)", "money", {"vl_bc_ipi"}),
    "vl_ipi": ("IPI", "sum(vl_ipi)", "money", {"vl_ipi"}),
    "cst_pis": ("CST PIS", "string_agg(DISTINCT cst_pis, ',' ORDER BY cst_pis)", "text", {"cst_pis"}),
    "vl_bc_pis": ("BC PIS", "sum(vl_bc_pis)", "money", {"vl_bc_pis"}),
    "vl_pis": ("PIS", "sum(vl_pis)", "money", {"vl_pis"}),
    "cst_cofins": ("CST COFINS", "string_agg(DISTINCT cst_cofins, ',' ORDER BY cst_cofins)", "text", {"cst_cofins"}),
    "vl_bc_cofins": ("BC COFINS", "sum(vl_bc_cofins)", "money", {"vl_bc_cofins"}),
    "vl_cofins": ("COFINS", "sum(vl_cofins)", "money", {"vl_cofins"}),
    "vl_trib_recuperaveis": ("Tributos Recuperáveis", "sum(vl_trib_recuperaveis)", "money", {"vl_trib_recuperaveis"}),
    "vl_custo_liquido": ("Custo Líquido de Entrada", "sum(vl_custo_liquido)", "money", {"vl_custo_liquido"}),
    "n_linhas": ("Qtd. Linhas", "", "int", {"n_linhas"}),
    "n_docs": ("Qtd. Documentos (mais lento)", "count(DISTINCT doc_key)", "int", set()),
}
ROW_LEVEL_METRICS = {"n_docs"}   # exigem a fato linha a linha
DEFAULT_METRICS = ["qtd", "unid", "preco_medio", "vl_item", "vl_desc", "vl_contabil", "vl_bc_icms", "vl_icms",
                   "vl_bc_icms_st", "vl_icms_st_fcp", "vl_bc_ipi", "vl_ipi", "cst_pis", "vl_bc_pis", "vl_pis",
                   "cst_cofins", "vl_bc_cofins", "vl_cofins", "vl_trib_recuperaveis", "vl_custo_liquido", "n_linhas"]


def _metric_expr(k: str, source: str) -> str:
    _, expr, typ, _ = METRICS[k]
    if k == "n_linhas":
        expr = "count(*)" if source == FATO else "sum(n_linhas)"
    if typ == "money":
        return f"CAST(coalesce({expr}, 0) AS DOUBLE)"
    if typ in ("qty", "price"):
        return f"CAST({expr} AS DOUBLE)"
    if typ == "int":
        return f"CAST(coalesce({expr}, 0) AS BIGINT)"
    return expr


def _metric_sql(keys: list[str], source: str) -> str:
    return ", ".join(f"{_metric_expr(k, source)} AS \"{k}\"" for k in keys)


def _path_extra(path: list[tuple[str, Any]] | None) -> list[tuple[str, Any]]:
    return [(DIMENSIONS[d][1], v) for d, v in (path or [])]


def source_for(gf: dict | None, rules: dict | None, dims: list[str], metrics: list[str],
               path: list[tuple[str, Any]] | None = None) -> str:
    fcols = columns_used(gf, rules)
    for d in list(dims) + [p[0] for p in (path or [])]:
        fcols |= dim_columns(d)
    mcols: set[str] = set()
    for m in metrics:
        mcols |= METRICS[m][3]
    return pick_source(fcols, mcols, needs_rows=bool(ROW_LEVEL_METRICS & set(metrics)))


def aggregate(db, gf: dict | None, rules: dict | None, dims: list[str], metrics: list[str] | None = None,
              path: list[tuple[str, Any]] | None = None, limit: int | None = config.UI_MAX_GRID_ROWS,
              order_by: str = "vl_contabil", source: str | None = None) -> pl.DataFrame:
    """Agrega pelas dimensões `dims` (várias = visão plana multinível), restrita pelo caminho de drill `path`.
    `source` força uma tabela específica (usado nos testes de equivalência)."""
    metrics = metrics or DEFAULT_METRICS
    src = source or source_for(gf, rules, dims, metrics, path)
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    sel, grp = [], []
    for d in dims:
        _, key, desc, _ = DIMENSIONS[d]
        sel.append(f"{key} AS \"{d}\"")
        grp.append(key)
        if desc:
            sel.append(f"{desc} AS \"{d}__desc\"")
    msql = _metric_sql(metrics, src)
    order = f'"{order_by}" DESC NULLS LAST' if order_by in metrics else "1"
    if not grp:
        return db.query(f"SELECT {msql} FROM {src} WHERE {where}", params)
    if limit and order_by in metrics and (len(dims) > 1 or src == FATO):
        # Duas fases: (1) só as N maiores chaves pela métrica de ordenação — passada leve;
        # (2) métricas completas (descrições, listas de CST...) apenas para essas chaves.
        gk = [f"g{i}" for i in range(len(grp))]
        top = (f"SELECT {', '.join(f'{k} AS {g}' for k, g in zip(grp, gk))}, {_metric_expr(order_by, src)} AS s "
               f"FROM {src} WHERE {where} GROUP BY {', '.join(grp)} ORDER BY s DESC NULLS LAST LIMIT {int(limit)}")
        on = " AND ".join(f"{k} IS NOT DISTINCT FROM top.{g}" for k, g in zip(grp, gk))
        sql = (f"WITH top AS ({top}) SELECT {', '.join(sel + [msql])} FROM {src} JOIN top ON {on} "
               f"WHERE {where} GROUP BY {', '.join(grp)} ORDER BY {order}")
    else:
        sql = (f"SELECT {', '.join(sel + [msql])} FROM {src} WHERE {where} GROUP BY {', '.join(grp)} "
               f"ORDER BY {order}" + (f" LIMIT {int(limit)}" if limit else ""))
    return db.query(sql, params)


def totals(db, gf: dict | None, rules: dict | None, metrics: list[str] | None = None,
           path: list[tuple[str, Any]] | None = None) -> dict:
    df = aggregate(db, gf, rules, [], metrics, path, limit=None)
    return df.to_dicts()[0] if df.height else {}


def count_documents(db, gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None) -> int:
    """Quantidade de documentos distintos (lê a fato; executada à parte para não atrasar a grade)."""
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    return int(db.scalar(f"SELECT count(DISTINCT doc_key) FROM {FATO} WHERE {where}", params) or 0)


def monthly_pivot(db, gf: dict | None, rules: dict | None, dims: list[str], metric: str = "vl_contabil",
                  path: list[tuple[str, Any]] | None = None, limit: int = config.UI_MAX_GRID_ROWS
                  ) -> tuple[pl.DataFrame, dict]:
    """Visão mês a mês: linhas = dims, colunas = competências, valores = métrica + total.
    Devolve (grade limitada às maiores linhas, totais reais por competência)."""
    df = aggregate(db, gf, rules, dims + ["competencia"], [metric], path, limit=None)
    if df.height == 0:
        return df, {}
    tot = df.group_by("competencia").agg(pl.col(metric).sum())
    totals_row = {r["competencia"]: r[metric] for r in tot.to_dicts()}
    totals_row["TOTAL"] = float(df[metric].sum() or 0)
    keys = [c for c in df.columns if c not in ("competencia", metric)]
    descs = [c for c in keys if c.endswith("__desc")]
    base_keys = [c for c in keys if c not in descs]
    piv = df.select(base_keys + ["competencia", metric]).pivot(
        on="competencia", index=base_keys, values=metric, aggregate_function="sum")
    comps = sorted(c for c in piv.columns if c not in base_keys)
    piv = piv.with_columns(pl.sum_horizontal([pl.col(c).fill_null(0) for c in comps]).alias("TOTAL"))
    if descs:
        dmap = df.group_by(base_keys).agg([pl.col(c).max() for c in descs])
        piv = piv.join(dmap, on=base_keys, how="left", nulls_equal=True)
    ordered = []
    for k in base_keys:
        ordered.append(k)
        if f"{k}__desc" in piv.columns:
            ordered.append(f"{k}__desc")
    piv = piv.select(ordered + comps + ["TOTAL"]).sort("TOTAL", descending=True)
    return piv.head(limit), totals_row


def documents(db, gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None,
              limit: int = config.UI_MAX_DRILL_ROWS) -> pl.DataFrame:
    """Drill-down: notas fiscais/documentos que compõem a linha consolidada selecionada."""
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    sql = f"""
        SELECT any_value(competencia) AS competencia, any_value(cnpj_filial) AS cnpj_filial,
               any_value(nome_filial) AS nome_filial, any_value(reg_doc) AS reg_doc, any_value(cod_mod) AS cod_mod,
               any_value(num_doc) AS num_doc, any_value(serie) AS serie, any_value(dt_doc) AS dt_doc,
               any_value(dt_e_s) AS dt_e_s, any_value(chave) AS chave,
               any_value(cnpj_cpf_fornecedor) AS cnpj_cpf_fornecedor,
               any_value(razao_social_fornecedor) AS razao_social_fornecedor,
               string_agg(DISTINCT cfop, ',' ORDER BY cfop) AS cfops, count(*) AS linhas,
               CAST(sum(qtd) AS DOUBLE) AS qtd, CAST(sum(vl_item) AS DOUBLE) AS vl_item,
               CAST(sum(vl_contabil) AS DOUBLE) AS vl_contabil, CAST(sum(vl_icms) AS DOUBLE) AS vl_icms,
               CAST(sum(coalesce(vl_icms_st, 0) + coalesce(vl_fcp, 0) + coalesce(vl_fcp_st, 0)) AS DOUBLE) AS vl_icms_st_fcp,
               CAST(sum(vl_ipi) AS DOUBLE) AS vl_ipi, CAST(sum(vl_pis) AS DOUBLE) AS vl_pis,
               CAST(sum(vl_cofins) AS DOUBLE) AS vl_cofins, max(status_efd) AS status_efd,
               string_agg(DISTINCT nivel_cruzamento_efd, ',') AS nivel_cruzamento_efd,
               string_agg(DISTINCT origem, ',') AS origem
        FROM {FATO} WHERE {where}
        GROUP BY doc_key
        ORDER BY dt_e_s NULLS LAST, num_doc LIMIT {int(limit)}"""
    return db.query(sql, params)


def lines(db, gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None,
          limit: int | None = config.UI_MAX_DRILL_ROWS, columns: list[str] | None = None) -> pl.DataFrame:
    """Linhas detalhadas da tabela fato (itens), para conferência e exportação."""
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "* EXCLUDE (doc_key)"
    lim = f" LIMIT {int(limit)}" if limit else ""
    return db.query(f"SELECT {cols} FROM {FATO} WHERE {where} ORDER BY competencia, cnpj_filial, dt_e_s, num_doc, "
                    f"num_item{lim}", params)


def lines_sql(gf: dict | None, rules: dict | None, path: list[tuple[str, Any]] | None = None) -> tuple[str, list]:
    params: list = []
    where = where_clause(gf, rules, params, _path_extra(path))
    return (f"SELECT * EXCLUDE (doc_key) FROM {FATO} WHERE {where} "
            f"ORDER BY competencia, cnpj_filial, dt_e_s, num_doc, num_item", params)


_OPTION_SPEC = {
    "competencia": ("competencia", None, set()),
    "filial": ("cnpj_filial", "max(nome_filial) || ' — ' || coalesce(max(uf_filial), '')", {"nome_filial", "uf_filial"}),
    "uf_filial": ("uf_filial", None, set()),
    "fornecedor": ("cnpj_cpf_fornecedor", "max(razao_social_fornecedor)", {"razao_social_fornecedor"}),
    "raiz_fornecedor": ("raiz_cnpj_fornecedor", "max(razao_social_fornecedor)", {"razao_social_fornecedor"}),
    "cfop": ("cfop", None, set()),
    "item": ("cod_item_unificado", "max(descr_item)", {"descr_item"}),
    "ncm": ("cod_ncm", None, set()),
}


def distinct_values(db, column: str, limit: int = 5000) -> list[dict]:
    """Opções dos seletores dos filtros globais, ordenadas por relevância (valor contábil).
    Lê sempre a menor tabela agregada que contém a coluna."""
    key, label, extra = _OPTION_SPEC[column]
    src = pick_source({key} | extra, {"vl_contabil"})
    order = "v" if column == "competencia" else "t DESC NULLS LAST"
    rows = db.query(f"SELECT {key} AS v, {label or key} AS l, CAST(sum(vl_contabil) AS DOUBLE) AS t FROM {src} "
                    f"WHERE {key} IS NOT NULL GROUP BY {key} ORDER BY {order} LIMIT {int(limit)}")
    return rows.to_dicts()
