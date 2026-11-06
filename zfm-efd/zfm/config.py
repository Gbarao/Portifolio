"""Caminhos do projeto e registro de log (tudo local, dentro de data/)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    """Pasta data/ do projeto. ZFM_DATA_DIR permite apontar outra pasta (testes)."""
    p = Path(os.environ.get("ZFM_DATA_DIR") or (RAIZ_PROJETO / "data"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def caminho_banco() -> Path:
    return pasta_dados() / "zfm.duckdb"


def pasta_logs() -> Path:
    p = pasta_dados() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


_LOG_CONFIGURADO = False


def logger() -> logging.Logger:
    global _LOG_CONFIGURADO
    log = logging.getLogger("zfm")
    if not _LOG_CONFIGURADO:
        log.setLevel(logging.INFO)
        h = RotatingFileHandler(pasta_logs() / "zfm.log", maxBytes=5_000_000,
                                backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(h)
        _LOG_CONFIGURADO = True
    return log
