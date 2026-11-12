"""Gerenciamento do DuckDB local: esquema, importação em lote (paralela), deduplicação por hash,
substituição por retificadora, consolidação da tabela fato, cobertura fiscal e backup."""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import re
import shutil
import threading
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import duckdb
import polars as pl

from app import config
from app.parser import detector, efd_contrib, sped_fiscal
from app.parser.normalizer import SCHEMAS

log = logging.getLogger("sped.engine")

_SQL_TYPES = {"s": "VARCHAR", "n": "DECIMAL(18,6)", "d": "DATE", "i": "BIGINT"}
_HERE = Path(__file__).resolve().parent

UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA",
           "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
           "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
           "51": "MT", "52": "GO", "53": "DF"}

# Derivação CFOP -> NAT_BC_CRED (Tabela 4.3.7) aplicada apenas quando o registro não informa a natureza
# (C170 da EFD-Contribuições). Parametrizável na tabela ref_cfop_nat_bc_cred; padrão '13' (outras operações).
_NAT_REVENDA = ["1102", "2102", "3102", "1113", "2113", "1117", "2117", "1118", "2118", "1121", "2121",
                "1403", "2403", "1652", "2652"]
_NAT_INSUMO = ["1101", "2101", "3101", "1111", "2111", "1116", "2116", "1120", "2120", "1122", "2122",
               "1126", "2126", "3126", "1128", "2128", "3128", "1401", "2401", "1651", "2651", "3651"]
_NAT_SERV_INSUMO = ["1124", "2124", "1125", "2125", "1933", "2933"]
_NAT_DEVOLUCAO = ["1201", "2201", "3201", "1202", "2202", "3202", "1203", "2203", "1204", "2204", "3211",
                  "1410", "2410", "1411", "2411", "1660", "2660", "1661", "2661", "1662", "2662"]
_NAT_ATIVO = ["1551", "2551", "3551", "1406", "2406"]
NAT_BC_CRED_DEFAULT = (
    [(c, "01") for c in _NAT_REVENDA] + [(c, "02") for c in _NAT_INSUMO] + [(c, "03") for c in _NAT_SERV_INSUMO]
    + [(c, "12") for c in _NAT_DEVOLUCAO] + [(c, "11") for c in _NAT_ATIVO]
)

RAW_SF = [t for t in SCHEMAS if t.startswith("sf_")]
RAW_EC = [t for t in SCHEMAS if t.startswith("ec_")]


# --------------------------------------------------------------------------------------
# Workers (nível de módulo para serem serializáveis no ProcessPool "spawn")
# --------------------------------------------------------------------------------------
def _parse_worker(args: tuple[str, str, int, str]) -> dict:
    path, tipo, file_id, out_dir = args
    t0 = time.perf_counter()
    try:
        mod = sped_fiscal if tipo == detector.TIPO_FISCAL else efd_contrib
        counts = mod.parse(path, file_id, Path(out_dir))
        return {"ok": True, "file_id": file_id, "counts": counts, "secs": time.perf_counter() - t0}
    except Exception as e:  # noqa: BLE001 — devolvido ao processo principal e registrado no log
        return {"ok": False, "file_id": file_id, "error": f"{type(e).__name__}: {e}"}


def _memory_limit() -> str:
    v = config.DUCKDB_MEMORY_LIMIT
    if v.endswith("%"):
        try:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            return f"{max(1, int(total * float(v[:-1]) / 100 / 1024**3))}GB"
        except (ValueError, OSError, AttributeError):
            return "4GB"
    return v


@dataclass
class ImportResult:
    arquivo: str
    acao: str
    mensagem: str = ""
    tipo: str = ""
    cnpj: str = ""
    competencia: str = ""
    file_id: int | None = None


@dataclass
class ImportSummary:
    resultados: list[ImportResult] = field(default_factory=list)
    competencias_reconsolidadas: list[str] = field(default_factory=list)
    segundos: float = 0.0

    def count(self, acao: str) -> int:
        return sum(1 for r in self.resultados if r.acao == acao)


class SpedDatabase:
    def __init__(self, db_path: str | Path | None = None, parquet_dir: str | Path | None = None):
        config.ensure_dirs()
        self.db_path = Path(db_path or config.DB_PATH)
        self.parquet_dir = Path(parquet_dir or config.PARQUET_DIR)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        self.write_lock = threading.RLock()
        self.con = self._connect()
        self._init_schema()

    # ------------------------------------------------------------------ conexão
    def _connect(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(str(self.db_path))
        con.execute(f"SET threads = {int(config.DUCKDB_THREADS)}")
        con.execute(f"SET memory_limit = '{_memory_limit()}'")
        con.execute(f"SET temp_directory = '{str(config.TEMP_DIR).replace(chr(39), '')}'")
        con.execute("SET preserve_insertion_order = false")
        return con

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Cursor independente (seguro para leitura concorrente a partir de outras threads)."""
        return self.con.cursor()

    def close(self) -> None:
        try:
            self.con.close()
        except Exception:  # noqa: BLE001
            pass

    def _init_schema(self) -> None:
        with self.write_lock:
            self.con.execute((_HERE / "schema.sql").read_text(encoding="utf-8"))
            for t, cols in SCHEMAS.items():
                ddl = ", ".join(f"{c} {_SQL_TYPES[ty]}" for c, ty in cols)
                self.con.execute(f"CREATE TABLE IF NOT EXISTS {t} ({ddl})")
            self.con.executemany("INSERT OR IGNORE INTO ref_uf_ibge VALUES (?, ?)", list(UF_IBGE.items()))
            self.con.executemany("INSERT OR IGNORE INTO ref_item_sintetico VALUES (?, ?)",
                                 list(config.ITEM_SINTETICO_POR_MODELO.items()))
            self.con.executemany("INSERT OR IGNORE INTO ref_cfop_nat_bc_cred VALUES (?, ?)", NAT_BC_CRED_DEFAULT)

    # ------------------------------------------------------------------ util
    def query(self, sql: str, params: list | tuple | None = None):
        cur = self.cursor()
        try:
            return cur.sql(sql, params=list(params) if params else None).pl()
        finally:
            cur.close()

    def scalar(self, sql: str, params: list | tuple | None = None):
        cur = self.cursor()
        try:
            r = cur.execute(sql, params or []).fetchone()
            return r[0] if r else None
        finally:
            cur.close()

    def _log(self, arquivo: str, acao: str, mensagem: str = "") -> None:
        self.con.execute("INSERT INTO sys_log_importacao (arquivo, acao, mensagem) VALUES (?, ?, ?)",
                         [arquivo, acao, mensagem])

    # ------------------------------------------------------------------ importação
    def import_paths(self, paths: Iterable[str | Path], progress: Callable[[str, float], None] | None = None,
                     workers: int | None = None, reconsolidar: bool = True) -> ImportSummary:
        t0 = time.perf_counter()
        prog = progress or (lambda msg, frac: None)
        files: list[Path] = []
        for p in paths:
            files.extend(detector.discover_files(p))
        files = list(dict.fromkeys(f.resolve() for f in files))
        summary = ImportSummary()
        if not files:
            return summary
        workers = max(1, min(workers or config.PARSER_WORKERS, len(files)))
        ctx = mp.get_context("spawn")

        # Etapa 1: cabeçalho + hash (paralelo)
        prog(f"Identificando {len(files)} arquivo(s)...", 0.02)
        headers: list[dict] = []
        if workers > 1 and len(files) > 1:
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
                futs = {ex.submit(detector.inspect_file, str(f)): f for f in files}
                for i, fut in enumerate(as_completed(futs), 1):
                    headers.append(fut.result())
                    prog(f"Identificados {i}/{len(files)}", 0.02 + 0.13 * i / len(files))
        else:
            headers = [detector.inspect_file(str(f)) for f in files]

        # Etapa 2: decisão (duplicado / retificadora / ignorado)
        plan = self._plan_imports(headers, summary)
        if not plan:
            self._finish_log(summary)
            summary.segundos = time.perf_counter() - t0
            return summary

        # Etapa 3: parsing streaming -> Parquet (paralelo)
        prog(f"Lendo {len(plan)} arquivo(s) em {workers} processo(s)...", 0.15)
        jobs = [(h["path"], h["tipo"], h["file_id"], str(self.parquet_dir)) for h in plan]
        results: dict[int, dict] = {}
        if workers > 1 and len(jobs) > 1:
            with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
                futs = [ex.submit(_parse_worker, j) for j in jobs]
                for i, fut in enumerate(as_completed(futs), 1):
                    r = fut.result()
                    results[r["file_id"]] = r
                    prog(f"Arquivos lidos: {i}/{len(jobs)}", 0.15 + 0.55 * i / len(jobs))
        else:
            for i, j in enumerate(jobs, 1):
                r = _parse_worker(j)
                results[r["file_id"]] = r
                prog(f"Arquivos lidos: {i}/{len(jobs)}", 0.15 + 0.55 * i / len(jobs))

        # Etapa 4: carga transacional no DuckDB (um arquivo por transação)
        affected: set[str] = set()
        for i, h in enumerate(plan, 1):
            prog(f"Gravando no banco: {Path(h['path']).name}", 0.70 + 0.15 * i / len(plan))
            r = results[h["file_id"]]
            res = ImportResult(arquivo=h["path"], acao="", tipo=h["tipo"], cnpj=h["cnpj"],
                               competencia=h["competencia"], file_id=h["file_id"])
            if not r["ok"]:
                self._drop_parquet(h["file_id"], h["tipo"])
                res.acao, res.mensagem = "ERRO", r["error"]
            else:
                try:
                    self._load_file(h, r["counts"])
                    res.acao = "SUBSTITUIDO" if h.get("replace_ids") else "IMPORTADO"
                    res.mensagem = (f"{r['counts'].get('_documentos', 0)} documentos de entrada, "
                                    f"{r['counts'].get('_linhas', 0)} linhas, {r['secs']:.1f}s")
                    if h.get("replace_ids"):
                        res.mensagem += f" — substituiu arquivo(s) {h['replace_ids']}"
                    affected.add(h["competencia"])
                    affected.update(h.get("replace_comps", []))
                except Exception as e:  # noqa: BLE001
                    self._drop_parquet(h["file_id"], h["tipo"])
                    res.acao, res.mensagem = "ERRO", f"{type(e).__name__}: {e}"
            summary.resultados.append(res)

        self._finish_log(summary)
        if reconsolidar and affected:
            prog("Consolidando SPED Fiscal x EFD-Contribuições...", 0.88)
            self.rebuild_fato(sorted(affected))
            summary.competencias_reconsolidadas = sorted(affected)
        prog("Concluído", 1.0)
        summary.segundos = time.perf_counter() - t0
        return summary

    def _finish_log(self, summary: ImportSummary) -> None:
        with self.write_lock:
            for r in summary.resultados:
                self._log(r.arquivo, r.acao, r.mensagem)

    def _plan_imports(self, headers: list[dict], summary: ImportSummary) -> list[dict]:
        cur = self.cursor()
        known = {row[0]: row[1] for row in cur.execute(
            "SELECT hash_sha256, ativo FROM sys_arquivos_importados").fetchall()}
        active = {}
        for row in cur.execute("SELECT tipo_sped, cnpj, competencia, id_arquivo, finalidade "
                               "FROM sys_arquivos_importados WHERE ativo").fetchall():
            active.setdefault((row[0], row[1], row[2]), []).append((row[3], row[4]))
        cur.close()

        valid: list[dict] = []
        seen_hash: set[str] = set()
        for h in headers:
            name = h["path"]
            if not h["tipo"] or h["erro"]:
                summary.resultados.append(ImportResult(name, "IGNORADO", h["erro"] or "Não é arquivo SPED"))
                continue
            if h["sha256"] in known:
                msg = "Arquivo idêntico já importado" + ("" if known[h["sha256"]] else " (versão substituída)")
                summary.resultados.append(ImportResult(name, "DUPLICADO", msg, h["tipo"], h["cnpj"], h["competencia"]))
                continue
            if h["sha256"] in seen_hash:
                summary.resultados.append(ImportResult(name, "DUPLICADO", "Arquivo repetido no mesmo lote",
                                                       h["tipo"], h["cnpj"], h["competencia"]))
                continue
            seen_hash.add(h["sha256"])
            valid.append(h)

        # Um vencedor por (tipo, CNPJ, competência): retificadora > original; depois o mais recente no disco
        groups: dict[tuple, list[dict]] = {}
        for h in valid:
            groups.setdefault((h["tipo"], h["cnpj"], h["competencia"]), []).append(h)
        plan: list[dict] = []
        for key, items in groups.items():
            items.sort(key=lambda x: (x["finalidade"] == "RETIFICADORA", os.path.getmtime(x["path"])))
            win = items[-1]
            for loser in items[:-1]:
                summary.resultados.append(ImportResult(loser["path"], "IGNORADO",
                                                       f"Mesmo período/estabelecimento de {Path(win['path']).name} "
                                                       "(versão mais recente no lote prevalece)",
                                                       loser["tipo"], loser["cnpj"], loser["competencia"]))
            existing = active.get(key, [])
            if existing and win["finalidade"] == "ORIGINAL" and any(f == "RETIFICADORA" for _, f in existing):
                summary.resultados.append(ImportResult(win["path"], "IGNORADO",
                                                       "Já existe retificadora ativa para o período; original ignorada",
                                                       win["tipo"], win["cnpj"], win["competencia"]))
                continue
            win["replace_ids"] = [i for i, _ in existing]
            win["replace_comps"] = [key[2]] if existing else []
            plan.append(win)

        with self.write_lock:
            for h in plan:
                h["file_id"] = self.con.execute("SELECT nextval('seq_arquivo')").fetchone()[0]
        return plan

    def _tables_for(self, tipo: str) -> list[str]:
        return RAW_SF if tipo == detector.TIPO_FISCAL else RAW_EC

    def _parquet_files(self, file_id: int, tipo: str) -> list[Path]:
        return [self.parquet_dir / t / f"{file_id}.parquet" for t in self._tables_for(tipo)]

    def _drop_parquet(self, file_id: int, tipo: str) -> None:
        for p in self._parquet_files(file_id, tipo):
            p.unlink(missing_ok=True)

    def _load_file(self, h: dict, counts: dict) -> None:
        fid, tipo = h["file_id"], h["tipo"]
        with self.write_lock:
            self.con.execute("BEGIN TRANSACTION")
            try:
                for old in h.get("replace_ids", []):
                    self._delete_raw(old, tipo)
                    self.con.execute("UPDATE sys_arquivos_importados SET ativo = FALSE, substituido_por = ?, "
                                     "data_substituicao = current_timestamp WHERE id_arquivo = ?", [fid, old])
                for t in self._tables_for(tipo):
                    pq = self.parquet_dir / t / f"{fid}.parquet"
                    if pq.exists() and counts.get(t, 0) > 0:
                        self.con.execute(f"INSERT INTO {t} BY NAME SELECT * FROM read_parquet(?)", [str(pq)])
                self.con.execute(
                    "INSERT INTO sys_arquivos_importados (id_arquivo, hash_sha256, tipo_sped, cnpj, nome, uf, "
                    "competencia, dt_ini, dt_fin, finalidade, cod_ver, caminho_origem, tamanho_bytes, linhas, "
                    "documentos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [fid, h["sha256"], tipo, h["cnpj"], h["nome"], h["uf"], h["competencia"], h["dt_ini"] or None,
                     h["dt_fin"] or None, h["finalidade"], h["cod_ver"], h["path"], h["tamanho"],
                     counts.get("_linhas", 0), counts.get("_documentos", 0)])
                self.con.execute("COMMIT")
            except Exception:
                self.con.execute("ROLLBACK")
                raise
        for old in h.get("replace_ids", []):
            self._drop_parquet(old, tipo)

    def _delete_raw(self, file_id: int, tipo: str) -> None:
        for t in self._tables_for(tipo):
            self.con.execute(f"DELETE FROM {t} WHERE file_id = ?", [file_id])

    # ------------------------------------------------------------------ consolidação
    def _consolidation_steps(self) -> list[tuple[str, str]]:
        sql = (_HERE / "queries_join.sql").read_text(encoding="utf-8")
        q = lambda xs: ", ".join(f"'{x}'" for x in xs)  # noqa: E731 — constantes do config
        sql = (sql.replace("{{COD_SIT_EXCL}}", q(config.COD_SIT_EXCLUIDOS))
                  .replace("{{CST_CRED}}", q(config.CST_PIS_COFINS_CREDITO))
                  .replace("{{CST_IPI_CRED}}", q(config.CST_IPI_CREDITO))
                  .replace("{{ITEM_SINT_C190}}", config.ITEM_SINTETICO_C190))
        m = re.search(r"-- @template alocar\n(.*?)-- @endtemplate\n", sql, re.S)
        template = m.group(1)
        sql = sql[:m.start()] + sql[m.end():]
        steps: list[tuple[str, str]] = []
        name, buf = "inicio", []
        for line in sql.splitlines(keepends=True):
            if line.startswith("-- @step "):
                if "".join(buf).strip():
                    steps.append((name, "".join(buf)))
                name, buf = line[9:].strip(), []
            elif line.startswith("-- @alloc "):
                if "".join(buf).strip():
                    steps.append((name, "".join(buf)))
                level, join = line[10:].split(":", 1)
                steps.append((f"alocar_{level.strip()}",
                              template.replace("{{LEVEL}}", level.strip()).replace("{{JOIN}}", join.strip())))
                name, buf = f"pos_alocar_{level.strip()}", []
            else:
                buf.append(line)
        if "".join(buf).strip():
            steps.append((name, "".join(buf)))
        return steps

    def rebuild_fato(self, competencias: list[str] | None = None,
                     progress: Callable[[str, float], None] | None = None) -> dict:
        """(Re)consolida a tabela fato para as competências informadas (None = todas)."""
        prog = progress or (lambda msg, frac: None)
        t0 = time.perf_counter()
        with self.write_lock:
            cur = self.con.cursor()
            try:
                cur.execute("CREATE OR REPLACE TEMP TABLE _scope (competencia VARCHAR)")
                if competencias is None:
                    cur.execute("INSERT INTO _scope SELECT DISTINCT competencia FROM sys_arquivos_importados "
                                "UNION SELECT DISTINCT competencia FROM fato_entradas_consolidadas")
                else:
                    cur.executemany("INSERT INTO _scope VALUES (?)", [[c] for c in competencias])
                steps = self._consolidation_steps()
                cur.execute("BEGIN TRANSACTION")
                try:
                    for i, (name, sql) in enumerate(steps, 1):
                        prog(f"Consolidação: {name}", i / len(steps))
                        try:
                            cur.execute(sql)
                        except duckdb.Error as e:
                            raise RuntimeError(f"Falha na etapa '{name}': {e}") from e
                    cur.execute("COMMIT")
                except Exception:
                    cur.execute("ROLLBACK")
                    raise
                n = cur.execute("SELECT count(*) FROM fato_entradas_consolidadas WHERE competencia IN "
                                "(SELECT competencia FROM _scope)").fetchone()[0]
            finally:
                cur.close()
        return {"linhas": n, "segundos": time.perf_counter() - t0}

    # ------------------------------------------------------------------ gestão da base
    def list_files(self, somente_ativos: bool = True):
        where = "WHERE ativo" if somente_ativos else ""
        return self.query(f"SELECT id_arquivo, tipo_sped, cnpj, nome, competencia, finalidade, documentos, linhas, "
                          f"round(tamanho_bytes / 1048576.0, 2) AS tamanho_mb, data_importacao, ativo, "
                          f"substituido_por, caminho_origem FROM sys_arquivos_importados {where} "
                          f"ORDER BY competencia DESC, tipo_sped, cnpj")

    def competencias(self) -> list[str]:
        cur = self.cursor()
        try:
            return [r[0] for r in cur.execute("SELECT DISTINCT competencia FROM sys_arquivos_importados "
                                              "WHERE ativo ORDER BY 1").fetchall()]
        finally:
            cur.close()

    def remove_files(self, file_ids: list[int], reconsolidar: bool = True) -> list[str]:
        comps: set[str] = set()
        with self.write_lock:
            for fid in file_ids:
                row = self.con.execute("SELECT tipo_sped, competencia, caminho_origem FROM sys_arquivos_importados "
                                       "WHERE id_arquivo = ?", [fid]).fetchone()
                if not row:
                    continue
                tipo, comp, path = row
                self.con.execute("BEGIN TRANSACTION")
                try:
                    self._delete_raw(fid, tipo)
                    self.con.execute("DELETE FROM sys_arquivos_importados WHERE id_arquivo = ?", [fid])
                    self._log(path, "REMOVIDO", f"Arquivo {fid} ({tipo} {comp}) removido da base")
                    self.con.execute("COMMIT")
                except Exception:
                    self.con.execute("ROLLBACK")
                    raise
                self._drop_parquet(fid, tipo)
                comps.add(comp)
        if reconsolidar and comps:
            self.rebuild_fato(sorted(comps))
        return sorted(comps)

    def remove_competencias(self, competencias: list[str], tipo: str | None = None,
                            cnpjs: list[str] | None = None) -> list[str]:
        sql = "SELECT id_arquivo FROM sys_arquivos_importados WHERE competencia IN (SELECT unnest(?))"
        params: list = [competencias]
        if tipo:
            sql += " AND tipo_sped = ?"
            params.append(tipo)
        if cnpjs:
            sql += " AND cnpj IN (SELECT unnest(?))"
            params.append(cnpjs)
        cur = self.cursor()
        ids = [r[0] for r in cur.execute(sql, params).fetchall()]
        cur.close()
        self.remove_files(ids)
        return competencias

    def coverage_matrix(self):
        """Filiais (linhas) x competências (colunas): AMBOS | SF | EC | '' (ausente)."""
        return self.query("""
            WITH sf AS (
                SELECT DISTINCT cnpj, competencia FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'ICMS_IPI'
            ), ec AS (
                SELECT DISTINCT e.cnpj, a.competencia FROM ec_estab e
                JOIN sys_arquivos_importados a ON a.id_arquivo = e.file_id AND a.ativo
                UNION
                SELECT DISTINCT cnpj, competencia FROM sys_arquivos_importados WHERE ativo AND tipo_sped = 'CONTRIB'
            ), filiais AS (SELECT cnpj FROM sf UNION SELECT cnpj FROM ec),
            comps AS (SELECT competencia FROM sf UNION SELECT competencia FROM ec)
            SELECT f.cnpj, coalesce(d.nome_filial, '') AS nome, coalesce(d.uf_filial, '') AS uf, c.competencia,
                   CASE WHEN sf.cnpj IS NOT NULL AND ec.cnpj IS NOT NULL THEN 'AMBOS'
                        WHEN sf.cnpj IS NOT NULL THEN 'SF' WHEN ec.cnpj IS NOT NULL THEN 'EC' ELSE '' END AS status
            FROM filiais f CROSS JOIN comps c
            LEFT JOIN sf ON sf.cnpj = f.cnpj AND sf.competencia = c.competencia
            LEFT JOIN ec ON ec.cnpj = f.cnpj AND ec.competencia = c.competencia
            LEFT JOIN dim_filial d ON d.cnpj_filial = f.cnpj
            ORDER BY f.cnpj, c.competencia
        """)

    def stats(self) -> dict:
        cur = self.cursor()
        try:
            r = cur.execute("""SELECT
                (SELECT count(*) FROM sys_arquivos_importados WHERE ativo),
                (SELECT count(*) FROM sys_arquivos_importados WHERE ativo AND tipo_sped='ICMS_IPI'),
                (SELECT count(*) FROM sys_arquivos_importados WHERE ativo AND tipo_sped='CONTRIB'),
                (SELECT count(*) FROM fato_entradas_consolidadas),
                (SELECT count(DISTINCT cnpj_filial) FROM fato_entradas_consolidadas),
                (SELECT count(DISTINCT competencia) FROM fato_entradas_consolidadas)""").fetchone()
        finally:
            cur.close()
        size = self.db_path.stat().st_size if self.db_path.exists() else 0
        pq_size = sum(p.stat().st_size for p in self.parquet_dir.rglob("*.parquet"))
        return {"arquivos": r[0], "arquivos_sf": r[1], "arquivos_ec": r[2], "linhas_fato": r[3], "filiais": r[4],
                "competencias": r[5], "db_mb": size / 1048576, "parquet_mb": pq_size / 1048576}

    def import_log(self, limit: int = 500):
        return self.query("SELECT data, acao, arquivo, mensagem FROM sys_log_importacao ORDER BY id DESC LIMIT ?",
                          [limit])

    # ------------------------------------------------------------------ sessão (auto-save)
    def session_get(self, chave: str, default=None):
        v = self.scalar("SELECT valor FROM sys_sessao WHERE chave = ?", [chave])
        return json.loads(v) if v else default

    def session_set(self, chave: str, valor) -> None:
        with self.write_lock:
            self.con.execute("INSERT OR REPLACE INTO sys_sessao VALUES (?, ?, current_timestamp)",
                             [chave, json.dumps(valor, ensure_ascii=False, default=str)])
        try:
            config.SESSION_PATH.write_text(json.dumps({chave: valor}, ensure_ascii=False, default=str),
                                           encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------ backup
    def backup(self, dest: str | Path | None = None, incluir_parquet: bool = False) -> Path:
        dest = Path(dest or config.BACKUP_DIR / f"backup_sped_{datetime.now():%Y%m%d_%H%M%S}.zip")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.write_lock:
            self.con.execute("CHECKPOINT")
            with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
                z.write(self.db_path, "sped_master.duckdb")
                if config.PRESETS_PATH.exists():
                    z.write(config.PRESETS_PATH, "user_presets.json")
                for p in config.SNAPSHOT_DIR.glob("*"):
                    z.write(p, f"snapshots/{p.name}")
                if incluir_parquet:
                    for p in self.parquet_dir.rglob("*.parquet"):
                        z.write(p, f"parquet_store/{p.relative_to(self.parquet_dir)}")
        return dest

    def restore(self, src: str | Path) -> None:
        src = Path(src)
        with zipfile.ZipFile(src) as z:
            names = z.namelist()
            if "sped_master.duckdb" not in names:
                raise ValueError("Backup inválido: sped_master.duckdb ausente")
            with self.write_lock:
                self.close()
                safety = self.db_path.with_suffix(f".antes_restauracao_{datetime.now():%Y%m%d_%H%M%S}.duckdb")
                if self.db_path.exists():
                    shutil.move(self.db_path, safety)
                wal = Path(str(self.db_path) + ".wal")
                wal.unlink(missing_ok=True)
                tmp = config.DATA_DIR / "_restore_tmp"
                shutil.rmtree(tmp, ignore_errors=True)
                z.extractall(tmp)
                shutil.move(tmp / "sped_master.duckdb", self.db_path)
                if (tmp / "user_presets.json").exists():
                    shutil.copy2(tmp / "user_presets.json", config.PRESETS_PATH)
                if (tmp / "snapshots").exists():
                    for p in (tmp / "snapshots").iterdir():
                        shutil.copy2(p, config.SNAPSHOT_DIR / p.name)
                if (tmp / "parquet_store").exists():
                    shutil.copytree(tmp / "parquet_store", self.parquet_dir, dirs_exist_ok=True)
                shutil.rmtree(tmp, ignore_errors=True)
                self.con = self._connect()
                self._init_schema()


_DB: SpedDatabase | None = None


def get_db() -> SpedDatabase:
    global _DB
    if _DB is None:
        _DB = SpedDatabase()
    return _DB
