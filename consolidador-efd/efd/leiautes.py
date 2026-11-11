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
