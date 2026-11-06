"""Dicionario de layout da EFD Contribuicoes (PIS/COFINS).

Campos conforme o Guia Pratico da EFD Contribuicoes. ATENCAO: conferir a lista
de campos no Guia Pratico da versao do COD_VER de cada arquivo (DECISOES.md,
D-003). Os registros C010/A010/F010/0140 definem o estabelecimento dos filhos.
"""
from __future__ import annotations

from .comum import Registro, VersaoLayout, campos, reg

TIPO = "CONTRIB"


def _m210(trib: str) -> tuple[VersaoLayout, VersaoLayout]:
    atual = campos(
        f"REG COD_CONT VL_REC_BRT VL_BC_CONT VL_AJUS_ACRES_BC_{trib} VL_AJUS_REDUC_BC_{trib} "
        f"VL_BC_CONT_AJUS ALIQ_{trib} QUANT_BC_{trib} ALIQ_{trib}_QUANT VL_CONT_APUR "
        "VL_AJUS_ACRES VL_AJUS_REDUC VL_CONT_DIFER VL_CONT_DIFER_ANT VL_CONT_PER")
    anterior = campos(
        f"REG COD_CONT VL_REC_BRT VL_BC_CONT ALIQ_{trib} QUANT_BC_{trib} ALIQ_{trib}_QUANT "
        "VL_CONT_APUR VL_AJUS_ACRES VL_AJUS_REDUC VL_CONT_DIFER VL_CONT_DIFER_ANT VL_CONT_PER")
    return (VersaoLayout("atual", atual),
            VersaoLayout("anterior_sem_ajustes_de_base", anterior))


def _m100(trib: str) -> str:
    return (f"REG COD_CRED IND_CRED_ORI VL_BC_{trib} ALIQ_{trib} QUANT_BC_{trib} "
            f"ALIQ_{trib}_QUANT VL_CRED VL_AJUS_ACRES VL_AJUS_REDUC VL_CRED_DIF VL_CRED_DISP "
            "IND_DESC_CRED VL_CRED_DESC SLD_CRED")


def _m105(trib: str) -> str:
    return (f"REG NAT_BC_CRED CST_{trib} VL_BC_{trib}_TOT VL_BC_{trib}_CUM VL_BC_{trib}_NC "
            f"VL_BC_{trib} QUANT_BC_{trib}_TOT QUANT_BC_{trib} DESC_CRED")


_M200 = ("REG VL_TOT_CONT_NC_PER VL_TOT_CRED_DESC VL_TOT_CRED_DESC_ANT VL_TOT_CONT_NC_DEV "
         "VL_RET_NC VL_OUT_DED_NC VL_CONT_NC_REC VL_TOT_CONT_CUM_PER VL_RET_CUM "
         "VL_OUT_DED_CUM VL_CONT_CUM_REC VL_TOT_CONT_REC")

_1100 = ("REG PER_APU_CRED ORIG_CRED CNPJ_SUC COD_CRED VL_CRED_APU VL_CRED_EXT_APU "
         "VL_TOT_CRED_APU VL_CRED_DESC_PA_ANT VL_CRED_PER_PA_ANT VL_CRED_DCOMP_PA_ANT "
         "SD_CRED_DISP_EFD VL_CRED_DESC_EFD VL_CRED_PER_EFD VL_CRED_DCOMP_EFD VL_CRED_TRANS "
         "VL_CRED_OUT SLD_CRED_FIM")

_C170 = (
    "REG NUM_ITEM COD_ITEM DESCR_COMPL QTD UNID VL_ITEM VL_DESC IND_MOV CST_ICMS CFOP "
    "COD_NAT VL_BC_ICMS ALIQ_ICMS VL_ICMS VL_BC_ICMS_ST ALIQ_ST VL_ICMS_ST IND_APUR "
    "CST_IPI COD_ENQ VL_BC_IPI ALIQ_IPI VL_IPI CST_PIS VL_BC_PIS ALIQ_PIS QUANT_BC_PIS "
    "ALIQ_PIS_QUANT VL_PIS CST_COFINS VL_BC_COFINS ALIQ_COFINS QUANT_BC_COFINS "
    "ALIQ_COFINS_QUANT VL_COFINS COD_CTA")

_C100 = (
    "REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER NUM_DOC CHV_NFE DT_DOC DT_E_S "
    "VL_DOC IND_PGTO VL_DESC VL_ABAT_NT VL_MERC IND_FRT VL_FRT VL_SEG VL_OUT_DA "
    "VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST VL_IPI VL_PIS VL_COFINS VL_PIS_ST "
    "VL_COFINS_ST")

REGISTROS: dict[str, Registro] = {r.reg: r for r in [
    reg("0000", "Abertura e identificacao",
        "REG COD_VER TIPO_ESCRIT IND_SIT_ESP NUM_REC_ANTERIOR DT_INI DT_FIN NOME CNPJ UF "
        "COD_MUN SUFRAMA IND_NAT_PJ IND_ATIV"),
    reg("0110", "Regimes de apuracao",
        "REG COD_INC_TRIB IND_APRO_CRED COD_TIPO_CONT IND_REG_CUM"),
    reg("0140", "Estabelecimentos",
        "REG COD_EST NOME CNPJ UF IE COD_MUN IM SUFRAMA", campo_cnpj_estab="CNPJ"),
    reg("0150", "Participantes",
        "REG COD_PART NOME COD_PAIS CNPJ CPF IE COD_MUN SUFRAMA END NUM COMPL BAIRRO",
        pai="0140"),
    reg("0190", "Unidades de medida", "REG UNID DESCR", pai="0140"),
    reg("0200", "Itens",
        "REG COD_ITEM DESCR_ITEM COD_BARRA COD_ANT_ITEM UNID_INV TIPO_ITEM COD_NCM EX_IPI "
        "COD_GEN COD_LST ALIQ_ICMS", pai="0140"),
    reg("A010", "Estabelecimento (servicos)", "REG CNPJ", campo_cnpj_estab="CNPJ"),
    reg("A100", "Documento de servico",
        "REG IND_OPER IND_EMIT COD_PART COD_SIT SER SUB NUM_DOC CHV_NFSE DT_DOC DT_EXE_SERV "
        "VL_DOC IND_PGTO VL_DESC VL_BC_PIS VL_PIS VL_BC_COFINS VL_COFINS VL_PIS_RET "
        "VL_COFINS_RET VL_ISS", pai="A010"),
    reg("A170", "Itens do documento de servico",
        "REG NUM_ITEM COD_ITEM DESCR_COMPL VL_ITEM VL_DESC NAT_BC_CRED IND_ORIG_CRED "
        "CST_PIS VL_BC_PIS ALIQ_PIS VL_PIS CST_COFINS VL_BC_COFINS ALIQ_COFINS VL_COFINS "
        "COD_CTA COD_CCUS", pai="A100"),
    reg("C010", "Estabelecimento (bloco C)", "REG CNPJ IND_ESCRI", campo_cnpj_estab="CNPJ"),
    reg("C100", "Documento (NF-e)", _C100, pai="C010"),
    reg("C170", "Itens do documento", _C170, pai="C100"),
    reg("C180", "Consolidacao das NF-e de saida por item",
        "REG COD_MOD DT_DOC_INI DT_DOC_FIN COD_ITEM COD_NCM EX_IPI VL_TOT_ITEM", pai="C010"),
    reg("C181", "Detalhamento PIS das saidas consolidadas",
        "REG CST_PIS CFOP VL_ITEM VL_DESC VL_BC_PIS ALIQ_PIS QUANT_BC_PIS ALIQ_PIS_QUANT "
        "VL_PIS COD_CTA", pai="C180"),
    reg("C185", "Detalhamento COFINS das saidas consolidadas",
        "REG CST_COFINS CFOP VL_ITEM VL_DESC VL_BC_COFINS ALIQ_COFINS QUANT_BC_COFINS "
        "ALIQ_COFINS_QUANT VL_COFINS COD_CTA", pai="C180"),
    reg("C190", "Consolidacao das entradas por item",
        "REG COD_MOD DT_REF_INI DT_REF_FIN COD_ITEM COD_NCM EX_IPI VL_TOT_ITEM", pai="C010"),
    reg("C191", "Detalhamento PIS das entradas consolidadas",
        "REG CNPJ_CPF_PART CST_PIS CFOP VL_ITEM VL_DESC VL_BC_PIS ALIQ_PIS QUANT_BC_PIS "
        "ALIQ_PIS_QUANT VL_PIS COD_CTA", pai="C190"),
    reg("C195", "Detalhamento COFINS das entradas consolidadas",
        "REG CNPJ_CPF_PART CST_COFINS CFOP VL_ITEM VL_DESC VL_BC_COFINS ALIQ_COFINS "
        "QUANT_BC_COFINS ALIQ_COFINS_QUANT VL_COFINS COD_CTA", pai="C190"),
    reg("F010", "Estabelecimento (bloco F)", "REG CNPJ", campo_cnpj_estab="CNPJ"),
    reg("F100", "Demais documentos e operacoes",
        "REG IND_OPER COD_PART COD_ITEM DT_OPER VL_OPER CST_PIS VL_BC_PIS ALIQ_PIS VL_PIS "
        "CST_COFINS VL_BC_COFINS ALIQ_COFINS VL_COFINS NAT_BC_CRED IND_ORIG_CRED COD_CTA "
        "COD_CCUS DESC_DOC_OPER", pai="F010"),
    reg("M100", "Credito de PIS", _m100("PIS")),
    reg("M105", "Detalhamento das bases do credito de PIS", _m105("PIS"), pai="M100"),
    reg("M200", "Consolidacao da contribuicao de PIS", _M200),
    reg("M210", "Detalhamento da contribuicao de PIS", *_m210("PIS"), pai="M200"),
    reg("M400", "Receitas isentas/aliquota zero/suspensao - PIS",
        "REG CST_PIS VL_TOT_REC COD_CTA DESC_COMPL"),
    reg("M410", "Detalhamento das receitas nao tributadas - PIS",
        "REG NAT_REC VL_REC COD_CTA DESC_COMPL", pai="M400"),
    reg("M500", "Credito de COFINS", _m100("COFINS")),
    reg("M505", "Detalhamento das bases do credito de COFINS", _m105("COFINS"), pai="M500"),
    reg("M600", "Consolidacao da contribuicao de COFINS", _M200),
    reg("M610", "Detalhamento da contribuicao de COFINS", *_m210("COFINS"), pai="M600"),
    reg("M800", "Receitas isentas/aliquota zero/suspensao - COFINS",
        "REG CST_COFINS VL_TOT_REC COD_CTA DESC_COMPL"),
    reg("M810", "Detalhamento das receitas nao tributadas - COFINS",
        "REG NAT_REC VL_REC COD_CTA DESC_COMPL", pai="M800"),
    reg("1100", "Controle de creditos fiscais - PIS", _1100),
    reg("1500", "Controle de creditos fiscais - COFINS", _1100),
    reg("9900", "Registros do arquivo", "REG REG_BLC QTD_REG_BLC"),
    reg("9999", "Encerramento do arquivo", "REG QTD_LIN"),
]}
