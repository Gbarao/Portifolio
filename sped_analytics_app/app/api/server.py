"""API local (FastAPI) que serve a interface web e expõe o motor de consolidação.

Tudo roda em 127.0.0.1. A interface (React, já compilada em app/web) conversa apenas com estes endpoints.
Endpoints síncronos (`def`) rodam no pool de threads do servidor; cada consulta usa um cursor próprio do DuckDB.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import polars as pl
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app import config
from app.database import analytics, audit, bloco_m, fornecedor, raw_view, snapshots
from app.database import filter_builder as fb
from app.database.aggregates import FATO
from app.database.engine import SpedDatabase, get_db
from app.exporter import excel_writer

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
EXPORT_DIR = config.DATA_DIR / "exports"
UPLOAD_DIR = config.DATA_DIR / "uploads"
APP_VERSION = "2.3.0"
STATE_VERSION = 3


# --------------------------------------------------------------------------------------
# Serialização
# --------------------------------------------------------------------------------------
def _type_of(name: str, dtype: pl.DataType) -> str:
    if name in analytics.METRICS:
        t = analytics.METRICS[name][2]
        return {"money": "money", "qty": "qty", "price": "price", "int": "int"}.get(t, "text")
    if name.startswith(("pct_", "aliq")):
        return "pct" if name.startswith("pct_") else "qty"
    if name.startswith("qtd"):
        return "qty"
    if dtype.is_integer():
        return "int"
    if dtype.is_float() or isinstance(dtype, pl.Decimal):
        return "money"
    if dtype == pl.Date or isinstance(dtype, pl.Datetime):
        return "date"
    if dtype == pl.Boolean:
        return "bool"
    return "text"


def payload(df: pl.DataFrame, limit: int | None = None) -> dict:
    """DataFrame -> {columns, types, rows} compacto (linhas como listas; números como float; datas ISO)."""
    if limit is not None and df.height > limit:
        df = df.head(limit)
    types = [_type_of(c, t) for c, t in zip(df.columns, df.dtypes)]
    exprs = []
    for c, t in zip(df.columns, df.dtypes):
        if isinstance(t, pl.Decimal):
            exprs.append(pl.col(c).cast(pl.Float64))
        elif t == pl.Date:
            exprs.append(pl.col(c).dt.strftime("%Y-%m-%d"))
        elif isinstance(t, pl.Datetime):
            exprs.append(pl.col(c).dt.strftime("%Y-%m-%d %H:%M"))
    if exprs:
        df = df.with_columns(exprs)
    return {"columns": df.columns, "types": types, "rows": [list(r) for r in df.rows()]}


def _clean(v: Any) -> Any:
    if isinstance(v, float) and v != v:
        return None
    if hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
        try:
            return float(v)
        except (TypeError, ValueError):
            return str(v)
    return v


def _json(data: Any) -> Response:
    return Response(json.dumps(data, ensure_ascii=False, default=str, separators=(",", ":")),
                    media_type="application/json")


def _path(p: list | None) -> list[tuple[str, Any]]:
    out = []
    for item in p or []:
        dim, val = item[0], item[1]
        if dim not in analytics.DIMENSIONS:
            raise HTTPException(400, f"Dimensão inválida: {dim}")
        out.append((dim, val))
    return out


def _dims(d: list | None) -> list[str]:
    d = [x for x in (d or []) if x in analytics.DIMENSIONS]
    return d


def _metrics(m: list | None) -> list[str]:
    m = [x for x in (m or []) if x in analytics.METRICS]
    return m or list(analytics.DEFAULT_METRICS)


def _context(q: dict) -> dict[str, str]:
    gf = q.get("gf") or {}
    path = q.get("path") or []
    return {
        "Gerado em": time.strftime("%d/%m/%Y %H:%M:%S"),
        "Filtros globais": json.dumps(gf, ensure_ascii=False) if gf else "(nenhum)",
        "Regras": fb.describe_rules(q.get("rules")) or "(nenhuma)",
        "Filtro salvo": q.get("appliedFilterName") or "",
        "Hierarquia": " → ".join(analytics.DIMENSIONS[d][0] for d in _dims(q.get("hierarchy") or q.get("dims"))),
        "Seleção": " > ".join(f"{analytics.DIMENSIONS[p[0]][0]}: {p[2] if len(p) > 2 else p[1]}" for p in path
                              if p and p[0] in analytics.DIMENSIONS),
    }


def _export_name(prefix: str, ext: str) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"


def _export_result(p: Path, linhas: int | None = None) -> dict:
    return {"name": p.name, "path": str(p), "url": f"/api/download/{p.name}", "linhas": linhas}


# --------------------------------------------------------------------------------------
# Tarefas em segundo plano (importação, backup, reconsolidação)
# --------------------------------------------------------------------------------------
class Jobs:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, kind: str, fn, *args, **kwargs) -> str:
        jid = uuid.uuid4().hex[:12]
        job = {"id": jid, "kind": kind, "status": "running", "msg": "Iniciando...", "frac": 0.0, "result": None,
               "error": None, "started": time.time(), "finished": None}
        with self._lock:
            if any(j["status"] == "running" and j["kind"] in ("import", "rebuild", "restore")
                   for j in self._jobs.values()) and kind in ("import", "rebuild", "restore"):
                raise HTTPException(409, "Já existe uma importação/reconsolidação em andamento")
            self._jobs[jid] = job

        def progress(msg: str, frac: float) -> None:
            job["msg"], job["frac"] = msg, float(frac)

        def run() -> None:
            try:
                job["result"] = fn(progress, *args, **kwargs)
                job["status"] = "done"
                job["frac"] = 1.0
                job["msg"] = "Concluído"
            except Exception as e:  # noqa: BLE001
                job["status"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"
                job["trace"] = traceback.format_exc()
            finally:
                job["finished"] = time.time()

        threading.Thread(target=run, daemon=True, name=f"job-{kind}").start()
        return jid

    def get(self, jid: str) -> dict:
        job = self._jobs.get(jid)
        if not job:
            raise HTTPException(404, "Tarefa não encontrada")
        return {k: v for k, v in job.items() if k != "trace"}

    def active(self) -> list[dict]:
        return [self.get(j) for j, v in self._jobs.items() if v["status"] == "running"]


# --------------------------------------------------------------------------------------
# Aplicação
# --------------------------------------------------------------------------------------
def create_app(db: SpedDatabase | None = None, native: bool = False) -> FastAPI:
    db = db or get_db()
    jobs = Jobs()
    api = FastAPI(title="Consolidação Fiscal SPED", docs_url=None, redoc_url=None, openapi_url=None)
    api.state.db = db
    api.state.native = native

    @api.exception_handler(fb.FilterError)
    def _filter_error(_req, exc: fb.FilterError):
        return JSONResponse({"detail": f"Filtro inválido: {exc}"}, status_code=400)

    @api.exception_handler(raw_view.RawQueryError)
    def _raw_error(_req, exc: raw_view.RawQueryError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # ---------------------------------------------------------------- consulta direta dos arquivos (sem cruzamento)
    @api.get("/api/raw/{tipo}/overview")
    def raw_overview(tipo: str):
        o = raw_view.overview(db, tipo)
        o["operadores"] = raw_view.OPS
        return _json(o)

    @api.post("/api/raw/{tipo}/registers")
    def raw_registers(tipo: str, q: dict = Body(default={})):
        return _json(raw_view.registers(db, tipo, q))

    @api.post("/api/raw/{tipo}/query")
    def raw_query(tipo: str, q: dict = Body(...)):
        t0 = time.perf_counter()
        limit = max(1, min(int(q.get("limit") or 1000), 5000))
        offset = max(0, int(q.get("offset") or 0))
        res = raw_view.query_register(db, tipo, q, limit, offset)
        rq = res["rq"]
        df = res["df"]
        out = payload(df) if df.width else {"columns": [a for a, _, _ in rq.columns], "types": rq.types(), "rows": []}
        kinds = {"money": "money", "qty": "qty", "int": "int", "date": "date"}
        out["types"] = ["text" if a in ("linha_no", "arquivo") else kinds.get(t, "text")
                        for (a, _, _), t in zip(rq.columns, rq.types())]
        out.update({"total": res["total"], "offset": offset, "labels": raw_view.labels(rq), "fields": rq.fields,
                    "docReg": rq.doc_reg, "ms": round((time.perf_counter() - t0) * 1000)})
        return _json(out)

    @api.post("/api/raw/{tipo}/lines")
    def raw_lines(tipo: str, q: dict = Body(...)):
        t0 = time.perf_counter()
        limit = max(1, min(int(q.get("limit") or 1000), 5000))
        offset = max(0, int(q.get("offset") or 0))
        res = raw_view.file_lines(db, tipo, q, limit, offset)
        out = payload(res["df"])
        out["types"] = ["text"] * len(out["columns"])
        out.update({"total": res["total"], "offset": offset, "ms": round((time.perf_counter() - t0) * 1000)})
        return _json(out)

    @api.post("/api/raw/{tipo}/export")
    def raw_export(tipo: str, q: dict = Body(...)):
        fmt = q.get("fmt") if q.get("fmt") in ("xlsx", "csv") else "xlsx"
        if q.get("modo") == "arquivo":
            res = raw_view.file_lines(db, tipo, q, 1, 0)
            sql, params, labels = res["sql"], res["params"], {"linha_no": "Linha no arquivo", "reg": "Registro",
                                                               "unidade": "Unidade (CNPJ)", "linha_original": "Linha original"}
            name = f"{'sped_fiscal' if tipo == 'ICMS_IPI' else 'efd_contribuicoes'}_arquivo_{int(q.get('arquivo') or 0)}"
        else:
            rq = raw_view.RegisterQuery(db, tipo, q)
            sql, params, labels = rq.select_sql(), rq.params, raw_view.labels(rq)
            name = f"{'sped_fiscal' if tipo == 'ICMS_IPI' else 'efd_contribuicoes'}_{rq.reg}"
        p = _export_name(name, fmt)
        n = None
        if fmt == "xlsx":
            _, n = excel_writer.export_query_excel(db, sql, params, p, q.get("reg") or "Linhas", labels,
                                                   raw_view.describe_filters(tipo, q))
        else:
            excel_writer.export_query_csv(db, sql, params, p)
        return _export_result(p, n)

    @api.get("/api/raw/pending")
    def raw_pending():
        return _json(db.files_without_lines())

    @api.post("/api/raw/index")
    def raw_index():
        return {"job": jobs.start("rebuild", lambda prog: db.index_lines(prog))}

    # ---------------------------------------------------------------- Bloco M (apuração PIS/Cofins)
    @api.exception_handler(fornecedor.FornecedorError)
    def _forn_error(_req, exc: fornecedor.FornecedorError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @api.get("/api/blocom/overview")
    def blocom_overview():
        return _json(bloco_m.overview(db))

    @api.post("/api/blocom/query")
    def blocom_query(q: dict = Body(default={})):
        t0 = time.perf_counter()
        res = bloco_m.analyze(db, q)
        sections = {}
        for key in bloco_m.SECTIONS:
            df = bloco_m.section(res, key)
            sections[key] = payload(df) if df.width else {"columns": [], "types": [], "rows": []}
        ver = res.get("verificacoes")
        n_div = int(ver.filter(pl.col("status") != "OK").height) if isinstance(ver, pl.DataFrame) and ver.height else 0
        return _json({"sections": sections, "kpis": res["kpis"], "leiaute": res["leiaute"],
                      "divergencias": n_div, "arquivos": len(res["ids"]), "labels": bloco_m.LABELS,
                      "ms": round((time.perf_counter() - t0) * 1000)})

    @api.post("/api/export/blocom")
    def export_blocom(q: dict = Body(default={})):
        res = bloco_m.analyze(db, q)
        sheets, labels = {}, {}
        for key, (sheet, _cols) in bloco_m.SECTIONS.items():
            df = bloco_m.section(res, key)
            if df.width:
                sheets[sheet] = df
                labels[sheet] = bloco_m.LABELS
        info = bloco_m.describe(q)
        if res["leiaute"]:
            info["Atenção – leiaute"] = "; ".join(
                f"{w['reg']}: {w['linhas']} linha(s) com {w['campos_encontrados']} campos (esperado {w['campos_esperados']})"
                for w in res["leiaute"])
        p = _export_name("bloco_m_efd_contribuicoes", "xlsx")
        excel_writer.export_frames_excel(p, sheets or {"Vazio": pl.DataFrame({"info": ["Sem registros do Bloco M"]})},
                                         info, labels=labels)
        return _export_result(p)

    # ---------------------------------------------------------------- busca por fornecedor
    @api.get("/api/fornecedor/buscar")
    def forn_search(q: str = ""):
        return _json(fornecedor.search(db, q))

    @api.post("/api/fornecedor/raiz")
    def forn_raiz(q: dict = Body(...)):
        return _json({"cnpjs": fornecedor.expand_raiz(db, str(q.get("raiz") or ""))})

    @api.post("/api/fornecedor/perfil")
    def forn_profile(q: dict = Body(...)):
        t0 = time.perf_counter()
        ids = fornecedor.norm_ids(q.get("cnpjs"))
        cad = fornecedor.cadastro(db, ids, q)
        cons = fornecedor.consolidado(db, ids, q)
        out = {"cnpjs": ids, "cadastro": payload(cad) if cad.width else None,
               "variantes": payload(fornecedor.cadastro_variantes(cad)) if cad.width else None,
               "alteracoes": None, "totais": {k: _clean(v) for k, v in cons["totais"].items()},
               "n_docs": cons["n_docs"]}
        alt = fornecedor.alteracoes(db, ids, q)
        if alt.width:
            out["alteracoes"] = payload(alt)
        for k in ("por_mes", "por_filial", "por_cfop", "por_item", "por_status", "por_cst_pis", "por_nat"):
            out[k] = payload(cons[k])
        out["ms"] = round((time.perf_counter() - t0) * 1000)
        return _json(out)

    @api.post("/api/fornecedor/arquivos")
    def forn_files(q: dict = Body(...)):
        t0 = time.perf_counter()
        rows = fornecedor.file_summary(db, fornecedor.norm_ids(q.get("cnpjs")), q)
        return _json({"registros": rows, "ms": round((time.perf_counter() - t0) * 1000)})

    @api.post("/api/export/fornecedor")
    def export_fornecedor(q: dict = Body(...)):
        ids = fornecedor.norm_ids(q.get("cnpjs"))
        cad = fornecedor.cadastro(db, ids, q)
        cons = fornecedor.consolidado(db, ids, q)
        gf = fornecedor.gf_for(ids, q)
        sheets: dict[str, pl.DataFrame] = {}
        if cad.width:
            sheets["Cadastro (versões)"] = fornecedor.cadastro_variantes(cad)
            sheets["Cadastro 0150 (todos)"] = cad
        alt = fornecedor.alteracoes(db, ids, q)
        if alt.width:
            sheets["Alterações 0175"] = alt
        for k, name in (("por_mes", "Entradas por mês"), ("por_filial", "Por filial"), ("por_cfop", "Por CFOP"),
                        ("por_item", "Por item"), ("por_status", "Status EFD")):
            sheets[name] = cons[k]
        sheets["Notas fiscais"] = analytics.documents(db, gf, None, None, limit=excel_writer.EXCEL_MAX_ROWS)
        sheets["Itens (consolidado)"] = analytics.lines(db, gf, None, None, limit=excel_writer.EXCEL_MAX_ROWS)
        summ = fornecedor.file_summary(db, ids, q)
        if summ:
            sheets["Arquivos – resumo"] = pl.DataFrame(summ).select(
                ["tipo_label", "reg", "descricao", "n", "entradas", "saidas", "arquivos"])
        labels = {}
        for r in summ:   # linhas originais por registro, com os nomes oficiais dos campos
            rq = raw_view.RegisterQuery(db, r["tipo"], {"reg": r["reg"], "participantes": ids,
                                                        "comp_ini": q.get("comp_ini"), "comp_fim": q.get("comp_fim")})
            name = f"{'SF' if r['tipo'] == 'ICMS_IPI' else 'EFD'} {r['reg']}"
            sheets[name] = db.query(rq.select_sql(), rq.params)
            labels[name] = raw_view.labels(rq)
        info = {"Fornecedor (CNPJ/CPF)": ", ".join(ids),
                "Período": f"{q.get('comp_ini') or 'início'} a {q.get('comp_fim') or 'fim'}",
                "Consolidado": "Entradas da base consolidada SPED Fiscal + EFD-Contribuições (sem duplicidade)",
                "Arquivos": "Linhas dos TXT ligadas ao participante (entradas e saídas), pelo código do 0150 de cada "
                            "arquivo, registros filhos dos documentos e C191/C195"}
        p = _export_name(f"fornecedor_{ids[0][:14].replace(':', '_')}", "xlsx")
        excel_writer.export_frames_excel(p, sheets, info, labels=labels)
        return _export_result(p)

    # ---------------------------------------------------------------- metadados e estado
    @api.get("/api/meta")
    def meta():
        return _json({
            "version": APP_VERSION,
            "native": bool(api.state.native),
            "dataDir": str(config.DATA_DIR),
            "exportDir": str(EXPORT_DIR),
            "maxGridRows": config.UI_MAX_GRID_ROWS,
            "workers": config.PARSER_WORKERS,
            "cpuCount": config.CPU_COUNT,
            "tolerancia": config.TOLERANCIA_DIVERGENCIA,
            "dimensions": [{"key": k, "label": v[0], "hasDesc": v[2] is not None}
                           for k, v in analytics.DIMENSIONS.items()],
            "metrics": [{"key": k, "label": v[0], "type": v[2], "rowLevel": k in analytics.ROW_LEVEL_METRICS}
                        for k, v in analytics.METRICS.items()],
            "defaultHierarchy": analytics.DEFAULT_HIERARCHY,
            "defaultMetrics": analytics.DEFAULT_METRICS,
            "fields": [{"key": k, "label": v[0], "type": v[1]} for k, v in fb.FIELDS.items()],
            "operators": fb.OPERATORS,
            "opsByType": fb.OPS_BY_TYPE,
            "checks": [{"key": k, "label": v, "informative": k in audit.INFORMATIVE} for k, v in audit.CHECKS.items()],
        })

    @api.get("/api/state")
    def get_state():
        st = db.session_get("ui_state") or {}
        if st.get("v") != STATE_VERSION:   # estado salvo pela interface anterior (NiceGUI): migra o essencial
            mode = {"drill": "arvore", "plana": "tabela", "mensal": "mensal"}.get(st.get("mode"), "arvore")
            st = {"v": STATE_VERSION, "gf": st.get("global_filters") or {}, "rules": st.get("rules"),
                  "hierarchy": st.get("hierarchy"), "metrics": [m for m in st.get("metrics") or [] if m != "n_docs"],
                  "mode": mode, "pivotMetric": st.get("pivot_metric") or "vl_contabil",
                  "appliedFilterName": st.get("applied_filter_name") or "", "page": "analise"}
        return _json(st)

    @api.put("/api/state")
    def put_state(st: dict = Body(...)):
        st["v"] = STATE_VERSION
        db.session_set("ui_state", st)
        return {"ok": True}

    @api.get("/api/options")
    def options():
        out = {}
        for key, col in (("filial", "filial"), ("fornecedor", "fornecedor"), ("cfop", "cfop"), ("item", "item"),
                         ("uf", "uf_filial"), ("ncm", "ncm")):
            try:
                out[key] = [[r["v"], r["l"]] for r in analytics.distinct_values(db, col, limit=5000)]
            except Exception:  # noqa: BLE001
                out[key] = []
        out["competencias"] = db.competencias()
        return _json(out)

    # ---------------------------------------------------------------- análise
    @api.post("/api/aggregate")
    def aggregate(q: dict = Body(...)):
        t0 = time.perf_counter()
        gf, rules = q.get("gf") or {}, q.get("rules")
        dims, metrics, path = _dims(q.get("dims")), _metrics(q.get("metrics")), _path(q.get("path"))
        limit = int(q.get("limit") or config.UI_MAX_GRID_ROWS)
        src = analytics.source_for(gf, rules, dims, metrics, path)
        df = analytics.aggregate(db, gf, rules, dims, metrics, path, limit=limit)
        out = payload(df)
        if q.get("withTotals", True):
            tot = analytics.totals(db, gf, rules, metrics, path)
            out["totals"] = {k: _clean(v) for k, v in tot.items()}
        out.update({"source": src, "truncated": df.height >= limit, "limit": limit,
                    "ms": round((time.perf_counter() - t0) * 1000)})
        return _json(out)

    @api.post("/api/totals")
    def totals(q: dict = Body(...)):
        t0 = time.perf_counter()
        metrics = _metrics(q.get("metrics"))
        tot = analytics.totals(db, q.get("gf") or {}, q.get("rules"), metrics, _path(q.get("path")))
        return _json({"totals": {k: _clean(v) for k, v in tot.items()},
                      "source": analytics.source_for(q.get("gf") or {}, q.get("rules"), [], metrics),
                      "ms": round((time.perf_counter() - t0) * 1000)})

    # ---------------------------------------------------------------- relatório dinâmico
    def _run_report(q: dict, limit: int | None):
        try:
            return analytics.report(db, q.get("gf") or {}, q.get("rules"), _dims(q.get("rows")),
                                    q.get("col") if q.get("col") in analytics.DIMENSIONS else None,
                                    list(q.get("metrics") or []), q.get("sort"), limit, q.get("texto") or "",
                                    q.get("having") or [])
        except analytics.ReportError as e:
            raise HTTPException(400, str(e))

    def _report_labels(r: dict, rows: list[str]) -> dict[str, str]:
        lab = {}
        for d in rows:
            lab[d] = analytics.DIMENSIONS[d][0]
            lab[f"{d}__desc"] = f"{analytics.DIMENSIONS[d][0]} — descrição"
        for m in r["metrics"]:
            lab[m] = analytics.METRICS[m][0]
        for cm in r["columns_meta"]:
            lab[cm["key"]] = f"{cm['group']} · {analytics.METRICS[cm['metric']][0]}"
        return lab

    @api.post("/api/report")
    def report(q: dict = Body(...)):
        t0 = time.perf_counter()
        limit = max(1, min(int(q.get("limit") or config.UI_MAX_GRID_ROWS), 20_000))
        r = _run_report(q, limit)
        out = payload(r["df"])
        types = []
        for c, t in zip(out["columns"], out["types"]):
            mk = c.split("\u241f")[-1]
            types.append(_type_of(mk, pl.Float64()) if mk in analytics.METRICS else t)
        out["types"] = types
        out.update({"totals": {k: _clean(v) for k, v in r["totals"].items()}, "columnsMeta": r["columns_meta"],
                    "truncated": r["truncated"], "rowCount": r["row_count"], "source": r["source"],
                    "metrics": r["metrics"], "sort": r["sort"], "labels": _report_labels(r, _dims(q.get("rows"))),
                    "ms": round((time.perf_counter() - t0) * 1000)})
        return _json(out)

    @api.post("/api/export/report")
    def export_report(q: dict = Body(...)):
        rows = _dims(q.get("rows"))
        r = _run_report(q, excel_writer.EXCEL_MAX_ROWS - 1)
        df = r["df"]
        if df.height and df.width:
            tot = {c: None for c in df.columns}
            tot[df.columns[0]] = "TOTAL"
            for c in df.columns:
                if c in r["totals"] and c != df.columns[0]:
                    tot[c] = r["totals"][c]
            df = pl.concat([df, pl.DataFrame([tot], schema=df.schema, strict=False)], how="vertical_relaxed")
        labels = _report_labels(r, rows)
        info = _context({**q, "hierarchy": rows})
        info["Linhas"] = " › ".join(analytics.DIMENSIONS[d][0] for d in rows) or "(nenhuma)"
        info["Colunas"] = analytics.DIMENSIONS[q["col"]][0] if q.get("col") in analytics.DIMENSIONS else "(nenhuma)"
        info["Valores"] = ", ".join(analytics.METRICS[m][0] for m in r["metrics"])
        srt = r["sort"]
        info["Ordenação"] = (f"{(analytics.METRICS.get(srt['by']) or analytics.DIMENSIONS.get(srt['by']))[0]} "
                             f"({'maior → menor' if srt['dir'] == 'desc' else 'menor → maior'})")
        if q.get("texto"):
            info["Texto nas linhas"] = q["texto"]
        for i, h in enumerate(q.get("having") or [], 1):
            info[f"Filtro por valor {i}"] = f"{analytics.METRICS.get(h.get('metric'), (h.get('metric'),))[0]} " \
                                            f"{h.get('op')} {h.get('value') if h.get('op') not in ('zero', 'nao_zero') else ''}"
        info["Base"] = "Consolidado SPED Fiscal + EFD-Contribuições (cada valor contado uma única vez)"
        if r["truncated"]:
            info["Atenção"] = f"Relatório limitado às {df.height - 1:,} primeiras linhas pela ordenação escolhida"
        p = _export_name("relatorio_dinamico", "xlsx")
        excel_writer.export_frames_excel(p, {"Relatorio": df}, info, labels={"Relatorio": labels})
        return _export_result(p, max(0, df.height - 1))

    @api.post("/api/count-docs")
    def count_docs(q: dict = Body(...)):
        return {"n": analytics.count_documents(db, q.get("gf") or {}, q.get("rules"), _path(q.get("path")))}

    @api.post("/api/pivot")
    def pivot(q: dict = Body(...)):
        t0 = time.perf_counter()
        gf, rules, dims, path = q.get("gf") or {}, q.get("rules"), _dims(q.get("dims")), _path(q.get("path"))
        metric = q.get("metric") if q.get("metric") in analytics.METRICS else "vl_contabil"
        limit = int(q.get("limit") or config.UI_MAX_GRID_ROWS)
        df, tot = analytics.monthly_pivot(db, gf, rules, dims, metric, path, limit=limit)
        out = payload(df)
        out["types"] = ["money" if c not in dims and not c.endswith("__desc") else t
                        for c, t in zip(out["columns"], out["types"])]
        out.update({"totals": {k: _clean(v) for k, v in tot.items()},
                    "source": analytics.source_for(gf, rules, dims + ["competencia"], [metric], path),
                    "truncated": df.height >= limit, "ms": round((time.perf_counter() - t0) * 1000)})
        return _json(out)

    @api.post("/api/documents")
    def documents(q: dict = Body(...)):
        t0 = time.perf_counter()
        df = analytics.documents(db, q.get("gf") or {}, q.get("rules"), _path(q.get("path")),
                                 limit=int(q.get("limit") or config.UI_MAX_DRILL_ROWS))
        out = payload(df)
        out["ms"] = round((time.perf_counter() - t0) * 1000)
        return _json(out)

    @api.post("/api/lines")
    def lines(q: dict = Body(...)):
        df = analytics.lines(db, q.get("gf") or {}, q.get("rules"), _path(q.get("path")),
                             limit=int(q.get("limit") or 2000))
        return _json(payload(df))

    # ---------------------------------------------------------------- exportação
    @api.post("/api/export/summary")
    def export_summary(q: dict = Body(...)):
        """Resumo pela hierarquia completa (visão plana), com totais e parâmetros."""
        gf, rules = q.get("gf") or {}, q.get("rules")
        mode = q.get("mode")
        dims = _dims(q.get("hierarchy")) or analytics.DEFAULT_HIERARCHY
        if mode == "mensal":
            metric = q.get("pivotMetric") if q.get("pivotMetric") in analytics.METRICS else "vl_contabil"
            df, _ = analytics.monthly_pivot(db, gf, rules, dims, metric, limit=excel_writer.EXCEL_MAX_ROWS)
        else:
            df = analytics.aggregate(db, gf, rules, dims, _metrics(q.get("metrics")),
                                     limit=excel_writer.EXCEL_MAX_ROWS)
        p = _export_name("resumo_consolidado", "xlsx")
        excel_writer.export_frames_excel(p, {"Resumo": df}, _context(q))
        return _export_result(p, df.height)

    @api.post("/api/export/lines")
    def export_lines(q: dict = Body(...)):
        fmt = q.get("fmt") if q.get("fmt") in ("xlsx", "csv", "parquet") else "xlsx"
        sql, params = analytics.lines_sql(q.get("gf") or {}, q.get("rules"), _path(q.get("path")))
        p = _export_name("itens_detalhados", fmt)
        n = None
        if fmt == "xlsx":
            _, n = excel_writer.export_query_excel(db, sql, params, p, "Itens", info=_context(q))
        elif fmt == "csv":
            excel_writer.export_query_csv(db, sql, params, p)
        else:
            excel_writer.export_query_parquet(db, sql, params, p)
        return _export_result(p, n)

    @api.post("/api/export/documents")
    def export_documents(q: dict = Body(...)):
        df = analytics.documents(db, q.get("gf") or {}, q.get("rules"), _path(q.get("path")),
                                 limit=excel_writer.EXCEL_MAX_ROWS)
        p = _export_name("notas_fiscais", "xlsx")
        excel_writer.export_frames_excel(p, {"Notas": df}, _context(q))
        return _export_result(p, df.height)

    @api.post("/api/export/audit")
    def export_audit(q: dict = Body(...)):
        gf, tol = q.get("gf") or {}, float(q.get("tol") or config.TOLERANCIA_DIVERGENCIA)
        checks = [q["check"]] if q.get("check") else list(audit.CHECKS)
        sheets, info = {}, {"Filtros": json.dumps(gf, ensure_ascii=False) or "(nenhum)", "Tolerância": str(tol)}
        for k in checks:
            if k not in audit.CHECKS:
                raise HTTPException(400, f"Verificação desconhecida: {k}")
            df = audit.run_check(db, k, gf, tol, limit=excel_writer.EXCEL_MAX_ROWS)
            sheets[k[:31]] = df
            info[k] = f"{audit.CHECKS[k]}: {df.height} linha(s)"
        p = _export_name("auditoria" if len(checks) > 1 else f"auditoria_{checks[0]}", "xlsx")
        excel_writer.export_frames_excel(p, sheets, info)
        return _export_result(p)

    @api.get("/api/download/{name}")
    def download(name: str):
        p = (EXPORT_DIR / name).resolve()
        bk = (config.BACKUP_DIR / name).resolve()
        for cand, base in ((p, EXPORT_DIR), (bk, config.BACKUP_DIR)):
            if cand.parent == base.resolve() and cand.is_file():
                return FileResponse(cand, filename=cand.name)
        raise HTTPException(404, "Arquivo não encontrado")

    @api.post("/api/open-folder")
    def open_folder(q: dict = Body(default={})):
        target = Path(q.get("path") or EXPORT_DIR)
        if target.is_file():
            target = target.parent
        allowed = [config.DATA_DIR.resolve()]
        if not any(str(target.resolve()).startswith(str(a)) for a in allowed):
            raise HTTPException(400, "Pasta fora do cofre de dados")
        target.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "path": str(target), "error": str(e)}
        return {"ok": True, "path": str(target)}

    # ---------------------------------------------------------------- regras e filtros salvos
    @api.post("/api/rules/preview")
    def rules_preview(q: dict = Body(...)):
        params: list = []
        try:
            sql = fb.rules_to_sql(q.get("rules"), params)
        except fb.FilterError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "sql": sql, "params": [str(p) for p in params],
                "description": fb.describe_rules(q.get("rules"))}

    @api.post("/api/rules/test")
    def rules_test(q: dict = Body(...)):
        t0 = time.perf_counter()
        gf, rules = q.get("gf") or {}, q.get("rules")
        tot = analytics.totals(db, gf, rules, ["n_linhas", "vl_contabil", "vl_pis", "vl_cofins", "vl_icms"])
        return _json({"totals": {k: _clean(v) for k, v in tot.items()},
                      "source": analytics.source_for(gf, rules, [], ["n_linhas", "vl_contabil"]),
                      "ms": round((time.perf_counter() - t0) * 1000)})

    @api.get("/api/filters")
    def list_filters():
        return _json(fb.list_filters(db))

    @api.post("/api/filters")
    def save_filter(q: dict = Body(...)):
        nome = (q.get("nome") or "").strip()
        if not nome:
            raise HTTPException(400, "Informe o nome do filtro")
        fid = fb.save_filter(db, nome, (q.get("categoria") or "Geral").strip() or "Geral",
                             q.get("definicao") or {}, q.get("id"))
        return {"id": fid}

    @api.delete("/api/filters/{fid}")
    def delete_filter(fid: int):
        fb.delete_filter(db, fid)
        return {"ok": True}

    # ---------------------------------------------------------------- snapshots
    @api.get("/api/snapshots")
    def list_snaps():
        return _json(snapshots.list_snapshots(db))

    @api.post("/api/snapshots")
    def save_snap(q: dict = Body(...)):
        st = q.get("state") or {}
        gf, rules = st.get("gf") or {}, st.get("rules")
        dims = _dims(st.get("hierarchy")) or analytics.DEFAULT_HIERARCHY
        if st.get("mode") == "mensal":
            metric = st.get("pivotMetric") if st.get("pivotMetric") in analytics.METRICS else "vl_contabil"
            df, _ = analytics.monthly_pivot(db, gf, rules, dims, metric, limit=200_000)
        else:
            df = analytics.aggregate(db, gf, rules, dims, _metrics(st.get("metrics")), limit=200_000)
        ctx = {**_context(st), "state": st}
        sid = snapshots.save_snapshot(db, (q.get("nome") or "Snapshot").strip(), q.get("anotacoes") or "", ctx, df)
        return {"id": sid, "linhas": df.height}

    @api.get("/api/snapshots/{sid}")
    def get_snap(sid: int):
        try:
            m, df, ok = snapshots.load_snapshot(db, sid)
        except KeyError:
            raise HTTPException(404, "Snapshot não encontrado")
        return _json({"meta": {k: v for k, v in m.items()}, "ok": ok, "total": df.height, **payload(df, 5000)})

    @api.post("/api/snapshots/{sid}/export")
    def export_snap(sid: int):
        m, df, _ = snapshots.load_snapshot(db, sid)
        p = _export_name(f"snapshot_{sid}", "xlsx")
        ctx = {k: str(v) for k, v in m["contexto"].items() if k != "state"}
        excel_writer.export_frames_excel(p, {"Snapshot": df}, {"Snapshot": m["nome"], "Criado em": m["criado_em"],
                                                               "Anotações": m["anotacoes"], **ctx})
        return _export_result(p, df.height)

    @api.delete("/api/snapshots/{sid}")
    def delete_snap(sid: int):
        snapshots.delete_snapshot(db, sid)
        return {"ok": True}

    # ---------------------------------------------------------------- auditoria
    @api.post("/api/audit/summary")
    def audit_summary(q: dict = Body(default={})):
        t0 = time.perf_counter()
        res = audit.summary(db, q.get("gf") or {})
        return _json({"items": res, "ms": round((time.perf_counter() - t0) * 1000)})

    @api.post("/api/audit/check")
    def audit_check(q: dict = Body(...)):
        k = q.get("check")
        if k not in audit.CHECKS:
            raise HTTPException(400, "Verificação desconhecida")
        df = audit.run_check(db, k, q.get("gf") or {}, float(q.get("tol") or config.TOLERANCIA_DIVERGENCIA))
        return _json({"check": k, "label": audit.CHECKS[k], "total": df.height, **payload(df, 20_000)})

    # ---------------------------------------------------------------- central de arquivos
    @api.get("/api/hub/stats")
    def hub_stats():
        return _json(db.stats())

    @api.get("/api/hub/coverage")
    def hub_coverage():
        df = db.coverage_matrix()
        comps = sorted(set(df["competencia"].to_list())) if df.height else []
        rows: dict[str, dict] = {}
        for r in df.to_dicts():
            e = rows.setdefault(r["cnpj"], {"cnpj": r["cnpj"], "nome": r["nome"], "uf": r["uf"], "status": {}})
            e["status"][r["competencia"]] = r["status"]
        return _json({"competencias": comps, "filiais": list(rows.values())})

    @api.get("/api/hub/files")
    def hub_files():
        return _json(payload(db.list_files()))

    @api.get("/api/hub/log")
    def hub_log():
        return _json(payload(db.import_log(1000)))

    @api.post("/api/hub/import")
    def hub_import(q: dict = Body(...)):
        paths = [str(p).strip().strip('"') for p in q.get("paths") or [] if str(p).strip()]
        missing = [p for p in paths if not Path(p).exists()]
        if not paths or missing:
            raise HTTPException(400, f"Caminho não encontrado: {', '.join(missing) or '(vazio)'}")
        workers = int(q.get("workers") or config.PARSER_WORKERS)
        return {"job": jobs.start("import", _import_job, db, paths, workers)}

    @api.post("/api/hub/upload")
    def hub_upload(files: list[UploadFile] = File(...)):
        dest = UPLOAD_DIR / time.strftime("%Y%m%d_%H%M%S")
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            name = Path(f.filename or "arquivo.txt").name
            with open(dest / name, "wb") as out:
                shutil.copyfileobj(f.file, out, length=8 * 1024 * 1024)
        return {"job": jobs.start("import", _import_job, db, [str(dest)], config.PARSER_WORKERS)}

    @api.get("/api/jobs/{jid}")
    def job(jid: str):
        return _json(jobs.get(jid))

    @api.get("/api/jobs")
    def jobs_active():
        return _json(jobs.active())

    @api.post("/api/hub/rebuild")
    def hub_rebuild():
        return {"job": jobs.start("rebuild", lambda prog: db.rebuild_fato(None, prog))}

    @api.post("/api/hub/remove-files")
    def hub_remove_files(q: dict = Body(...)):
        ids = [int(i) for i in q.get("ids") or []]
        if not ids:
            raise HTTPException(400, "Nenhum arquivo selecionado")
        return {"job": jobs.start("rebuild", lambda prog: {"competencias": db.remove_files(ids)})}

    @api.post("/api/hub/remove-competencias")
    def hub_remove_comps(q: dict = Body(...)):
        comps = [str(c) for c in q.get("competencias") or []]
        if not comps:
            raise HTTPException(400, "Nenhuma competência selecionada")
        tipo = q.get("tipo") or None
        return {"job": jobs.start("rebuild", lambda prog: {
            "competencias": db.remove_competencias(comps, tipo)})}

    @api.post("/api/hub/backup")
    def hub_backup(q: dict = Body(default={})):
        def run(prog):
            prog("Gerando backup...", 0.2)
            p = db.backup(None, bool(q.get("incluirParquet")))
            return {"name": p.name, "path": str(p), "url": f"/api/download/{p.name}"}
        return {"job": jobs.start("backup", run)}

    @api.post("/api/hub/restore")
    def hub_restore(q: dict = Body(...)):
        p = str(q.get("path") or "").strip().strip('"')
        if not p or not Path(p).is_file():
            raise HTTPException(400, "Arquivo de backup não encontrado")

        def run(prog):
            prog("Restaurando backup...", 0.2)
            db.restore(p)
            return {"ok": True}
        return {"job": jobs.start("restore", run)}

    @api.get("/api/native/pick-folder")
    def pick_folder():
        if not api.state.native:
            return {"available": False, "path": None}
        try:
            import webview  # type: ignore
            win = webview.windows[0]
            kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
            res = win.create_file_dialog(kind)
            return {"available": True, "path": (res[0] if res else None)}
        except Exception as e:  # noqa: BLE001
            return {"available": False, "path": None, "error": str(e)}

    # ---------------------------------------------------------------- interface (arquivos estáticos)
    if WEB_DIR.is_dir():
        api.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

        @api.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404)
            f = (WEB_DIR / full_path).resolve()
            if full_path and f.is_file() and f.parent == WEB_DIR.resolve():
                return FileResponse(f)
            return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})
    else:
        @api.get("/")
        def no_ui():
            return Response("Interface não encontrada (app/web). Reinstale o pacote.", media_type="text/plain")

    return api


def _import_job(prog, db: SpedDatabase, paths: list[str], workers: int) -> dict:
    s = db.import_paths(paths, progress=prog, workers=workers)
    return {
        "segundos": round(s.segundos, 1),
        "competencias": s.competencias_reconsolidadas,
        "contagem": {a: s.count(a) for a in ("IMPORTADO", "SUBSTITUIDO", "DUPLICADO", "IGNORADO", "ERRO")},
        "resultados": [{"arquivo": Path(r.arquivo).name, "caminho": r.arquivo, "acao": r.acao, "mensagem": r.mensagem,
                        "tipo": r.tipo, "cnpj": r.cnpj, "competencia": r.competencia} for r in s.resultados[:2000]],
    }
