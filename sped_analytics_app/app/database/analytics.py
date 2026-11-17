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
    "filial": ("Unidade (filial)", "cnpj_filial", "max(nome_filial)", "nome_filial"),
    "fornecedor": ("Fornecedor", "cnpj_cpf_fornecedor", "max(razao_social_fornecedor)", "razao_social_fornecedor"),
    "cfop": ("CFOP", "cfop", None, None),
    "item": ("Item (código)", "cod_item_unificado", "max(descr_item)", "descr_item"),
    "descr_item": ("Descrição do item", "descr_item", None, None),
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
    "cod_mod": ("Modelo do documento", "cod_mod", None, None),
    "aliq_icms": ("Alíquota ICMS", "aliq_icms", None, None),
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


# --------------------------------------------------------------------------------------
# Relatório dinâmico (tabela dinâmica): linhas x [coluna] x valores, sempre sobre a base consolidada
# --------------------------------------------------------------------------------------
ADDITIVE = {k for k, v in METRICS.items() if v[2] in ("money", "qty", "int") and k != "n_docs"}
MAX_PIVOT_COLUMNS = 60
HAVING_OPS = {">": ">", ">=": ">=", "<": "<", "<=": "<=", "=": "=", "!=": "<>", "zero": "= 0", "nao_zero": "<> 0"}


class ReportError(ValueError):
    pass


def _num(v) -> float:
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError as e:
        raise ReportError(f"Valor numérico inválido: {v!r}") from e


def report(db, gf: dict | None, rules: dict | None, rows: list[str], col: str | None, metrics: list[str],
           sort: dict | None = None, limit: int | None = config.UI_MAX_GRID_ROWS, texto: str = "",
           having: list[dict] | None = None) -> dict:
    """Relatório dinâmico (linhas x coluna opcional x valores).

    Sem duplicidade por construção: cada linha da tabela fato (SPED Fiscal com o PIS/COFINS da EFD já atribuído
    a uma única linha, mais as linhas "somente EFD") entra em exatamente um grupo. Os totais são calculados direto
    da base — com filtro por valor ativo, somente sobre os grupos que passam no filtro —, nunca somando o que está
    na tela.

    sort   = {"by": <métrica ou dimensão das linhas>, "dir": "desc" | "asc"}
    texto  = busca nos códigos e descrições das dimensões das linhas
    having = [{"metric": ..., "op": ">", "value": ...}] — filtros por valor sobre cada grupo (linha do relatório)
    """
    rows = [d for d in rows if d in DIMENSIONS]
    if len(set(rows)) != len(rows):
        raise ReportError("A mesma dimensão aparece duas vezes nas linhas")
    if col and (col not in DIMENSIONS or col in rows):
        raise ReportError("Dimensão de colunas inválida (não pode repetir uma das linhas)")
    metrics = [m for m in dict.fromkeys(metrics) if m in METRICS]
    if col:
        metrics = [m for m in metrics if METRICS[m][2] != "text"]   # listas de CST não cabem em células cruzadas
    if not metrics:
        raise ReportError("Escolha ao menos um valor" + (" numérico" if col else ""))

    having = [h for h in (having or []) if h.get("metric") in METRICS and METRICS[h["metric"]][2] != "text"]
    sort = sort or {}
    sdir = "ASC" if sort.get("dir") == "asc" else "DESC"
    sby = sort.get("by")
    if sby not in rows and (sby not in METRICS or METRICS[sby][2] == "text"):
        sby = next((m for m in metrics if METRICS[m][2] != "text"), "vl_contabil")

    used_metrics = list(dict.fromkeys(metrics + [h["metric"] for h in having] + ([sby] if sby in METRICS else [])))
    dims_all = rows + ([col] if col else [])
    src = source_for(gf, rules, dims_all, used_metrics)
    params: list = []
    where = where_clause(gf, rules, params)
    if texto and texto.strip() and rows:
        parts = []
        for d in rows:
            _, key, _, desc_col = DIMENSIONS[d]
            parts.append(f"coalesce(CAST({key} AS VARCHAR), '')")
            if desc_col:
                parts.append(f"coalesce({desc_col}, '')")
        params.append(texto.strip().lower())
        concat = " || ' ' || ".join(parts)
        where += f" AND contains(lower({concat}), ${len(params)})"

    keys = [DIMENSIONS[d][1] for d in rows]
    gk = [f"g{i}" for i in range(len(keys))]
    on = " AND ".join(f"{k} IS NOT DISTINCT FROM q.{g}" for k, g in zip(keys, gk))
    hv = []
    for h in having:
        op = HAVING_OPS.get(h.get("op"))
        if not op:
            raise ReportError(f"Operador inválido: {h.get('op')}")
        expr = f"coalesce({_metric_expr(h['metric'], src)}, 0)"
        if h["op"] in ("zero", "nao_zero"):
            hv.append(f"{expr} {op}")
        else:
            params.append(_num(h.get("value")))
            hv.append(f"{expr} {op} ${len(params)}")
    having_sql = f" HAVING {' AND '.join(hv)}" if hv else ""

    sel = []
    for d in rows:
        _, key, desc, _ = DIMENSIONS[d]
        sel.append(f'{key} AS "{d}"')
        if desc:
            sel.append(f'{desc} AS "{d}__desc"')
    col_key = DIMENSIONS[col][1] if col else None
    if col:
        sel.append(f'{col_key} AS "__col"')
    msql = _metric_sql(metrics, src)

    row_count, truncated = None, False
    if rows:
        s_expr = _metric_expr(sby, src) if sby in METRICS else DIMENSIONS[sby][1]
        grouped = (f"SELECT {', '.join(f'{k} AS {g}' for k, g in zip(keys, gk))}, {s_expr} AS s FROM {src} "
                   f"WHERE {where} GROUP BY {', '.join(keys)}{having_sql}")
        lim = f" LIMIT {int(limit)}" if limit else ""
        top = (f"SELECT *, row_number() OVER (ORDER BY s {sdir} NULLS LAST) AS rk FROM ({grouped}) "
               f"ORDER BY s {sdir} NULLS LAST{lim}")
        group_by = keys + ([col_key] if col else [])
        sql = (f"WITH q AS ({top}) SELECT {', '.join(sel + [msql])}, any_value(q.rk) AS __rank FROM {src} "
               f"JOIN q ON {on} WHERE {where} GROUP BY {', '.join(group_by)}")
        df = db.query(sql, params)
        row_count = int(db.scalar(f"SELECT count(*) FROM ({grouped})", params) or 0)
        truncated = bool(limit) and row_count > limit
        # totais: direto da base; com filtro por valor, apenas dos grupos qualificados
        base_from = (f"{src} JOIN ({grouped}) q ON {on} WHERE {where}" if hv else f"{src} WHERE {where}")
    else:
        sql = f"SELECT {', '.join(sel + [msql])} FROM {src} WHERE {where}" + (f" GROUP BY {col_key}" if col else "")
        df = db.query(sql, params)
        base_from = f"{src} WHERE {where}"

    tot_df = db.query(f"SELECT {msql} FROM {base_from}", params)
    tot = tot_df.to_dicts()[0] if tot_df.height else {}

    columns_meta: list[dict] = []
    if col:
        n_cols = df["__col"].n_unique() if df.height else 0
        col_tot = db.query(f"SELECT {col_key} AS __col, {msql} FROM {base_from} GROUP BY {col_key}", params)
        col_vals = sorted(set(col_tot["__col"].to_list()) | set(df["__col"].to_list() if df.height else []),
                          key=lambda v: (v is None, str(v)))
        if len(col_vals) > MAX_PIVOT_COLUMNS or n_cols > MAX_PIVOT_COLUMNS:
            raise ReportError(f"A dimensão '{DIMENSIONS[col][0]}' tem {len(col_vals)} valores; em colunas o limite é "
                              f"{MAX_PIVOT_COLUMNS}. Use-a nas linhas ou filtre antes.")
        idx = [c for c in df.columns if c not in metrics and c not in ("__col", "__rank")]
        if idx:
            out = df.group_by(idx, maintain_order=True).agg(pl.col("__rank").first()) if "__rank" in df.columns \
                else df.select(idx).unique(maintain_order=True)
        else:
            out = pl.DataFrame({"__one": [1]})
        for v in col_vals:
            label = "(vazio)" if v is None else str(v)
            ren = {m: f"{label}\u241f{m}" for m in metrics}
            part = df.filter(pl.col("__col").is_null() if v is None else pl.col("__col") == v)
            part = part.select(idx + metrics).rename(ren)
            if idx:
                out = out.join(part, on=idx, how="left", nulls_equal=True)
            else:
                out = pl.concat([out, part if part.height else pl.DataFrame({c: [None] for c in ren.values()})],
                                how="horizontal")
            ct = col_tot.filter(pl.col("__col").is_null() if v is None else pl.col("__col") == v).to_dicts()
            for m in metrics:
                columns_meta.append({"key": ren[m], "group": label, "metric": m})
                tot[ren[m]] = ct[0][m] if ct else None
        for m in metrics:
            if m in ADDITIVE:
                cols = [mm["key"] for mm in columns_meta if mm["metric"] == m and mm["group"] != "TOTAL"]
                out = out.with_columns(pl.sum_horizontal([pl.col(c).fill_null(0) for c in cols]).alias(f"TOTAL\u241f{m}"))
                columns_meta.append({"key": f"TOTAL\u241f{m}", "group": "TOTAL", "metric": m})
                tot[f"TOTAL\u241f{m}"] = tot.get(m)
        df = out.drop([c for c in ("__one",) if c in out.columns])
    if "__rank" in df.columns:
        df = df.sort("__rank", nulls_last=True).drop("__rank")
    return {"df": df, "totals": tot, "columns_meta": columns_meta, "truncated": truncated, "source": src,
            "row_count": row_count, "metrics": metrics, "sort": {"by": sby, "dir": sdir.lower()}}
