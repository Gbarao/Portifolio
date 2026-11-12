"""Leiautes dos registros-alvo (ordem oficial dos campos, Guia Prático EFD ICMS/IPI e EFD-Contribuições).

Cada leiaute é a lista de campos na ordem do arquivo, iniciando por REG. Campos acrescidos em versões
posteriores ficam ao final; arquivos de versões antigas simplesmente não os trazem (o parser devolve vazio).
"""

# ======================================================================================
# EFD ICMS/IPI (SPED Fiscal)
# ======================================================================================
SF = {
    "0000": ["REG", "COD_VER", "COD_FIN", "DT_INI", "DT_FIN", "NOME", "CNPJ", "CPF", "UF", "IE",
             "COD_MUN", "IM", "SUFRAMA", "IND_PERFIL", "IND_ATIV"],
    "0150": ["REG", "COD_PART", "NOME", "COD_PAIS", "CNPJ", "CPF", "IE", "COD_MUN", "SUFRAMA",
             "END", "NUM", "COMPL", "BAIRRO"],
    "0175": ["REG", "DT_ALT", "NR_CAMPO", "CONT_ANT"],
    "0190": ["REG", "UNID", "DESCR"],
    "0200": ["REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM", "UNID_INV", "TIPO_ITEM",
             "COD_NCM", "EX_IPI", "COD_GEN", "COD_LST", "ALIQ_ICMS", "CEST"],
    "0205": ["REG", "DESCR_ANT_ITEM", "DT_INI", "DT_FIM", "COD_ANT_ITEM"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "0500": ["REG", "DT_ALT", "COD_NAT_CC", "IND_CTA", "NIVEL", "COD_CTA", "NOME_CTA"],
    "C100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "NUM_DOC", "CHV_NFE",
             "DT_DOC", "DT_E_S", "VL_DOC", "IND_PGTO", "VL_DESC", "VL_ABAT_NT", "VL_MERC", "IND_FRT",
             "VL_FRT", "VL_SEG", "VL_OUT_DA", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST",
             "VL_IPI", "VL_PIS", "VL_COFINS", "VL_PIS_ST", "VL_COFINS_ST"],
    "C170": ["REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "QTD", "UNID", "VL_ITEM", "VL_DESC", "IND_MOV",
             "CST_ICMS", "CFOP", "COD_NAT", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "ALIQ_ST",
             "VL_ICMS_ST", "IND_APUR", "CST_IPI", "COD_ENQ", "VL_BC_IPI", "ALIQ_IPI", "VL_IPI", "CST_PIS",
             "VL_BC_PIS", "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "CST_COFINS",
             "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA",
             "VL_ABAT_NT"],
    "C190": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
             "VL_ICMS_ST", "VL_RED_BC", "VL_IPI", "COD_OBS"],
    "C191": ["REG", "VL_FCP_OP", "VL_FCP_ST", "VL_FCP_RET"],
    "C197": ["REG", "COD_AJ", "DESCR_COMPL_AJ", "COD_ITEM", "VL_BC_ICMS", "ALIQ_ICMS", "VL_ICMS", "VL_OUTROS"],
    "C500": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "COD_CONS",
             "NUM_DOC", "DT_DOC", "DT_E_S", "VL_DOC", "VL_DESC", "VL_FORN", "VL_SERV_NT", "VL_TERC", "VL_DA",
             "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST", "VL_ICMS_ST", "COD_INF", "VL_PIS", "VL_COFINS",
             "TP_LIGACAO", "COD_GRUPO_TENSAO", "CHV_DOCE", "FIN_DOCE", "CHV_DOCE_REF", "IND_DEST",
             "COD_MUN_DEST", "COD_CTA"],
    "C590": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_ST",
             "VL_ICMS_ST", "VL_RED_BC", "COD_OBS"],
    "D100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
             "CHV_CTE", "DT_DOC", "DT_A_P", "TP_CTE", "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT", "VL_SERV",
             "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF", "COD_CTA", "COD_MUN_ORIG", "COD_MUN_DEST"],
    "D190": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_RED_BC", "COD_OBS"],
    "D500": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
             "DT_DOC", "DT_A_P", "VL_DOC", "VL_DESC", "VL_SERV", "VL_SERV_NT", "VL_TERC", "VL_DA",
             "VL_BC_ICMS", "VL_ICMS", "COD_INF", "VL_PIS", "VL_COFINS", "COD_CTA", "TP_ASSINANTE"],
    "D590": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_BC_ICMS_UF",
             "VL_ICMS_UF", "VL_RED_BC", "COD_OBS"],
    # NFCom (modelo 62) — registros D700/D730
    "D700": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "NUM_DOC", "DT_DOC",
             "DT_E_S", "VL_DOC", "VL_DESC", "VL_SERV", "VL_SERV_NT", "VL_TERC", "VL_DA", "VL_BC_ICMS",
             "VL_ICMS", "COD_INF", "VL_PIS", "VL_COFINS", "CHV_DOCE"],
    "D730": ["REG", "CST_ICMS", "CFOP", "ALIQ_ICMS", "VL_OPR", "VL_BC_ICMS", "VL_ICMS", "VL_RED_BC", "COD_OBS"],
}

# ======================================================================================
# EFD-Contribuições (PIS/COFINS)
# ======================================================================================
EC = {
    "0000": ["REG", "COD_VER", "TIPO_ESCRIT", "IND_SIT_ESP", "NUM_REC_ANTERIOR", "DT_INI", "DT_FIN", "NOME",
             "CNPJ", "UF", "COD_MUN", "SUFRAMA", "IND_NAT_PJ", "IND_ATIV"],
    "0140": ["REG", "COD_EST", "NOME", "CNPJ", "UF", "IE", "COD_MUN", "IM", "SUFRAMA"],
    "0150": SF["0150"],
    "0190": SF["0190"],
    "0200": ["REG", "COD_ITEM", "DESCR_ITEM", "COD_BARRA", "COD_ANT_ITEM", "UNID_INV", "TIPO_ITEM",
             "COD_NCM", "EX_IPI", "COD_GEN", "COD_LST", "ALIQ_ICMS"],
    "0205": SF["0205"],
    "0500": SF["0500"],
    "A010": ["REG", "CNPJ"],
    "A100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_SIT", "SER", "SUB", "NUM_DOC", "CHV_NFSE",
             "DT_DOC", "DT_EXE_SERV", "VL_DOC", "IND_PGTO", "VL_DESC", "VL_BC_PIS", "VL_PIS", "VL_BC_COFINS",
             "VL_COFINS", "VL_PIS_RET", "VL_COFINS_RET", "VL_ISS"],
    "A170": ["REG", "NUM_ITEM", "COD_ITEM", "DESCR_COMPL", "VL_ITEM", "VL_DESC", "NAT_BC_CRED",
             "IND_ORIG_CRED", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS",
             "ALIQ_COFINS", "VL_COFINS", "COD_CTA", "COD_CCUS"],
    "C010": ["REG", "CNPJ", "IND_ESCRI"],
    "C100": SF["C100"],
    "C170": SF["C170"][:-1],  # sem VL_ABAT_NT
    "C190": ["REG", "COD_MOD", "DT_REF_INI", "DT_REF_FIN", "COD_ITEM", "COD_NCM", "EX_IPI", "VL_TOT_ITEM"],
    "C191": ["REG", "CNPJ_CPF_PART", "CST_PIS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_PIS", "ALIQ_PIS",
             "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_PIS", "COD_CTA"],
    "C195": ["REG", "CNPJ_CPF_PART", "CST_COFINS", "CFOP", "VL_ITEM", "VL_DESC", "VL_BC_COFINS",
             "ALIQ_COFINS", "QUANT_BC_COFINS", "ALIQ_COFINS_QUANT", "VL_COFINS", "COD_CTA"],
    "C500": ["REG", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC", "DT_DOC", "DT_ENT", "VL_DOC",
             "VL_ICMS", "COD_INF", "VL_PIS", "VL_COFINS", "CHV_DOCE"],
    "C501": ["REG", "CST_PIS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "COD_CTA"],
    "C505": ["REG", "CST_COFINS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "D010": ["REG", "CNPJ"],
    "D100": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
             "CHV_CTE", "DT_DOC", "DT_A_P", "TP_CTE", "CHV_CTE_REF", "VL_DOC", "VL_DESC", "IND_FRT", "VL_SERV",
             "VL_BC_ICMS", "VL_ICMS", "VL_NT", "COD_INF", "COD_CTA"],
    "D101": ["REG", "IND_NAT_FRT", "VL_ITEM", "CST_PIS", "NAT_BC_CRED", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "COD_CTA"],
    "D105": ["REG", "IND_NAT_FRT", "VL_ITEM", "CST_COFINS", "NAT_BC_CRED", "VL_BC_COFINS", "ALIQ_COFINS",
             "VL_COFINS", "COD_CTA"],
    "D500": ["REG", "IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "SUB", "NUM_DOC",
             "DT_DOC", "DT_A_P", "VL_DOC", "VL_DESC", "VL_SERV", "VL_SERV_NT", "VL_TERC", "VL_DA",
             "VL_BC_ICMS", "VL_ICMS", "COD_INF", "VL_PIS", "VL_COFINS"],
    "D501": ["REG", "CST_PIS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "COD_CTA"],
    "D505": ["REG", "CST_COFINS", "VL_ITEM", "NAT_BC_CRED", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA"],
    "F010": ["REG", "CNPJ"],
    "F100": ["REG", "IND_OPER", "COD_PART", "COD_ITEM", "DT_OPER", "VL_OPER", "CST_PIS", "VL_BC_PIS",
             "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "NAT_BC_CRED",
             "IND_ORIG_CRED", "COD_CTA", "COD_CCUS", "DESC_DOC_OPER"],
    "F120": ["REG", "NAT_BC_CRED", "IDENT_BEM_IMOB", "IND_ORIG_CRED", "IND_UTIL_BEM_IMOB", "VL_OPER_DEP",
             "PARC_OPER_NAO_BC_CRED", "CST_PIS", "VL_BC_PIS", "ALIQ_PIS", "VL_PIS", "CST_COFINS",
             "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA", "COD_CCUS", "DESC_BEM_IMOB"],
    "F130": ["REG", "NAT_BC_CRED", "IDENT_BEM_IMOB", "IND_ORIG_CRED", "IND_UTIL_BEM_IMOB", "MES_OPER_AQUIS",
             "VL_OPER_AQUIS", "PARC_OPER_NAO_BC_CRED", "VL_BC_CRED", "IND_NR_PARC", "CST_PIS", "VL_BC_PIS",
             "ALIQ_PIS", "VL_PIS", "CST_COFINS", "VL_BC_COFINS", "ALIQ_COFINS", "VL_COFINS", "COD_CTA",
             "COD_CCUS", "DESC_BEM_IMOB"],
}


def index_of(layout: list[str]) -> dict[str, int]:
    return {name: i for i, name in enumerate(layout)}
