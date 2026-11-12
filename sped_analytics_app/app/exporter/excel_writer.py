"""Exportação otimizada: Excel (.xlsx em modo streaming), CSV (padrão BR: ';' e vírgula decimal) e Parquet.

Exportações de consultas são feitas em lotes direto do DuckDB (sem materializar tudo na RAM). Planilhas acima
do limite do Excel (1.048.576 linhas) são divididas automaticamente em várias abas.
"""
from __future__ import annotations

import datetime as dt
import decimal
from pathlib import Path

import polars as pl
import xlsxwriter

EXCEL_MAX_ROWS = 1_048_575  # + cabeçalho
BATCH = 50_000

LABELS: dict[str, str] = {}


def _label(c: str) -> str:
    try:
        from app.database.filter_builder import FIELDS
        from app.database.analytics import DIMENSIONS, METRICS
        if c in FIELDS:
            return FIELDS[c][0]
        if c in METRICS:
            return METRICS[c][0]
        if c in DIMENSIONS:
            return DIMENSIONS[c][0]
        if c.endswith("__desc") and c[:-6] in DIMENSIONS:
            return DIMENSIONS[c[:-6]][0] + " (Descrição)"
    except ImportError:
        pass
    return LABELS.get(c, c)


class _Book:
    def __init__(self, path: Path):
        self.wb = xlsxwriter.Workbook(str(path), {"constant_memory": True, "strings_to_numbers": False,
                                                  "strings_to_urls": False})
        self.f_head = self.wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "#FFFFFF",
                                          "border": 1, "text_wrap": True, "valign": "vcenter"})
        self.f_money = self.wb.add_format({"num_format": "#,##0.00"})
        self.f_qty = self.wb.add_format({"num_format": "#,##0.000###"})
        self.f_int = self.wb.add_format({"num_format": "#,##0"})
        self.f_date = self.wb.add_format({"num_format": "dd/mm/yyyy"})
        self.f_text = self.wb.add_format({"num_format": "@"})

    def fmt_for(self, name: str, dtype) -> object | None:
        if dtype in ("date",):
            return self.f_date
        if dtype == "int":
            return self.f_int
        if dtype == "num":
            n = name.lower()
            if n.startswith(("qtd", "aliq", "preco")):
                return self.f_qty
            return self.f_money
        return None


def _kind(dtype: pl.DataType) -> str:
    if dtype.is_integer():
        return "int"
    if dtype.is_float() or isinstance(dtype, pl.Decimal):
        return "num"
    if dtype in (pl.Date, pl.Datetime) or isinstance(dtype, pl.Datetime):
        return "date"
    return "text"


def _write_sheet_header(ws, book: _Book, cols: list[str], kinds: list[str]) -> None:
    ws.set_row(0, 30)
    for j, (c, k) in enumerate(zip(cols, kinds)):
        ws.write_string(0, j, _label(c), book.f_head)
        width = 14 if k in ("num", "int", "date") else min(max(len(_label(c)) + 2, 12), 45)
        if c in ("chave",):
            width = 46
        ws.set_column(j, j, width, book.fmt_for(c, k))
    ws.freeze_panes(1, 0)


def _write_value(ws, i: int, j: int, v, fmt) -> None:
    if v is None:
        return
    if isinstance(v, (int, float, decimal.Decimal)) and not isinstance(v, bool):
        ws.write_number(i, j, float(v), fmt)
    elif isinstance(v, (dt.date, dt.datetime)):
        ws.write_datetime(i, j, v if isinstance(v, dt.datetime) else dt.datetime(v.year, v.month, v.day), fmt)
    elif isinstance(v, bool):
        ws.write_string(i, j, "Sim" if v else "Não")
    else:
        ws.write_string(i, j, str(v))


def _batches_to_book(book: _Book, batches, base_name: str) -> int:
    ws = None
    sheet_no = 0
    row = 0
    total = 0
    cols: list[str] = []
    kinds: list[str] = []
    fmts: list = []
    for df in batches:
        if not cols:
            cols = df.columns
            kinds = [_kind(t) for t in df.dtypes]
            fmts = [book.fmt_for(c, k) for c, k in zip(cols, kinds)]
        for rec in df.iter_rows():
            if ws is None or row > EXCEL_MAX_ROWS:
                sheet_no += 1
                name = base_name if sheet_no == 1 else f"{base_name}_{sheet_no}"
                ws = book.wb.add_worksheet(name[:31])
                _write_sheet_header(ws, book, cols, kinds)
                row = 1
            for j, v in enumerate(rec):
                _write_value(ws, row, j, v, fmts[j])
            row += 1
            total += 1
    if ws is None:  # sem dados: cria aba vazia com cabeçalho
        ws = book.wb.add_worksheet(base_name[:31])
        if cols:
            _write_sheet_header(ws, book, cols, kinds)
    elif cols:
        ws.autofilter(0, 0, max(row - 1, 1), len(cols) - 1)
    return total


def export_frames_excel(path: str | Path, sheets: dict[str, pl.DataFrame], info: dict[str, str] | None = None) -> Path:
    """Exporta um ou mais DataFrames (resultado da grade, auditoria, snapshot) para .xlsx formatado."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book = _Book(path)
    if info:
        ws = book.wb.add_worksheet("Parametros")
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 110)
        for i, (k, v) in enumerate(info.items()):
            ws.write_string(i, 0, str(k), book.f_head)
            ws.write_string(i, 1, str(v))
    for name, df in sheets.items():
        _batches_to_book(book, [df], name)
    book.wb.close()
    return path


def _query_batches(db, sql: str, params: list):
    cur = db.cursor()
    try:
        reader = cur.sql(sql, params=params or None).to_arrow_reader(BATCH)
        for rb in reader:
            yield pl.from_arrow(rb)
    finally:
        cur.close()


def export_query_excel(db, sql: str, params: list, path: str | Path, sheet: str = "Dados",
                       info: dict[str, str] | None = None) -> tuple[Path, int]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    book = _Book(path)
    if info:
        ws = book.wb.add_worksheet("Parametros")
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 110)
        for i, (k, v) in enumerate(info.items()):
            ws.write_string(i, 0, str(k), book.f_head)
            ws.write_string(i, 1, str(v))
    n = _batches_to_book(book, _query_batches(db, sql, params), sheet)
    book.wb.close()
    return path, n


def _br_select(db, sql: str, params: list) -> str:
    """Envolve a consulta convertendo números para vírgula decimal e datas para dd/mm/aaaa."""
    cur = db.cursor()
    try:
        desc = cur.execute(f"DESCRIBE {sql}", params).fetchall()
    finally:
        cur.close()
    cols = []
    for name, typ, *_ in desc:
        q = f'"{name}"'
        t = str(typ).upper()
        if t.startswith(("DECIMAL", "DOUBLE", "FLOAT", "REAL")):
            cols.append(f"replace(CAST({q} AS VARCHAR), '.', ',') AS {q}")
        elif t == "DATE":
            cols.append(f"strftime({q}, '%d/%m/%Y') AS {q}")
        else:
            cols.append(q)
    return f"SELECT {', '.join(cols)} FROM ({sql})"


def export_query_csv(db, sql: str, params: list, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = _br_select(db, sql, params)
    target = str(path).replace("'", "''")
    with db.write_lock:
        cur = db.cursor()
        try:
            cur.execute(f"COPY ({wrapped}) TO '{target}' (FORMAT CSV, DELIMITER ';', HEADER TRUE)", params)
        finally:
            cur.close()
    return path


def export_query_parquet(db, sql: str, params: list, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target = str(path).replace("'", "''")
    cur = db.cursor()
    try:
        cur.execute(f"COPY ({sql}) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)", params)
    finally:
        cur.close()
    return path


def export_frame_csv(df: pl.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.with_columns([pl.col(c).cast(pl.Float64) for c, t in zip(df.columns, df.dtypes) if isinstance(t, pl.Decimal)])
    df.write_csv(path, separator=";", decimal_comma=True, date_format="%d/%m/%Y")
    return path
