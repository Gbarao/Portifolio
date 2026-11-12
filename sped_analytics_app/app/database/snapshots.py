"""Análises congeladas (snapshots imutáveis em Parquet, com hash de integridade)."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import polars as pl

from app import config


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def save_snapshot(db, nome: str, anotacoes: str, contexto: dict, df: pl.DataFrame) -> int:
    config.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with db.write_lock:
        sid = db.con.execute("SELECT nextval('seq_snapshot')").fetchone()[0]
        path = config.SNAPSHOT_DIR / f"snapshot_{sid:06d}.parquet"
        df.write_parquet(path, compression="zstd")
        try:
            os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)  # somente leitura
        except OSError:
            pass
        db.con.execute("INSERT INTO sys_snapshots_analises (id, nome, anotacoes, contexto_json, arquivo, linhas, "
                       "hash_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       [sid, nome, anotacoes, json.dumps(contexto, ensure_ascii=False, default=str), path.name,
                        df.height, _sha(path)])
    return sid


def list_snapshots(db) -> list[dict]:
    cur = db.cursor()
    try:
        rows = cur.execute("SELECT id, nome, anotacoes, criado_em, linhas, contexto_json FROM sys_snapshots_analises "
                           "ORDER BY id DESC").fetchall()
    finally:
        cur.close()
    return [{"id": r[0], "nome": r[1], "anotacoes": r[2] or "", "criado_em": str(r[3])[:19], "linhas": r[4],
             "contexto": json.loads(r[5] or "{}")} for r in rows]


def load_snapshot(db, sid: int) -> tuple[dict, pl.DataFrame, bool]:
    """Retorna (metadados, dados, integridade_ok)."""
    cur = db.cursor()
    try:
        r = cur.execute("SELECT id, nome, anotacoes, criado_em, contexto_json, arquivo, hash_sha256 "
                        "FROM sys_snapshots_analises WHERE id = ?", [sid]).fetchone()
    finally:
        cur.close()
    if not r:
        raise KeyError(sid)
    path = config.SNAPSHOT_DIR / r[5]
    meta = {"id": r[0], "nome": r[1], "anotacoes": r[2] or "", "criado_em": str(r[3])[:19],
            "contexto": json.loads(r[4] or "{}")}
    if not path.exists():
        return meta, pl.DataFrame(), False
    return meta, pl.read_parquet(path), _sha(path) == r[6]


def delete_snapshot(db, sid: int) -> None:
    cur = db.cursor()
    r = cur.execute("SELECT arquivo FROM sys_snapshots_analises WHERE id = ?", [sid]).fetchone()
    cur.close()
    with db.write_lock:
        db.con.execute("DELETE FROM sys_snapshots_analises WHERE id = ?", [sid])
    if r:
        p = config.SNAPSHOT_DIR / r[0]
        if p.exists():
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            p.unlink()
