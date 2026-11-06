"""Perimetro de empresas (SPEC 5.3): cadastro automatico a partir das EFDs.

Niveis: grupo (selecao do usuario) > empresa (raiz do CNPJ, 8 digitos) >
estabelecimento (CNPJ completo + IE).
"""
from __future__ import annotations

import duckdb
import pandas as pd

SQL_ESTABELECIMENTOS = """
WITH fontes AS (
    SELECT r.CNPJ AS cnpj, r.IE AS ie, r.UF AS uf, r.NOME AS nome, r.COD_MUN AS cod_mun,
           r.SUFRAMA AS suframa, a.dt_ini, 1 AS prioridade, TRUE AS tem_icms, FALSE AS tem_contrib
    FROM arquivos a JOIN raw_icms_0000 r USING (arquivo_id)
    WHERE a.ativo
    UNION ALL
    SELECT r.CNPJ, r.IE, r.UF, r.NOME, r.COD_MUN, r.SUFRAMA, a.dt_ini, 2, FALSE, TRUE
    FROM arquivos a JOIN raw_contrib_0140 r USING (arquivo_id)
    WHERE a.ativo
    UNION ALL
    SELECT r.CNPJ, NULL, r.UF, r.NOME, r.COD_MUN, r.SUFRAMA, a.dt_ini, 3, FALSE, TRUE
    FROM arquivos a JOIN raw_contrib_0000 r USING (arquivo_id)
    WHERE a.ativo
)
SELECT
    cnpj,
    substr(cnpj, 1, 8) AS raiz,
    arg_min(ie, prioridade * 100000000 - epoch(dt_ini)) FILTER (WHERE ie IS NOT NULL) AS ie,
    arg_min(uf, prioridade * 100000000 - epoch(dt_ini)) AS uf,
    arg_min(nome, prioridade * 100000000 - epoch(dt_ini)) AS nome,
    arg_min(cod_mun, prioridade * 100000000 - epoch(dt_ini)) AS cod_mun,
    arg_min(suframa, prioridade * 100000000 - epoch(dt_ini)) FILTER (WHERE suframa IS NOT NULL) AS suframa,
    bool_or(tem_icms) AS tem_efd_icms_ipi,
    bool_or(tem_contrib) AS na_efd_contribuicoes,
    arg_min(uf, prioridade * 100000000 - epoch(dt_ini)) = 'AM' AS no_amazonas
FROM fontes
WHERE cnpj IS NOT NULL
GROUP BY cnpj
ORDER BY cnpj
"""


def estabelecimentos(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(SQL_ESTABELECIMENTOS).df()


def empresas(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Uma linha por raiz de CNPJ, com a razao social mais recente."""
    est = estabelecimentos(con)
    if est.empty:
        return pd.DataFrame(columns=["raiz", "razao_social", "qtd_estab", "qtd_estab_am"])
    g = est.groupby("raiz").agg(
        razao_social=("nome", "first"),
        qtd_estab=("cnpj", "count"),
        qtd_estab_am=("no_amazonas", "sum"),
    ).reset_index()
    g["qtd_estab_am"] = g["qtd_estab_am"].astype(int)
    return g
