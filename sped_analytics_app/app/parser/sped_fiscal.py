"""Parser streaming do SPED Fiscal (EFD ICMS/IPI) — Blocos 0, C e D (somente entradas).

Lê linha a linha (nunca carrega o arquivo inteiro), mantém uma máquina de estados com o documento pai
corrente e grava cada registro-alvo em Parquet via SinkSet.
"""
from __future__ import annotations

from pathlib import Path

from app import config
from app.parser.layouts import SF, index_of
from app.parser.normalizer import SinkSet, pick, split_line

TABLES = ["sf_part", "sf_part_hist", "sf_unid", "sf_item_cad", "sf_item_hist", "sf_nat", "sf_conta",
          "sf_doc", "sf_c170", "sf_anal", "sf_c191", "sf_c197"]


def _idx(reg: str, names: list[str]) -> list[int]:
    ix = index_of(SF[reg])
    return [ix[n] if n else 10_000 for n in names]  # 10_000 => campo inexistente nesse registro ('')


# Mapas de campos (ordem = esquema da tabela destino, sem as colunas de contexto)
I_0150 = _idx("0150", ["COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE", "COD_MUN"])
I_0175 = _idx("0175", ["DT_ALT", "NR_CAMPO", "CONT_ANT"])
I_0190 = _idx("0190", ["UNID", "DESCR"])
I_0200 = _idx("0200", ["COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM", "UNID_INV", "TIPO_ITEM",
                       "COD_NCM", "EX_IPI", "COD_GEN", "COD_LST", "ALIQ_ICMS", "CEST"])
I_0205 = _idx("0205", ["DESCR_ANT_ITEM", "DT_INI", "DT_FIM", "COD_ANT_ITEM"])
I_0400 = _idx("0400", ["COD_NAT", "DESCR_NAT"])
I_0500 = _idx("0500", ["DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA", "NOME_CTA"])

_DOC_FIELDS = ["IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "NUM_DOC", "CHAVE", "DT_DOC",
               "DT_E_S", "VL_DOC", "VL_DESC", "VL_MERC", "VL_FRT", "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS",
               "VL_BC_ICMS_ST", "VL_ICMS_ST", "VL_IPI", "VL_PIS", "VL_COFINS"]
_DOC_ALIASES = {
    "C100": {"CHAVE": "CHV_NFE"},
    "C500": {"CHAVE": "CHV_DOCE", "VL_MERC": "VL_FORN", "VL_OUT_DA": "VL_DA"},
    "D100": {"CHAVE": "CHV_CTE", "DT_E_S": "DT_A_P", "VL_MERC": "VL_SERV"},
    "D500": {"DT_E_S": "DT_A_P", "VL_MERC": "VL_SERV", "VL_OUT_DA": "VL_DA"},
    "D700": {"CHAVE": "CHV_DOCE", "VL_MERC": "VL_SERV", "VL_OUT_DA": "VL_DA"},
}


def _doc_idx(reg: str) -> list[int]:
    ix = index_of(SF[reg])
    al = _DOC_ALIASES.get(reg, {})
    return [ix.get(al.get(f, f), 10_000) for f in _DOC_FIELDS]


I_DOC = {r: _doc_idx(r) for r in _DOC_ALIASES}
I_C170 = _idx("C170", ["NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID", "VL_ITEM", "VL_DESC", "IND_MOV",
                       "CST_ICMS", "CFOP", "COD_NAT", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
                       "ALIQ_ST", "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ", "VL_BC_IPI", "ALIQ_IPI", "VL_IPI",
                       "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS",
                       "VL_COFINS", "COD_CTA", "VL_ABAT_NT"])

_ANAL_FIELDS = ["CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST",
                "VL_RED_BC", "VL_IPI"]


def _anal_idx(reg: str) -> list[int]:
    ix = index_of(SF[reg])
    return [ix.get(f, 10_000) for f in _ANAL_FIELDS]


I_ANAL = {r: _anal_idx(r) for r in ("C190", "C590", "D190", "D590", "D730")}
ANAL_PARENT = {"C190": "C100", "C590": "C500", "D190": "D100", "D590": "D500", "D730": "D700"}
I_C191 = _idx("C191", ["VL_FCP_OP", "VL_FCP_ST", "VL_FCP_RET"])
I_C197 = _idx("C197", ["COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"])


def parse(path: str | Path, file_id: int, out_dir: Path) -> dict[str, int]:
    sinks = SinkSet(file_id, out_dir, TABLES)
    doc_id = 0
    anal_id = 0
    cur_doc_reg: str | None = None  # registro pai corrente (C100/C500/D100/D500/D700) ou None se ignorado
    cur_anal: int | None = None
    cur_part: str | None = None
    cur_item: str | None = None
    lines = 0
    try:
        with open(path, "r", encoding=config.FILE_ENCODING, errors="replace", newline="") as f:
            for line in f:
                lines += 1
                p = split_line(line)
                if not p:
                    continue
                reg = p[0]
                if reg in I_DOC:  # documento pai
                    if p[1] != "0":  # apenas entradas (IND_OPER = 0)
                        cur_doc_reg = None
                        continue
                    doc_id += 1
                    cur_doc_reg = reg
                    cur_anal = None
                    sinks.add("sf_doc", [file_id, doc_id, reg, *pick(p, I_DOC[reg])])
                elif reg == "C170":
                    if cur_doc_reg == "C100":
                        sinks.add("sf_c170", [file_id, doc_id, *pick(p, I_C170)])
                elif reg in I_ANAL:
                    if cur_doc_reg == ANAL_PARENT[reg]:
                        anal_id += 1
                        cur_anal = anal_id
                        sinks.add("sf_anal", [file_id, doc_id, anal_id, reg, *pick(p, I_ANAL[reg])])
                elif reg == "C191":
                    if cur_doc_reg == "C100" and cur_anal is not None:
                        sinks.add("sf_c191", [file_id, doc_id, cur_anal, *pick(p, I_C191)])
                elif reg == "C197":
                    if cur_doc_reg == "C100":
                        sinks.add("sf_c197", [file_id, doc_id, *pick(p, I_C197)])
                elif reg == "0150":
                    cur_part = p[1] if len(p) > 1 else ""
                    sinks.add("sf_part", [file_id, *pick(p, I_0150)])
                elif reg == "0175":
                    sinks.add("sf_part_hist", [file_id, cur_part, *pick(p, I_0175)])
                elif reg == "0200":
                    cur_item = p[1] if len(p) > 1 else ""
                    sinks.add("sf_item_cad", [file_id, *pick(p, I_0200)])
                elif reg == "0205":
                    sinks.add("sf_item_hist", [file_id, cur_item, *pick(p, I_0205)])
                elif reg == "0190":
                    sinks.add("sf_unid", [file_id, *pick(p, I_0190)])
                elif reg == "0400":
                    sinks.add("sf_nat", [file_id, *pick(p, I_0400)])
                elif reg == "0500":
                    sinks.add("sf_conta", [file_id, *pick(p, I_0500)])
                elif reg == "9999":
                    break  # após o 9999 vem a assinatura digital
                elif reg[1:] == "001" or reg[1:] == "990":
                    cur_doc_reg = None  # abertura/encerramento de bloco
        counts = sinks.close()
    except Exception:
        sinks.abort()
        raise
    counts["_linhas"] = lines
    counts["_documentos"] = doc_id
    return counts
