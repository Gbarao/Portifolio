"""Parser streaming da EFD-Contribuições — Blocos 0, A, C, D e F (somente operações de entrada/crédito).

A escrituração é centralizada na matriz: o CNPJ da filial vem do 0140 (cadastros do Bloco 0) e dos
registros A010/C010/D010/F010 (movimento). A máquina de estados carimba cada documento/item com o
CNPJ do estabelecimento ativo no momento da leitura.
"""
from __future__ import annotations

from pathlib import Path

from app import config
from app.parser.layouts import EC, index_of
from app.parser.normalizer import SCHEMAS, SinkSet, pick, split_line

TABLES = ["ec_estab", "ec_bloco_estab", "ec_part", "ec_item_cad", "ec_item_hist", "ec_conta", "ec_doc",
          "ec_item", "ec_doc_trib", "ec_c190", "ec_c191_195", "ec_f"]

_NONE = 10_000


def _map(reg: str, cols: list[str], aliases: dict[str, str] | None = None) -> list[int]:
    ix = index_of(EC[reg])
    al = aliases or {}
    out = []
    for c in cols:
        name = al.get(c, c.upper())
        out.append(ix.get(name, _NONE) if name else _NONE)
    return out


def _schema_cols(table: str, skip: int) -> list[str]:
    return [c for c, _ in SCHEMAS[table]][skip:]


I_0140 = _map("0140", _schema_cols("ec_estab", 1))
I_0150 = _map("0150", _schema_cols("ec_part", 2))
I_0200 = _map("0200", _schema_cols("ec_item_cad", 2))
I_0205 = _map("0205", ["descr_ant_item", "dt_ini", "dt_fim", "cod_ant_item"])
I_0500 = _map("0500", _schema_cols("ec_conta", 1))

_DOC_COLS = _schema_cols("ec_doc", 4)  # após file_id, doc_id, cnpj_filial, reg
I_DOC = {
    "C100": _map("C100", _DOC_COLS, {"chave": "CHV_NFE", "dt_e_s": "DT_E_S"}),
    "A100": _map("A100", _DOC_COLS, {"cod_mod": "", "chave": "CHV_NFSE", "dt_e_s": "DT_EXE_SERV", "vl_merc": "",
                                     "vl_icms": "", "vl_ipi": ""}),
    "C500": _map("C500", _DOC_COLS, {"ind_oper": "", "ind_emit": "", "chave": "CHV_DOCE", "dt_e_s": "DT_ENT",
                                     "vl_desc": "", "vl_merc": "", "vl_ipi": ""}),
    "D100": _map("D100", _DOC_COLS, {"chave": "CHV_CTE", "dt_e_s": "DT_A_P", "vl_merc": "VL_SERV", "vl_ipi": "",
                                     "vl_pis": "", "vl_cofins": ""}),
    "D500": _map("D500", _DOC_COLS, {"chave": "", "dt_e_s": "DT_A_P", "vl_merc": "VL_SERV", "vl_ipi": ""}),
}
HAS_IND_OPER = {"C100", "A100", "D100", "D500"}

_ITEM_COLS = _schema_cols("ec_item", 4)  # após file_id, doc_id, cnpj_filial, reg
I_ITEM = {
    "C170": _map("C170", _ITEM_COLS, {"nat_bc_cred": ""}),
    "A170": _map("A170", _ITEM_COLS, {"qtd": "", "unid": "", "cst_icms": "", "cfop": "", "aliq_icms": "",
                                      "vl_bc_icms": "", "vl_icms": "", "vl_icms_st": "", "vl_ipi": ""}),
}
ITEM_PARENT = {"C170": "C100", "A170": "A100"}

_TRIB_COLS = ["cst", "vl_item", "nat_bc_cred", "vl_bc", "aliq", "vl", "cod_cta"]
I_TRIB = {}
TRIB_PARENT = {}
for _r, _parent, _t in (("C501", "C500", "PIS"), ("C505", "C500", "COFINS"), ("D101", "D100", "PIS"),
                        ("D105", "D100", "COFINS"), ("D501", "D500", "PIS"), ("D505", "D500", "COFINS")):
    I_TRIB[_r] = (_map(_r, _TRIB_COLS, {"cst": f"CST_{_t}", "vl_bc": f"VL_BC_{_t}", "aliq": f"ALIQ_{_t}",
                                        "vl": f"VL_{_t}"}), _t)
    TRIB_PARENT[_r] = _parent

I_C190 = _map("C190", _schema_cols("ec_c190", 3))
_C19X_COLS = ["cnpj_cpf_part", "cst", "cfop", "vl_item", "vl_desc", "vl_bc", "aliq", "vl", "cod_cta"]
I_C19X = {
    "C191": (_map("C191", _C19X_COLS, {"cst": "CST_PIS", "vl_bc": "VL_BC_PIS", "aliq": "ALIQ_PIS", "vl": "VL_PIS"}),
             "PIS"),
    "C195": (_map("C195", _C19X_COLS, {"cst": "CST_COFINS", "vl_bc": "VL_BC_COFINS", "aliq": "ALIQ_COFINS",
                                       "vl": "VL_COFINS"}), "COFINS"),
}

_F_COLS = _schema_cols("ec_f", 3)  # após file_id, cnpj_filial, reg
I_F = {
    "F100": _map("F100", _F_COLS, {"descr": "DESC_DOC_OPER", "vl_oper": "VL_OPER"}),
    "F120": _map("F120", _F_COLS, {"ind_oper": "", "cod_part": "", "cod_item": "IDENT_BEM_IMOB", "dt_oper": "",
                                   "vl_oper": "VL_OPER_DEP", "descr": "DESC_BEM_IMOB"}),
    "F130": _map("F130", _F_COLS, {"ind_oper": "", "cod_part": "", "cod_item": "IDENT_BEM_IMOB", "dt_oper": "",
                                   "vl_oper": "VL_OPER_AQUIS", "descr": "DESC_BEM_IMOB"}),
}


def parse(path: str | Path, file_id: int, out_dir: Path) -> dict[str, int]:
    sinks = SinkSet(file_id, out_dir, TABLES)
    cnpj_0140 = ""  # estabelecimento corrente no Bloco 0
    cnpj_mov = ""  # estabelecimento corrente nos blocos de movimento (X010)
    matriz = ""
    doc_id = 0
    c190_id = 0
    cur_doc_reg: str | None = None
    cur_c190: int | None = None
    cur_item0200 = ""
    lines = 0
    try:
        with open(path, "r", encoding=config.FILE_ENCODING, errors="replace", newline="") as f:
            for line in f:
                lines += 1
                p = split_line(line)
                if not p:
                    continue
                reg = p[0]
                if reg in I_ITEM:
                    if cur_doc_reg == ITEM_PARENT[reg]:
                        sinks.add("ec_item", [file_id, doc_id, cnpj_mov, reg, *pick(p, I_ITEM[reg])])
                elif reg in I_DOC:
                    if reg in HAS_IND_OPER and p[1] != "0":
                        cur_doc_reg = None
                        continue
                    doc_id += 1
                    cur_doc_reg = reg
                    row = pick(p, I_DOC[reg])
                    if reg == "C500":
                        row[0] = "0"
                    sinks.add("ec_doc", [file_id, doc_id, cnpj_mov, reg, *row])
                elif reg in I_TRIB:
                    if cur_doc_reg == TRIB_PARENT[reg]:
                        idx, trib = I_TRIB[reg]
                        sinks.add("ec_doc_trib", [file_id, doc_id, reg, trib, *pick(p, idx)])
                elif reg == "C190":
                    c190_id += 1
                    cur_c190 = c190_id
                    cur_doc_reg = None
                    sinks.add("ec_c190", [file_id, c190_id, cnpj_mov, *pick(p, I_C190)])
                elif reg in I_C19X:
                    if cur_c190 is not None:
                        idx, trib = I_C19X[reg]
                        sinks.add("ec_c191_195", [file_id, cur_c190, reg, trib, *pick(p, idx)])
                elif reg in I_F:
                    if reg == "F100" and (len(p) < 2 or p[1] != "0"):
                        continue  # F100 IND_OPER 0 = aquisição/custo/despesa com crédito
                    row = pick(p, I_F[reg])
                    if reg != "F100":
                        row[0] = "0"
                    sinks.add("ec_f", [file_id, cnpj_mov, reg, *row])
                elif reg in ("A010", "C010", "D010", "F010"):
                    cnpj_mov = p[1] if len(p) > 1 else ""
                    cur_doc_reg = None
                    cur_c190 = None
                    sinks.add("ec_bloco_estab", [file_id, reg, cnpj_mov, p[2] if reg == "C010" and len(p) > 2 else ""])
                elif reg == "0140":
                    cnpj_0140 = p[3] if len(p) > 3 else ""
                    sinks.add("ec_estab", [file_id, *pick(p, I_0140)])
                elif reg == "0150":
                    sinks.add("ec_part", [file_id, cnpj_0140 or matriz, *pick(p, I_0150)])
                elif reg == "0200":
                    cur_item0200 = p[1] if len(p) > 1 else ""
                    sinks.add("ec_item_cad", [file_id, cnpj_0140 or matriz, *pick(p, I_0200)])
                elif reg == "0205":
                    sinks.add("ec_item_hist", [file_id, cnpj_0140 or matriz, cur_item0200, *pick(p, I_0205)])
                elif reg == "0500":
                    sinks.add("ec_conta", [file_id, *pick(p, I_0500)])
                elif reg == "0000":
                    matriz = p[8] if len(p) > 8 else ""
                elif reg == "9999":
                    break
                elif reg[1:] in ("001", "990"):
                    cur_doc_reg = None
                    cur_c190 = None
                elif reg in ("C180", "C380", "C395", "C400", "C490", "C600", "C800", "D200", "D300", "D350",
                             "D600", "A111", "A120"):
                    cur_doc_reg = None  # outros pais: impede vinculação indevida de filhos
                    cur_c190 = None
        counts = sinks.close()
    except Exception:
        sinks.abort()
        raise
    counts["_linhas"] = lines
    counts["_documentos"] = doc_id
    return counts
