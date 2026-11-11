# -*- coding: utf-8 -*-
"""
Definições compartilhadas: colunas da base, rótulos de origem e registros tratados.

IMPORTANTE (procedência dos leiautes)
-------------------------------------
As posições de campo usadas em `leitor.py` seguem os leiautes da EFD ICMS/IPI
e da EFD-Contribuições. Como salvaguarda, a aplicação NÃO confia cegamente
nessas posições: a cada carga ela confere o resultado contra redundâncias do
próprio arquivo (registro 9900, totais do cabeçalho do documento, registro
analítico C190 e formato dos campos-chave). Se um campo estiver deslocado em
relação ao arquivo real, essas conferências acusam.
"""

FISCAL = "FISCAL"
CONTRIB = "CONTRIB"

NOME_FONTE = {FISCAL: "EFD Fiscal (ICMS/IPI)", CONTRIB: "EFD Contribuições"}

# COD_SIT de documentos sem valor fiscal: 02 cancelado, 03 cancelado
# extemporâneo, 04 denegado, 05 numeração inutilizada.
SIT_IGNORAR = frozenset(("02", "03", "04", "05"))

# ----------------------------------------------------------------------------
# Colunas dos arquivos intermediários (Parquet). Valores monetários são
# gravados em CENTAVOS (inteiro) para que nenhuma soma dependa de ponto
# flutuante; quantidades e alíquotas são inteiros escalados (sufixo _eN).
# ----------------------------------------------------------------------------
TEXTO_ITENS = [
    "fonte", "registro", "empresa_raiz", "estab_cnpj", "periodo",
    "cod_mod", "cod_sit", "ser", "sub", "num_doc", "chave", "dt_doc", "dt_e_s",
    "part_cod", "part_doc", "part_nome", "doc_id",
    "num_item", "cod_item", "descr_item", "ncm", "cfop", "cst_icms", "unid",
    "cst_pis", "cst_cofins", "nat_bc_cred", "cod_cta",
]
INTEIRO_ITENS = ["linha", "linha_doc", "qtd_e5", "aliq_icms_e2", "aliq_pis_e4",
                 "aliq_cofins_e4"]
MEDIDAS = [
    "vl_item", "vl_opr", "vl_desc", "vl_bc_icms", "vl_icms", "vl_bc_icms_st",
    "vl_icms_st", "vl_red_bc", "vl_ipi", "vl_bc_pis", "vl_pis", "vl_bc_cofins",
    "vl_cofins", "vl_iss",
]
COLUNAS_ITENS = TEXTO_ITENS + INTEIRO_ITENS + MEDIDAS

TEXTO_DOCS = [
    "fonte", "registro", "empresa_raiz", "estab_cnpj", "periodo",
    "cod_mod", "cod_sit", "ser", "sub", "num_doc", "chave", "dt_doc", "dt_e_s",
    "part_cod", "part_doc", "part_nome", "doc_id",
]
INTEIRO_DOCS = ["linha_doc", "n_itens"]
MEDIDAS_DOCS = ["vl_doc", "vl_bc_icms", "vl_icms", "vl_bc_icms_st", "vl_icms_st",
                "vl_ipi", "vl_pis", "vl_cofins", "vl_iss"]
COLUNAS_DOCS = TEXTO_DOCS + INTEIRO_DOCS + MEDIDAS_DOCS

TEXTO_ANA = ["registro", "cst_icms", "cfop"]
INTEIRO_ANA = ["linha", "linha_doc", "aliq_icms_e2"]
MEDIDAS_ANA = ["vl_opr", "vl_bc_icms", "vl_icms", "vl_bc_icms_st", "vl_icms_st",
               "vl_red_bc", "vl_ipi"]
COLUNAS_ANA = TEXTO_ANA + INTEIRO_ANA + MEDIDAS_ANA

# ----------------------------------------------------------------------------
# Registros lidos em cada escrituração (os demais são apenas contados).
# ----------------------------------------------------------------------------
TRATADOS = {
    FISCAL: ("0000", "0150", "0200", "C100", "C170", "C190", "C500", "C590",
             "D100", "D190", "D500", "D590", "9900"),
    CONTRIB: ("0000", "0140", "0150", "0200", "A010", "A100", "A170", "C010",
              "C100", "C170", "C190", "C191", "C195", "C500", "C501", "C505",
              "D010", "D100", "D101", "D105", "D500", "D501", "D505", "F010",
              "F100", "9900"),
}

# Registros que podem conter valores de entradas/créditos e que esta versão
# NÃO consolida. Quando aparecem no arquivo, a aba de auditoria avisa.
ATENCAO = {
    FISCAL: {
        "D700": "NFCom (modelo 62)",
        "C800": "CF-e-SAT",
        "G125": "CIAP - crédito de ICMS do ativo imobilizado",
        "1600": "Operações com instrumentos de pagamento",
    },
    CONTRIB: {
        "C395": "NF de venda a consumidor - aquisições com crédito",
        "C396": "Itens do C395",
        "F120": "Créditos sobre encargos de depreciação/amortização",
        "F130": "Créditos sobre o valor de aquisição do imobilizado",
        "F150": "Crédito presumido sobre estoque de abertura",
        "D350": "Resumo diário de cupom fiscal - transporte",
    },
}

# ----------------------------------------------------------------------------
# Rótulos de origem: toda coluna exibida/exportada diz de onde veio.
# ----------------------------------------------------------------------------
ROTULO_MEDIDA = {
    "vl_item": {
        FISCAL: "VL_ITEM (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_ITEM (Reg. C170/A170/C501/D101/D501/C191) e VL_OPER (Reg. F100) · EFD Contribuições",
    },
    "vl_opr": {
        FISCAL: "VL_OPR (Reg. C190 de documento sem C170, C590, D190, D590 · EFD Fiscal)",
    },
    "vl_desc": {
        FISCAL: "VL_DESC (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_DESC (Reg. C170/A170/C191 · EFD Contribuições)",
    },
    "vl_bc_icms": {
        FISCAL: "VL_BC_ICMS (Reg. C170/C190/C590/D190/D590 · EFD Fiscal)",
        CONTRIB: "VL_BC_ICMS (Reg. C170 · EFD Contribuições)",
    },
    "vl_icms": {
        FISCAL: "VL_ICMS (Reg. C170/C190/C590/D190/D590 · EFD Fiscal)",
        CONTRIB: "VL_ICMS (Reg. C170 · EFD Contribuições)",
    },
    "vl_bc_icms_st": {
        FISCAL: "VL_BC_ICMS_ST (Reg. C170/C190/C590 · EFD Fiscal)",
        CONTRIB: "VL_BC_ICMS_ST (Reg. C170 · EFD Contribuições)",
    },
    "vl_icms_st": {
        FISCAL: "VL_ICMS_ST (Reg. C170/C190/C590 · EFD Fiscal)",
        CONTRIB: "VL_ICMS_ST (Reg. C170 · EFD Contribuições)",
    },
    "vl_red_bc": {
        FISCAL: "VL_RED_BC (Reg. C190/C590/D190/D590 · EFD Fiscal)",
    },
    "vl_ipi": {
        FISCAL: "VL_IPI (Reg. C170/C190 · EFD Fiscal)",
        CONTRIB: "VL_IPI (Reg. C170 · EFD Contribuições)",
    },
    "vl_bc_pis": {
        FISCAL: "VL_BC_PIS (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_BC_PIS (Reg. C170/A170/C501/D101/D501/C191/F100 · EFD Contribuições)",
    },
    "vl_pis": {
        FISCAL: "VL_PIS (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_PIS (Reg. C170/A170/C501/D101/D501/C191/F100 · EFD Contribuições)",
    },
    "vl_bc_cofins": {
        FISCAL: "VL_BC_COFINS (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_BC_COFINS (Reg. C170/A170/C505/D105/D505/C195/F100 · EFD Contribuições)",
    },
    "vl_cofins": {
        FISCAL: "VL_COFINS (Reg. C170 · EFD Fiscal)",
        CONTRIB: "VL_COFINS (Reg. C170/A170/C505/D105/D505/C195/F100 · EFD Contribuições)",
    },
    "vl_iss": {
        CONTRIB: "VL_ISS (Reg. A100, distribuído entre os A170 na proporção do VL_ITEM · EFD Contribuições)",
    },
}

SUFIXO_FONTE = {FISCAL: "fiscal", CONTRIB: "contrib"}

# Medidas exibidas por padrão na visão consolidada: (medida, fonte)
MEDIDAS_PADRAO = [
    ("vl_item", FISCAL), ("vl_opr", FISCAL), ("vl_bc_icms", FISCAL),
    ("vl_icms", FISCAL), ("vl_icms_st", FISCAL), ("vl_ipi", FISCAL),
    ("vl_item", CONTRIB), ("vl_bc_pis", CONTRIB), ("vl_pis", CONTRIB),
    ("vl_bc_cofins", CONTRIB), ("vl_cofins", CONTRIB),
]

ROTULO_PAREAMENTO = {
    "AMBAS": "Documento nas duas escriturações",
    "SO_FISCAL": "Só na EFD Fiscal",
    "SO_CONTRIB": "Só na EFD Contribuições",
    "SEM_CONTRAPARTE": "A outra EFD deste período não foi carregada",
    "NAO_SE_APLICA": "Registro sem documento na EFD Fiscal (serviços, F100, consolidado)",
}


# ----------------------------------------------------------------------------
# Nomes dos campos de cada registro, na ordem do leiaute (campo 1 = REG).
# Usados para exibir as linhas do TXT campo a campo e comparar as duas EFDs.
# ----------------------------------------------------------------------------
C100 = ("REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER NUM_DOC CHV_NFE DT_DOC "
        "DT_E_S VL_DOC IND_PGTO VL_DESC VL_ABAT_NT VL_MERC IND_FRT VL_FRT VL_SEG "
        "VL_OUT_DA VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST VL_IPI VL_PIS "
        "VL_COFINS VL_PIS_ST VL_COFINS_ST")
C170 = ("REG NUM_ITEM COD_ITEM DESCR_COMPL QTD UNID VL_ITEM VL_DESC IND_MOV CST_ICMS "
        "CFOP COD_NAT VL_BC_ICMS ALIQ_ICMS VL_ICMS VL_BC_ICMS_ST ALIQ_ST VL_ICMS_ST "
        "IND_APUR CST_IPI COD_ENQ VL_BC_IPI ALIQ_IPI VL_IPI CST_PIS VL_BC_PIS "
        "ALIQ_PIS QUANT_BC_PIS ALIQ_PIS_QUANT VL_PIS CST_COFINS VL_BC_COFINS "
        "ALIQ_COFINS QUANT_BC_COFINS ALIQ_COFINS_QUANT VL_COFINS COD_CTA")
P0150 = "REG COD_PART NOME COD_PAIS CNPJ CPF IE COD_MUN SUFRAMA END NUM COMPL BAIRRO"
P0200 = ("REG COD_ITEM DESCR_ITEM COD_BARRA COD_ANT_ITEM UNID_INV TIPO_ITEM COD_NCM "
         "EX_IPI COD_GEN COD_LST ALIQ_ICMS")
D100 = ("REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER SUB NUM_DOC CHV_CTE DT_DOC "
        "DT_A_P TP_CT-e CHV_CTE_REF VL_DOC VL_DESC IND_FRT VL_SERV VL_BC_ICMS VL_ICMS "
        "VL_NT COD_INF COD_CTA")
D500 = ("REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER SUB NUM_DOC DT_DOC DT_A_P "
        "VL_DOC VL_DESC VL_SERV VL_SERV_NT VL_TERC VL_DA VL_BC_ICMS VL_ICMS COD_INF "
        "VL_PIS VL_COFINS")

_NOMES = {
    FISCAL: {  # EFD ICMS/IPI
        "0000": "REG COD_VER COD_FIN DT_INI DT_FIN NOME CNPJ CPF UF IE COD_MUN IM SUFRAMA IND_PERFIL IND_ATIV",
        "0001": "REG IND_MOV", "0150": P0150, "0190": "REG UNID DESCR",
        "0200": P0200 + " CEST", "0990": "REG QTD_LIN_0",
        "C001": "REG IND_MOV", "C100": C100, "C170": C170 + " VL_ABAT_NT",
        "C190": "REG CST_ICMS CFOP ALIQ_ICMS VL_OPR VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST VL_RED_BC VL_IPI COD_OBS",
        "C500": ("REG IND_OPER IND_EMIT COD_PART COD_MOD COD_SIT SER SUB COD_CONS NUM_DOC "
                 "DT_DOC DT_E_S VL_DOC VL_DESC VL_FORN VL_SERV_NT VL_TERC VL_DA VL_BC_ICMS "
                 "VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST COD_INF VL_PIS VL_COFINS TP_LIGACAO "
                 "COD_GRUPO_TENSAO CHV_DOCe FIN_DOCe CHV_DOCe_REF IND_DEST COD_MUN_DEST "
                 "COD_CTA COD_MOD_DOC_REF HASH_DOC_REF SER_DOC_REF NUM_DOC_REF MES_DOC_REF "
                 "ENER_INJET OUTRAS_DED"),
        "C590": "REG CST_ICMS CFOP ALIQ_ICMS VL_OPR VL_BC_ICMS VL_ICMS VL_BC_ICMS_ST VL_ICMS_ST VL_RED_BC COD_OBS",
        "C990": "REG QTD_LIN_C",
        "D001": "REG IND_MOV", "D100": D100 + " COD_MUN_ORIG COD_MUN_DEST",
        "D190": "REG CST_ICMS CFOP ALIQ_ICMS VL_OPR VL_BC_ICMS VL_ICMS VL_RED_BC COD_OBS",
        "D500": D500 + " COD_CTA TP_ASSINANTE",
        "D590": "REG CST_ICMS CFOP ALIQ_ICMS VL_OPR VL_BC_ICMS VL_ICMS VL_BC_ICMS_UF VL_ICMS_UF VL_RED_BC COD_OBS",
        "D990": "REG QTD_LIN_D",
        "9001": "REG IND_MOV", "9900": "REG REG_BLC QTD_REG_BLC",
        "9990": "REG QTD_LIN_9", "9999": "REG QTD_LIN",
    },
    CONTRIB: {  # EFD-Contribuições
        "0000": "REG COD_VER TIPO_ESCRIT IND_SIT_ESP NUM_REC_ANTERIOR DT_INI DT_FIN NOME CNPJ UF COD_MUN SUFRAMA IND_NAT_PJ IND_ATIV",
        "0001": "REG IND_MOV", "0110": "REG COD_INC_TRIB IND_APRO_CRED COD_TIPO_CONT IND_REG_CUM",
        "0140": "REG COD_EST NOME CNPJ UF IE COD_MUN IM SUFRAMA",
        "0150": P0150, "0190": "REG UNID DESCR", "0200": P0200, "0990": "REG QTD_LIN_0",
        "A001": "REG IND_MOV", "A010": "REG CNPJ",
        "A100": ("REG IND_OPER IND_EMIT COD_PART COD_SIT SER SUB NUM_DOC CHV_NFSE DT_DOC "
                 "DT_EXE_SERV VL_DOC IND_PGTO VL_DESC VL_BC_PIS VL_PIS VL_BC_COFINS "
                 "VL_COFINS VL_PIS_RET VL_COFINS_RET VL_ISS"),
        "A170": ("REG NUM_ITEM COD_ITEM DESCR_COMPL VL_ITEM VL_DESC NAT_BC_CRED IND_ORIG_CRED "
                 "CST_PIS VL_BC_PIS ALIQ_PIS VL_PIS CST_COFINS VL_BC_COFINS ALIQ_COFINS "
                 "VL_COFINS COD_CTA COD_CCUS"),
        "A990": "REG QTD_LIN_A",
        "C001": "REG IND_MOV", "C010": "REG CNPJ IND_ESCRI", "C100": C100, "C170": C170,
        "C190": "REG COD_MOD DT_REF_INI DT_REF_FIN COD_ITEM COD_NCM EX_IPI VL_TOT_ITEM",
        "C191": "REG CNPJ_CPF_PART CST_PIS CFOP VL_ITEM VL_DESC VL_BC_PIS ALIQ_PIS QUANT_BC_PIS ALIQ_PIS_QUANT VL_PIS COD_CTA",
        "C195": "REG CNPJ_CPF_PART CST_COFINS CFOP VL_ITEM VL_DESC VL_BC_COFINS ALIQ_COFINS QUANT_BC_COFINS ALIQ_COFINS_QUANT VL_COFINS COD_CTA",
        "C500": "REG COD_PART COD_MOD COD_SIT SER SUB NUM_DOC DT_DOC DT_ENT VL_DOC VL_ICMS COD_INF VL_PIS VL_COFINS CHV_DOCe",
        "C501": "REG CST_PIS VL_ITEM NAT_BC_CRED VL_BC_PIS ALIQ_PIS VL_PIS COD_CTA",
        "C505": "REG CST_COFINS VL_ITEM NAT_BC_CRED VL_BC_COFINS ALIQ_COFINS VL_COFINS COD_CTA",
        "C990": "REG QTD_LIN_C",
        "D001": "REG IND_MOV", "D010": "REG CNPJ", "D100": D100,
        "D101": "REG IND_NAT_FRT VL_ITEM CST_PIS NAT_BC_CRED VL_BC_PIS ALIQ_PIS VL_PIS COD_CTA",
        "D105": "REG IND_NAT_FRT VL_ITEM CST_COFINS NAT_BC_CRED VL_BC_COFINS ALIQ_COFINS VL_COFINS COD_CTA",
        "D500": D500,
        "D501": "REG CST_PIS VL_ITEM NAT_BC_CRED VL_BC_PIS ALIQ_PIS VL_PIS COD_CTA",
        "D505": "REG CST_COFINS VL_ITEM NAT_BC_CRED VL_BC_COFINS ALIQ_COFINS VL_COFINS COD_CTA",
        "D990": "REG QTD_LIN_D",
        "F001": "REG IND_MOV", "F010": "REG CNPJ",
        "F100": ("REG IND_OPER COD_PART COD_ITEM DT_OPER VL_OPER CST_PIS VL_BC_PIS ALIQ_PIS "
                 "VL_PIS CST_COFINS VL_BC_COFINS ALIQ_COFINS VL_COFINS NAT_BC_CRED "
                 "IND_ORIG_CRED COD_CTA COD_CCUS DESC_DOC_OPER"),
        "F990": "REG QTD_LIN_F",
        "9001": "REG IND_MOV", "9900": "REG REG_BLC QTD_REG_BLC",
        "9990": "REG QTD_LIN_9", "9999": "REG QTD_LIN",
    },
}
NOMES_CAMPOS = {t: {r: c.split() for r, c in regs.items()} for t, regs in _NOMES.items()}


def campos_da_linha(fonte: str, texto: str) -> list[tuple[str, str]]:
    """[(nome do campo, valor)] de uma linha do TXT. Campos além do leiaute
    conhecido aparecem como CAMPO_n."""
    partes = texto.split("|")[1:-1] if texto.endswith("|") else texto.split("|")[1:]
    nomes = NOMES_CAMPOS.get(fonte, {}).get(partes[0] if partes else "", [])
    return [(nomes[i] if i < len(nomes) else f"CAMPO_{i + 1}", v) for i, v in enumerate(partes)]
