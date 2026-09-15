"""Cache SQLite: torna a execucao idempotente e retomavel."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .parser import Resultado

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consultas (
    chave              TEXT PRIMARY KEY,
    raiz               TEXT,
    status             TEXT NOT NULL,
    cnpj_retornado     TEXT,
    nome_empresarial   TEXT,
    situacao_simples   TEXT,
    situacao_simei     TEXT,
    optante_simples    INTEGER,
    optante_simei      INTEGER,
    data_consulta      TEXT,
    mensagem           TEXT,
    atualizado_em      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consultas_raiz ON consultas(raiz);
CREATE INDEX IF NOT EXISTS idx_consultas_status ON consultas(status);
"""


class Cache:
    """Uma linha por CNPJ consultado. Reexecutar o job nao repete requisicao."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.caminho, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(_SCHEMA)

    def concluidos(self, incluir_erros: bool = False) -> set[str]:
        """Chaves ja resolvidas; por padrao erros ficam de fora para retentativa."""
        sql = "SELECT chave FROM consultas"
        if not incluir_erros:
            sql += " WHERE status = 'OK'"
        return {linha[0] for linha in self.con.execute(sql)}

    def gravar(self, resultado: Resultado, raiz: str | None = None) -> None:
        self.con.execute(
            """
            INSERT INTO consultas (chave, raiz, status, cnpj_retornado, nome_empresarial,
                                   situacao_simples, situacao_simei, optante_simples,
                                   optante_simei, data_consulta, mensagem, atualizado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(chave) DO UPDATE SET
                raiz=excluded.raiz, status=excluded.status,
                cnpj_retornado=excluded.cnpj_retornado,
                nome_empresarial=excluded.nome_empresarial,
                situacao_simples=excluded.situacao_simples,
                situacao_simei=excluded.situacao_simei,
                optante_simples=excluded.optante_simples,
                optante_simei=excluded.optante_simei,
                data_consulta=excluded.data_consulta,
                mensagem=excluded.mensagem,
                atualizado_em=excluded.atualizado_em
            """,
            (
                resultado.cnpj_consultado,
                raiz,
                resultado.status,
                resultado.cnpj_retornado,
                resultado.nome_empresarial,
                resultado.situacao_simples,
                resultado.situacao_simei,
                _bool(resultado.optante_simples),
                _bool(resultado.optante_simei),
                resultado.data_consulta,
                resultado.mensagem,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )

    def por_chave(self) -> dict[str, dict]:
        return {
            linha["chave"]: dict(linha)
            for linha in self.con.execute("SELECT * FROM consultas")
        }

    def contagem_por_status(self) -> dict[str, int]:
        return {
            l[0]: l[1]
            for l in self.con.execute(
                "SELECT status, COUNT(*) FROM consultas GROUP BY status"
            )
        }

    def fechar(self) -> None:
        self.con.close()


def _bool(valor: bool | None) -> int | None:
    return None if valor is None else int(valor)
