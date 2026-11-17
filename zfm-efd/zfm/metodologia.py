"""Metodologia: o que cada cenario cruza, de onde vem cada dado e o que cada conferencia compara.

O texto do tratamento To Be e das conferencias e montado a partir das tabelas de parametros em
uso (param_regras_cenario, param_conferencia_cenario, param_premissas): muda quando os
parametros mudam. Os criterios de classificacao descrevem a visao v_cenarios (zfm/visoes.py).
"""
from __future__ import annotations

import pandas as pd

from . import params

# ---------------------------------------------------------------------------
# Fontes comuns
# ---------------------------------------------------------------------------
F_ENTRADA = ("EFD ICMS/IPI do estabelecimento: C100 (IND_OPER = 0; COD_SIT 02–05 fora) + C170 (CFOP, COD_ITEM, "
             "VL_ITEM − VL_DESC, CST, ICMS, IPI, PIS, COFINS). Documento sem C170: C190 (VL_OPR − IPI − ST). "
             "Fornecedor: 0150 do mesmo arquivo (CNPJ, UF pelo COD_MUN, COD_PAIS, SUFRAMA, IE).")
F_SAIDA = ("Produto e receita: EFD Contribuições — C170 (detalhada) ou C180 + C181/C185 (consolidada): COD_ITEM, "
           "CFOP, VL_ITEM − VL_DESC, CST/alíquota/valor de PIS e COFINS. Destino: C190 + 0150 da EFD ICMS/IPI do "
           "mesmo estabelecimento, mês e CFOP (destinatário exato pelo COD_PART na detalhada; rateado pela "
           "proporção do C190 na consolidada). Produto: 0200 + Parâmetros > Produtos (incentivado, TIPI, tipo de bem).")
F_TIPO = "Tipo ZFM e regime do estabelecimento do grupo: Parâmetros > Empresas ZFM (CNPJ do estabelecimento)."
F_TIPO_PART = ("Tipo ZFM do participante: Parâmetros > Empresas ZFM (CNPJ); sem linha, automático = habilitado "
               "se AM + município da ZFM (Parâmetros > Municípios ZFM) + CNPJ + SUFRAMA no 0150.")
F_SERV = "EFD Contribuições: A100/A170 (IND_OPER = 0) e F100 (IND_OPER = 0) dos estabelecimentos do AM."

AS_IS_ENT = ("Crédito escriturado na própria operação (valor negativo): ICMS e IPI do C170/C190; PIS/COFINS só "
             "com CST 50 a 66.")
AS_IS_SAI = ("Débito escriturado na própria operação: ICMS, IPI, PIS e COFINS do item (ICMS estimado pela proporção "
             "do C190 quando a Contribuições não traz o ICMS do item).")
AS_IS_C4 = (AS_IS_SAI + " Crédito estímulo e fundos do ICMS (E111/E116 classificados em Parâmetros > Códigos de "
            "ajuste) são distribuídos entre as vendas C4 pela proporção do ICMS debitado.")

#              cenario, criterio, fontes, as_is, cruzamentos
_CENARIOS = [
    ("C1a", "Entrada de compra com CFOP 3xxx ou fornecedor no exterior (0150 COD_PAIS ≠ 1058); estabelecimento "
            "= indústria incentivada.", F_ENTRADA + " " + F_TIPO, AS_IS_ENT, "Q3, Q4, Q14, R4/Q7, Q15, conferências"),
    ("C1b", "Importação (como C1a); estabelecimento habilitado; CFOP de compra para revenda e premissa "
            "'revenda_presencial' = sim.", F_ENTRADA + " " + F_TIPO, AS_IS_ENT, "Q3, Q4, Q14, R4/Q7, conferências"),
    ("C1c", "Importação (como C1a); estabelecimento habilitado; demais finalidades.", F_ENTRADA + " " + F_TIPO,
     AS_IS_ENT, "Q3, Q4, Q14, R4/Q7, conferências"),
    ("C2a", "Entrada de compra com CFOP 2xxx de fornecedor com UF ≠ AM; estabelecimento = indústria incentivada. "
            "Origem Sul/Sudeste exceto ES define o percentual do art. 447.", F_ENTRADA + " " + F_TIPO, AS_IS_ENT,
     "Q3, Q4, Q14, R4/Q7, Q15, conferências; alerta de comprovação de ingresso"),
    ("C2b", "Como C2a; estabelecimento habilitado do regime regular.", F_ENTRADA + " " + F_TIPO, AS_IS_ENT,
     "Q3, Q4, Q14, R4/Q7, conferências; alerta de comprovação de ingresso"),
    ("C2c", "Como C2a; estabelecimento habilitado do Simples (regime em Empresas ZFM).", F_ENTRADA + " " + F_TIPO,
     AS_IS_ENT, "Q3, Q4, Q14, R4/Q7, conferências"),
    ("C3a", "Entrada de compra com CFOP 1xxx de fornecedor indústria incentivada da ZFM; estabelecimento = indústria "
            "incentivada; bem intermediário (Produtos > tipo_bem) ou, com 'c3a_intermediario' = "
            "compra_industrializacao, CFOP de compra para industrialização.",
     F_ENTRADA + " " + F_TIPO + " " + F_TIPO_PART, AS_IS_ENT, "Q3, Q4, Q14, R4/Q7, conferências"),
    ("C3b", "Entrada de compra com CFOP 1xxx de fornecedor habilitado ou indústria da ZFM, nos demais casos.",
     F_ENTRADA + " " + F_TIPO_PART, AS_IS_ENT, "Q3, Q4, Q14, R4/Q7"),
    ("C4a", "Venda (CFOP de receita) de produção própria (categoria venda_producao) de produto incentivado, por "
            "estabelecimento indústria incentivada, para fora da ZFM (interna fora da ZFM ou interestadual), "
            "destinatário contribuinte (CNPJ + IE no 0150).", F_SAIDA + " " + F_TIPO, AS_IS_C4,
     "R3/Q8, R4/Q7, Q13, Q15, R5, conferências (PIS 0,65/1,3; COFINS 3/6; CST IPI 52)"),
    ("C4b", "Como C4a, destinatário não contribuinte ou consumidor final.", F_SAIDA + " " + F_TIPO, AS_IS_C4,
     "R3/Q8, R4/Q7, Q13, Q15, R5, conferências"),
    ("C4c", "Venda de produto incentivado para destinatário na ZFM (AM + município da ZFM + SUFRAMA), exceto C4d.",
     F_SAIDA + " " + F_TIPO + " " + F_TIPO_PART, AS_IS_C4, "R3/Q8, R4/Q7, Q13, Q15, R5, conferências"),
    ("C4d", "Venda para a ZFM de produto intermediário (tipo_bem) a destinatário indústria incentivada.",
     F_SAIDA + " " + F_TIPO + " " + F_TIPO_PART, AS_IS_C4, "R3/Q8, R4/Q7, Q15, R5, conferências"),
    ("EXP", "Venda com CFOP 7xxx ou destinatário no exterior. Fora do escopo: fica na base sem débito.", F_SAIDA,
     AS_IS_SAI, "R3/Q8"),
    ("TR", "Transferência entre estabelecimentos (CFOP com categoria 'transferencia' em Parâmetros > CFOPs). Tratada "
           "à parte (premissa 'transferencias_na_base_cbs_ibs').", F_SAIDA + " " + F_ENTRADA, AS_IS_SAI,
     "Q16 não acusa: a mesma NF-e é saída num estabelecimento e entrada no outro"),
    ("REM", "Remessas, retornos e outras operações sem receita (saída com 'eh_receita' = não) ou entrada cuja "
            "finalidade do CFOP não é compra.", F_SAIDA + " " + F_ENTRADA, "Escriturado na operação (normalmente zero).",
     "Parâmetros > CFOPs"),
    ("SRV", "Serviços tomados (A100/A170 e F100 de entrada).", F_SERV, "Crédito de PIS/COFINS na apuração.",
     "R3/Q8"),
    ("NC_S", "Saída de receita que não se encaixa: revenda, produto não incentivado ou estabelecimento que não é "
             "indústria incentivada. O motivo aparece na tela.", F_SAIDA, AS_IS_SAI, "Alertas > Não classificado"),
    ("NC_E", "Entrada de compra que não se encaixa: estabelecimento sem tipo ZFM, fornecedor do AM fora da ZFM ou "
             "sem SUFRAMA, CFOP 2xxx com fornecedor do AM.", F_ENTRADA, AS_IS_ENT, "Alertas > Não classificado"),
]

C5 = ("C5", "IPI por produto (vendas C4)",
      "Receita C4 anualizada por produto × alíquota TIPI. TIPI de 31/12/2023 ≥ 'limite_tipi_ipi' (6,5%): IPI mantido "
      "para o concorrente; abaixo e produzido na ZFM em 2024: IPI zero para todos. TIC: análise manual.",
      "Vendas C4 (EFD Contribuições) + Parâmetros > Produtos (aliq_tipi_2023, produzido_zfm_2024, eh_tic, "
      "nivel_credito_estimulo, tipo_bem).",
      "Carga própria de IPI da ZFM = 0 (CST 52). Vantagem competitiva = receita × TIPI (IPI do concorrente).",
      "Q10 (CST de IPI nas saídas incentivadas), conferência CST 52")


def _fr(v) -> str:
    if v is None or pd.isna(v):
        return "0"
    v = float(v)
    return "integral" if v == 1 else "zero" if v == 0 else f"{v * 100:g}%".replace(".", ",")


def tratamento_to_be(r) -> str:
    """Texto do tratamento To Be de uma linha de param_regras_cenario."""
    p = []
    if r.sentido == "saida" or (r.cbs_debito or 0) or (r.ibs_debito or 0):
        p.append(f"débito sobre a venda: CBS {_fr(r.cbs_debito)}, IBS {_fr(r.ibs_debito)} da alíquota do ano")
    if (r.cbs_entrada or 0) or (r.ibs_entrada or 0):
        cred = {"sim": "creditável", "nao": "não creditável", "regime": "creditável só no regime regular"}.get(
            str(r.entrada_creditavel), str(r.entrada_creditavel))
        p.append(f"devido na entrada: CBS {_fr(r.cbs_entrada)}, IBS {_fr(r.ibs_entrada)} ({cred})")
    if (r.cbs_credito_fornecedor or 0) or (r.ibs_credito_fornecedor or 0):
        p.append(f"crédito do tributo do fornecedor: CBS {_fr(r.cbs_credito_fornecedor)}, "
                 f"IBS {_fr(r.ibs_credito_fornecedor)} (regime regular)")
    if r.cp_cbs_450:
        p.append("crédito presumido de CBS do art. 450 (6% ou 2% da venda, por produto)")
    if r.cp_ibs_450:
        p.append("crédito presumido de IBS do art. 450 (55%/75%/90,25%/100% do saldo devedor, por tipo de bem), "
                 f"a partir de {params.premissa(None, 'ano_inicio_cp450_ibs', '2029')}")
    if r.cp_ibs_entrada == "447":
        p.append(f"crédito presumido de IBS do art. 447: {params.premissa(None, 'cp447_sul_sudeste_exceto_es', '7,5')}% "
                 f"(Sul/Sudeste exceto ES) ou {params.premissa(None, 'cp447_demais_e_es', '13,5')}% (demais e ES) "
                 "das compras × fator de transição")
    elif r.cp_ibs_entrada == "449":
        p.append(f"crédito presumido de IBS do art. 449: {params.premissa(None, 'cp449', '7,5')}% das compras × "
                 "fator de transição")
    elif r.cp_ibs_entrada == "444":
        p.append(f"crédito presumido de IBS de {_fr((r.cp_444_pct or 0) / 100)} da alíquota (art. 444)")
    if not p:
        return "Sem CBS/IBS."
    return "; ".join(p).capitalize() + "."


def cenarios() -> pd.DataFrame:
    regras = params.carregar("param_regras_cenario").set_index("cenario")
    conf = params.carregar("param_conferencia_cenario")
    linhas = []
    for cen, criterio, fontes, asis, cruz in _CENARIOS:
        r = regras.loc[cen] if cen in regras.index else None
        confs = [f"{c.tributo}: {c.mensagem}" for c in conf.itertuples()
                 if cen in [x.strip() for x in str(c.cenarios).split(";")]]
        linhas.append({
            "cenario": cen, "descricao": r.descricao if r is not None else "", "sentido":
            (r.sentido if r is not None else ""), "como_identifica": criterio, "dados_lidos": fontes,
            "as_is": asis, "to_be": tratamento_to_be(r) if r is not None else "Sem regra cadastrada.",
            "ICMS e IPI no To Be": "ICMS = As Is × fator do ICMS do ano; IPI = As Is × 'fator_ipi_proprio'; PIS/COFINS = 0.",
            "conferencias_as_is": " | ".join(confs) or "—", "cruzamentos": cruz,
            "base_legal": r.base_legal if r is not None else "", "observacao": r.observacao if r is not None else ""})
    c5 = C5
    linhas.append({"cenario": c5[0], "descricao": c5[1], "sentido": "saida", "como_identifica": c5[2],
                   "dados_lidos": c5[3], "as_is": c5[4], "to_be": "Vantagem To Be = IPI mantido para o concorrente "
                   "(produtos TIPI ≥ 6,5%); perda = vantagem hoje − To Be. Métrica separada da carga própria.",
                   "ICMS e IPI no To Be": "", "conferencias_as_is": "IPI: CST 52 nas vendas incentivadas",
                   "cruzamentos": c5[5], "base_legal": "LC 214/2025, art. 454", "observacao": ""})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Cruzamentos e conferencias
# ---------------------------------------------------------------------------
CRUZAMENTOS = [
    # codigo, titulo, lado A, lado B, ligacao, tolerancia, o que indica / impacto
    ("Q1", "Completude", "EFD ICMS/IPI de cada estabelecimento do AM (0000)", "EFD Contribuições da empresa (0000 da matriz)",
     "Estabelecimento × mês; empresa = raiz do CNPJ", "—",
     "Mês sem uma das EFDs: a carga As Is e a base daquele mês ficam incompletas."),
    ("Q17", "Cobertura (inclui 0140)", "Estabelecimentos com EFD ICMS/IPI e os do 0140 da Contribuições com IE",
     "Meses do primeiro ao último carregado da empresa", "CNPJ do estabelecimento × mês",
     "—", "Mostra exatamente qual EFD falta. Também roda antes da importação, lendo só o 0000/0140 dos arquivos."),
    ("Q2", "Integridade do arquivo", "Registros lidos", "Bloco 9 (9900 e 9999)", "Registro", "0",
     "Arquivo incompleto ou alterado."),
    ("Q3", "Itens × documento", "Soma do C170 (VL_ITEM, VL_ICMS, VL_IPI)", "C100 (VL_MERC, VL_ICMS, VL_IPI)",
     "Arquivo + linha do C100 (pai do C170)", "tolerancia_conciliacao", "Item faltando ou valor divergente no documento."),
    ("Q4", "Analítico × documento", "Soma do C190 (VL_OPR, VL_ICMS, VL_IPI)", "C100 (VL_DOC, VL_ICMS, VL_IPI)",
     "Arquivo + linha do C100", "tolerancia_conciliacao", "O C190 alimenta o destino das saídas e as entradas sem C170."),
    ("Q14", "Itens × analítico por CFOP", "Soma do C170 por CFOP (BC ICMS, ICMS, IPI)", "C190 do mesmo CFOP",
     "Documento + CFOP", "tolerancia_conciliacao", "CFOP do item diferente do analítico muda a classificação."),
    ("Q5", "R1 – Documentos × apuração do ICMS", "ICMS do C190 (saídas e entradas)", "E110 (débitos e créditos)",
     "Arquivo (estabelecimento × mês)", "tolerancia_conciliacao", "Ajustes fora dos documentos ou documento faltando."),
    ("Q6", "R2 – Documentos × apuração do IPI", "IPI do C190", "E520", "Arquivo", "tolerancia_conciliacao",
     "Idem para o IPI."),
    ("Q7", "R4 – Pareamento Fiscal × Contribuições", "C100 da EFD ICMS/IPI (+0150)", "C100 da EFD Contribuições (+0150)",
     "Estabelecimento + sentido + chave da NF-e (44 posições) ou, sem chave, modelo|série|número|data|CNPJ do participante",
     "tolerancia_conciliacao",
     "Documento só numa EFD (com as duas carregadas) ou com valor, data, participante ou PIS/COFINS diferentes. "
     "Sem contrapartida (a outra EFD do mês não foi carregada), Contribuições consolidada e entrada sem crédito "
     "aparecem no resumo, não como erro. Na consolidada: total do C180 × C190 de saídas."),
    ("Q15", "CFOP e itens do mesmo documento", "C190 (CFOPs) e C170 da EFD ICMS/IPI", "C170 da EFD Contribuições",
     "Documento pareado + CFOP; item pelo NUM_ITEM", "tolerancia_conciliacao",
     "O CFOP liga o produto (Contribuições) ao destino (Fiscal). CFOP diferente leva o destino ao rateio ou à regra "
     "geral e pode mudar o cenário."),
    ("Q16", "Documento repetido", "C100 de uma EFD", "C100 da mesma EFD em outro arquivo/período",
     "Estabelecimento + sentido + chave", "—", "Documento escriturado duas vezes: a segunda ocorrência aparece aqui."),
    ("Q8", "R3 – Receitas × bloco M", "Receita da base (C170/C181, A100, F100 de saída)", "M210/M610 + M400/M800",
     "Empresa × mês", "tolerancia_receita_pct (%)", "Receita não explicada pelos documentos."),
    ("Q13", "Consolidação da Contribuições", "C181 (PIS) e C185 (COFINS)", "C180 (VL_TOT_ITEM)", "Linha do C180",
     "tolerancia_conciliacao", "Receita do produto contada a mais ou a menos."),
    ("Q9", "Alíquotas de PIS/COFINS", "C170/C181/C185 das vendas incentivadas", "Premissas aliq_pis/cofins_zfm_validas",
     "Item", "—", "Alíquota fora da regra da ZFM (0,65/3 ou 1,3/6)."),
    ("Q10", "CST de IPI", "C170 das vendas incentivadas", "Premissa cst_ipi_isento (52)", "Item", "—",
     "IPI não isento em produto incentivado."),
    ("Q11", "Códigos de ajuste", "E111/E116", "Parâmetros > Códigos de ajuste", "Código", "—",
     "Código sem classe: crédito estímulo/fundos podem ficar fora."),
    ("Q12", "E116 × E110", "Soma do E116", "VL_ICMS_RECOLHER + DEB_ESP do E110", "Arquivo", "tolerancia_conciliacao",
     "Obrigação informada além da apuração (ex.: fundos)."),
    ("R5", "Base de operações × apuração", "Carga recalculada com débitos/créditos da base", "Carga da apuração "
     "(E110/E520/M200/M600)", "Estabelecimento/empresa × mês × tributo", "tolerancia_conciliacao",
     "O que não fecha vira 'ajuste de reconciliação', separado do efeito da reforma."),
]


def cruzamentos() -> pd.DataFrame:
    return pd.DataFrame(CRUZAMENTOS, columns=["codigo", "cruzamento", "lado_a", "lado_b", "ligacao", "tolerancia",
                                              "o_que_indica"])


# ---------------------------------------------------------------------------
# De onde vem cada dado usado nos calculos
# ---------------------------------------------------------------------------
FONTES = [
    ("Empresa e estabelecimento", "Ambas", "0000; 0140 (Contribuições); C010", "CNPJ, UF, IE, COD_MUN, SUFRAMA",
     "Perímetro (só AM), raiz do CNPJ, tipo ZFM automático"),
    ("Participante (fornecedor/cliente)", "Ambas", "0150 de cada arquivo", "CNPJ, CPF, COD_PAIS, COD_MUN, IE, SUFRAMA",
     "UF/região de origem, ZFM, contribuinte, exterior, empresa do grupo"),
    ("Produto", "Ambas", "0200 + C180 (NCM)", "COD_ITEM, COD_NCM, tipo", "Produtos incentivados, TIPI, tipo de bem"),
    ("Receita por produto", "Contribuições", "C170 (detalhada) ou C180/C181/C185 (consolidada)",
     "COD_ITEM, CFOP, VL_ITEM, VL_DESC, CST/ALIQ/VL de PIS e COFINS", "Base de CBS/IBS das saídas (C4), C5"),
    ("Destino das saídas", "ICMS/IPI", "C100 + C190 + 0150", "CFOP, VL_OPR, VL_ICMS, participante",
     "Tipo de operação (ZFM, interestadual, exportação), contribuinte; rateio na consolidada"),
    ("Entradas", "ICMS/IPI", "C100 + C170 (ou C190) + 0150", "CFOP, VL_ITEM − VL_DESC, CSTs, ICMS, IPI, PIS, COFINS",
     "Cenários C1–C3, créditos presumidos 447/449/444"),
    ("Serviços tomados", "Contribuições", "A100/A170, F100", "VL_ITEM, VL_OPER", "Cenário SRV"),
    ("Devoluções", "ICMS/IPI", "C190/C170 com CFOP de devolução", "CFOP (Parâmetros > CFOPs > devolucao_de)",
     "Abatem a operação de origem"),
    ("ICMS As Is", "ICMS/IPI", "E110, E111, E116", "VL_ICMS_RECOLHER, DEB_ESP, ajustes classificados",
     "Carga As Is, crédito estímulo, fundos"),
    ("IPI As Is", "ICMS/IPI", "E520", "VL_SD_IPI", "Carga As Is"),
    ("PIS/COFINS As Is", "Contribuições", "M200/M600 (+M210/M610, M400/M800)", "VL_TOT_CONT_REC",
     "Carga As Is, rateada ao AM pela receita (premissa rateio_pis_cofins_am)"),
    ("Saldos credores", "Ambas", "E110, E520, 1100/1500", "Saldos a transportar", "Informação para a transição"),
]


def fontes() -> pd.DataFrame:
    return pd.DataFrame(FONTES, columns=["dado", "efd", "registros", "campos", "usado_em"])
