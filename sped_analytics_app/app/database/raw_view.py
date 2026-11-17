"""Consulta direta dos arquivos SPED (sem cruzamento): o que está escrito no TXT, registro a registro.

Cada linha guardada na importação é dividida pelo separador "|" no momento da consulta e exibida com os nomes
oficiais dos campos. Para registros filhos (C170, C190, D190, E110...) são acrescentadas colunas de contexto do
documento-pai (número, série, chave, data, participante), e para registros com COD_PART/COD_ITEM, os dados do
participante (0150) e do item (0200) do PRÓPRIO arquivo. Nada é combinado entre arquivos diferentes.
"""
from __future__ import annotations

import re
from typing import Any

import polars as pl

from app.parser import catalog

TABLE = {"ICMS_IPI": "sf_linhas", "CONTRIB": "ec_linhas"}
PART = {"ICMS_IPI": "sf_part", "CONTRIB": "ec_part"}
ITEM = {"ICMS_IPI": "sf_item_cad", "CONTRIB": "ec_item_cad"}
_REG_RE = re.compile(r"^[0-9A-Z]{4}$")

OPS = {"=": "igual a", "!=": "diferente de", "contem": "contém", "comeca": "começa com", "em": "está em (lista)",
       ">": "maior que", ">=": "maior ou igual", "<": "menor que", "<=": "menor ou igual", "vazio": "vazio",
       "preenchido": "preenchido"}


class RawQueryError(ValueError):
    pass


def _tipo(tipo: str) -> str:
    if tipo not in TABLE:
        raise RawQueryError("Tipo de arquivo inválido")
    return tipo


# --------------------------------------------------------------------------------------
# Metadados: arquivos, unidades, registros
# --------------------------------------------------------------------------------------
def _file_ids(db, tipo: str, q: dict) -> list[int]:
    conds, params = ["ativo", "tipo_sped = ?"], [tipo]
    if q.get("competencias"):
        conds.append("competencia IN (SELECT unnest(?))")
        params.append([str(c) for c in q["competencias"]])
    if q.get("comp_ini"):
        conds.append("competencia >= ?")
        params.append(str(q["comp_ini"]))
    if q.get("comp_fim"):
        conds.append("competencia <= ?")
        params.append(str(q["comp_fim"]))
    if q.get("arquivos"):
        conds.append("id_arquivo IN (SELECT unnest(?))")
        params.append([int(x) for x in q["arquivos"]])
    cur = db.cursor()
    try:
        return [r[0] for r in cur.execute(f"SELECT id_arquivo FROM sys_arquivos_importados WHERE {' AND '.join(conds)}",
                                          params).fetchall()]
    finally:
        cur.close()


def overview(db, tipo: str) -> dict:
    """Arquivos, competências e unidades disponíveis para a tela; arquivos ainda sem linhas originais."""
    tipo = _tipo(tipo)
    files = db.query("""
        SELECT a.id_arquivo, a.competencia, a.cnpj, a.nome, a.finalidade, a.linhas, a.caminho_origem,
               EXISTS (SELECT 1 FROM linhas_contagem c WHERE c.file_id = a.id_arquivo) AS indexado
        FROM sys_arquivos_importados a WHERE a.ativo AND a.tipo_sped = ? ORDER BY a.competencia DESC, a.cnpj""", [tipo])
    units = db.query("""
        WITH u AS (
            SELECT c.cnpj_estab AS cnpj, sum(c.n) AS linhas FROM linhas_contagem c
            JOIN sys_arquivos_importados a ON a.id_arquivo = c.file_id AND a.ativo AND a.tipo_sped = ?
            WHERE c.cnpj_estab IS NOT NULL GROUP BY 1
        ), nomes AS (
            SELECT cnpj, any_value(nome) AS nome FROM (
                SELECT cnpj_filial AS cnpj, nome_filial AS nome FROM dim_filial
                UNION ALL SELECT cnpj, nome FROM sys_arquivos_importados
                UNION ALL SELECT cnpj, nome FROM ec_estab) GROUP BY 1
        )
        SELECT u.cnpj, n.nome, u.linhas FROM u LEFT JOIN nomes n USING (cnpj) ORDER BY n.nome, u.cnpj""", [tipo])
    return {"arquivos": files.to_dicts(), "unidades": units.to_dicts(),
            "competencias": sorted({f["competencia"] for f in files.to_dicts()}),
            "blocos": catalog.BLOCOS[tipo]}


def registers(db, tipo: str, q: dict) -> list[dict]:
    """Registros presentes na seleção, com quantidade de linhas (via contagem gravada na importação)."""
    tipo = _tipo(tipo)
    ids = _file_ids(db, tipo, q)
    if not ids:
        return []
    params: list = []
    cond = ""
    if q.get("unidades"):
        cond = " AND cnpj_estab IN (SELECT unnest(?))"
        params.append([str(u) for u in q["unidades"]])
    df = db.query(f"SELECT reg, sum(n) AS n FROM linhas_contagem WHERE file_id IN ({','.join(map(str, ids))}){cond} "
                  "GROUP BY reg", params)
    order = {b: i for i, b in enumerate(catalog.BLOCOS[tipo])}
    out = [{"reg": r["reg"], "n": int(r["n"]), "bloco": r["reg"][:1], "descricao": catalog.descricao(tipo, r["reg"]),
            "conhecido": catalog.layout(tipo, r["reg"]) is not None} for r in df.to_dicts()]
    return sorted(out, key=lambda r: (order.get(r["bloco"], 99), r["reg"]))


# --------------------------------------------------------------------------------------
# Consulta de um registro
# --------------------------------------------------------------------------------------
def _expr(idx: int, kind: str, alias: str = "r.f") -> str:
    raw = f"nullif({alias}[{idx}], '')"
    if kind in ("money", "qty"):
        return f"TRY_CAST(replace({raw}, ',', '.') AS DOUBLE)"
    if kind == "date":
        return f"CAST(TRY_STRPTIME({raw}, '%d%m%Y') AS DATE)"
    return raw


class RegisterQuery:
    """Monta o SQL de consulta de um registro com filtros; reutilizado para grade, contagem e exportação."""

    def __init__(self, db, tipo: str, q: dict):
        self.db, self.tipo, self.q = db, _tipo(tipo), q
        reg = str(q.get("reg") or "").upper()
        if not _REG_RE.match(reg):
            raise RawQueryError("Registro inválido")
        self.reg = reg
        self.table = TABLE[tipo]
        self.ids = _file_ids(db, tipo, q)
        self.params: list = []
        self._build()

    # ---------------------------------------------------------------- partes
    def _base_where(self) -> str:
        if not self.ids:
            return "FALSE"
        conds = [f"l.file_id IN ({','.join(map(str, self.ids))})", f"l.reg = '{self.reg}'"]
        if self.q.get("unidades"):
            self.params.append([str(u) for u in self.q["unidades"]])
            conds.append(f"l.cnpj_estab IN (SELECT unnest(${len(self.params)}))")
        if (self.q.get("busca") or "").strip():
            self.params.append(str(self.q["busca"]).strip().lower())
            conds.append(f"contains(lower(l.linha), ${len(self.params)})")
        return " AND ".join(conds)

    def _field_count(self, where: str) -> int:
        cur = self.db.cursor()
        try:
            r = cur.execute(f"SELECT max(len(string_split(l.linha, '|'))) FROM {self.table} l WHERE {where}",
                            self.params).fetchone()
        finally:
            cur.close()
        return max(0, int(r[0] or 0) - 2)   # '|REG|a|b|' -> ['', 'REG', 'a', 'b', '']

    def _doc_reg(self, where: str) -> str | None:
        if self.reg[:1] in ("0", "9") or self.reg.endswith("001") or self.reg.endswith("990"):
            return None
        cur = self.db.cursor()
        try:
            r = cur.execute(f"""SELECT d.reg FROM {self.table} l JOIN {self.table} d
                                ON d.file_id = l.file_id AND d.line_no = l.doc_line
                                WHERE {where} AND l.doc_line <> l.line_no
                                GROUP BY 1 ORDER BY count(*) DESC LIMIT 1""", self.params).fetchone()
        finally:
            cur.close()
        return r[0] if r else None

    def _build(self) -> None:
        where = self._base_where()
        nf = self._field_count(where) if self.ids else 0
        lay = catalog.layout(self.tipo, self.reg) or ["REG"]
        n_fields = max(len(lay), nf)
        names = [lay[i] if i < len(lay) else f"CAMPO_{i + 1:02d}" for i in range(n_fields)]
        self.fields = names[1:]                      # sem o REG
        self.field_index = {n: i + 2 for i, n in enumerate(names)}  # posição em string_split

        self.doc_reg = self._doc_reg(where) if self.ids else None
        doc_lay = catalog.layout(self.tipo, self.doc_reg) if self.doc_reg else None
        self.doc_fields = [f for f in catalog.DOC_ID_FIELDS if doc_lay and f in doc_lay]
        doc_idx = {n: i + 2 for i, n in enumerate(doc_lay or [])}

        # Ordem das colunas: contexto mínimo -> nº do documento-pai -> CAMPOS DO REGISTRO -> demais dados do
        # documento-pai -> participante/item (0150/0200 do próprio arquivo) -> arquivo -> linha original
        cols: list[tuple[str, str, str]] = [   # (alias, expressão, tipo)
            ("competencia", "a.competencia", "text"), ("unidade", "r.cnpj_estab", "text"),
            ("linha_no", "r.line_no", "int")]
        joins = ["JOIN sys_arquivos_importados a ON a.id_arquivo = r.file_id"]
        doc_cols: list[tuple[str, str, str]] = []
        if self.doc_reg:
            joins.append("LEFT JOIN docs d ON d.file_id = r.file_id AND d.line_no = r.doc_line")
            for f in self.doc_fields:
                col = (f"doc_{f.lower()}", _expr(doc_idx[f], catalog.field_kind(f), "d.g"), catalog.field_kind(f))
                if f == "NUM_DOC":
                    cols.append(col)
                else:
                    doc_cols.append(col)

        for f in self.fields:
            k = catalog.field_kind(f)
            cols.append((f, _expr(self.field_index[f], k), k))
        cols += doc_cols

        # participante (0150) e item (0200) do próprio arquivo
        part_src = None
        if "COD_PART" in self.field_index:
            part_src = f"r.f[{self.field_index['COD_PART']}]"
        elif "COD_PART" in self.doc_fields:
            part_src = f"d.g[{doc_idx['COD_PART']}]"
        if part_src:
            if self.tipo == "CONTRIB":
                joins.append(f"""LEFT JOIN (SELECT DISTINCT ON (file_id, cnpj_filial, cod_part) * FROM ec_part
                                 ORDER BY ALL) p ON p.file_id = r.file_id AND p.cnpj_filial IS NOT DISTINCT FROM
                                 r.cnpj_estab AND p.cod_part = {part_src}""")
            else:
                joins.append(f"""LEFT JOIN (SELECT DISTINCT ON (file_id, cod_part) * FROM sf_part ORDER BY ALL) p
                                 ON p.file_id = r.file_id AND p.cod_part = {part_src}""")
            cols += [("part_cnpj_cpf", "coalesce(p.cnpj, p.cpf)", "text"), ("part_nome", "p.nome", "text")]
        if "COD_ITEM" in self.field_index:
            src = f"r.f[{self.field_index['COD_ITEM']}]"
            if self.tipo == "CONTRIB":
                joins.append(f"""LEFT JOIN (SELECT DISTINCT ON (file_id, cnpj_filial, cod_item) * FROM ec_item_cad
                                 ORDER BY ALL) it ON it.file_id = r.file_id AND it.cnpj_filial IS NOT DISTINCT FROM
                                 r.cnpj_estab AND it.cod_item = {src}""")
            else:
                joins.append(f"""LEFT JOIN (SELECT DISTINCT ON (file_id, cod_item) * FROM sf_item_cad ORDER BY ALL) it
                                 ON it.file_id = r.file_id AND it.cod_item = {src}""")
            cols += [("item_descr", "it.descr_item", "text"), ("item_ncm", "it.cod_ncm", "text"),
                     ("item_tipo", "it.tipo_item", "text")]
        cols += [("arquivo", "r.file_id", "int"), ("linha_original", "r.linha", "text")]
        self.columns = cols

        # filtros sobre campos e operação (entradas/saídas) — avaliados com split_part sobre a linha, sem montar
        # todas as colunas: a consulta localiza primeiro só as linhas que interessam (fase 1) e depois monta as
        # colunas apenas da página pedida (fase 2).
        conds = []
        for c in self.q.get("condicoes") or []:
            conds.append(self._cond(c))
        self.doc_in_keys = False
        oper = self.q.get("operacao")
        if oper in ("0", "1"):
            self.params.append(oper)
            if "IND_OPER" in self.field_index:
                conds.append(f"split_part(l.linha, '|', {self.field_index['IND_OPER']}) = ${len(self.params)}")
            elif "IND_OPER" in self.doc_fields:
                conds.append(f"split_part(dk.linha, '|', {doc_idx['IND_OPER']}) = ${len(self.params)}")
                self.doc_in_keys = True
            else:
                self.params.pop()
        key_join = (f" JOIN {self.table} dk ON dk.file_id = l.file_id AND dk.line_no = l.doc_line "
                    f"AND dk.reg = '{self.doc_reg}'") if self.doc_in_keys else ""
        self.keys_from = f"FROM {self.table} l{key_join} WHERE {' AND '.join([where] + conds)}"
        self.joins = joins
        self.ids_sql = ",".join(map(str, self.ids)) or "NULL"

    def _sp(self, field: str) -> str:
        return f"nullif(split_part(l.linha, '|', {self.field_index[field]}), '')"

    def _cond(self, c: dict) -> str:
        field, op, val = c.get("campo"), c.get("op"), c.get("valor")
        if field not in self.field_index or field == "REG":
            raise RawQueryError(f"Campo inválido: {field}")
        if op not in OPS:
            raise RawQueryError(f"Operador inválido: {op}")
        raw = self._sp(field)
        kind = catalog.field_kind(field)
        if op == "vazio":
            return f"coalesce({raw}, '') = ''"
        if op == "preenchido":
            return f"coalesce({raw}, '') <> ''"
        if op in ("contem", "comeca"):
            self.params.append(str(val or "").lower())
            fn = "contains" if op == "contem" else "starts_with"
            return f"{fn}(lower(coalesce({raw}, '')), ${len(self.params)})"
        if op == "em":
            vals = [v.strip() for v in re.split(r"[;,]", str(val or "")) if v.strip()]
            if not vals:
                raise RawQueryError(f"Lista vazia em {field}")
            self.params.append(vals)
            return f"{raw} IN (SELECT unnest(${len(self.params)}))"
        if kind in ("money", "qty") and op in (">", ">=", "<", "<=", "=", "!="):
            try:
                num = float(str(val).replace(".", "").replace(",", ".")) if "," in str(val) else float(val)
            except (TypeError, ValueError):
                raise RawQueryError(f"Valor numérico inválido em {field}: {val!r}")
            self.params.append(num)
            return f"coalesce(TRY_CAST(replace({raw}, ',', '.') AS DOUBLE), 0) {op} ${len(self.params)}"
        if kind == "date" and op in (">", ">=", "<", "<=", "=", "!="):
            m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str(val or "").strip())
            iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else str(val or "").strip()
            self.params.append(iso)
            return f"CAST(TRY_STRPTIME({raw}, '%d%m%Y') AS DATE) {op} CAST(${len(self.params)} AS DATE)"
        self.params.append(str(val or "").strip())
        return f"coalesce({raw}, '') {op} ${len(self.params)}"

    # ---------------------------------------------------------------- SQL final
    def select_sql(self, limit: int | None = None, offset: int = 0) -> str:
        """Fase 1: chaves (arquivo, linha) filtradas e paginadas. Fase 2: colunas só dessas linhas."""
        sel = ", ".join(f'{e} AS "{a}"' for a, e, _ in self.columns)
        page = f" ORDER BY l.file_id, l.line_no LIMIT {int(limit)} OFFSET {int(offset)}" if limit else ""
        docs = ""
        if self.doc_reg:
            docs = (f", docs AS (SELECT d.file_id, d.line_no, d.reg, string_split(d.linha, '|') AS g FROM {self.table} d "
                    f"JOIN (SELECT DISTINCT file_id, doc_line FROM k) kd ON d.file_id = kd.file_id "
                    f"AND d.line_no = kd.doc_line WHERE d.file_id IN ({self.ids_sql}) AND d.reg = '{self.doc_reg}')")
        return (f"WITH k AS (SELECT l.file_id, l.line_no, l.doc_line {self.keys_from}{page}), "
                f"r AS (SELECT l.file_id, l.line_no, l.cnpj_estab, l.doc_line, l.linha, string_split(l.linha, '|') AS f "
                f"FROM {self.table} l JOIN k ON k.file_id = l.file_id AND k.line_no = l.line_no "
                f"WHERE l.file_id IN ({self.ids_sql}) AND l.reg = '{self.reg}'){docs} "
                f"SELECT {sel} FROM r {' '.join(self.joins)} ORDER BY r.file_id, r.line_no")

    def count_sql(self) -> str:
        return f"SELECT count(*) {self.keys_from}"

    def types(self) -> list[str]:
        return [t for _, _, t in self.columns]


def query_register(db, tipo: str, q: dict, limit: int = 1000, offset: int = 0) -> dict:
    rq = RegisterQuery(db, tipo, q)
    df = db.query(rq.select_sql(limit, offset), rq.params) if rq.ids else pl.DataFrame()
    total = None
    if offset == 0:
        total = int(db.scalar(rq.count_sql(), rq.params) or 0) if rq.ids else 0
    return {"df": df, "rq": rq, "total": total}


def file_lines(db, tipo: str, q: dict, limit: int = 1000, offset: int = 0) -> dict:
    """Texto original de um arquivo, na ordem das linhas (com filtro opcional por registro e texto)."""
    tipo = _tipo(tipo)
    fid = int(q.get("arquivo") or 0)
    conds, params = ["file_id = $1"], [fid]
    regs = [r for r in (q.get("registros") or []) if _REG_RE.match(str(r))]
    if regs:
        params.append(regs)
        conds.append(f"reg IN (SELECT unnest(${len(params)}))")
    if (q.get("busca") or "").strip():
        params.append(str(q["busca"]).strip().lower())
        conds.append(f"contains(lower(linha), ${len(params)})")
    where = " AND ".join(conds)
    t = TABLE[tipo]
    df = db.query(f"SELECT line_no AS linha_no, reg, cnpj_estab AS unidade, linha AS linha_original FROM {t} "
                  f"WHERE {where} ORDER BY line_no LIMIT {int(limit)} OFFSET {int(offset)}", params)
    total = int(db.scalar(f"SELECT count(*) FROM {t} WHERE {where}", params) or 0) if offset == 0 else None
    return {"df": df, "total": total, "sql": f"SELECT line_no AS linha_no, reg, cnpj_estab AS unidade, "
                                               f"linha AS linha_original FROM {t} WHERE {where} ORDER BY line_no",
            "params": params}


def labels(rq: RegisterQuery) -> dict[str, str]:
    """Rótulos legíveis para as colunas de contexto (os campos do registro mantêm o nome oficial)."""
    out = {"competencia": "Competência", "unidade": "Unidade (CNPJ)", "arquivo": "Arquivo (ID)",
           "linha_no": "Linha no arquivo", "part_cnpj_cpf": "Participante CNPJ/CPF (0150)",
           "part_nome": "Participante nome (0150)", "item_descr": "Descrição do item (0200)",
           "item_ncm": "NCM (0200)", "item_tipo": "Tipo do item (0200)", "linha_original": "Linha original"}
    for f in rq.doc_fields:
        out[f"doc_{f.lower()}"] = f"{rq.doc_reg} · {f}"
    return out


def describe_filters(tipo: str, q: dict) -> dict[str, str]:
    out: dict[str, Any] = {"Arquivo": "SPED Fiscal (EFD ICMS/IPI)" if tipo == "ICMS_IPI" else "EFD-Contribuições"}
    if q.get("reg"):
        out["Registro"] = f"{q['reg']} — {catalog.descricao(tipo, q['reg'])}"
    if q.get("competencias"):
        out["Competências"] = ", ".join(q["competencias"])
    if q.get("comp_ini") or q.get("comp_fim"):
        out["Período"] = f"{q.get('comp_ini') or 'início'} a {q.get('comp_fim') or 'fim'}"
    if q.get("unidades"):
        out["Unidades"] = ", ".join(q["unidades"])
    if q.get("arquivos"):
        out["Arquivos (ID)"] = ", ".join(map(str, q["arquivos"]))
    if q.get("operacao") in ("0", "1"):
        out["Operação"] = "Entradas" if q["operacao"] == "0" else "Saídas"
    if q.get("busca"):
        out["Texto na linha"] = q["busca"]
    for i, c in enumerate(q.get("condicoes") or [], 1):
        out[f"Condição {i}"] = f"{c.get('campo')} {OPS.get(c.get('op'), c.get('op'))} {c.get('valor') or ''}".strip()
    return {k: str(v) for k, v in out.items()}
