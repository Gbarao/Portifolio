"""Tradutor seguro de filtros dinâmicos (JSON) -> SQL parametrizado + persistência de filtros salvos.

Segurança: nomes de coluna só são aceitos se existirem no catálogo da tabela fato (whitelist);
operadores vêm de um conjunto fechado; todos os valores trafegam como parâmetros ($n), nunca concatenados.

Formato da regra:
    {"op": "AND" | "OR", "rules": [
        {"field": "cst_pis", "operator": "em", "value": ["50", "51"]},
        {"field": "vl_icms", "operator": ">", "value": 0},
        {"op": "OR", "rules": [...]}          # grupos aninhados
    ]}
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app import config

FATO = "fato_entradas_consolidadas"

# Catálogo de campos filtráveis: coluna -> (rótulo, tipo)
FIELDS: dict[str, tuple[str, str]] = {
    "competencia": ("Competência (AAAA-MM)", "text"),
    "cnpj_filial": ("CNPJ Filial", "text"),
    "nome_filial": ("Nome Filial", "text"),
    "uf_filial": ("UF Filial", "text"),
    "raiz_cnpj_filial": ("Raiz CNPJ Filial", "text"),
    "origem": ("Origem da Linha", "text"),
    "reg_doc": ("Registro do Documento", "text"),
    "cnpj_cpf_fornecedor": ("CNPJ/CPF Fornecedor", "text"),
    "raiz_cnpj_fornecedor": ("Raiz CNPJ Fornecedor", "text"),
    "razao_social_fornecedor": ("Razão Social Fornecedor", "text"),
    "uf_fornecedor": ("UF Fornecedor", "text"),
    "cod_mod": ("Modelo Documento", "text"),
    "cod_sit": ("Situação Documento", "text"),
    "ind_emit": ("Indicador Emitente", "text"),
    "serie": ("Série", "text"),
    "num_doc": ("Número Documento", "text"),
    "chave": ("Chave NF-e/CT-e", "text"),
    "dt_doc": ("Data Emissão", "date"),
    "dt_e_s": ("Data Entrada", "date"),
    "cod_item": ("Código Item", "text"),
    "cod_item_unificado": ("Código Item Unificado (0205)", "text"),
    "descr_item": ("Descrição Item", "text"),
    "tipo_item": ("Tipo Item (0200)", "text"),
    "cod_ncm": ("NCM", "text"),
    "cest": ("CEST", "text"),
    "cod_barra": ("Código de Barras", "text"),
    "unid": ("Unidade", "text"),
    "cfop": ("CFOP", "text"),
    "cod_nat": ("Natureza Operação", "text"),
    "cst_icms": ("CST ICMS", "text"),
    "aliq_icms": ("Alíquota ICMS", "number"),
    "cst_ipi": ("CST IPI", "text"),
    "aliq_ipi": ("Alíquota IPI", "number"),
    "cst_pis": ("CST PIS", "text"),
    "aliq_pis": ("Alíquota PIS", "number"),
    "cst_cofins": ("CST COFINS", "text"),
    "aliq_cofins": ("Alíquota COFINS", "number"),
    "nat_bc_cred": ("Natureza BC Crédito", "text"),
    "nat_bc_cred_origem": ("Origem NAT_BC_CRED", "text"),
    "cod_cta": ("Conta Contábil", "text"),
    "qtd": ("Quantidade", "number"),
    "vl_item": ("Valor Item", "number"),
    "vl_desc": ("Desconto", "number"),
    "vl_rateio_c190": ("Rateio p/ C190", "number"),
    "vl_contabil": ("Valor Contábil", "number"),
    "vl_bc_icms": ("BC ICMS", "number"),
    "vl_icms": ("Valor ICMS", "number"),
    "vl_bc_icms_st": ("BC ICMS-ST", "number"),
    "vl_icms_st": ("Valor ICMS-ST", "number"),
    "vl_fcp": ("Valor FCP", "number"),
    "vl_fcp_st": ("Valor FCP-ST", "number"),
    "vl_bc_ipi": ("BC IPI", "number"),
    "vl_ipi": ("Valor IPI", "number"),
    "vl_bc_pis": ("BC PIS", "number"),
    "vl_pis": ("Valor PIS", "number"),
    "vl_bc_cofins": ("BC COFINS", "number"),
    "vl_cofins": ("Valor COFINS", "number"),
    "vl_trib_recuperaveis": ("Tributos Recuperáveis", "number"),
    "vl_custo_liquido": ("Custo Líquido", "number"),
    "nivel_cruzamento_efd": ("Nível Cruzamento EFD", "text"),
    "status_efd": ("Status EFD-Contribuições", "text"),
    "flag_item_sintetico": ("Item Sintético", "bool"),
    "flag_sem_c190": ("Item sem C190", "bool"),
}

OPERATORS: dict[str, str] = {
    "=": "igual a", "!=": "diferente de", ">": "maior que", ">=": "maior ou igual", "<": "menor que",
    "<=": "menor ou igual", "entre": "entre (a;b)", "em": "está em (lista)", "nao_em": "não está em (lista)",
    "comeca_com": "começa com", "nao_comeca_com": "não começa com", "termina_com": "termina com",
    "contem": "contém", "nao_contem": "não contém", "vazio": "vazio / nulo", "preenchido": "preenchido",
}
OPS_BY_TYPE = {
    "text": ["=", "!=", "em", "nao_em", "comeca_com", "nao_comeca_com", "termina_com", "contem", "nao_contem",
             "vazio", "preenchido", ">", "<", "entre"],
    "number": ["=", "!=", ">", ">=", "<", "<=", "entre", "em", "nao_em", "vazio", "preenchido"],
    "date": ["=", "!=", ">", ">=", "<", "<=", "entre", "vazio", "preenchido"],
    "bool": ["=", "!="],
}


class FilterError(ValueError):
    pass


def _as_list(v: Any) -> list:
    if isinstance(v, (list, tuple, set)):
        return [x for x in v if x not in (None, "")]
    if v is None:
        return []
    return [x.strip() for x in str(v).replace(";", ",").split(",") if x.strip()]


def _num(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).strip()
        if "," in s:  # formato brasileiro 1.234,56
            s = s.replace(".", "").replace(",", ".")
        return float(s)
    except ValueError as e:
        raise FilterError(f"Valor numérico inválido: {v!r}") from e


def _date(v: Any) -> str:
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d%m%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise FilterError(f"Data inválida: {v!r}")


def _bool(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "sim", "s", "yes", "verdadeiro")


def _rule_sql(rule: dict, params: list) -> str:
    field = rule.get("field")
    if field not in FIELDS:
        raise FilterError(f"Campo não permitido: {field!r}")
    op = rule.get("operator")
    ftype = FIELDS[field][1]
    if op not in OPS_BY_TYPE[ftype]:
        raise FilterError(f"Operador {op!r} não aplicável ao campo {field}")
    val = rule.get("value")
    col = f'"{field}"'

    if op == "vazio":
        return f"({col} IS NULL OR CAST({col} AS VARCHAR) = '')" if ftype != "number" else f"coalesce({col}, 0) = 0"
    if op == "preenchido":
        return f"({col} IS NOT NULL AND CAST({col} AS VARCHAR) <> '')" if ftype != "number" else f"coalesce({col}, 0) <> 0"

    if ftype == "number":
        expr = f"coalesce({col}, 0)"
        conv = _num
    elif ftype == "date":
        expr, conv = col, _date
    elif ftype == "bool":
        expr, conv = f"coalesce({col}, false)", _bool
    else:
        expr, conv = f"trim({col})", lambda x: str(x).strip()

    if op in ("em", "nao_em"):
        vals = [conv(x) for x in _as_list(val)]
        if not vals:
            raise FilterError(f"Lista vazia para {field}")
        ph = []
        for x in vals:
            params.append(x)
            ph.append(f"${len(params)}")
        neg = "NOT " if op == "nao_em" else ""
        return f"{expr} {neg}IN ({', '.join(ph)})"
    if op == "entre":
        vals = _as_list(val)
        if len(vals) != 2:
            raise FilterError(f"'entre' exige dois valores (a;b) em {field}")
        params.extend([conv(vals[0]), conv(vals[1])])
        return f"{expr} BETWEEN ${len(params) - 1} AND ${len(params)}"
    if op in ("comeca_com", "nao_comeca_com", "termina_com", "contem", "nao_contem"):
        params.append(str(val or "").strip().lower())
        p = f"${len(params)}"
        e = f"lower(coalesce({col}, ''))"
        return {"comeca_com": f"starts_with({e}, {p})", "nao_comeca_com": f"NOT starts_with({e}, {p})",
                "termina_com": f"ends_with({e}, {p})", "contem": f"contains({e}, {p})",
                "nao_contem": f"NOT contains({e}, {p})"}[op]
    params.append(conv(val))
    return f"{expr} {op} ${len(params)}"


def rules_to_sql(node: dict | None, params: list, depth: int = 0) -> str:
    """Converte a árvore de regras em expressão SQL; devolve 'TRUE' se vazia."""
    if not node:
        return "TRUE"
    if depth > 8:
        raise FilterError("Aninhamento de grupos excessivo")
    if "field" in node:
        return _rule_sql(node, params)
    op = str(node.get("op", "AND")).upper()
    if op not in ("AND", "OR"):
        raise FilterError(f"Conector inválido: {op}")
    parts = [rules_to_sql(r, params, depth + 1) for r in node.get("rules", []) if r]
    parts = [p for p in parts if p != "TRUE"]
    if not parts:
        return "TRUE"
    return "(" + f" {op} ".join(parts) + ")"


# --------------------------------------------------------------------------------------
# Filtros globais fixos (barra superior)
# --------------------------------------------------------------------------------------
def global_filters_sql(gf: dict | None, params: list) -> str:
    gf = gf or {}
    conds: list[str] = []

    def in_list(col: str, values) -> None:
        vals = _as_list(values)
        if vals:
            ph = []
            for v in vals:
                params.append(str(v))
                ph.append(f"${len(params)}")
            conds.append(f"{col} IN ({', '.join(ph)})")

    in_list("competencia", gf.get("competencias"))
    if gf.get("comp_ini"):
        params.append(str(gf["comp_ini"]))
        conds.append(f"competencia >= ${len(params)}")
    if gf.get("comp_fim"):
        params.append(str(gf["comp_fim"]))
        conds.append(f"competencia <= ${len(params)}")
    if gf.get("ano"):
        in_list("left(competencia, 4)", gf.get("ano"))
    in_list("cnpj_filial", gf.get("filiais"))
    in_list("uf_filial", gf.get("ufs_filial"))
    in_list("raiz_cnpj_filial", gf.get("raizes_filial"))
    in_list("cnpj_cpf_fornecedor", gf.get("fornecedores"))
    in_list("raiz_cnpj_fornecedor", gf.get("raizes_fornecedor"))
    in_list("cfop", gf.get("cfops"))
    in_list("cod_item_unificado", gf.get("itens"))
    in_list("cod_ncm", gf.get("ncms"))
    for key, col in (("busca_fornecedor", "razao_social_fornecedor"), ("busca_item", "descr_item"),
                     ("busca_filial", "nome_filial")):
        if gf.get(key):
            params.append(str(gf[key]).strip().lower())
            conds.append(f"contains(lower(coalesce({col}, '')), ${len(params)})")
    if gf.get("ncm_prefixo"):
        params.append(str(gf["ncm_prefixo"]).strip())
        conds.append(f"starts_with(coalesce(cod_ncm, ''), ${len(params)})")
    if gf.get("cfop_prefixo"):
        params.append(str(gf["cfop_prefixo"]).strip())
        conds.append(f"starts_with(coalesce(cfop, ''), ${len(params)})")
    return " AND ".join(conds) if conds else "TRUE"


def where_clause(gf: dict | None, rules: dict | None, params: list, extra: list[tuple[str, Any]] | None = None) -> str:
    parts = [global_filters_sql(gf, params), rules_to_sql(rules, params)]
    for expr, value in extra or []:
        if value is None:
            parts.append(f"{expr} IS NULL")
        else:
            params.append(value)
            parts.append(f"{expr} = ${len(params)}")
    parts = [p for p in parts if p != "TRUE"]
    return " AND ".join(parts) if parts else "TRUE"


def describe_rules(node: dict | None) -> str:
    if not node:
        return ""
    if "field" in node:
        lbl = FIELDS.get(node["field"], (node["field"],))[0]
        op = OPERATORS.get(node["operator"], node["operator"])
        v = node.get("value")
        return f"{lbl} {op}" + ("" if node["operator"] in ("vazio", "preenchido") else f" {v}")
    inner = f" {node.get('op', 'AND').upper().replace('AND', 'E').replace('OR', 'OU')} ".join(
        describe_rules(r) for r in node.get("rules", []) if r)
    return f"({inner})" if inner else ""


# --------------------------------------------------------------------------------------
# Biblioteca de filtros salvos (DuckDB + espelho em user_presets.json)
# --------------------------------------------------------------------------------------
def validate(definicao: dict) -> None:
    rules_to_sql(definicao.get("rules"), [])
    global_filters_sql(definicao.get("global"), [])


def save_filter(db, nome: str, categoria: str, definicao: dict, filtro_id: int | None = None) -> int:
    validate(definicao)
    payload = json.dumps(definicao, ensure_ascii=False)
    with db.write_lock:
        if filtro_id:
            db.con.execute("UPDATE sys_filtros_salvos SET nome=?, categoria=?, definicao_json=?, "
                           "atualizado_em=current_timestamp WHERE id=?", [nome, categoria, payload, filtro_id])
            fid = filtro_id
        else:
            fid = db.con.execute("INSERT INTO sys_filtros_salvos (nome, categoria, definicao_json) VALUES (?, ?, ?) "
                                 "RETURNING id", [nome, categoria, payload]).fetchone()[0]
    _mirror_json(db)
    return fid


def delete_filter(db, filtro_id: int) -> None:
    with db.write_lock:
        db.con.execute("DELETE FROM sys_filtros_salvos WHERE id = ?", [filtro_id])
    _mirror_json(db)


def list_filters(db) -> list[dict]:
    cur = db.cursor()
    try:
        rows = cur.execute("SELECT id, nome, categoria, definicao_json, atualizado_em FROM sys_filtros_salvos "
                           "ORDER BY categoria, nome").fetchall()
    finally:
        cur.close()
    return [{"id": r[0], "nome": r[1], "categoria": r[2] or "Geral", "definicao": json.loads(r[3]),
             "atualizado_em": str(r[4])} for r in rows]


def _mirror_json(db) -> None:
    try:
        config.PRESETS_PATH.write_text(json.dumps({"filtros": list_filters(db)}, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    except OSError:
        pass


def import_presets_json(db) -> int:
    """Recarrega filtros do user_presets.json (ex.: após copiar o arquivo de outra máquina)."""
    if not config.PRESETS_PATH.exists():
        return 0
    data = json.loads(config.PRESETS_PATH.read_text(encoding="utf-8"))
    existing = {(f["nome"], f["categoria"]) for f in list_filters(db)}
    n = 0
    for f in data.get("filtros", []):
        if (f["nome"], f.get("categoria") or "Geral") not in existing:
            save_filter(db, f["nome"], f.get("categoria") or "Geral", f["definicao"])
            n += 1
    return n
