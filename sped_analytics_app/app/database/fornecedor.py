"""Busca por fornecedor (participante): tudo o que existe sobre um CNPJ/CPF na base.

  * cadastro: todas as versões do registro 0150 (e alterações 0175) em todos os arquivos, SPED Fiscal e
    EFD-Contribuições;
  * consolidado: as entradas da tabela fato (mesma base da Análise e do Relatório dinâmico, sem duplicidade);
  * arquivos como estão: cada linha dos TXT ligada ao participante, entradas e saídas —
      - registros com COD_PART (C100, C500, D100, D500, D700, H010, A100, F100...) cujo código, no próprio arquivo,
        aponta para o CNPJ/CPF (o código do participante é definido em cada arquivo pelo 0150);
      - registros filhos desses documentos (C170, C190, C191, C197, D190, A170, C501/C505, D101/D105...);
      - C191/C195 da EFD-Contribuições, que trazem o CNPJ/CPF do participante no próprio registro;
      - os próprios 0150 e 0175.
"""
from __future__ import annotations

import re

import polars as pl

from app.database import analytics
from app.parser import catalog

TABLE = {"ICMS_IPI": "sf_linhas", "CONTRIB": "ec_linhas"}
TIPO_LABEL = {"ICMS_IPI": "SPED Fiscal", "CONTRIB": "EFD-Contribuições"}


class FornecedorError(ValueError):
    pass


def digits(v: str) -> str:
    return re.sub(r"\D", "", str(v or ""))


def norm_ids(cnpjs: list | None) -> list[str]:
    out = []
    for c in cnpjs or []:
        s = str(c).strip()
        out.append(s.upper() if s.upper().startswith("EXT:") else digits(s))
    out = [x for x in dict.fromkeys(out) if x]
    if not out:
        raise FornecedorError("Informe ao menos um CNPJ ou CPF")
    return out


# --------------------------------------------------------------------------------------
# Busca (lista de sugestões)
# --------------------------------------------------------------------------------------
def search(db, q: str, limit: int = 40) -> dict:
    q = (q or "").strip()
    if len(q) < 2:
        return {"itens": [], "raiz": None}
    d = digits(q)
    params: list = []
    if d and len(d) >= 3 and re.fullmatch(r"[\d\s./-]+", q):
        params.append(d)
        cond = "starts_with(f.cnpj_cpf, $1) OR contains(f.cnpj_cpf, $1)"
    else:
        params.append(q.lower())
        cond = "contains(lower(coalesce(f.razao_social, '')), $1)"
    src = analytics.pick_source({"cnpj_cpf_fornecedor"}, {"vl_contabil"})
    rows = db.query(f"""
        WITH v AS (SELECT cnpj_cpf_fornecedor AS k, CAST(sum(vl_contabil) AS DOUBLE) AS vl,
                          CAST(sum(vl_pis) + sum(vl_cofins) AS DOUBLE) AS pc
                   FROM {src} GROUP BY 1)
        SELECT f.cnpj_cpf, f.razao_social, f.uf, f.ultima_competencia, v.vl AS vl_contabil, v.pc AS pis_cofins,
               v.k IS NOT NULL AS tem_entradas
        FROM dim_fornecedor f LEFT JOIN v ON v.k = f.cnpj_cpf
        WHERE {cond}
        ORDER BY v.vl DESC NULLS LAST, f.razao_social LIMIT {int(limit)}""", params).to_dicts()
    raiz = None
    if len(d) >= 8:
        r8 = d[:8]
        n = db.query("SELECT count(*) AS n, any_value(razao_social) AS nome FROM dim_fornecedor "
                     "WHERE length(cnpj_cpf) = 14 AND starts_with(cnpj_cpf, ?)", [r8]).to_dicts()[0]
        if n["n"] > 1:
            raiz = {"raiz": r8, "n": int(n["n"]), "nome": n["nome"]}
    return {"itens": rows, "raiz": raiz}


def expand_raiz(db, raiz: str) -> list[str]:
    r8 = digits(raiz)[:8]
    if len(r8) != 8:
        raise FornecedorError("Raiz de CNPJ inválida")
    df = db.query("SELECT cnpj_cpf FROM dim_fornecedor WHERE length(cnpj_cpf) = 14 AND starts_with(cnpj_cpf, ?) "
                  "ORDER BY 1", [r8])
    return df["cnpj_cpf"].to_list() if df.height else [r8]


# --------------------------------------------------------------------------------------
# Linhas dos arquivos ligadas ao participante
# --------------------------------------------------------------------------------------
def _file_ids(db, tipo: str, q: dict) -> list[int]:
    conds, params = ["ativo", "tipo_sped = ?"], [tipo]
    if q.get("comp_ini"):
        conds.append("competencia >= ?")
        params.append(str(q["comp_ini"]))
    if q.get("comp_fim"):
        conds.append("competencia <= ?")
        params.append(str(q["comp_fim"]))
    df = db.query(f"SELECT id_arquivo FROM sys_arquivos_importados WHERE {' AND '.join(conds)}", params)
    return [int(x) for x in df["id_arquivo"].to_list()] if df.height else []


def _pos(tipo: str, reg: str, field: str) -> int | None:
    lay = catalog.LAYOUTS[tipo].get(reg) or []
    return lay.index(field) + 2 if field in lay else None   # posição em split_part (1 = vazio antes do 1º "|")


def participant_lines_sql(tipo: str, ids: list[int], ph: str) -> str:
    """SQL com (file_id, line_no, reg, ind_oper) de todas as linhas ligadas aos CNPJ/CPF do parâmetro `ph`
    (lista de strings só com dígitos)."""
    t = TABLE[tipo]
    idl = ",".join(map(str, ids)) or "NULL"
    lay = catalog.LAYOUTS[tipo]
    doc_regs = {r: _pos(tipo, r, "COD_PART") for r in lay if r != "0150" and "COD_PART" in lay[r]}
    cp_case = " ".join(f"WHEN '{r}' THEN split_part(l.linha, '|', {p})" for r, p in doc_regs.items())
    op_case = " ".join(f"WHEN '{r}' THEN split_part(l.linha, '|', {_pos(tipo, r, 'IND_OPER')})"
                       for r in doc_regs if _pos(tipo, r, "IND_OPER"))
    op_default = "'0'" if tipo == "CONTRIB" else "NULL"   # C500 da EFD-Contribuições só tem entradas
    regs_in = ", ".join(f"'{r}'" for r in doc_regs)
    cpart_regs = [r for r in lay if "CNPJ_CPF_PART" in lay[r]]
    estab_ok = ("TRUE" if tipo == "ICMS_IPI" else
                "(p.estab IS NOT DISTINCT FROM c.cnpj_estab OR NOT EXISTS (SELECT 1 FROM allp a WHERE "
                "a.file_id = c.file_id AND a.cod_part = c.cp AND a.estab IS NOT DISTINCT FROM c.cnpj_estab))")
    m_cnpj = ""
    if cpart_regs:
        pos = {r: _pos(tipo, r, "CNPJ_CPF_PART") for r in cpart_regs}
        case = " ".join(f"WHEN '{r}' THEN split_part(linha, '|', {p})" for r, p in pos.items())
        m_cnpj = (f" UNION ALL SELECT file_id, line_no, reg, '0' FROM {t} WHERE file_id IN ({idl}) AND reg IN "
                  f"({', '.join(repr(r) for r in cpart_regs)}) AND regexp_replace(CASE reg {case} END, '\\D', '', 'g') "
                  f"IN (SELECT unnest({ph}))")
    return f"""(
        WITH allp AS (
            SELECT file_id, line_no, cnpj_estab AS estab, split_part(linha, '|', 3) AS cod_part,
                   'EXT:' || upper(trim(split_part(linha, '|', 4))) AS ext,
                   regexp_replace(split_part(linha, '|', 6), '\\D', '', 'g') AS cnpj,
                   regexp_replace(split_part(linha, '|', 7), '\\D', '', 'g') AS cpf
            FROM {t} WHERE file_id IN ({idl}) AND reg = '0150'
        ), p AS (
            SELECT * FROM allp WHERE cnpj IN (SELECT unnest({ph})) OR cpf IN (SELECT unnest({ph}))
               OR ext IN (SELECT unnest({ph}))
        ), c AS (
            SELECT l.file_id, l.line_no, l.reg, l.doc_line, l.cnpj_estab, CASE l.reg {cp_case} END AS cp,
                   {f"CASE l.reg {op_case} ELSE {op_default} END" if op_case else op_default} AS ind_oper
            FROM {t} l WHERE l.file_id IN ({idl}) AND l.reg IN ({regs_in or "''"})
        ), md AS (
            SELECT DISTINCT c.file_id, c.line_no, c.reg, c.doc_line, c.ind_oper
            FROM c JOIN p ON p.file_id = c.file_id AND p.cod_part = c.cp WHERE {estab_ok}
        ), p0175 AS (
            SELECT l.file_id, l.line_no, l.reg FROM {t} l
            ASOF JOIN allp a ON a.file_id = l.file_id AND l.line_no >= a.line_no
            WHERE l.file_id IN ({idl}) AND l.reg = '0175'
              AND EXISTS (SELECT 1 FROM p WHERE p.file_id = a.file_id AND p.line_no = a.line_no)
        )
        SELECT file_id, line_no, reg, ind_oper FROM md
        UNION ALL
        SELECT l.file_id, l.line_no, l.reg, d.ind_oper FROM {t} l
        JOIN md d ON d.file_id = l.file_id AND l.doc_line = d.line_no AND d.doc_line = d.line_no
        WHERE l.file_id IN ({idl}) AND l.line_no <> l.doc_line
        UNION ALL SELECT file_id, line_no, '0150', NULL FROM p
        UNION ALL SELECT file_id, line_no, reg, NULL FROM p0175
        {m_cnpj}
    )"""


def file_summary(db, cnpjs: list[str], q: dict) -> list[dict]:
    """Quantidade de linhas por arquivo (tipo) e registro, separando entradas e saídas."""
    out = []
    for tipo in ("ICMS_IPI", "CONTRIB"):
        ids = _file_ids(db, tipo, q)
        if not ids:
            continue
        sql = participant_lines_sql(tipo, ids, "$1")
        rows = db.query(f"""SELECT reg, count(*) AS n, count(*) FILTER (WHERE ind_oper = '0') AS entradas,
                                   count(*) FILTER (WHERE ind_oper = '1') AS saidas,
                                   count(DISTINCT file_id) AS arquivos
                            FROM {sql} GROUP BY reg""", [cnpjs]).to_dicts()
        for r in rows:
            r.update({"tipo": tipo, "tipo_label": TIPO_LABEL[tipo], "descricao": catalog.descricao(tipo, r["reg"])})
        order = {b: i for i, b in enumerate(catalog.BLOCOS[tipo])}
        out += sorted(rows, key=lambda r: (order.get(r["reg"][:1], 99), r["reg"]))
    return out


# --------------------------------------------------------------------------------------
# Cadastro (0150) em todos os arquivos
# --------------------------------------------------------------------------------------
def cadastro(db, cnpjs: list[str], q: dict) -> pl.DataFrame:
    frames = []
    for tipo in ("ICMS_IPI", "CONTRIB"):
        ids = _file_ids(db, tipo, q)
        if not ids:
            continue
        t = TABLE[tipo]
        df = db.query(f"""
            WITH x AS (SELECT l.file_id, l.line_no, l.cnpj_estab, string_split(l.linha, '|') AS f
                       FROM {t} l WHERE l.file_id IN ({','.join(map(str, ids))}) AND l.reg = '0150')
            SELECT '{TIPO_LABEL[tipo]}' AS arquivo_tipo, a.competencia, coalesce(x.cnpj_estab, a.cnpj) AS unidade,
                   x.f[3] AS cod_part, x.f[4] AS nome, x.f[5] AS cod_pais, nullif(x.f[6], '') AS cnpj,
                   nullif(x.f[7], '') AS cpf, nullif(x.f[8], '') AS ie, nullif(x.f[9], '') AS cod_mun,
                   u.uf, nullif(x.f[11], '') AS endereco, nullif(x.f[12], '') AS numero,
                   nullif(x.f[13], '') AS complemento, nullif(x.f[14], '') AS bairro, x.file_id, x.line_no
            FROM x JOIN sys_arquivos_importados a ON a.id_arquivo = x.file_id
            LEFT JOIN ref_uf_ibge u ON u.cod = left(x.f[9], 2)
            WHERE regexp_replace(x.f[6], '\\D', '', 'g') IN (SELECT unnest($1))
               OR regexp_replace(x.f[7], '\\D', '', 'g') IN (SELECT unnest($1))""", [cnpjs])
        frames.append(df)
    frames = [f for f in frames if f.height]
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="vertical_relaxed").sort(["competencia", "arquivo_tipo", "unidade"])


def cadastro_variantes(cad: pl.DataFrame) -> pl.DataFrame:
    """Versões distintas do cadastro (nome, IE, endereço, município), com período em que aparecem."""
    if cad.height == 0:
        return cad
    keys = ["nome", "cnpj", "cpf", "ie", "uf", "cod_mun", "endereco", "numero", "bairro"]
    return cad.group_by(keys, maintain_order=True).agg(
        pl.col("competencia").min().alias("primeira"), pl.col("competencia").max().alias("ultima"),
        pl.col("arquivo_tipo").unique().sort().str.join(" + ").alias("arquivos"),
        pl.col("cod_part").unique().sort().str.join(", ").alias("codigos"),
        pl.col("unidade").n_unique().alias("unidades"), pl.len().alias("ocorrencias"),
    ).sort(["ultima", "primeira"], descending=True)


def alteracoes(db, cnpjs: list[str], q: dict) -> pl.DataFrame:
    """Registros 0175 (alteração do cadastro do participante) ligados ao CNPJ/CPF."""
    frames = []
    for tipo in ("ICMS_IPI", "CONTRIB"):
        if not catalog.LAYOUTS[tipo].get("0175"):
            continue
        ids = _file_ids(db, tipo, q)
        if not ids:
            continue
        sql = participant_lines_sql(tipo, ids, "$1")
        df = db.query(f"""
            SELECT '{TIPO_LABEL[tipo]}' AS arquivo_tipo, a.competencia, split_part(l.linha, '|', 3) AS dt_alt,
                   split_part(l.linha, '|', 4) AS nr_campo, split_part(l.linha, '|', 5) AS cont_ant, l.file_id, l.line_no
            FROM {TABLE[tipo]} l JOIN {sql} s ON s.file_id = l.file_id AND s.line_no = l.line_no AND s.reg = '0175'
            JOIN sys_arquivos_importados a ON a.id_arquivo = l.file_id""", [cnpjs])
        frames.append(df)
    frames = [f for f in frames if f.height]
    return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()


# --------------------------------------------------------------------------------------
# Consolidado (tabela fato — só entradas)
# --------------------------------------------------------------------------------------
METRICS = ["vl_contabil", "vl_icms", "vl_icms_st_fcp", "vl_ipi", "vl_pis", "vl_cofins", "vl_trib_recuperaveis",
           "vl_custo_liquido", "qtd"]


def gf_for(cnpjs: list[str], q: dict) -> dict:
    gf = {"fornecedores": cnpjs}
    for k in ("comp_ini", "comp_fim"):
        if q.get(k):
            gf[k] = q[k]
    return gf


def consolidado(db, cnpjs: list[str], q: dict) -> dict:
    gf = gf_for(cnpjs, q)
    metrics = [m for m in METRICS if m in analytics.METRICS]
    tot = analytics.totals(db, gf, None, metrics)
    out = {"totais": tot, "n_docs": analytics.count_documents(db, gf, None)}
    for key, dims in (("por_mes", ["competencia"]), ("por_filial", ["filial"]), ("por_cfop", ["cfop"]),
                      ("por_item", ["item"]), ("por_status", ["status_efd"]), ("por_cst_pis", ["cst_pis"]),
                      ("por_nat", ["nat_bc_cred"])):
        out[key] = analytics.aggregate(db, gf, None, dims, metrics, limit=2000 if key == "por_item" else None)
    pm = out["por_mes"]
    if pm.height:
        out["por_mes"] = pm.sort("competencia")
    return out
