"""Checagens de completude e integridade (SPEC 7.1, Q1 e Q2).

Q3 a Q11 entram na Fase 3 (zfm/conciliacoes.py).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from .empresas import estabelecimentos

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

OK = "OK"
FALTA_ICMS = "Falta EFD ICMS/IPI"
FALTA_CONTRIB = "Falta EFD Contribuições"
FALTAM_AMBAS = "Faltam as duas"


def periodo_padrao(con: duckdb.DuckDBPyConnection, ano: int = 2026) -> tuple[int, int]:
    """(ano, ultimo_mes) para o YTD: ultimo mes com algum arquivo ativo no ano."""
    r = con.execute(
        "SELECT max(month(dt_ini)) FROM arquivos WHERE ativo AND year(dt_ini) = ?", [ano]
    ).fetchall()
    return ano, int(r[0][0]) if r and r[0][0] else 0


def q1_completude(con: duckdb.DuckDBPyConnection, ano: int = 2026,
                  mes_fim: int | None = None) -> pd.DataFrame:
    """Matriz estabelecimento x mes: as duas EFDs existem para cada mes do YTD?

    Por estabelecimento do AM: EFD ICMS/IPI do proprio CNPJ e EFD Contribuicoes
    da empresa (raiz do CNPJ), que e entregue pela matriz.
    """
    if mes_fim is None:
        _, mes_fim = periodo_padrao(con, ano)
    est = estabelecimentos(con)
    est = est[est["no_amazonas"]] if not est.empty else est
    colunas = ["raiz", "cnpj", "ie", "nome"] + MESES[:mes_fim]
    if est.empty or mes_fim == 0:
        return pd.DataFrame(columns=colunas)
    arq = con.execute(
        """SELECT tipo, cnpj, raiz, month(dt_ini) AS mes FROM arquivos
           WHERE ativo AND year(dt_ini) = ?""", [ano]).df()
    icms = set(zip(arq.loc[arq.tipo == "ICMS_IPI", "cnpj"], arq.loc[arq.tipo == "ICMS_IPI", "mes"]))
    contrib = set(zip(arq.loc[arq.tipo == "CONTRIB", "raiz"], arq.loc[arq.tipo == "CONTRIB", "mes"]))
    linhas = []
    for _, e in est.iterrows():
        linha = {"raiz": e["raiz"], "cnpj": e["cnpj"], "ie": e["ie"], "nome": e["nome"]}
        for m in range(1, mes_fim + 1):
            tem_i = (e["cnpj"], m) in icms
            tem_c = (e["raiz"], m) in contrib
            linha[MESES[m - 1]] = (OK if tem_i and tem_c else FALTA_ICMS if tem_c
                                   else FALTA_CONTRIB if tem_i else FALTAM_AMBAS)
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=colunas)


def q2_integridade(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Contagens do bloco 9 (9900 e 9999) x registros efetivamente lidos."""
    return con.execute(
        """
        SELECT a.arquivo_id, a.nome_arquivo, a.tipo, a.cnpj, a.dt_ini,
               c.reg AS registro, c.qtd_lida AS qtd_lida,
               c.qtd_9900 AS qtd_informada_9900,
               CASE WHEN c.qtd_9900 IS NULL THEN 'Registro sem linha no 9900'
                    ELSE 'Quantidade diferente do 9900' END AS problema
        FROM arquivo_contagens c JOIN arquivos a USING (arquivo_id)
        WHERE a.ativo AND (c.qtd_9900 IS NULL OR c.qtd_9900 <> c.qtd_lida)
        UNION ALL
        SELECT a.arquivo_id, a.nome_arquivo, a.tipo, a.cnpj, a.dt_ini,
               '9999', a.qtd_linhas, a.qtd_linhas_9999,
               CASE WHEN a.qtd_linhas_9999 IS NULL THEN 'Arquivo sem registro 9999'
                    ELSE 'Total de linhas diferente do 9999' END
        FROM arquivos a
        WHERE a.ativo AND (a.qtd_linhas_9999 IS NULL OR a.qtd_linhas_9999 <> a.qtd_linhas)
        ORDER BY 1, 6
        """).df()


def avisos_carga(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        """SELECT a.nome_arquivo, v.reg AS registro, v.mensagem, v.qtd AS ocorrencias,
                  v.linha_exemplo
           FROM avisos_carga v JOIN arquivos a USING (arquivo_id)
           WHERE a.ativo ORDER BY a.nome_arquivo, v.reg""").df()


def arquivos_carregados(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        """SELECT arquivo_id, nome_arquivo,
                  CASE tipo WHEN 'ICMS_IPI' THEN 'EFD ICMS/IPI' ELSE 'EFD Contribuições' END AS tipo,
                  cnpj, ie, uf, nome, strftime(dt_ini, '%m/%Y') AS periodo, cod_ver AS versao_layout,
                  CASE WHEN retificador THEN 'Sim' ELSE 'Não' END AS retificadora,
                  CASE WHEN ativo THEN 'Em uso' ELSE 'Substituído' END AS situacao,
                  qtd_linhas, strftime(dt_carga, '%d/%m/%Y %H:%M') AS carregado_em
           FROM arquivos ORDER BY tipo, cnpj, dt_ini, arquivo_id""").df()
