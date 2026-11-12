"""Estado compartilhado da interface e utilitários de grade (AG Grid) e formatação."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any

import polars as pl

from app.database.analytics import DEFAULT_HIERARCHY, DEFAULT_METRICS, DIMENSIONS, METRICS
from app.database.filter_builder import FIELDS

JS_MONEY = ("params => (params.value === null || params.value === undefined || params.value === '') ? '' : "
            "Number(params.value).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})")
JS_QTY = ("params => (params.value === null || params.value === undefined || params.value === '') ? '' : "
          "Number(params.value).toLocaleString('pt-BR', {minimumFractionDigits: 0, maximumFractionDigits: 4})")
JS_INT = ("params => (params.value === null || params.value === undefined) ? '' : "
          "Number(params.value).toLocaleString('pt-BR', {maximumFractionDigits: 0})")
JS_CNPJ = ("params => { const v = params.value || ''; "
           "if (/^\\d{14}$/.test(v)) return v.replace(/^(\\d{2})(\\d{3})(\\d{3})(\\d{4})(\\d{2})$/, '$1.$2.$3/$4-$5'); "
           "if (/^\\d{11}$/.test(v)) return v.replace(/^(\\d{3})(\\d{3})(\\d{3})(\\d{2})$/, '$1.$2.$3-$4'); return v; }")

CNPJ_COLS = {"cnpj", "cnpj_filial", "cnpj_cpf_fornecedor", "filial", "fornecedor", "cnpj_cpf_part"}


@dataclass
class AppState:
    """Estado da sessão de análise (salvo automaticamente e restaurado ao reabrir)."""
    global_filters: dict = field(default_factory=dict)
    rules: dict = field(default_factory=lambda: {"op": "AND", "rules": []})
    hierarchy: list[str] = field(default_factory=lambda: list(DEFAULT_HIERARCHY))
    metrics: list[str] = field(default_factory=lambda: list(DEFAULT_METRICS))
    mode: str = "drill"           # drill | plana | mensal
    pivot_metric: str = "vl_contabil"
    path: list[list] = field(default_factory=list)   # [[dim, valor, rótulo], ...]
    tab: str = "analise"
    applied_filter_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "AppState":
        s = cls()
        if not d:
            return s
        for k, v in d.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.hierarchy = [h for h in s.hierarchy if h in DIMENSIONS] or list(DEFAULT_HIERARCHY)
        s.metrics = [m for m in s.metrics if m in METRICS] or list(DEFAULT_METRICS)
        return s

    def path_tuples(self) -> list[tuple[str, Any]]:
        return [(p[0], p[1]) for p in self.path]


def df_to_rows(df: pl.DataFrame) -> list[dict]:
    """Converte DataFrame em linhas JSON-serializáveis (Decimal -> float, datas -> dd/mm/aaaa)."""
    if df.is_empty():
        return []
    exprs = []
    for c, t in zip(df.columns, df.dtypes):
        if isinstance(t, pl.Decimal):
            exprs.append(pl.col(c).cast(pl.Float64))
        elif t == pl.Date:
            exprs.append(pl.col(c).dt.strftime("%d/%m/%Y"))
        elif isinstance(t, pl.Datetime):
            exprs.append(pl.col(c).dt.strftime("%d/%m/%Y %H:%M"))
        elif t == pl.Boolean:
            exprs.append(pl.when(pl.col(c)).then(pl.lit("Sim")).otherwise(pl.lit("Não")).alias(c))
    if exprs:
        df = df.with_columns(exprs)
    return df.to_dicts()


def label_for(col: str) -> str:
    if col.endswith("__desc"):
        base = col[:-6]
        return "Descrição" if base not in DIMENSIONS else f"{DIMENSIONS[base][0]} — Descrição"
    if col in DIMENSIONS:
        return DIMENSIONS[col][0]
    if col in METRICS:
        return METRICS[col][0]
    if col in FIELDS:
        return FIELDS[col][0]
    return {"vl_contabil": "Valor Contábil", "TOTAL": "TOTAL", "linhas": "Linhas", "cfops": "CFOPs",
            "vl_icms_st_fcp": "ICMS-ST + FCP", "file_id": "ID Arquivo", "doc_id": "ID Doc",
            "id_arquivo": "ID", "tipo_sped": "Tipo", "cnpj": "CNPJ (0000)", "nome": "Nome", "finalidade": "Finalidade",
            "documentos": "Docs. Entrada", "linhas": "Linhas", "tamanho_mb": "Tamanho (MB)",
            "data_importacao": "Importado em", "ativo": "Ativo", "substituido_por": "Substituído por",
            "caminho_origem": "Caminho de origem", "data": "Data", "acao": "Ação", "arquivo": "Arquivo",
            "mensagem": "Mensagem", "comp_efd": "Competência EFD"}.get(col, col)


def col_defs(df: pl.DataFrame, pin_first: int = 0, hide: set[str] | None = None) -> list[dict]:
    hide = hide or set()
    defs = []
    for i, (c, t) in enumerate(zip(df.columns, df.dtypes)):
        d: dict[str, Any] = {"field": c, "headerName": label_for(c), "sortable": True, "resizable": True,
                             "filter": True}
        if c in hide:
            d["hide"] = True
        kind = METRICS.get(c, (None, None, None))[2]
        if t.is_numeric() or isinstance(t, pl.Decimal):
            if kind in ("qty", "price") or c.startswith(("qtd", "aliq", "preco")):
                d[":valueFormatter"] = JS_QTY
            elif kind == "int" or t.is_integer():
                d[":valueFormatter"] = JS_INT
            else:
                d[":valueFormatter"] = JS_MONEY
            d["type"] = "rightAligned"
            d["filter"] = "agNumberColumnFilter"
            d["minWidth"] = 120
        else:
            d["minWidth"] = 110
            if c in CNPJ_COLS:
                d[":valueFormatter"] = JS_CNPJ
                d["minWidth"] = 160
            if c.endswith("__desc") or c in ("razao_social_fornecedor", "descr_item", "nome_filial", "descricao"):
                d["minWidth"] = 220
            if c == "chave":
                d["minWidth"] = 330
        if i < pin_first:
            d["pinned"] = "left"
        defs.append(d)
    return defs


def grid_options(df: pl.DataFrame, pin_first: int = 0, totals: dict | None = None, hide: set[str] | None = None,
                 extra: dict | None = None) -> dict:
    opts = {
        "columnDefs": col_defs(df, pin_first, hide),
        "rowData": df_to_rows(df),
        "defaultColDef": {"sortable": True, "resizable": True, "filter": True},
        "rowSelection": {"mode": "singleRow", "checkboxes": False, "enableClickSelection": True},
        "animateRows": False,
        "suppressFieldDotNotation": True,
        "enableCellTextSelection": True,
        "ensureDomOrder": True,
        "localeText": {"noRowsToShow": "Sem dados para os filtros atuais"},
    }
    if totals:
        opts["pinnedBottomRowData"] = [totals]
    if extra:
        opts.update(extra)
    return opts


def totals_row(df: pl.DataFrame, label_col: str | None = None) -> dict:
    row: dict[str, Any] = {}
    for c, t in zip(df.columns, df.dtypes):
        if (t.is_numeric() or isinstance(t, pl.Decimal)) and c not in ("preco_medio", "file_id", "doc_id", "num_item"):
            if c.startswith("aliq"):
                continue
            row[c] = float(df[c].cast(pl.Float64).sum() or 0)
    if "preco_medio" in df.columns and "qtd" in df.columns and "vl_item" in df.columns:
        q = row.get("qtd") or 0
        row["preco_medio"] = (row.get("vl_item", 0) / q) if q else None
    if label_col:
        row[label_col] = "TOTAL"
    return row


def set_grid(grid, opts: dict) -> None:
    """Substitui opções da grade preservando o tema (exigido pelo componente AG Grid do NiceGUI)."""
    theme = grid.options.get("theme", "quartz")
    grid.options.clear()
    grid.options.update(opts)
    grid.options["theme"] = theme
    grid.update()


def fmt_money(v) -> str:
    if v is None:
        return "—"
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_cnpj(v: str | None) -> str:
    if v and len(v) == 14 and v.isdigit():
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
    if v and len(v) == 11 and v.isdigit():
        return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"
    return v or ""


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")
