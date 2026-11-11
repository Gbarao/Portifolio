# -*- coding: utf-8 -*-
"""
Base de dados local (DuckDB): carga, garantias contra duplicidade e tabelas
derivadas.

Como a duplicidade é evitada
----------------------------
1. Arquivo: o mesmo conteúdo nunca entra duas vezes. Há dois hashes: o dos
   bytes (mesmo arquivo com outro nome) e o do conteúdo normalizado (mesmo
   arquivo regravado em outra codificação ou com outra quebra de linha).
2. Versão: uma escrituração por empresa/IE, tipo de EFD e período. Original +
   retificadora: fica a retificadora. Dois arquivos do mesmo tipo para o mesmo
   período: a carga dos novos é bloqueada, porque o arquivo não diz qual é o
   mais recente.
3. Carga: cada arquivo entra em uma transação. A contagem de linhas e a soma
   de cada coluna de valor gravadas no banco têm de ser iguais às calculadas
   durante a leitura, e a chave (arquivo, linha) tem de ser única. Qualquer
   diferença desfaz a transação.
4. Documento: o mesmo documento escriturado mais de uma vez na mesma EFD
   (por exemplo, em dois períodos) conta uma vez. As demais ocorrências ficam
   marcadas como repetidas, visíveis na aba de conferências e fora dos totais.
5. Consolidação: a visão é uma união das duas escriturações seguida de soma
   condicional por fonte. Não há junção entre as tabelas de fatos, então uma
   linha nunca é multiplicada. As junções auxiliares são feitas com tabelas
   de chave única e a contagem de linhas é conferida ao final.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata

import duckdb

from .leiautes import (COLUNAS_ANA, COLUNAS_DOCS, COLUNAS_ITENS, CONTRIB, FISCAL,
                       INTEIRO_ANA, MEDIDAS, MEDIDAS_ANA, MEDIDAS_DOCS,
                       TEXTO_ANA, TEXTO_DOCS, TEXTO_ITENS)
from .leitor import identidade, inspecionar, processar_arquivo
from . import comando_modulo

_DATAS = ("periodo", "dt_doc", "dt_e_s")
_C2 = "0.01::DECIMAL(3,2)"

# Colunas da visão pré-agregada (tudo que não depende do documento).
DIMENSOES_VISAO = [
    "fonte", "registro", "empresa_raiz", "empresa_nome", "estab_cnpj", "periodo",
    "estab_nome", "part_doc", "cfop", "cfop_conc", "cod_item", "ncm", "cst_icms", "cst_pis",
    "cst_cofins", "cod_mod", "pareamento", "nat_bc_cred", "regime",
]


TABELAS_POR_ARQUIVO = ("itens_base", "docs_base", "analitico_base", "txt_base", "arquivos")


class ErroDeCarga(Exception):
    pass


# ============================================================================
# Conexão e esquema
# ============================================================================

def _tipo_coluna(c: str) -> str:
    if c in _DATAS:
        return "DATE"
    if c in ("linha", "linha_doc", "n_itens"):
        return "BIGINT"
    if c == "qtd_e5":
        return "DECIMAL(18,5)"
    if c == "aliq_icms_e2":
        return "DECIMAL(9,2)"
    if c in ("aliq_pis_e4", "aliq_cofins_e4"):
        return "DECIMAL(11,4)"
    if c in MEDIDAS or c in MEDIDAS_DOCS or c in MEDIDAS_ANA:
        return "DECIMAL(18,2)"
    return "VARCHAR"


def _nome_final(c: str) -> str:
    return {"qtd_e5": "qtd", "aliq_icms_e2": "aliq_icms", "aliq_pis_e4": "aliq_pis",
            "aliq_cofins_e4": "aliq_cofins"}.get(c, c)


def _ddl(tabela: str, colunas) -> str:
    cols = ", ".join(f"{_nome_final(c)} {_tipo_coluna(c)}" for c in colunas)
    return f"CREATE TABLE IF NOT EXISTS {tabela} (arquivo_id INTEGER, {cols})"


def _expr_carga(c: str, textos) -> str:
    """Expressão que converte a coluna do Parquet para o tipo final."""
    if c in _DATAS:
        return f"TRY_CAST({c} AS DATE)"
    if c == "doc_id":
        return "doc_id"
    if c in textos:
        return f"coalesce({c}, '')"
    if c == "qtd_e5":
        return "(qtd_e5 * 0.00001::DECIMAL(6,5))::DECIMAL(18,5)"
    if c == "aliq_icms_e2":
        return f"(aliq_icms_e2 * {_C2})::DECIMAL(9,2)"
    if c in ("aliq_pis_e4", "aliq_cofins_e4"):
        return f"({c} * 0.0001::DECIMAL(5,4))::DECIMAL(11,4)"
    if c in ("linha", "linha_doc", "n_itens"):
        return c
    return f"({c} * {_C2})::DECIMAL(18,2)"


def abrir(caminho_db: str):
    """Abre (ou cria) a base e garante o esquema."""
    os.makedirs(os.path.dirname(os.path.abspath(caminho_db)), exist_ok=True)
    con = duckdb.connect(caminho_db)
    con.execute("""
        CREATE TABLE IF NOT EXISTS arquivos (
            arquivo_id INTEGER PRIMARY KEY, tipo VARCHAR, cnpj VARCHAR, ie VARCHAR,
            empresa_raiz VARCHAR, nome VARCHAR, uf VARCHAR, dt_ini DATE,
            dt_fin DATE, periodo DATE, finalidade VARCHAR, retificadora BOOLEAN,
            cod_ver VARCHAR, caminho VARCHAR, nome_arquivo VARCHAR,
            tamanho BIGINT, hash_bruto VARCHAR UNIQUE,
            hash_conteudo VARCHAR UNIQUE, encoding VARCHAR, linhas BIGINT,
            carregado_em TIMESTAMP, segundos DOUBLE, meta VARCHAR)""")
    con.execute("CREATE SEQUENCE IF NOT EXISTS seq_arquivo START 1")
    con.execute(_ddl("itens_base", COLUNAS_ITENS))
    con.execute(_ddl("docs_base", COLUNAS_DOCS))
    con.execute(_ddl("analitico_base", COLUNAS_ANA))
    con.execute("""CREATE TABLE IF NOT EXISTS txt_base (arquivo_id INTEGER, registro VARCHAR,
                   texto VARCHAR, linha_doc BIGINT, linha BIGINT)""")
    con.execute("CREATE TABLE IF NOT EXISTS cfop (cfop VARCHAR PRIMARY KEY, descricao VARCHAR)")
    con.execute("CREATE TABLE IF NOT EXISTS regimes (raiz VARCHAR PRIMARY KEY, regime VARCHAR, ano INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS estado (chave VARCHAR PRIMARY KEY, valor VARCHAR)")
    if not _existe(con, "itens"):
        reconstruir(con)
    return con


def _existe(con, tabela: str) -> bool:
    return con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [tabela]).fetchone()[0] > 0


def estado(con, chave: str, padrao: str = "") -> str:
    r = con.cursor().execute("SELECT valor FROM estado WHERE chave = ?", [chave]).fetchone()
    return r[0] if r else padrao


def gravar_estado(con, chave: str, valor: str):
    con.cursor().execute("INSERT OR REPLACE INTO estado VALUES (?, ?)", [chave, str(valor)])


# ============================================================================
# Planejamento da carga (identifica duplicados e conflitos ANTES de ler)
# ============================================================================

def planejar(con, caminhos) -> list[dict]:
    """Decide o que fazer com cada arquivo: CARREGAR, JA_CARREGADO, IGNORADO,
    CONFLITO ou INVALIDO. Nada é gravado aqui."""
    vistos, plano = set(), []
    existentes = con.cursor().execute(
        "SELECT arquivo_id, tipo, cnpj, ie, CAST(dt_ini AS VARCHAR), "
        "CAST(dt_fin AS VARCHAR), retificadora, hash_conteudo, nome_arquivo "
        "FROM arquivos").fetchall()
    por_hash = {e[7]: e for e in existentes}
    por_ident = {}
    for e in existentes:
        por_ident.setdefault((e[1], e[2], e[3], e[4], e[5]), []).append(e)

    novos = {}
    for caminho in caminhos:
        caminho = os.path.abspath(caminho)
        if caminho in vistos:
            continue
        vistos.add(caminho)
        info = inspecionar(caminho)
        item = {"info": info, "acao": "", "motivo": "", "substitui": []}
        plano.append(item)
        if info.get("erro") or not info.get("tipo"):
            item.update(acao="INVALIDO", motivo=info.get("erro") or "Tipo não reconhecido.")
        elif info["hash_conteudo"] in por_hash:
            item.update(acao="JA_CARREGADO", motivo=(
                f"Mesmo conteúdo de '{por_hash[info['hash_conteudo']][8]}', já na base "
                "(o nome, a codificação e a quebra de linha não importam)."))
        else:
            repetido = next((o for o in plano[:-1]
                             if o["info"].get("hash_conteudo") == info["hash_conteudo"]), None)
            if repetido:
                item.update(acao="IGNORADO", motivo=(
                    f"Mesmo conteúdo de '{repetido['info']['nome_arquivo']}', selecionado "
                    "junto (o nome, a codificação e a quebra de linha não importam)."))
            else:
                novos.setdefault(identidade(info), []).append(item)

    for ident, itens in novos.items():
        na_base = por_ident.get(ident, [])
        if len(itens) == 1 and not na_base:
            itens[0]["acao"] = "CARREGAR"
            continue
        retif_novos = [i for i in itens if i["info"]["retificadora"]]
        retif_base = [e for e in na_base if e[6]]
        if len(retif_novos) + len(retif_base) == 1:
            if retif_novos:
                vencedor = retif_novos[0]
                vencedor["acao"] = "CARREGAR"
                vencedor["substitui"] = [e[0] for e in na_base]
                if na_base:
                    vencedor["motivo"] = ("Retificadora: substitui o original "
                                          f"'{na_base[0][8]}' que está na base.")
                for i in itens:
                    if i is not vencedor:
                        i.update(acao="IGNORADO", motivo="Original substituído pela "
                                 f"retificadora '{vencedor['info']['nome_arquivo']}'.")
            else:
                for i in itens:
                    i.update(acao="IGNORADO", motivo="A base já tem a retificadora "
                             f"deste período ('{retif_base[0][8]}').")
            continue
        nomes = [i["info"]["nome_arquivo"] for i in itens] + [f"{e[8]} (na base)" for e in na_base]
        for i in itens:
            i.update(acao="CONFLITO", motivo=(
                "Há mais de uma versão desta escrituração para o mesmo período e o "
                "arquivo não informa qual é a mais recente: " + "; ".join(nomes) +
                ". Mantenha só a versão vigente (remova a antiga da base, se for o caso)."))
    return plano


# ============================================================================
# Carga
# ============================================================================

def _conferir(cur, tabela, aid, medidas, chave, controle, nome):
    somas = "".join(f", coalesce(CAST(sum({m}) * 100 AS HUGEINT), 0)" for m in medidas)
    r = cur.execute(
        f"SELECT count(*), count(DISTINCT {chave}){somas} FROM {tabela} "
        f"WHERE arquivo_id = ?", [aid]).fetchone()
    if r[0] != controle["n"]:
        raise ErroDeCarga(f"{nome}: {r[0]} linhas no banco, {controle['n']} lidas do arquivo.")
    if r[0] != r[1]:
        raise ErroDeCarga(f"{nome}: chave (arquivo, {chave}) repetida.")
    for m, valor in zip(medidas, r[2:]):
        if int(valor) != int(controle["somas"][m]):
            raise ErroDeCarga(
                f"{nome}: total de {m} no banco ({int(valor)} centavos) diferente "
                f"do lido do arquivo ({controle['somas'][m]} centavos).")


def _carregar_um(con, meta: dict, substitui) -> int:
    """Carrega um arquivo em transação única, com os totais de controle."""
    cur = con.cursor()
    aid = cur.execute("SELECT nextval('seq_arquivo')").fetchone()[0]
    pasta = meta["pasta"]
    guardar = {k: meta.get(k) for k in (
        "contagem", "campos_por_registro", "tem_9900", "divergencias_9900",
        "registros_tratados", "registros_atencao", "descartes", "anomalias",
        "exemplos_anomalias", "estabelecimentos", "estabs_com_movimento",
        "ind_escri", "controle")}
    cur.execute("BEGIN TRANSACTION")
    try:
        for antigo in substitui:
            for t in TABELAS_POR_ARQUIVO:
                cur.execute(f"DELETE FROM {t} WHERE arquivo_id = ?", [antigo])
        for tabela, arquivo, colunas, textos in (
                ("itens_base", "itens.parquet", COLUNAS_ITENS, TEXTO_ITENS),
                ("docs_base", "docs.parquet", COLUNAS_DOCS, TEXTO_DOCS),
                ("analitico_base", "analitico.parquet", COLUNAS_ANA, TEXTO_ANA)):
            sel = ", ".join(_expr_carga(c, textos) for c in colunas)
            cur.execute(f"INSERT INTO {tabela} SELECT {aid}, {sel} FROM read_parquet(?)",
                        [os.path.join(pasta, arquivo)])
        cur.execute("INSERT INTO txt_base SELECT ?, registro, texto, linha_doc, linha "
                    "FROM read_parquet(?)", [aid, os.path.join(pasta, "txt.parquet")])
        datas_invalidas = cur.execute(
            "SELECT count(*) FROM read_parquet(?) WHERE dt_doc IS NOT NULL "
            "AND TRY_CAST(dt_doc AS DATE) IS NULL",
            [os.path.join(pasta, "docs.parquet")]).fetchone()[0]
        if datas_invalidas:
            guardar["anomalias"] = dict(guardar["anomalias"] or {})
            guardar["anomalias"]["Documentos com data inexistente no calendário"] = datas_invalidas
        c = meta["controle"]
        _conferir(cur, "itens_base", aid, MEDIDAS, "linha", c["itens"], "Itens")
        _conferir(cur, "docs_base", aid, MEDIDAS_DOCS, "linha_doc", c["docs"], "Documentos")
        _conferir(cur, "analitico_base", aid, MEDIDAS_ANA, "linha", c["analitico"], "Analítico")
        _conferir(cur, "txt_base", aid, [], "linha", c["txt"], "Texto original")
        cur.execute(
            "INSERT INTO arquivos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,now(),?,?)",
            [aid, meta["tipo"], meta["cnpj"], meta.get("ie", ""), meta["empresa_raiz"],
             meta["nome"], meta.get("uf", ""), meta["dt_ini"], meta["dt_fin"],
             meta["periodo"], meta["finalidade"], meta["retificadora"],
             meta["cod_ver"], meta["caminho"], meta["nome_arquivo"],
             meta["tamanho"], meta["hash_bruto"], meta["hash_conteudo"],
             meta["encoding"], meta["linhas"], meta["segundos"],
             json.dumps(guardar, ensure_ascii=False)])
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    return aid


def _ler_em_processos(tarefas, destinos, n_proc, avisar) -> dict:
    """Lê cada arquivo em um processo próprio (python -m efd.trabalhador),
    até `n_proc` ao mesmo tempo. Devolve {hash do conteúdo: metadados}."""
    raiz_pacote = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0)     # só existe no Windows
    pendentes, ativos, metas, feitos = list(tarefas), [], {}, 0
    while pendentes or ativos:
        while pendentes and len(ativos) < n_proc:
            p = pendentes.pop(0)
            pasta = destinos[p["info"]["hash_conteudo"]]
            os.makedirs(pasta, exist_ok=True)
            with open(os.path.join(pasta, "info.json"), "w", encoding="utf-8") as f:
                json.dump(p["info"], f, ensure_ascii=False)
            log = open(os.path.join(pasta, "erro.log"), "w", encoding="utf-8")
            proc = subprocess.Popen(
                comando_modulo("efd.trabalhador", pasta), cwd=raiz_pacote,
                stdout=subprocess.DEVNULL, stderr=log, creationflags=sem_janela)
            ativos.append((proc, log, p, pasta))
        time.sleep(0.05)
        for ativo in list(ativos):
            proc, log, p, pasta = ativo
            if proc.poll() is None:
                continue
            ativos.remove(ativo)
            log.close()
            try:
                with open(os.path.join(pasta, "meta.json"), "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                meta = None      # o processo não terminou a leitura: tenta aqui mesmo
            if meta is not None:
                meta["modo_leitura"] = "processo próprio"
                metas[p["info"]["hash_conteudo"]] = meta
            feitos += 1
            avisar(feitos, p["info"]["nome_arquivo"])
    return metas


def carregar(con, plano, pasta_base: str, progresso=None, processos=None) -> list[dict]:
    """Lê os arquivos marcados como CARREGAR e grava na base.

    processos=None  um processo de leitura por arquivo, até o número de núcleos
    processos=0     lê neste mesmo processo, um arquivo por vez
    """
    tarefas = [p for p in plano if p["acao"] == "CARREGAR"]
    staging = os.path.join(pasta_base, "staging")
    resultados = []
    if not tarefas:
        return resultados
    destinos = {p["info"]["hash_conteudo"]: os.path.join(staging, p["info"]["hash_conteudo"][:24])
                for p in tarefas}

    def avisar(feitos, nome):
        if progresso:
            progresso(feitos, len(tarefas), nome)

    metas = {}
    if processos != 0:
        n_proc = max(1, min(len(tarefas), processos or os.cpu_count() or 1))
        try:
            metas = _ler_em_processos(tarefas, destinos, n_proc, avisar)
        except OSError:
            metas = {}           # não foi possível criar processos: lê em sequência
    feitos = len(metas)
    for p in tarefas:
        h = p["info"]["hash_conteudo"]
        if h not in metas:
            metas[h] = processar_arquivo(p["info"], destinos[h])
            feitos += 1
            avisar(min(feitos, len(tarefas)), p["info"]["nome_arquivo"])

    for p in tarefas:
        meta = metas[p["info"]["hash_conteudo"]]
        r = {"nome_arquivo": p["info"]["nome_arquivo"], "tipo": p["info"]["tipo"],
             "ok": False, "mensagem": ""}
        resultados.append(r)
        if meta.get("erro"):
            r["mensagem"] = meta["erro"]
            continue
        igual = con.cursor().execute(
            "SELECT nome_arquivo FROM arquivos WHERE hash_conteudo = ?",
            [meta["hash_conteudo"]]).fetchone()
        if igual:
            r["mensagem"] = (f"Ignorado: mesmo conteúdo de '{igual[0]}' (difere só "
                             "na codificação ou na quebra de linha).")
            continue
        try:
            _carregar_um(con, meta, p.get("substitui") or [])
            r.update(ok=True, linhas=meta["linhas"], itens=meta["controle"]["itens"]["n"],
                     segundos=meta["segundos"],
                     modo_leitura=meta.get("modo_leitura", "mesmo processo"),
                     mensagem=p.get("motivo") or "Carregado e conferido.")
        except Exception as e:
            r["mensagem"] = f"Carga desfeita: {e}"
    shutil.rmtree(staging, ignore_errors=True)
    reconstruir(con)
    return resultados


def remover_arquivo(con, arquivo_id: int):
    cur = con.cursor()
    cur.execute("BEGIN TRANSACTION")
    for t in TABELAS_POR_ARQUIVO:
        cur.execute(f"DELETE FROM {t} WHERE arquivo_id = ?", [arquivo_id])
    cur.execute("COMMIT")
    reconstruir(con)


def limpar(con):
    cur = con.cursor()
    for t in TABELAS_POR_ARQUIVO:
        cur.execute(f"DELETE FROM {t}")
    reconstruir(con)


# ============================================================================
# Tabelas derivadas e verificações de integridade
# ============================================================================

def reconstruir(con) -> list[dict]:
    """Recalcula repetições, pareamento, CFOP conciliado e a visão agregada,
    e roda as verificações de integridade. Devolve a lista de verificações."""
    cur = con.cursor()
    t0 = time.time()
    cur.execute("""
        CREATE OR REPLACE TABLE dim_empresa AS
        SELECT empresa_raiz,
               coalesce(max(nome) FILTER (WHERE tipo = 'CONTRIB'), max(nome)) AS empresa_nome
        FROM arquivos GROUP BY empresa_raiz""")
    # Nome de cada estabelecimento: 0140 da EFD-Contribuições e, na falta dele,
    # 0000 da EFD Fiscal (que é por estabelecimento).
    nomes = {}
    for cnpj, nome, tipo, meta in cur.execute(
            "SELECT cnpj, nome, tipo, meta FROM arquivos ORDER BY tipo, periodo DESC").fetchall():
        if tipo == "FISCAL":
            nomes.setdefault(cnpj, nome)
        else:
            for c, n in (json.loads(meta).get("estabelecimentos") or {}).items():
                nomes.setdefault(c, n)
    cur.execute("CREATE OR REPLACE TABLE dim_estab (estab_cnpj VARCHAR PRIMARY KEY, estab_nome VARCHAR)")
    if nomes:
        cur.executemany("INSERT INTO dim_estab VALUES (?, ?)", list(nomes.items()))
    cur.execute("""
        CREATE OR REPLACE TABLE cob_fiscal AS
        SELECT DISTINCT cnpj AS estab_cnpj, periodo FROM arquivos WHERE tipo = 'FISCAL'""")
    cur.execute("""
        CREATE OR REPLACE TABLE cob_contrib AS
        SELECT DISTINCT empresa_raiz, periodo FROM arquivos WHERE tipo = 'CONTRIB'""")

    # Ocorrências de cada documento dentro da mesma EFD. A primeira vale; a
    # preferência é do arquivo cujo período contém a data de entrada.
    cur.execute("""
        CREATE OR REPLACE TABLE docs AS
        SELECT d.*,
               row_number() OVER (
                   PARTITION BY fonte, empresa_raiz, doc_id
                   ORDER BY CASE WHEN date_trunc('month', coalesce(dt_e_s, dt_doc)) = periodo
                                 THEN 0 ELSE 1 END,
                            periodo, arquivo_id, linha_doc) AS ocorrencia,
               count(*) OVER (PARTITION BY fonte, empresa_raiz, doc_id) AS n_ocorrencias
        FROM docs_base d""")
    cur.execute("""
        CREATE OR REPLACE TABLE doc_fontes AS
        SELECT empresa_raiz, doc_id,
               bool_or(fonte = 'FISCAL') AS tem_fiscal,
               bool_or(fonte = 'CONTRIB') AS tem_contrib
        FROM docs WHERE ocorrencia = 1 GROUP BY empresa_raiz, doc_id""")
    # CFOP do documento na EFD Fiscal, quando é um só (para dar CFOP às linhas
    # da Contribuições que não têm o campo: energia, frete, comunicação).
    cur.execute("""
        CREATE OR REPLACE TABLE cfop_fiscal AS
        SELECT d.empresa_raiz, d.doc_id, min(b.cfop) AS cfop
        FROM itens_base b
        JOIN docs d ON d.arquivo_id = b.arquivo_id AND d.linha_doc = b.linha_doc
        WHERE b.fonte = 'FISCAL' AND d.ocorrencia = 1 AND b.cfop <> ''
          AND b.doc_id IS NOT NULL
        GROUP BY d.empresa_raiz, d.doc_id
        HAVING count(DISTINCT b.cfop) = 1""")
    cur.execute("""
        CREATE OR REPLACE TABLE itens AS
        SELECT b.*,
               coalesce(e.empresa_nome, '') AS empresa_nome,
               coalesce(de.estab_nome, '') AS estab_nome,
               coalesce(d.ocorrencia > 1, false) AS repetido,
               CASE
                   WHEN b.doc_id IS NULL OR b.registro = 'A170' THEN 'NAO_SE_APLICA'
                   WHEN f.tem_fiscal AND f.tem_contrib THEN 'AMBAS'
                   WHEN b.fonte = 'FISCAL' THEN
                       CASE WHEN cc.periodo IS NOT NULL THEN 'SO_FISCAL' ELSE 'SEM_CONTRAPARTE' END
                   ELSE
                       CASE WHEN cf.periodo IS NOT NULL THEN 'SO_CONTRIB' ELSE 'SEM_CONTRAPARTE' END
               END AS pareamento,
               CASE WHEN b.cfop <> '' THEN b.cfop ELSE coalesce(x.cfop, '') END AS cfop_conc,
               coalesce(r.regime, '') AS regime
        FROM itens_base b
        LEFT JOIN dim_empresa e ON e.empresa_raiz = b.empresa_raiz
        LEFT JOIN dim_estab de ON de.estab_cnpj = b.estab_cnpj
        LEFT JOIN docs d ON d.arquivo_id = b.arquivo_id AND d.linha_doc = b.linha_doc
                        AND b.doc_id IS NOT NULL
        LEFT JOIN doc_fontes f ON f.empresa_raiz = b.empresa_raiz AND f.doc_id = b.doc_id
        LEFT JOIN cob_contrib cc ON cc.empresa_raiz = b.empresa_raiz AND cc.periodo = b.periodo
        LEFT JOIN cob_fiscal cf ON cf.estab_cnpj = b.estab_cnpj AND cf.periodo = b.periodo
        LEFT JOIN cfop_fiscal x ON x.empresa_raiz = b.empresa_raiz AND x.doc_id = b.doc_id
                               AND b.fonte = 'CONTRIB'
        LEFT JOIN regimes r ON r.raiz = substr(b.part_doc, 1, 8) AND length(b.part_doc) = 14""")
    dims = ", ".join(DIMENSOES_VISAO)
    somas = ", ".join(f"sum({m}) AS {m}" for m in MEDIDAS)
    cur.execute(f"""
        CREATE OR REPLACE TABLE visao AS
        SELECT {dims}, max(part_nome) AS part_nome, max(descr_item) AS descr_item,
               count(*) AS n_linhas, sum(qtd) AS qtd, {somas}
        FROM itens WHERE NOT repetido GROUP BY {dims}""")

    verificacoes = verificar(con)
    versao = int(estado(con, "versao", "0")) + 1
    gravar_estado(con, "versao", versao)
    gravar_estado(con, "verificacoes", json.dumps(verificacoes, ensure_ascii=False))
    gravar_estado(con, "segundos_derivados", round(time.time() - t0, 2))
    return verificacoes


def verificar(con) -> list[dict]:
    """Verificações de integridade: se alguma falhar, os totais não são confiáveis."""
    cur = con.cursor()
    v = []

    def checar(nome, ok, detalhe=""):
        v.append({"verificacao": nome, "ok": bool(ok), "detalhe": detalhe})

    a, b = cur.execute("SELECT (SELECT count(*) FROM itens), (SELECT count(*) FROM itens_base)").fetchone()
    checar("As tabelas derivadas têm exatamente as linhas carregadas (nenhuma junção multiplicou linhas)",
           a == b, f"{a:,} derivadas, {b:,} carregadas")

    a, b = cur.execute("SELECT count(*), count(DISTINCT (arquivo_id, linha)) FROM itens").fetchone()
    checar("Cada linha de item é única por (arquivo, linha do arquivo)", a == b,
           f"{a:,} linhas, {b:,} chaves")

    a, b = cur.execute("SELECT count(*), count(DISTINCT (arquivo_id, linha_doc)) FROM docs").fetchone()
    checar("Cada documento é único por (arquivo, linha do cabeçalho)", a == b,
           f"{a:,} documentos, {b:,} chaves")

    n = cur.execute("""
        SELECT count(*) FROM (
            SELECT fonte, empresa_raiz, doc_id FROM docs WHERE ocorrencia = 1
            GROUP BY fonte, empresa_raiz, doc_id HAVING count(*) > 1)""").fetchone()[0]
    checar("Nenhum documento conta mais de uma vez dentro da mesma EFD", n == 0,
           f"{n} documentos contados em duplicidade")

    n = cur.execute("""
        SELECT count(*) FROM itens i JOIN docs d
          ON d.arquivo_id = i.arquivo_id AND d.linha_doc = i.linha_doc
        WHERE i.doc_id IS NOT NULL AND d.ocorrencia > 1 AND NOT i.repetido""").fetchone()[0]
    checar("Todos os itens de documentos repetidos estão fora dos totais", n == 0,
           f"{n} itens de documentos repetidos ainda somando")

    somas_v = ", ".join(f"coalesce(sum({m}), 0)" for m in MEDIDAS)
    visao = cur.execute(f"SELECT fonte, coalesce(sum(n_linhas), 0), {somas_v} FROM visao GROUP BY fonte ORDER BY fonte").fetchall()
    itens = cur.execute(f"SELECT fonte, count(*), {somas_v} FROM itens WHERE NOT repetido GROUP BY fonte ORDER BY fonte").fetchall()
    checar("A visão consolidada soma exatamente o mesmo que os itens (por fonte e por coluna de valor)",
           visao == itens, "totais idênticos" if visao == itens else "totais diferentes")

    arquivos = cur.execute("SELECT arquivo_id, nome_arquivo, meta FROM arquivos").fetchall()
    contagens = dict(cur.execute("SELECT arquivo_id, count(*) FROM itens_base GROUP BY arquivo_id").fetchall())
    ruins = [nome for aid, nome, meta in arquivos
             if json.loads(meta)["controle"]["itens"]["n"] != contagens.get(aid, 0)]
    checar("Cada arquivo tem no banco a mesma quantidade de linhas lida do .txt",
           not ruins, ", ".join(ruins) if ruins else f"{len(arquivos)} arquivo(s) conferido(s)")

    n = cur.execute("""
        SELECT count(*) FROM (
            SELECT tipo, cnpj, ie, dt_ini, dt_fin FROM arquivos
            GROUP BY ALL HAVING count(*) > 1)""").fetchone()[0]
    checar("Há uma única versão de cada escrituração por empresa/IE e período", n == 0,
           f"{n} escrituração(ões) com mais de uma versão")
    return verificacoes_ordenadas(v)


def verificacoes_ordenadas(v):
    return sorted(v, key=lambda x: x["ok"])


def ultimas_verificacoes(con) -> list[dict]:
    bruto = estado(con, "verificacoes", "[]")
    return json.loads(bruto)


# ============================================================================
# Tabelas auxiliares: CFOP e regime tributário
# ============================================================================

def _texto_normalizado(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower().replace(" ", "_")


def _ler_planilha(caminho: str, com_cabecalho: bool):
    import pandas as pd
    from .leitor import detectar_encoding
    ext = os.path.splitext(caminho)[1].lower()
    cab = 0 if com_cabecalho else None
    if ext in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(caminho, dtype=str, header=cab)
    return pd.read_csv(caminho, dtype=str, sep=None, engine="python", header=cab,
                       encoding=detectar_encoding(caminho), on_bad_lines="skip")


def carregar_cfop(con, caminho: str) -> int:
    """Carrega a tabela de CFOP de um arquivo fornecido pelo usuário (CSV, TXT
    ou Excel). A coluna do código é a que tem valores no formato 9999 ou
    9.999; a descrição é a coluna de texto mais longa."""
    df = _ler_planilha(caminho, com_cabecalho=False)
    padrao = re.compile(r"^\d\.?\d{3}$")
    melhor, col_cod = 0, None
    for c in df.columns:
        n = df[c].astype(str).str.strip().str.match(padrao).sum()
        if n > melhor:
            melhor, col_cod = n, c
    if col_cod is None or melhor < 10:
        raise ValueError("Não encontrei uma coluna de códigos CFOP (formato 9999 ou 9.999).")
    outras = [c for c in df.columns if c != col_cod]
    if not outras:
        raise ValueError("O arquivo tem só a coluna de códigos, falta a descrição.")
    validas = df[df[col_cod].astype(str).str.strip().str.match(padrao)]
    col_desc = max(outras, key=lambda c: validas[c].astype(str).str.len().mean())
    pares = {}
    for cod, desc in zip(validas[col_cod], validas[col_desc]):
        cod = str(cod).strip().replace(".", "")
        desc = "" if desc is None or str(desc) == "nan" else str(desc).strip()
        if desc:
            pares[cod] = desc
    cur = con.cursor()
    cur.execute("BEGIN TRANSACTION")
    cur.execute("DELETE FROM cfop")
    cur.executemany("INSERT INTO cfop VALUES (?, ?)", list(pares.items()))
    cur.execute("COMMIT")
    gravar_estado(con, "cfop_origem", f"{os.path.basename(caminho)} · {len(pares)} códigos · "
                  f"carregada em {time.strftime('%d/%m/%Y %H:%M')}")
    gravar_estado(con, "versao", int(estado(con, "versao", "0")) + 1)
    return len(pares)


def carregar_regimes(con, caminho: str, rotulo: str) -> int:
    """Planilha de regime tributário (colunas ano, cnpj, forma_de_tributacao).
    O cruzamento é pela raiz do CNPJ; prevalece o ano mais recente."""
    df = _ler_planilha(caminho, com_cabecalho=True)
    cols = {_texto_normalizado(c): c for c in df.columns}
    col_cnpj = cols.get("cnpj") or next(
        (v for k, v in cols.items() if k.startswith("cnpj") and "scp" not in k), None)
    if col_cnpj is None:
        raise ValueError(f"Planilha sem coluna de CNPJ: {list(df.columns)}")
    col_forma = next((v for k, v in cols.items() if "forma" in k and "tribut" in k), None)
    col_ano = cols.get("ano")
    atuais = {r[0]: (r[2] or 0, r[1]) for r in con.cursor().execute(
        "SELECT raiz, regime, ano FROM regimes").fetchall()}
    for linha in df.itertuples(index=False):
        reg = dict(zip(df.columns, linha))
        digitos = re.sub(r"\D", "", str(reg.get(col_cnpj) or ""))
        if not digitos or len(digitos) > 14:
            continue
        raiz = digitos.zfill(14)[:8]   # recompõe zeros à esquerda perdidos no Excel
        forma = reg.get(col_forma) if col_forma else None
        regime = str(forma).strip().upper() if forma is not None and str(forma) != "nan" else rotulo.upper()
        try:
            ano = int(re.sub(r"\D", "", str(reg.get(col_ano) or ""))[:4] or 0) if col_ano else 0
        except ValueError:
            ano = 0
        if raiz not in atuais or ano >= atuais[raiz][0]:
            atuais[raiz] = (ano, regime)
    cur = con.cursor()
    cur.execute("BEGIN TRANSACTION")
    cur.execute("DELETE FROM regimes")
    cur.executemany("INSERT INTO regimes VALUES (?, ?, ?)",
                    [(raiz, reg, ano) for raiz, (ano, reg) in atuais.items()])
    cur.execute("COMMIT")
    reconstruir(con)
    return len(atuais)


# ============================================================================
# Consultas de apoio às telas de conferência
# ============================================================================

def tabela_arquivos(con):
    return con.cursor().execute("""
        SELECT a.arquivo_id, a.tipo, a.nome_arquivo, a.cnpj, a.ie, a.nome,
               a.dt_ini, a.dt_fin, a.retificadora, a.cod_ver, a.linhas,
               coalesce(i.n, 0) AS itens, a.encoding, a.carregado_em, a.segundos
        FROM arquivos a
        LEFT JOIN (SELECT arquivo_id, count(*) n FROM itens_base GROUP BY 1) i USING (arquivo_id)
        ORDER BY a.empresa_raiz, a.periodo, a.tipo, a.cnpj""").df()


def metas(con) -> list[dict]:
    saida = []
    for aid, nome, tipo, meta in con.cursor().execute(
            "SELECT arquivo_id, nome_arquivo, tipo, meta FROM arquivos ORDER BY arquivo_id").fetchall():
        m = json.loads(meta)
        m.update(arquivo_id=aid, nome_arquivo=nome, tipo=tipo)
        saida.append(m)
    return saida


def _escopo(escopo, raiz="empresa_raiz", estab="estab_cnpj"):
    """Recorte por empresa (raiz do CNPJ) e/ou estabelecimento: (sql, parâmetros).
    escopo = (lista de raízes, lista de CNPJs de estabelecimento) ou None."""
    if not escopo or not (escopo[0] or escopo[1]):
        return "TRUE", []
    partes, params = [], []
    for col, valores in ((raiz, escopo[0]), (estab, escopo[1])):
        if valores:
            partes.append(f"{col} IN ({', '.join('?' for _ in valores)})")
            params += list(valores)
    return "(" + " OR ".join(partes) + ")", params


def empresas_e_estabelecimentos(con):
    """Opções do seletor de empresa: [(tipo 'E' ou 'S', código, nome)]."""
    cur = con.cursor()
    emp = cur.execute("SELECT empresa_raiz, empresa_nome FROM dim_empresa ORDER BY 2, 1").fetchall()
    est = cur.execute("""
        SELECT DISTINCT i.estab_cnpj, coalesce(d.estab_nome, '') FROM itens_base i
        LEFT JOIN dim_estab d USING (estab_cnpj) WHERE i.estab_cnpj <> '' ORDER BY 1""").fetchall()
    return [("E", r, n) for r, n in emp] + [("S", c, n) for c, n in est]


def conf_cabecalho(con, escopo=None):
    """Cabeçalho do documento x soma dos detalhes. Serve de prova do leiaute:
    se as posições de campo estivessem erradas, quase nada bateria."""
    sql, params = _cabecalho_sql(escopo)
    return con.cursor().execute(f"""{sql}
        SELECT fonte, registro AS cabecalho, campo,
               count(*) AS documentos,
               count(*) FILTER (WHERE cab = soma) AS iguais,
               count(*) FILTER (WHERE cab <> soma) AS diferentes,
               sum(cab) AS total_cabecalho, sum(soma) AS total_detalhes
        FROM comp GROUP BY fonte, registro, campo ORDER BY fonte, registro, campo""", params).df()


def conf_cabecalho_docs(con, escopo=None, limite: int = 1000):
    """Documentos cujo cabeçalho não fecha com os detalhes (um por linha e campo)."""
    sql, params = _cabecalho_sql(escopo)
    return con.cursor().execute(f"""{sql}
        SELECT c.fonte, c.registro, a.nome_arquivo, d.num_doc, d.part_nome, c.campo,
               c.cab AS total_cabecalho, c.soma AS total_detalhes,
               c.cab - c.soma AS diferenca, d.empresa_raiz, d.doc_id, c.arquivo_id, c.linha_doc
        FROM comp c JOIN docs d USING (arquivo_id, linha_doc) JOIN arquivos a USING (arquivo_id)
        WHERE c.cab <> c.soma
        ORDER BY abs(c.cab - c.soma) DESC LIMIT {int(limite)}""", params).df()


def _cabecalho_sql(escopo):
    filtro, params = _escopo(escopo, "d.empresa_raiz", "d.estab_cnpj")
    sql = f"""
        WITH det AS (
            SELECT arquivo_id, linha_doc,
                   sum(coalesce(vl_pis, 0)) AS pis, sum(coalesce(vl_cofins, 0)) AS cofins
            FROM itens_base WHERE fonte = 'CONTRIB' AND doc_id IS NOT NULL
            GROUP BY arquivo_id, linha_doc),
        ana AS (
            SELECT arquivo_id, linha_doc,
                   sum(coalesce(vl_bc_icms, 0)) AS bc, sum(coalesce(vl_icms, 0)) AS icms,
                   sum(coalesce(vl_icms_st, 0)) AS st, sum(coalesce(vl_ipi, 0)) AS ipi
            FROM analitico_base GROUP BY arquivo_id, linha_doc),
        d AS (SELECT * FROM docs d WHERE {filtro}),
        comp AS (
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_PIS' AS campo,
                   coalesce(d.vl_pis, 0) AS cab, coalesce(det.pis, 0) AS soma
            FROM d LEFT JOIN det USING (arquivo_id, linha_doc)
            WHERE d.fonte = 'CONTRIB' AND d.registro IN ('C100', 'A100', 'C500', 'D500')
            UNION ALL
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_COFINS',
                   coalesce(d.vl_cofins, 0), coalesce(det.cofins, 0)
            FROM d LEFT JOIN det USING (arquivo_id, linha_doc)
            WHERE d.fonte = 'CONTRIB' AND d.registro IN ('C100', 'A100', 'C500', 'D500')
            UNION ALL
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_BC_ICMS',
                   coalesce(d.vl_bc_icms, 0), coalesce(ana.bc, 0)
            FROM d LEFT JOIN ana USING (arquivo_id, linha_doc) WHERE d.fonte = 'FISCAL'
            UNION ALL
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_ICMS',
                   coalesce(d.vl_icms, 0), coalesce(ana.icms, 0)
            FROM d LEFT JOIN ana USING (arquivo_id, linha_doc) WHERE d.fonte = 'FISCAL'
            UNION ALL
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_ICMS_ST',
                   coalesce(d.vl_icms_st, 0), coalesce(ana.st, 0)
            FROM d LEFT JOIN ana USING (arquivo_id, linha_doc)
            WHERE d.fonte = 'FISCAL' AND d.registro IN ('C100', 'C500')
            UNION ALL
            SELECT d.arquivo_id, d.linha_doc, d.fonte, d.registro, 'VL_IPI',
                   coalesce(d.vl_ipi, 0), coalesce(ana.ipi, 0)
            FROM d LEFT JOIN ana USING (arquivo_id, linha_doc)
            WHERE d.fonte = 'FISCAL' AND d.registro = 'C100')"""
    return sql, params


def conf_c190(con, limite: int = 500, escopo=None):
    """EFD Fiscal: analítico C190 x soma dos itens C170, por documento e CFOP."""
    cur = con.cursor()
    filtro, params = _escopo(escopo)
    base_sql = f"""
        WITH i AS (
            SELECT arquivo_id, linha_doc, cfop,
                   sum(coalesce(vl_bc_icms, 0)) bc, sum(coalesce(vl_icms, 0)) icms,
                   sum(coalesce(vl_icms_st, 0)) st, sum(coalesce(vl_ipi, 0)) ipi
            FROM itens_base WHERE fonte = 'FISCAL' AND registro = 'C170' AND {filtro}
            GROUP BY arquivo_id, linha_doc, cfop),
        a AS (
            SELECT arquivo_id, linha_doc, cfop,
                   sum(coalesce(vl_bc_icms, 0)) bc, sum(coalesce(vl_icms, 0)) icms,
                   sum(coalesce(vl_icms_st, 0)) st, sum(coalesce(vl_ipi, 0)) ipi
            FROM analitico_base WHERE registro = 'C190'
              AND (arquivo_id, linha_doc) IN (SELECT DISTINCT arquivo_id, linha_doc FROM i)
            GROUP BY arquivo_id, linha_doc, cfop),
        c AS (
            SELECT coalesce(i.arquivo_id, a.arquivo_id) arquivo_id,
                   coalesce(i.linha_doc, a.linha_doc) linha_doc,
                   coalesce(i.cfop, a.cfop) cfop,
                   coalesce(i.bc, 0) bc_c170, coalesce(a.bc, 0) bc_c190,
                   coalesce(i.icms, 0) icms_c170, coalesce(a.icms, 0) icms_c190,
                   coalesce(i.st, 0) st_c170, coalesce(a.st, 0) st_c190,
                   coalesce(i.ipi, 0) ipi_c170, coalesce(a.ipi, 0) ipi_c190
            FROM i FULL JOIN a ON i.arquivo_id = a.arquivo_id
                              AND i.linha_doc = a.linha_doc AND i.cfop = a.cfop)"""
    resumo = cur.execute(base_sql + """
        SELECT count(*) AS grupos,
               count(*) FILTER (WHERE bc_c170 = bc_c190 AND icms_c170 = icms_c190
                                  AND st_c170 = st_c190 AND ipi_c170 = ipi_c190) AS iguais,
               sum(icms_c170) AS icms_c170, sum(icms_c190) AS icms_c190
        FROM c""", params).fetchone()
    difs = cur.execute(base_sql + f"""
        SELECT ar.nome_arquivo, d.num_doc, d.chave, d.part_nome, c.cfop,
               c.bc_c170, c.bc_c190, c.icms_c170, c.icms_c190,
               c.st_c170, c.st_c190, c.ipi_c170, c.ipi_c190,
               d.empresa_raiz, d.doc_id, c.arquivo_id, c.linha_doc
        FROM c JOIN docs d USING (arquivo_id, linha_doc)
               JOIN arquivos ar USING (arquivo_id)
        WHERE NOT (bc_c170 = bc_c190 AND icms_c170 = icms_c190
                   AND st_c170 = st_c190 AND ipi_c170 = ipi_c190)
        ORDER BY abs(c.icms_c170 - c.icms_c190) DESC LIMIT {int(limite)}""", params).df()
    return {"grupos": resumo[0], "iguais": resumo[1], "icms_c170": resumo[2],
            "icms_c190": resumo[3]}, difs


def conf_pareamento(con, escopo=None):
    filtro, params = _escopo(escopo)
    return con.cursor().execute(f"""
        SELECT fonte, pareamento, count(DISTINCT (arquivo_id, linha_doc)) AS documentos,
               count(*) AS linhas, sum(vl_item) AS vl_item, sum(vl_opr) AS vl_opr,
               sum(vl_icms) AS vl_icms, sum(vl_pis) AS vl_pis, sum(vl_cofins) AS vl_cofins
        FROM itens WHERE NOT repetido AND {filtro}
        GROUP BY fonte, pareamento ORDER BY fonte, pareamento""", params).df()


def documentos_so_um_lado(con, escopo=None, limite: int = 1000):
    """Documentos que estão em uma EFD e não na outra (com as duas carregadas)."""
    filtro, params = _escopo(escopo)
    return con.cursor().execute(f"""
        SELECT fonte, pareamento, num_doc, any_value(chave) chave, any_value(part_nome) part_nome,
               any_value(dt_doc) dt_doc, count(*) linhas, sum(vl_item) vl_item, sum(vl_opr) vl_opr,
               sum(vl_icms) vl_icms, sum(vl_pis) vl_pis, sum(vl_cofins) vl_cofins,
               empresa_raiz, doc_id, arquivo_id, linha_doc
        FROM itens WHERE NOT repetido AND pareamento IN ('SO_FISCAL', 'SO_CONTRIB') AND {filtro}
        GROUP BY fonte, pareamento, num_doc, empresa_raiz, doc_id, arquivo_id, linha_doc
        ORDER BY coalesce(sum(vl_item), sum(vl_opr)) DESC NULLS LAST LIMIT {int(limite)}""", params).df()


def divergencias_itens(con, limite: int = 1000, escopo=None):
    """Itens C170 presentes nas duas EFDs (mesmo documento e NUM_ITEM) com
    conteúdo diferente. Cada lado é reduzido a uma linha por chave antes da
    junção; chaves ambíguas ficam de fora."""
    filtro, params = _escopo(escopo)
    return con.cursor().execute(f"""
        WITH lado AS (
            SELECT fonte, empresa_raiz, doc_id, num_item,
                   any_value(cfop) cfop, any_value(cod_item) cod_item,
                   any_value(vl_item) vl_item, any_value(coalesce(vl_bc_icms, 0)) vl_bc_icms,
                   any_value(coalesce(vl_icms, 0)) vl_icms,
                   any_value(coalesce(vl_icms_st, 0)) vl_icms_st,
                   any_value(coalesce(vl_ipi, 0)) vl_ipi,
                   any_value(num_doc) num_doc, any_value(part_nome) part_nome
            FROM itens
            WHERE registro = 'C170' AND NOT repetido AND doc_id IS NOT NULL AND {filtro}
            GROUP BY fonte, empresa_raiz, doc_id, num_item HAVING count(*) = 1)
        SELECT f.num_doc, f.part_nome, f.num_item,
               f.cod_item AS cod_item_fiscal, c.cod_item AS cod_item_contrib,
               f.cfop AS cfop_fiscal, c.cfop AS cfop_contrib,
               f.vl_item AS vl_item_fiscal, c.vl_item AS vl_item_contrib,
               f.vl_bc_icms AS vl_bc_icms_fiscal, c.vl_bc_icms AS vl_bc_icms_contrib,
               f.vl_icms AS vl_icms_fiscal, c.vl_icms AS vl_icms_contrib,
               f.vl_icms_st AS vl_icms_st_fiscal, c.vl_icms_st AS vl_icms_st_contrib,
               f.vl_ipi AS vl_ipi_fiscal, c.vl_ipi AS vl_ipi_contrib,
               CASE WHEN f.doc_id LIKE 'K%' THEN substr(f.doc_id, 2) ELSE f.doc_id END AS documento,
               f.empresa_raiz, f.doc_id
        FROM (SELECT * FROM lado WHERE fonte = 'FISCAL') f
        JOIN (SELECT * FROM lado WHERE fonte = 'CONTRIB') c
          ON c.empresa_raiz = f.empresa_raiz AND c.doc_id = f.doc_id AND c.num_item = f.num_item
        WHERE f.cfop <> c.cfop OR f.cod_item <> c.cod_item OR f.vl_item <> c.vl_item
           OR f.vl_bc_icms <> c.vl_bc_icms OR f.vl_icms <> c.vl_icms
           OR f.vl_icms_st <> c.vl_icms_st OR f.vl_ipi <> c.vl_ipi
        ORDER BY abs(f.vl_icms - c.vl_icms) DESC, f.num_doc LIMIT {int(limite)}""", params).df()


def repeticoes(con, escopo=None):
    filtro, params = _escopo(escopo, "d.empresa_raiz", "d.estab_cnpj")
    return con.cursor().execute(f"""
        SELECT d.fonte, d.registro, d.num_doc, d.chave, d.part_nome, d.dt_doc,
               d.vl_doc, d.ocorrencia, d.n_ocorrencias, a.nome_arquivo, d.periodo,
               d.linha_doc AS linha_no_arquivo,
               CASE WHEN d.ocorrencia = 1 THEN 'Conta nos totais' ELSE 'Repetida: fora dos totais' END AS situacao,
               d.empresa_raiz, d.doc_id, d.arquivo_id, d.linha_doc
        FROM docs d JOIN arquivos a USING (arquivo_id)
        WHERE d.n_ocorrencias > 1 AND {filtro}
        ORDER BY d.fonte, d.doc_id, d.ocorrencia""", params).df()


def linhas_identicas(con, limite: int = 500, escopo=None):
    """Registros sem identidade de documento (F100, consolidado C191/C195) que
    aparecem com conteúdo idêntico no mesmo arquivo. Não são excluídos: o
    arquivo não permite dizer se é repetição ou lançamento legítimo."""
    filtro, params = _escopo(escopo, "i.empresa_raiz", "i.estab_cnpj")
    return con.cursor().execute(f"""
        SELECT a.nome_arquivo, i.registro, i.part_nome, i.cod_item, i.descr_item,
               i.cfop, i.dt_doc, i.vl_item, i.vl_pis, i.vl_cofins, count(*) AS vezes,
               min(i.linha) AS primeira_linha, i.arquivo_id
        FROM itens i JOIN arquivos a USING (arquivo_id)
        WHERE i.doc_id IS NULL AND {filtro}
        GROUP BY a.nome_arquivo, i.registro, i.part_nome, i.cod_item, i.descr_item, i.cfop,
                 i.dt_doc, i.vl_item, i.vl_pis, i.vl_cofins, i.arquivo_id, i.vl_bc_pis,
                 i.vl_bc_cofins, i.cst_pis, i.cst_cofins, i.cod_cta, i.estab_cnpj
        HAVING count(*) > 1 ORDER BY vezes DESC LIMIT {int(limite)}""", params).df()


def cobertura(con):
    """Quais escriturações estão carregadas por estabelecimento e período."""
    return con.cursor().execute("""
        WITH f AS (SELECT cnpj AS estab, periodo, empresa_raiz FROM arquivos WHERE tipo = 'FISCAL'),
             c AS (SELECT DISTINCT i.estab_cnpj AS estab, i.periodo, i.empresa_raiz
                   FROM itens_base i WHERE i.fonte = 'CONTRIB'),
             t AS (SELECT * FROM f UNION SELECT * FROM c)
        SELECT t.empresa_raiz, t.estab AS estabelecimento, t.periodo,
               EXISTS (SELECT 1 FROM f WHERE f.estab = t.estab AND f.periodo = t.periodo) AS efd_fiscal,
               EXISTS (SELECT 1 FROM cob_contrib k WHERE k.empresa_raiz = t.empresa_raiz
                                                    AND k.periodo = t.periodo) AS efd_contribuicoes
        FROM t ORDER BY 1, 2, 3""").df()


# ============================================================================
# Linhas originais do TXT (pop-up de comparação)
# ============================================================================

def ocorrencias_documento(con, empresa_raiz: str, doc_id: str):
    """Todas as ocorrências de um documento na base (as duas EFDs e repetições)."""
    return con.cursor().execute("""
        SELECT d.fonte, d.arquivo_id, d.linha_doc, d.ocorrencia, d.n_ocorrencias, d.num_doc,
               d.periodo, a.nome_arquivo, a.cnpj
        FROM docs d JOIN arquivos a USING (arquivo_id)
        WHERE d.empresa_raiz = ? AND d.doc_id = ?
        ORDER BY d.fonte DESC, d.ocorrencia""", [empresa_raiz, doc_id]).fetchall()


def linhas_documento(con, arquivo_id: int, linha_doc: int):
    """Linhas do TXT de um documento (cabeçalho e registros filhos), em ordem."""
    return con.cursor().execute(
        "SELECT linha, registro, texto FROM txt_base WHERE arquivo_id = ? AND linha_doc = ? "
        "ORDER BY linha", [int(arquivo_id), int(linha_doc)]).fetchall()


def linha_txt(con, arquivo_id: int, linha: int):
    r = con.cursor().execute("SELECT linha, registro, texto FROM txt_base WHERE arquivo_id = ? "
                             "AND linha = ?", [int(arquivo_id), int(linha)]).fetchone()
    return [r] if r else []


def tem_texto(con, arquivo_id: int) -> bool:
    return con.cursor().execute("SELECT count(*) FROM txt_base WHERE arquivo_id = ?",
                                [int(arquivo_id)]).fetchone()[0] > 0


# ============================================================================
# Backup e restauração
# ============================================================================

def fazer_backup(con, destino_pasta: str, arquivos_extras=()) -> str:
    """Copia a base inteira para um novo arquivo .duckdb na pasta indicada
    (e os arquivos de configuração junto). Devolve o caminho do backup."""
    os.makedirs(destino_pasta, exist_ok=True)
    carimbo = time.strftime("%Y-%m-%d_%H%M%S")
    destino = os.path.join(destino_pasta, f"consolidador_efd_backup_{carimbo}.duckdb")
    cur = con.cursor()          # a cópia lê um retrato consistente da base
    origem = cur.execute("SELECT current_database()").fetchone()[0]
    cur.execute(f"ATTACH ? AS bkp", [destino])
    try:
        cur.execute(f'COPY FROM DATABASE "{origem}" TO bkp')
    finally:
        cur.execute("DETACH bkp")
    for extra in arquivos_extras:
        if os.path.isfile(extra):
            nome, ext = os.path.splitext(os.path.basename(extra))
            shutil.copy2(extra, os.path.join(destino_pasta, f"{nome}_{carimbo}{ext}"))
    return destino


def validar_backup(caminho: str) -> int:
    """Abre um backup só para leitura e devolve quantas escriturações ele tem."""
    c = duckdb.connect(caminho, read_only=True)
    try:
        return c.execute("SELECT count(*) FROM arquivos").fetchone()[0]
    finally:
        c.close()
