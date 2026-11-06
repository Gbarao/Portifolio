"""Banco local DuckDB: criacao das tabelas e carga em lotes.

Uma tabela bruta por registro: raw_icms_c100, raw_contrib_m210 etc. As
colunas recebem o nome do campo do Guia Pratico, mais arquivo_id, linha_num,
pai_linha (linha do registro pai) e cnpj_estab (estabelecimento propagado).
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .config import caminho_banco
from .layouts import efd_contrib, efd_icms_ipi
from .layouts.comum import Registro, tipo_coluna

LAYOUTS = {
    efd_icms_ipi.TIPO: efd_icms_ipi.REGISTROS,
    efd_contrib.TIPO: efd_contrib.REGISTROS,
}
PREFIXO = {efd_icms_ipi.TIPO: "icms", efd_contrib.TIPO: "contrib"}
COLUNAS_CONTROLE = ("arquivo_id", "linha_num", "pai_linha", "cnpj_estab", "layout_versao")


def tabela_raw(tipo: str, reg: str) -> str:
    return f"raw_{PREFIXO[tipo]}_{reg.lower()}"


def _ddl_raw(tipo: str, r: Registro) -> str:
    cols = [
        "arquivo_id INTEGER NOT NULL",
        "linha_num BIGINT NOT NULL",
        "pai_linha BIGINT",
        "cnpj_estab VARCHAR",
        "layout_versao VARCHAR",
    ]
    cols += [f'"{c}" {tipo_coluna(c)}' for c in r.campos_uniao]
    return f"CREATE TABLE IF NOT EXISTS {tabela_raw(tipo, r.reg)} ({', '.join(cols)})"


_DDL_CONTROLE = [
    "CREATE SEQUENCE IF NOT EXISTS seq_arquivo START 1",
    """CREATE TABLE IF NOT EXISTS arquivos (
        arquivo_id INTEGER PRIMARY KEY,
        tipo VARCHAR NOT NULL,
        cnpj VARCHAR, raiz VARCHAR, ie VARCHAR, uf VARCHAR, nome VARCHAR,
        dt_ini DATE, dt_fin DATE,
        cod_ver VARCHAR, cod_fin VARCHAR, retificador BOOLEAN,
        hash_sha256 VARCHAR, nome_arquivo VARCHAR, caminho VARCHAR, encoding VARCHAR,
        dt_carga TIMESTAMP, ativo BOOLEAN, substituido_por INTEGER,
        qtd_linhas BIGINT, bytes BIGINT, qtd_linhas_9999 BIGINT
    )""",
    """CREATE TABLE IF NOT EXISTS arquivo_contagens (
        arquivo_id INTEGER, reg VARCHAR, qtd_lida BIGINT, qtd_9900 BIGINT
    )""",
    """CREATE TABLE IF NOT EXISTS avisos_carga (
        arquivo_id INTEGER, reg VARCHAR, tipo_aviso VARCHAR, mensagem VARCHAR,
        qtd BIGINT, linha_exemplo BIGINT
    )""",
]


def criar_esquema(con: duckdb.DuckDBPyConnection) -> None:
    for ddl in _DDL_CONTROLE:
        con.execute(ddl)
    for tipo, registros in LAYOUTS.items():
        for r in registros.values():
            if r.carregar:
                con.execute(_ddl_raw(tipo, r))


def conectar(caminho: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    caminho = Path(caminho) if caminho else caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(caminho))
    criar_esquema(con)
    return con


def _expr_cast(coluna: str) -> str:
    t = tipo_coluna(coluna)
    c = f'NULLIF(TRIM("{coluna}"), \'\')'
    if t.startswith("DECIMAL"):
        return f"TRY_CAST(REPLACE({c}, ',', '.') AS {t})"
    if t == "DATE":
        return f"TRY_CAST(TRY_STRPTIME({c}, '%d%m%Y') AS DATE)"
    if t == "BIGINT":
        return f"TRY_CAST({c} AS BIGINT)"
    return f'NULLIF("{coluna}", \'\')'


def inserir_csv(con: duckdb.DuckDBPyConnection, tipo: str, reg: str,
                campos: tuple[str, ...], caminho_csv: str | Path) -> None:
    """Grava no banco um arquivo temporario (separado por |, texto cru) de um registro.

    A conversao de tipos e feita no SQL: decimais com virgula viram DECIMAL
    exato (sem ponto flutuante) e datas DDMMAAAA viram DATE.
    """
    colunas = list(COLUNAS_CONTROLE) + list(campos)
    defs = ", ".join(f"'{c}': 'VARCHAR'" for c in colunas)
    caminho = str(caminho_csv).replace("'", "''")
    destino = ", ".join(list(COLUNAS_CONTROLE) + [f'"{c}"' for c in campos])
    origem = ", ".join(
        ["CAST(arquivo_id AS INTEGER)", "CAST(linha_num AS BIGINT)",
         "TRY_CAST(pai_linha AS BIGINT)", "cnpj_estab", "layout_versao"]
        + [_expr_cast(c) for c in campos])
    con.execute(
        f"INSERT INTO {tabela_raw(tipo, reg)} ({destino}) SELECT {origem} FROM read_csv("
        f"'{caminho}', delim='|', quote='', escape='', header=false, auto_detect=false, "
        f"encoding='utf-8', columns={{{defs}}})")


def consultar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    return con.execute(sql, params or []).df()


def apagar_dados(con: duckdb.DuckDBPyConnection) -> None:
    """Remove todos os dados carregados (as EFDs originais nao sao tocadas)."""
    tabelas = [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        " AND table_type = 'BASE TABLE'").fetchall()]
    for t in tabelas:
        if t.startswith("raw_") or t in ("arquivos", "arquivo_contagens", "avisos_carga"):
            con.execute(f"DELETE FROM {t}")
