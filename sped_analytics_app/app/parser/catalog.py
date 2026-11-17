"""Catálogo para a consulta direta dos arquivos: blocos, descrição dos registros e nomes dos campos.

Os nomes de campos seguem os Guias Práticos da EFD ICMS/IPI e da EFD-Contribuições. Registros fora deste catálogo
(ou campos além do previsto, de versões mais novas do leiaute) são exibidos como CAMPO_02, CAMPO_03...; o conteúdo
mostrado é sempre o do arquivo, e a coluna "Linha original" traz o texto exato.
"""
from __future__ import annotations

from app.parser.layouts import EC as _EC_TARGET
from app.parser.layouts import SF as _SF_TARGET

BLOCOS = {
    "ICMS_IPI": {
        "0": "Abertura, identificação e referências", "B": "Escrituração e apuração do ISS",
        "C": "Documentos fiscais I – mercadorias (ICMS/IPI)", "D": "Documentos fiscais II – serviços (ICMS)",
        "E": "Apuração do ICMS e do IPI", "G": "Controle do crédito de ICMS do ativo permanente (CIAP)",
        "H": "Inventário físico", "K": "Controle da produção e do estoque", "1": "Outras informações",
        "9": "Controle e encerramento do arquivo digital",
    },
    "CONTRIB": {
        "0": "Abertura, identificação e referências", "A": "Documentos fiscais – serviços (ISS)",
        "C": "Documentos fiscais I – mercadorias (ICMS/IPI)", "D": "Documentos fiscais II – serviços (ICMS)",
        "F": "Demais documentos e operações", "I": "Operações das instituições financeiras e assemelhadas",
        "M": "Apuração da contribuição e crédito de PIS/Pasep e Cofins",
        "P": "Apuração da contribuição previdenciária sobre a receita bruta",
        "1": "Complemento da escrituração – controle de saldos de créditos e retenções e outras informações",
        "9": "Controle e encerramento do arquivo digital",
    },
}

_COMUM_DESC = {
    "0000": "Abertura do arquivo digital e identificação da entidade",
    "0005": "Dados complementares da entidade", "0100": "Dados do contabilista",
    "0150": "Tabela de cadastro do participante", "0175": "Alteração da tabela de cadastro de participante",
    "0190": "Identificação das unidades de medida", "0200": "Tabela de identificação do item (produtos e serviços)",
    "0205": "Alteração do item", "0220": "Fatores de conversão de unidades",
    "0400": "Tabela de natureza da operação/prestação",
    "0450": "Tabela de informação complementar do documento fiscal",
    "0460": "Tabela de observações do lançamento fiscal", "0500": "Plano de contas contábeis",
    "9900": "Registros do arquivo", "9999": "Encerramento do arquivo digital",
}

DESCRICOES = {
    "ICMS_IPI": {
        **_COMUM_DESC,
        "0015": "Dados do contribuinte substituto ou responsável pelo ICMS destino",
        "C100": "Nota fiscal (01), avulsa (1B), de produtor (04), NF-e (55) e NFC-e (65)",
        "C101": "Informação complementar – operações interestaduais a consumidor final não contribuinte (EC 87/15)",
        "C110": "Informação complementar da nota fiscal", "C170": "Itens do documento",
        "C190": "Registro analítico do documento", "C191": "Informações do Fundo de Combate à Pobreza (FCP)",
        "C195": "Observações do lançamento fiscal",
        "C197": "Outras obrigações tributárias, ajustes e informações de valores provenientes de documento fiscal",
        "C500": "Nota fiscal/conta de energia elétrica, água e gás", "C590": "Registro analítico do documento",
        "D100": "Conhecimento de transporte e documentos de transporte", "D190": "Registro analítico dos documentos",
        "D500": "Nota fiscal de serviço de comunicação/telecomunicação", "D590": "Registro analítico do documento",
        "D700": "Nota fiscal fatura eletrônica de serviços de comunicação (NFCom)", "D730": "Registro analítico (NFCom)",
        "E100": "Período da apuração do ICMS", "E110": "Apuração do ICMS – operações próprias",
        "E111": "Ajuste/benefício/incentivo da apuração do ICMS",
        "E116": "Obrigações do ICMS recolhido ou a recolher – operações próprias",
        "E200": "Período da apuração do ICMS – substituição tributária",
        "E500": "Período de apuração do IPI", "E510": "Consolidação dos valores do IPI", "E520": "Apuração do IPI",
        "H005": "Totais do inventário", "H010": "Inventário",
    },
    "CONTRIB": {
        **_COMUM_DESC,
        "0110": "Regimes de apuração da contribuição social e de apropriação de crédito",
        "0140": "Tabela de cadastro de estabelecimentos",
        "A010": "Identificação do estabelecimento", "A100": "Documento – nota fiscal de serviço",
        "A170": "Complemento do documento – itens do documento",
        "C010": "Identificação do estabelecimento",
        "C100": "Documento – NF (01), avulsa (1B), de produtor (04), NF-e (55) e NFC-e (65)",
        "C170": "Complemento do documento – itens do documento",
        "C180": "Consolidação de notas fiscais eletrônicas emitidas (vendas)",
        "C190": "Consolidação de notas fiscais eletrônicas – aquisições com direito a crédito e devoluções",
        "C191": "Detalhamento da consolidação – PIS/Pasep", "C195": "Detalhamento da consolidação – Cofins",
        "C500": "Nota fiscal/conta de energia elétrica, água e gás – documentos de entrada/aquisição",
        "C501": "Complemento da operação – PIS/Pasep", "C505": "Complemento da operação – Cofins",
        "D010": "Identificação do estabelecimento", "D100": "Aquisição de serviços de transporte",
        "D101": "Complemento do documento de transporte – PIS/Pasep",
        "D105": "Complemento do documento de transporte – Cofins",
        "D500": "Nota fiscal de serviço de comunicação – aquisição com direito a crédito",
        "D501": "Complemento da operação – PIS/Pasep", "D505": "Complemento da operação – Cofins",
        "F010": "Identificação do estabelecimento",
        "F100": "Demais documentos e operações geradoras de contribuição e créditos",
        "F120": "Bens do ativo imobilizado – créditos com base nos encargos de depreciação e amortização",
        "F130": "Bens do ativo imobilizado – créditos com base no valor de aquisição",
        "M100": "Crédito de PIS/Pasep relativo ao período",
        "M105": "Detalhamento da base de cálculo do crédito apurado no período – PIS/Pasep",
        "M200": "Consolidação da contribuição para o PIS/Pasep do período",
        "M500": "Crédito de Cofins relativo ao período",
        "M505": "Detalhamento da base de cálculo do crédito apurado no período – Cofins",
        "M600": "Consolidação da contribuição para a seguridade social – Cofins do período",
    },
}

_EXTRA_COMUM = {
    "0005": ["REG", "FANTASIA", "CEP", "END", "NUM", "COMPL", "BAIRRO", "FONE", "FAX", "EMAIL"],
    "0100": ["REG", "NOME", "CPF", "CRC", "CNPJ", "CEP", "END", "NUM", "COMPL", "BAIRRO", "FONE", "FAX", "EMAIL",
             "COD_MUN"],
    "0220": ["REG", "UNID_CONV", "FAT_CONV"],
    "0450": ["REG", "COD_INF", "TXT"],
    "0460": ["REG", "COD_OBS", "TXT"],
    "9900": ["REG", "REG_BLC", "QTD_REG_BLC"],
    "9999": ["REG", "QTD_LIN"],
}

_SF_EXTRA = {
    **_EXTRA_COMUM,
    "0015": ["REG", "UF_ST", "IE_ST"],
    "C101": ["REG", "VL_FCP_UF_DEST", "VL_ICMS_UF_DEST", "VL_ICMS_UF_REM"],
    "C110": ["REG", "COD_INF", "TXT_COMPL"],
    "C195": ["REG", "COD_OBS", "TXT_COMPL"],
    "E100": ["REG", "DT_INI", "DT_FIN"],
    "E110": ["REG", "VL_TOT_DEBITOS", "VL_AJ_DEBITOS", "VL_TOT_AJ_DEBITOS", "VL_ESTORNOS_CRED", "VL_TOT_CREDITOS",
             "VL_AJ_CREDITOS", "VL_TOT_AJ_CREDITOS", "VL_ESTORNOS_DEB", "VL_SLD_CREDOR_ANT", "VL_SLD_APURADO",
             "VL_TOT_DED", "VL_ICMS_RECOLHER", "VL_SLD_CREDOR_TRANSPORTAR", "DEB_ESP"],
    "E111": ["REG", "COD_AJ_APUR", "DESCR_COMPL_AJ", "VL_AJ_APUR"],
    "E116": ["REG", "COD_OR", "VL_OR", "DT_VCTO", "COD_REC", "NUM_PROC", "IND_PROC", "PROC", "TXT_COMPL", "MES_REF"],
    "E200": ["REG", "UF", "DT_INI", "DT_FIN"],
    "E500": ["REG", "IND_APUR", "DT_INI", "DT_FIN"],
    "E510": ["REG", "CFOP", "CST_IPI", "VL_CONT_IPI", "VL_BC_IPI", "VL_IPI"],
    "E520": ["REG", "VL_SD_ANT_IPI", "VL_DEB_IPI", "VL_CRED_IPI", "VL_OD_IPI", "VL_OC_IPI", "VL_SC_IPI", "VL_SD_IPI"],
    "H005": ["REG", "DT_INV", "VL_INV", "MOT_INV"],
    "H010": ["REG", "COD_ITEM", "UNID", "QTD", "VL_UNIT", "VL_ITEM", "IND_PROP", "COD_PART", "TXT_COMPL", "COD_CTA",
             "VL_ITEM_IR"],
}

_EC_EXTRA = {
    **_EXTRA_COMUM,
    "0110": ["REG", "COD_INC_TRIB", "IND_APRO_CRED", "COD_TIPO_CONT", "IND_REG_CUM"],
    "0400": ["REG", "COD_NAT", "DESCR_NAT"],
    "M100": ["REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_PIS", "ALIQ_PIS", "QUANT_BC_PIS", "ALIQ_PIS_QUANT", "VL_CRED",
             "VL_AJUS_ACRES", "VL_AJUS_REDUC", "VL_CRED_DIF", "VL_CRED_DISP", "IND_DESC_CRED", "VL_CRED_DESC",
             "SLD_CRED"],
    "M105": ["REG", "NAT_BC_CRED", "CST_PIS", "VL_BC_PIS_TOT", "VL_BC_PIS_CUM", "VL_BC_PIS_NC", "VL_BC_PIS",
             "QUANT_BC_PIS_TOT", "QUANT_BC_PIS", "DESC_CRED"],
    "M200": ["REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC", "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV",
             "VL_RET_NC", "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER", "VL_RET_CUM", "VL_OUT_DED_CUM",
             "VL_CONT_CUM_REC", "VL_TOT_CONT_REC"],
    "M500": ["REG", "COD_CRED", "IND_CRED_ORI", "VL_BC_COFINS", "ALIQ_COFINS", "QUANT_BC_COFINS",
             "ALIQ_COFINS_QUANT", "VL_CRED", "VL_AJUS_ACRES", "VL_AJUS_REDUC", "VL_CRED_DIFER", "VL_CRED_DISP",
             "IND_DESC_CRED", "VL_CRED_DESC", "SLD_CRED"],
    "M505": ["REG", "NAT_BC_CRED", "CST_COFINS", "VL_BC_COFINS_TOT", "VL_BC_COFINS_CUM", "VL_BC_COFINS_NC",
             "VL_BC_COFINS", "QUANT_BC_COFINS_TOT", "QUANT_BC_COFINS", "DESC_CRED"],
    "M600": ["REG", "VL_TOT_CONT_NC_PER", "VL_TOT_CRED_DESC", "VL_TOT_CRED_DESC_ANT", "VL_TOT_CONT_NC_DEV",
             "VL_RET_NC", "VL_OUT_DED_NC", "VL_CONT_NC_REC", "VL_TOT_CONT_CUM_PER", "VL_RET_CUM", "VL_OUT_DED_CUM",
             "VL_CONT_CUM_REC", "VL_TOT_CONT_REC"],
}

LAYOUTS = {"ICMS_IPI": {**_SF_EXTRA, **_SF_TARGET}, "CONTRIB": {**_EC_EXTRA, **_EC_TARGET}}

# Campos de identificação do documento mostrados ao lado dos registros filhos (C170 -> dados do C100 etc.)
DOC_ID_FIELDS = ["IND_OPER", "IND_EMIT", "COD_PART", "COD_MOD", "COD_SIT", "SER", "NUM_DOC", "CHV_NFE", "CHV_CTE",
                 "CHV_DOCE", "CHV_NFSE", "DT_DOC", "DT_E_S", "DT_A_P", "DT_ENT", "DT_EXE_SERV", "DT_INI", "DT_FIN",
                 "COD_CRED", "NAT_BC_CRED"]


def layout(tipo: str, reg: str) -> list[str] | None:
    lay = LAYOUTS[tipo].get(reg)
    if lay:
        return lay
    if reg.endswith("001"):
        return ["REG", "IND_MOV"]
    if reg.endswith("990"):
        return ["REG", f"QTD_LIN_{reg[0]}"]
    return None


def descricao(tipo: str, reg: str) -> str:
    d = DESCRICOES[tipo].get(reg)
    if d:
        return d
    if reg.endswith("001"):
        return f"Abertura do Bloco {reg[0]}"
    if reg.endswith("990"):
        return f"Encerramento do Bloco {reg[0]}"
    return ""


def field_kind(name: str) -> str:
    """money | qty | date | text — usado para tipar a exibição/exportação (o texto original é sempre preservado)."""
    n = name.upper()
    if n.startswith("DT_"):
        return "date"
    if n.startswith(("VL_", "SLD_", "DEB_ESP")) or n in ("VL",):
        return "money"
    if n.startswith(("ALIQ", "QTD", "QUANT", "FAT_CONV")):
        return "qty"
    return "text"
