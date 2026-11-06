"""Dicionario de layout da EFD ICMS/IPI.

Campos conforme o Guia Pratico da EFD ICMS/IPI. ATENCAO: conferir a lista de
campos de cada registro no Guia Pratico da versao indicada no COD_VER do
registro 0000 de cada arquivo (ver DECISOES.md, D-003). Versoes alternativas
("anterior") cobrem layouts antigos com menos campos; a escolha e feita pelo
numero de campos da linha quando o COD_VER nao estiver mapeado.
"""
from __future__ import annotations

from .comum import Registro, VersaoLayout, campos, reg

TIPO = "ICMS_IPI"

_C170_ATUAL = (
    "REG NUM_ITEM COD_ITEM DESCR_COMPL QTD UNID VL_ITEM VL_DESC IND_MOV CST_ICMS CFOP "
    "COD_NAT VL_BC_ICMS ALIQ_ICMS VL_ICMS VL_BC_ICMS_ST ALIQ_ST VL_ICMS_ST IND_APUR "
    "CST_IPI COD_ENQ VL_BC_IPI ALIQ_IPI VL_IPI CST_PIS VL_BC_PIS ALIQ_PIS QUANT_BC_PIS "
    "ALIQ_PIS_QUANT VL_PIS CST_COFINS VL_BC_COFINS ALIQ_COFINS QUANT_BC_COFINS "
    "ALIQ_COFINS_QUANT VL_COFINS COD_CTA VL_ABAT_NT"
)

REGISTROS: dict[str, Registro] = {r.reg: r for r in [
    reg("0000", "Abertura e identificacao",
        "REG COD_VER COD_FIN DT_INI DT_FIN NOME CNPJ CPF UF IE COD_MUN IM SUFRAMA "
        "IND_PERFIL IND_ATIV"),
    reg("0150", "Participantes",
        "REG COD_PART NOME COD_PAIS CNPJ CPF IE COD_MUN SUFRAMA END NUM COMPL BAIRRO"),
    reg("0190", "Unidades de medida", "REG UNID DESCR"),
    reg("0200", "Itens",
        VersaoLayout("atual", campos(
            "REG COD_ITEM DESCR_ITEM COD_BARRA COD_ANT_ITEM UNID_INV TIPO_ITEM COD_NCM "
            "EX_IPI COD_GEN COD_LST ALIQ_ICMS CEST")),
        VersaoLayout("anterior_sem_CEST", campos(
            "REG COD_ITEM DESCR_ITEM COD_BARRA COD_ANT_ITEM UNID_INV TIPO_ITEM COD_NCM "
            "EX_IPI COD_GEN COD_LST ALIQ_ICMS"))),
    reg("C100", "Documento (NF-e)",
        "REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER NUM_DOC CHV_NFE DT_DOC DT_E_S "
        "VL_DOC IND_PGTO VL_DESC VL_ABAT_NT VL_MERC IND_FRT VL_FRT VL_SEG VL_OUT_DA "
        "VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST VL_IPI VL_PIS VL_COFINS VL_PIS_ST "
        "VL_COFINS_ST"),
    reg("C170", "Itens do documento",
        VersaoLayout("atual", campos(_C170_ATUAL),
                     observacao="VL_ABAT_NT ao final: conferir no Guia Pratico"),
        VersaoLayout("anterior_sem_VL_ABAT_NT", campos(_C170_ATUAL)[:-1]),
        pai="C100"),
    reg("C190", "Registro analitico do documento",
        "REG CST_ICMS CFOP ALIQ_ICMS VL_OPR VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST "
        "VL_RED_BC VL_IPI COD_OBS", pai="C100"),
    reg("E100", "Periodo da apuracao do ICMS", "REG DT_INI DT_FIN"),
    reg("E110", "Apuracao do ICMS",
        "REG VL_TOT_DEBITOS VL_AJ_DEBITOS VL_TOT_AJ_DEBITOS VL_ESTORNOS_CRED "
        "VL_TOT_CREDITOS VL_AJ_CREDITOS VL_TOT_AJ_CREDITOS VL_ESTORNOS_DEB "
        "VL_SLD_CREDOR_ANT VL_SLD_APURADO VL_TOT_DED VL_ICMS_RECOLHER "
        "VL_SLD_CREDOR_TRANSPORTAR DEB_ESP", pai="E100"),
    reg("E111", "Ajustes da apuracao do ICMS",
        "REG COD_AJ_APUR DESCR_COMPL_AJ VL_AJ_APUR", pai="E110"),
    reg("E112", "Informacoes adicionais dos ajustes",
        "REG NUM_DA NUM_PROC IND_PROC PROC TXT_COMPL", pai="E111"),
    reg("E113", "Documentos fiscais dos ajustes",
        VersaoLayout("atual", campos(
            "REG COD_PART COD_MOD SER SUB NUM_DOC DT_DOC COD_ITEM VL_AJ_ITEM CHV_DOCe")),
        VersaoLayout("anterior_sem_CHV_DOCe", campos(
            "REG COD_PART COD_MOD SER SUB NUM_DOC DT_DOC COD_ITEM VL_AJ_ITEM")),
        pai="E111"),
    reg("E115", "Informacoes adicionais da apuracao",
        "REG COD_INF_ADIC VL_INF_ADIC DESCR_COMPL_AJ", pai="E110"),
    reg("E116", "Obrigacoes do ICMS a recolher",
        VersaoLayout("atual", campos(
            "REG COD_OR VL_OR DT_VCTO COD_REC NUM_PROC IND_PROC PROC TXT_COMPL MES_REF")),
        VersaoLayout("anterior_sem_MES_REF", campos(
            "REG COD_OR VL_OR DT_VCTO COD_REC NUM_PROC IND_PROC PROC TXT_COMPL")),
        pai="E110"),
    reg("E500", "Periodo de apuracao do IPI", "REG IND_APUR DT_INI DT_FIN"),
    reg("E510", "Consolidacao dos valores do IPI",
        "REG CFOP CST_IPI VL_CONT_IPI VL_BC_IPI VL_IPI", pai="E500"),
    reg("E520", "Apuracao do IPI",
        "REG VL_SD_ANT_IPI VL_DEB_IPI VL_CRED_IPI VL_OD_IPI VL_OC_IPI VL_SC_IPI VL_SD_IPI",
        pai="E500"),
    reg("E530", "Ajustes da apuracao do IPI",
        "REG IND_AJ VL_AJ COD_AJ IND_DOC NUM_DOC DESCR_AJ", pai="E520"),
    reg("H005", "Totais do inventario", "REG DT_INV VL_INV MOT_INV"),
    reg("H010", "Inventario",
        "REG COD_ITEM UNID QTD VL_UNIT VL_ITEM IND_PROP COD_PART TXT_COMPL COD_CTA VL_ITEM_IR",
        pai="H005"),
    reg("9900", "Registros do arquivo", "REG REG_BLC QTD_REG_BLC"),
    reg("9999", "Encerramento do arquivo", "REG QTD_LIN"),
]}
