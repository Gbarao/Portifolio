"""Tabelas de códigos da EFD-Contribuições usadas para descrever os valores do Bloco M.

Só constam descrições conferidas com as tabelas oficiais (4.3.3, 4.3.6, 4.3.7 do Guia Prático); para códigos fora
daqui a tela mostra apenas o código, com a indicação da tabela.
"""
from __future__ import annotations

# Tabela 4.3.3 — Código da Situação Tributária (CST) do PIS/Pasep e da Cofins
CST_PIS_COFINS = {
    "01": "Operação tributável com alíquota básica",
    "02": "Operação tributável com alíquota diferenciada",
    "03": "Operação tributável com alíquota por unidade de medida de produto",
    "04": "Operação tributável monofásica – revenda a alíquota zero",
    "05": "Operação tributável por substituição tributária",
    "06": "Operação tributável a alíquota zero",
    "07": "Operação isenta da contribuição",
    "08": "Operação sem incidência da contribuição",
    "09": "Operação com suspensão da contribuição",
    "49": "Outras operações de saída",
    "50": "Crédito – vinculada exclusivamente a receita tributada no mercado interno",
    "51": "Crédito – vinculada exclusivamente a receita não tributada no mercado interno",
    "52": "Crédito – vinculada exclusivamente a receita de exportação",
    "53": "Crédito – vinculada a receitas tributadas e não tributadas no mercado interno",
    "54": "Crédito – vinculada a receitas tributadas no mercado interno e de exportação",
    "55": "Crédito – vinculada a receitas não tributadas no mercado interno e de exportação",
    "56": "Crédito – vinculada a receitas tributadas e não tributadas no mercado interno e de exportação",
    "60": "Crédito presumido – vinculada exclusivamente a receita tributada no mercado interno",
    "61": "Crédito presumido – vinculada exclusivamente a receita não tributada no mercado interno",
    "62": "Crédito presumido – vinculada exclusivamente a receita de exportação",
    "63": "Crédito presumido – vinculada a receitas tributadas e não tributadas no mercado interno",
    "64": "Crédito presumido – vinculada a receitas tributadas no mercado interno e de exportação",
    "65": "Crédito presumido – vinculada a receitas não tributadas no mercado interno e de exportação",
    "66": "Crédito presumido – vinculada a receitas tributadas e não tributadas no mercado interno e de exportação",
    "67": "Crédito presumido – outras operações",
    "70": "Aquisição sem direito a crédito",
    "71": "Aquisição com isenção",
    "72": "Aquisição com suspensão",
    "73": "Aquisição a alíquota zero",
    "74": "Aquisição sem incidência da contribuição",
    "75": "Aquisição por substituição tributária",
    "98": "Outras operações de entrada",
    "99": "Outras operações",
}

# CSTs de crédito vinculados a mais de um tipo de receita: a base total (VL_BC_*_TOT do M105/M505) se repete em cada
# tipo de crédito (COD_CRED 1xx/2xx/3xx) para o qual é rateada.
CST_RATEIO = {"53", "54", "55", "56", "63", "64", "65", "66"}

# Tabela 4.3.7 — Base de cálculo do crédito (NAT_BC_CRED)
NAT_BC_CRED = {
    "01": "Aquisição de bens para revenda",
    "02": "Aquisição de bens utilizados como insumo",
    "03": "Aquisição de serviços utilizados como insumo",
    "04": "Energia elétrica e térmica, inclusive sob a forma de vapor",
    "05": "Aluguéis de prédios",
    "06": "Aluguéis de máquinas e equipamentos",
    "07": "Armazenagem de mercadoria e frete na operação de venda",
    "08": "Contraprestações de arrendamento mercantil",
    "09": "Máquinas, equipamentos e outros bens do ativo imobilizado (encargos de depreciação)",
    "10": "Máquinas, equipamentos e outros bens do ativo imobilizado (valor de aquisição)",
    "11": "Amortização e depreciação de edificações e benfeitorias em imóveis",
    "12": "Devolução de vendas sujeitas à incidência não cumulativa",
    "13": "Outras operações com direito a crédito",
    "14": "Atividade de transporte de cargas – subcontratação",
    "15": "Atividade imobiliária – custo incorrido de unidade imobiliária",
    "16": "Atividade imobiliária – custo orçado de unidade não concluída",
    "17": "Prestação de serviços de limpeza, conservação e manutenção – vale-transporte, vale-refeição ou "
          "vale-alimentação, fardamento ou uniforme",
    "18": "Estoque de abertura de bens",
}

# Tabela 4.3.6 — Código de tipo de crédito (COD_CRED): 1º dígito = receita a que se vincula; 2 últimos = tipo
COD_CRED_GRUPO = {
    "1": "vinculado à receita tributada no mercado interno",
    "2": "vinculado à receita não tributada no mercado interno",
    "3": "vinculado à receita de exportação",
}
COD_CRED_TIPO = {
    "01": "Alíquota básica",
    "02": "Alíquotas diferenciadas",
    "03": "Alíquota por unidade de produto",
    "04": "Estoque de abertura",
    "05": "Aquisição de embalagens para revenda",
    "06": "Presumido da agroindústria",
    "07": "Outros créditos presumidos",
    "08": "Importação",
    "09": "Atividade imobiliária",
    "99": "Outros",
}

# Tabela 4.3.5 — Código de contribuição social apurada (COD_CONT): somente os códigos mais usuais
COD_CONT = {
    "01": "Não cumulativa – alíquota básica",
    "02": "Não cumulativa – alíquotas diferenciadas",
    "03": "Não cumulativa – alíquota por unidade de medida de produto",
    "51": "Cumulativa – alíquota básica",
    "52": "Cumulativa – alíquotas diferenciadas",
    "53": "Cumulativa – alíquota por unidade de medida de produto",
}

# Códigos de receita (DARF) mais usuais informados no M205/M605 (4 primeiros dígitos)
COD_REC = {
    "6912": "PIS/Pasep não cumulativo",
    "8109": "PIS/Pasep cumulativo",
    "5856": "Cofins não cumulativa",
    "2172": "Cofins cumulativa",
}

IND_AJ = {"0": "Redução", "1": "Acréscimo"}
IND_CRED_ORI = {"0": "Operações próprias", "1": "Evento de incorporação, cisão ou fusão"}


def cst_desc(c: str | None) -> str:
    return CST_PIS_COFINS.get(str(c or ""), "") if c else ""


def nat_desc(n: str | None) -> str:
    return NAT_BC_CRED.get(str(n or ""), "") if n else ""


def cod_cred_desc(c: str | None) -> str:
    c = str(c or "")
    if len(c) != 3:
        return ""
    tipo = COD_CRED_TIPO.get(c[1:])
    grupo = COD_CRED_GRUPO.get(c[0])
    if not tipo or not grupo:
        return ""
    return f"{tipo} – {grupo}"


def cod_cont_desc(c: str | None) -> str:
    c = str(c or "")
    return COD_CONT.get(c, f"Código {c} (Tabela 4.3.5)" if c else "")


def cod_rec_desc(c: str | None) -> str:
    return COD_REC.get(str(c or "")[:4], "")
