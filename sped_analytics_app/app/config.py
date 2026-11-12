"""Configurações locais: diretórios, paralelismo, memória e regras de negócio parametrizáveis."""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------------------
# Diretórios (100% locais). SPED_DATA_DIR permite apontar o cofre para outro disco.
# --------------------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
BASE_DIR = APP_DIR.parent
DATA_DIR = Path(os.environ.get("SPED_DATA_DIR", BASE_DIR / "data")).resolve()
PARQUET_DIR = DATA_DIR / "parquet_store"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
BACKUP_DIR = DATA_DIR / "backups"
TEMP_DIR = DATA_DIR / "duckdb_tmp"
DB_PATH = DATA_DIR / "sped_master.duckdb"
PRESETS_PATH = DATA_DIR / "user_presets.json"
SESSION_PATH = DATA_DIR / "last_session.json"

# --------------------------------------------------------------------------------------
# Desempenho
# --------------------------------------------------------------------------------------
CPU_COUNT = os.cpu_count() or 2
PARSER_WORKERS = int(os.environ.get("SPED_PARSER_WORKERS", max(1, CPU_COUNT - 1)))
PARSER_BATCH_ROWS = int(os.environ.get("SPED_BATCH_ROWS", 200_000))  # flush para Parquet a cada N linhas
DUCKDB_THREADS = int(os.environ.get("SPED_DUCKDB_THREADS", CPU_COUNT))
DUCKDB_MEMORY_LIMIT = os.environ.get("SPED_DUCKDB_MEMORY", "60%")  # acima disso o DuckDB faz spill em disco
PARQUET_COMPRESSION = "zstd"
PARQUET_COMPRESSION_LEVEL = 6
FILE_ENCODING = "latin-1"  # leiaute oficial: ISO-8859-1

# --------------------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------------------
UI_HOST = "127.0.0.1"  # nunca expor na rede
UI_PORT = int(os.environ.get("SPED_UI_PORT", 8765))
UI_MAX_GRID_ROWS = 50_000  # linhas máximas enviadas à grade (o restante via exportação)
UI_MAX_DRILL_ROWS = 5_000

# --------------------------------------------------------------------------------------
# Regras de negócio
# --------------------------------------------------------------------------------------
# Situações de documento excluídas da consolidação (cancelado, cancelado extemporâneo, denegado, inutilizado)
COD_SIT_EXCLUIDOS = ("02", "03", "04", "05")

# CST PIS/COFINS de entrada com direito a crédito (Tabela 4.3.3)
CST_PIS_COFINS_CREDITO = tuple(str(c) for c in range(50, 57)) + tuple(str(c) for c in range(60, 67))

# CST IPI de entrada com recuperação de crédito
CST_IPI_CREDITO = ("00",)

# TIPO_ITEM considerados insumo/revenda na auditoria de créditos
TIPO_ITEM_INSUMO_REVENDA = ("00", "01", "02", "03", "04", "05", "06", "10")

# Itens sintéticos (registros sem COD_ITEM discriminado)
ITEM_SINTETICO_POR_MODELO = {
    "06": "_ENERGIA_", "66": "_ENERGIA_",  # NF energia elétrica / NF3e
    "28": "_GAS_", "29": "_AGUA_",
    "21": "_TELECOM_", "22": "_TELECOM_", "62": "_TELECOM_",
    "07": "_FRETE_CTE_", "08": "_FRETE_CTE_", "8B": "_FRETE_CTE_", "09": "_FRETE_CTE_",
    "10": "_FRETE_CTE_", "11": "_FRETE_CTE_", "26": "_FRETE_CTE_", "27": "_FRETE_CTE_",
    "57": "_FRETE_CTE_", "63": "_FRETE_CTE_", "67": "_FRETE_CTE_",
}
ITEM_SINTETICO_C190 = "_SEM_ITEM_C190_"

TOLERANCIA_DIVERGENCIA = 0.05  # R$ — diferenças abaixo disso não são apontadas na auditoria


def ensure_dirs() -> None:
    for d in (DATA_DIR, PARQUET_DIR, SNAPSHOT_DIR, BACKUP_DIR, TEMP_DIR):
        d.mkdir(parents=True, exist_ok=True)
