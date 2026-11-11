#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera EFDs SINTÉTICAS (dados fictícios) para testar o consolidador.

Os registros são montados a partir da lista de campos de cada leiaute, pelo
NOME do campo. Assim o gerador não depende das posições usadas no leitor: se o
leitor ler uma posição errada, os testes acusam.

Cenário (empresa de raiz 11.222.333, matriz /0001-81 e filial /0002-62):

  Janeiro/2026
    A  NF-e 1001  nas duas EFDs, 2 itens, com ICMS ST e IPI
    B  NF-e 1002  nas duas EFDs, mas a Contribuições diverge (CFOP e VL_ICMS)
    C  NF-e 1003  só na EFD Fiscal
    D  NF-e 1004  só na EFD Contribuições
    E  NF-e 1005  emissão própria: Fiscal só com C190 (sem C170)
    F  NF-e 2001  SAÍDA (ignorada)        G  NF-e 1006 CANCELADA (ignorada)
       Energia (C500), frete (D100, CT-e) e telecom (D500) nas duas EFDs
       Serviço (A100/A170) e F100, só na Contribuições
    H  NF-e 5001  da filial, nas duas EFDs (a Fiscal da filial tem retificadora)
  Fevereiro/2026
    I  NF-e 1010  nas duas EFDs (C190 da Fiscal não fecha com o C170)
    A  NF-e 1001  escriturada DE NOVO na Fiscal de fevereiro (repetição)
    J  NF-e 5010  da filial, só na Contribuições (Fiscal da filial não enviada)
       Consolidação C190/C191/C195 da filial na Contribuições

Uso:  python gerar_sinteticos.py [pasta]            # cenário funcional
      python gerar_sinteticos.py [pasta] --docs N   # + par de volume com N documentos
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Leiautes (lista de campos, na ordem do registro)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from efd.leiautes import CONTRIB, FISCAL, NOMES_CAMPOS  # noqa: E402

# Leiautes por NOME de campo (definidos em efd/leiautes.py)
LEIAUTE = {"F": NOMES_CAMPOS[FISCAL], "C": NOMES_CAMPOS[CONTRIB]}


def v(x, casas=2):
    """Número no formato do SPED (vírgula decimal)."""
    return "" if x is None else f"{x:.{casas}f}".replace(".", ",")


class Arquivo:
    def __init__(self, tipo):
        self.tipo = tipo            # "F" ou "C"
        self.linhas = []

    def add(self, reg, **campos):
        nomes = LEIAUTE[self.tipo][reg]
        desconhecidos = set(campos) - {n.replace("-", "_") for n in nomes}
        assert not desconhecidos, f"{reg}: campos fora do leiaute {desconhecidos}"
        valores = [reg] + [str(campos.get(n.replace("-", "_"), "")) for n in nomes[1:]]
        self.linhas.append("|" + "|".join(valores) + "|")

    def finalizar(self, erro_9900=None):
        """Acrescenta o bloco 9 com as contagens reais (9900)."""
        contagem = {}
        for l in self.linhas:
            contagem[l[1:5]] = contagem.get(l[1:5], 0) + 1
        contagem["9001"] = 1
        contagem["9990"] = 1
        contagem["9999"] = 1
        contagem["9900"] = len(contagem) + 1
        bloco9 = ["|9001|0|"]
        for reg in sorted(contagem):
            qtd = contagem[reg]
            if erro_9900 and reg == erro_9900:
                qtd += 1
            bloco9.append(f"|9900|{reg}|{qtd}|")
        bloco9.append(f"|9990|{len(bloco9) + 2}|")
        total = len(self.linhas) + len(bloco9) + 1
        bloco9.append(f"|9999|{total}|")
        self.linhas += bloco9
        return self

    def gravar(self, caminho, encoding="latin-1", fim_de_linha="\r\n"):
        with open(caminho, "w", encoding=encoding, newline="") as f:
            f.write(fim_de_linha.join(self.linhas) + fim_de_linha)
        return caminho


# ---------------------------------------------------------------------------
# Cadastros
# ---------------------------------------------------------------------------
MATRIZ, FILIAL = "11222333000181", "11222333000262"
NOME = "INDÚSTRIA EXEMPLO S.A."
ACO, TRANSP, ENERGIA, TELECOM, CONTAB, CLIENTE = (
    "99888777000166", "55444333000122", "33222111000144", "77666555000188",
    "22111000000133", "12345678000195")
# o MESMO fornecedor tem códigos diferentes em cada escrituração (de propósito)
PART = {
    ACO: ("FORNECEDOR AÇO LTDA", "F001", "FOR001"),
    TRANSP: ("TRANSPORTADORA RÁPIDA LTDA", "F002", "FOR002"),
    ENERGIA: ("ENERGIA ELÉTRICA PAULISTA S.A.", "F003", "FOR003"),
    TELECOM: ("TELECOM BRASIL S.A.", "F004", "FOR004"),
    CONTAB: ("SERVIÇOS CONTÁBEIS AVANÇADOS ME", None, "FOR005"),
    CLIENTE: ("CLIENTE VAREJO LTDA", "C001", "CLI001"),
}
ITENS = {"ITEM001": ("CHAPA DE AÇO 3MM", "72085100", "KG"),
         "ITEM002": ("PARAFUSO SEXTAVADO M8", "73181500", "UN"),
         "SERV001": ("CONSULTORIA CONTÁBIL MENSAL", "", "UN")}


def chave(n):
    """Chave fictícia de 44 dígitos, distinta por documento."""
    return f"3526{n:040d}"


def cod(cnpj, tipo):
    return PART[cnpj][1 if tipo == "F" else 2]


def bloco0(a, tipo, cnpj, dt_ini, dt_fin, finalidade="0", estabs=(MATRIZ,)):
    if tipo == "F":
        a.add("0000", COD_VER="020", COD_FIN=finalidade, DT_INI=dt_ini, DT_FIN=dt_fin,
              NOME=NOME, CNPJ=cnpj, UF="SP", IE="110042490114" if cnpj == MATRIZ else "110042490220",
              COD_MUN="3550308", IND_PERFIL="A", IND_ATIV="0")
        a.add("0001", IND_MOV="0")
        for doc, (nome, cf, _) in PART.items():
            if cf:
                a.add("0150", COD_PART=cf, NOME=nome, COD_PAIS="01058", CNPJ=doc, COD_MUN="3550308")
    else:
        a.add("0000", COD_VER="006", TIPO_ESCRIT=finalidade, DT_INI=dt_ini, DT_FIN=dt_fin,
              NOME=NOME, CNPJ=MATRIZ, UF="SP", COD_MUN="3550308", IND_NAT_PJ="00", IND_ATIV="0")
        a.add("0001", IND_MOV="0")
        a.add("0110", COD_INC_TRIB="1", IND_APRO_CRED="1", COD_TIPO_CONT="1")
        for e in estabs:
            a.add("0140", COD_EST="E" + e[-6:], NOME=NOME + (" - MATRIZ" if e == MATRIZ else " - FILIAL"),
                  CNPJ=e, UF="SP", COD_MUN="3550308")
            for doc, (nome, _, cc) in PART.items():
                a.add("0150", COD_PART=cc, NOME=nome, COD_PAIS="01058", CNPJ=doc, COD_MUN="3550308")
    a.add("0190", UNID="UN", DESCR="UNIDADE")
    a.add("0190", UNID="KG", DESCR="QUILOGRAMA")
    for c, (descr, ncm, un) in ITENS.items():
        a.add("0200", COD_ITEM=c, DESCR_ITEM=descr, UNID_INV=un,
              TIPO_ITEM="09" if c.startswith("SERV") else "01", COD_NCM=ncm)


def nf(a, tipo, forn, num, n_chave, dt, dt_es, itens, ind_oper="0", ind_emit="1",
       cod_sit="00", so_c190=False, c190_icms=None, sem_itens=False):
    """NF-e (C100). `itens`: lista de dicts com cod, vl, cfop, bc, icms, bc_st,
    st, ipi, pis, cofins, cst_pis. O cabeçalho e o C190 são somados dos itens."""
    if cod_sit == "02":
        a.add("C100", IND_OPER=ind_oper, IND_EMIT=ind_emit, COD_PART=cod(forn, tipo),
              COD_MOD="55", COD_SIT="02", SER="1", NUM_DOC=num, CHV_NFE=chave(n_chave))
        return
    s = lambda k: sum(i.get(k, 0) for i in itens)
    vl_doc = s("vl") + s("ipi") + s("st")
    a.add("C100", IND_OPER=ind_oper, IND_EMIT=ind_emit, COD_PART=cod(forn, tipo), COD_MOD="55",
          COD_SIT=cod_sit, SER="1", NUM_DOC=num, CHV_NFE=chave(n_chave), DT_DOC=dt, DT_E_S=dt_es,
          VL_DOC=v(vl_doc), IND_PGTO="0", VL_MERC=v(s("vl")), IND_FRT="9",
          VL_BC_ICMS=v(s("bc")), VL_ICMS=v(c190_icms if c190_icms is not None else s("icms")),
          VL_BC_ICMS_ST=v(s("bc_st")), VL_ICMS_ST=v(s("st")), VL_IPI=v(s("ipi")),
          VL_PIS=v(s("pis")), VL_COFINS=v(s("cofins")))
    if not (so_c190 or sem_itens):
        for n, i in enumerate(itens, 1):
            extra = {}
            if tipo == "C" or i.get("pis_na_fiscal"):
                extra = dict(CST_PIS=i.get("cst_pis", "50"), VL_BC_PIS=v(i["vl"] if i.get("pis") else 0),
                             ALIQ_PIS=v(1.65, 4), VL_PIS=v(i.get("pis", 0)),
                             CST_COFINS=i.get("cst_pis", "50"),
                             VL_BC_COFINS=v(i["vl"] if i.get("cofins") else 0),
                             ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(i.get("cofins", 0)))
            a.add("C170", NUM_ITEM=n, COD_ITEM=i["cod"], QTD=v(i.get("qtd", 10), 5),
                  UNID=ITENS[i["cod"]][2], VL_ITEM=v(i["vl"]), VL_DESC=v(0), IND_MOV="0",
                  CST_ICMS=i.get("cst", "000"), CFOP=i["cfop"], VL_BC_ICMS=v(i.get("bc", 0)),
                  ALIQ_ICMS=v(i.get("aliq", 18)), VL_ICMS=v(i.get("icms", 0)),
                  VL_BC_ICMS_ST=v(i.get("bc_st", 0)), VL_ICMS_ST=v(i.get("st", 0)),
                  VL_IPI=v(i.get("ipi", 0)), COD_CTA="1.1.01.001", **extra)
    if tipo == "F":
        grupos = {}
        for i in itens:
            g = grupos.setdefault((i.get("cst", "000"), i["cfop"], i.get("aliq", 18)),
                                  dict(vl=0, bc=0, icms=0, bc_st=0, st=0, ipi=0))
            for k in g:
                g[k] += i.get(k, 0)
        for (cst, cfop, aliq), g in grupos.items():
            a.add("C190", CST_ICMS=cst, CFOP=cfop, ALIQ_ICMS=v(aliq),
                  VL_OPR=v(g["vl"] + g["ipi"] + g["st"]), VL_BC_ICMS=v(g["bc"]),
                  VL_ICMS=v(c190_icms if c190_icms is not None else g["icms"]),
                  VL_BC_ICMS_ST=v(g["bc_st"]), VL_ICMS_ST=v(g["st"]), VL_RED_BC=v(0),
                  VL_IPI=v(g["ipi"]))


def item(cod_item, vl, cfop, icms=None, aliq=18, **k):
    d = dict(cod=cod_item, vl=vl, cfop=cfop, aliq=aliq, bc=vl if icms is None or icms else 0,
             icms=round(vl * aliq / 100, 2) if icms is None else icms,
             pis=round(vl * 0.0165, 2), cofins=round(vl * 0.076, 2))
    d.update(k)
    return d


# Documentos do cenário (os mesmos dicionários servem às duas escriturações)
DOC_A = [item("ITEM001", 1000.00, "1101", ipi=50.00, qtd=100),
         item("ITEM002", 500.00, "1101", bc_st=600.00, st=25.00, qtd=500)]
DOC_B = [item("ITEM001", 2000.00, "1101")]
DOC_B_CONTRIB = [item("ITEM001", 2000.00, "1102", icms=350.00)]      # divergente
DOC_C = [item("ITEM002", 300.00, "1556", icms=0, cst="090", pis=0, cofins=0, cst_pis="70")]
DOC_D = [item("ITEM001", 400.00, "1101")]
DOC_E = [item("ITEM001", 800.00, "1949", pis=0, cofins=0, cst_pis="70")]
DOC_F = [item("ITEM001", 8000.00, "5101")]
DOC_H = [item("ITEM001", 1200.00, "2101", aliq=12)]
DOC_H_RETIF = [item("ITEM001", 1200.00, "2101", aliq=12, icms=156.00)]
DOC_I = [item("ITEM002", 700.00, "1101")]
DOC_J = [item("ITEM002", 150.00, "1101", pis=2.48, cofins=11.40)]


def fiscal(cnpj, mes, docs, finalidade="0", com_servicos=False, erro_9900=None):
    a = Arquivo("F")
    ini, fim = f"01{mes:02d}2026", f"{28 if mes == 2 else 31}{mes:02d}2026"
    bloco0(a, "F", cnpj, ini, fim, finalidade)
    a.add("C001", IND_MOV="0")
    for d in docs:
        nf(a, "F", **d)
    if com_servicos:
        a.add("C500", IND_OPER="0", IND_EMIT="1", COD_PART=cod(ENERGIA, "F"), COD_MOD="06",
              COD_SIT="00", SER="1", NUM_DOC="777", DT_DOC="10012026", DT_E_S="12012026",
              VL_DOC=v(2000), VL_FORN=v(2000), VL_BC_ICMS=v(2000), VL_ICMS=v(360),
              VL_BC_ICMS_ST=v(0), VL_ICMS_ST=v(0))
        a.add("C590", CST_ICMS="000", CFOP="1253", ALIQ_ICMS=v(18), VL_OPR=v(2000),
              VL_BC_ICMS=v(2000), VL_ICMS=v(360), VL_BC_ICMS_ST=v(0), VL_ICMS_ST=v(0),
              VL_RED_BC=v(0))
    a.add("C990", QTD_LIN_C="0")
    a.add("D001", IND_MOV="0" if com_servicos else "1")
    if com_servicos:
        a.add("D100", IND_OPER="0", IND_EMIT="1", COD_PART=cod(TRANSP, "F"), COD_MOD="57",
              COD_SIT="00", SER="1", NUM_DOC="888", CHV_CTE=chave(600), DT_DOC="08012026",
              DT_A_P="09012026", TP_CT_e="0", VL_DOC=v(400), VL_DESC=v(0), IND_FRT="1",
              VL_SERV=v(400), VL_BC_ICMS=v(400), VL_ICMS=v(48), VL_NT=v(0))
        a.add("D190", CST_ICMS="000", CFOP="1352", ALIQ_ICMS=v(12), VL_OPR=v(400),
              VL_BC_ICMS=v(400), VL_ICMS=v(48), VL_RED_BC=v(0))
        a.add("D500", IND_OPER="0", IND_EMIT="1", COD_PART=cod(TELECOM, "F"), COD_MOD="22",
              COD_SIT="00", SER="U", NUM_DOC="999", DT_DOC="12012026", DT_A_P="12012026",
              VL_DOC=v(250), VL_DESC=v(0), VL_SERV=v(250), VL_BC_ICMS=v(250), VL_ICMS=v(62.50))
        a.add("D590", CST_ICMS="000", CFOP="1303", ALIQ_ICMS=v(25), VL_OPR=v(250),
              VL_BC_ICMS=v(250), VL_ICMS=v(62.50), VL_BC_ICMS_UF=v(0), VL_ICMS_UF=v(0),
              VL_RED_BC=v(0))
    a.add("D990", QTD_LIN_D="0")
    return a.finalizar(erro_9900)


def contrib(mes, blocos, finalidade="0"):
    """`blocos`: {cnpj do estabelecimento: {"nfs": [...], "extras": bool, ...}}"""
    a = Arquivo("C")
    ini, fim = f"01{mes:02d}2026", f"{28 if mes == 2 else 31}{mes:02d}2026"
    bloco0(a, "C", MATRIZ, ini, fim, finalidade, estabs=tuple(blocos))
    # ---- Bloco A (serviços) ----
    a.add("A001", IND_MOV="0")
    for est, b in blocos.items():
        if not b.get("extras"):
            continue
        a.add("A010", CNPJ=est)
        a.add("A100", IND_OPER="0", IND_EMIT="1", COD_PART=cod(CONTAB, "C"), COD_SIT="00",
              SER="1", NUM_DOC="55", DT_DOC="05012026", DT_EXE_SERV="05012026",
              VL_DOC=v(1000), IND_PGTO="0", VL_DESC=v(0), VL_BC_PIS=v(1000), VL_PIS=v(16.50),
              VL_BC_COFINS=v(1000), VL_COFINS=v(76.00), VL_PIS_RET=v(0), VL_COFINS_RET=v(0),
              VL_ISS=v(50.01))
        for n, (vl, pis, cof) in enumerate(((333.33, 5.50, 25.33), (666.67, 11.00, 50.67)), 1):
            a.add("A170", NUM_ITEM=n, COD_ITEM="SERV001", VL_ITEM=v(vl), VL_DESC=v(0),
                  NAT_BC_CRED="03", IND_ORIG_CRED="0", CST_PIS="50", VL_BC_PIS=v(vl),
                  ALIQ_PIS=v(1.65, 4), VL_PIS=v(pis), CST_COFINS="50", VL_BC_COFINS=v(vl),
                  ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(cof), COD_CTA="3.1.02.001")
        # serviço PRESTADO (saída): deve ser ignorado
        a.add("A100", IND_OPER="1", IND_EMIT="0", COD_PART=cod(CLIENTE, "C"), COD_SIT="00",
              SER="1", NUM_DOC="56", DT_DOC="10012026", VL_DOC=v(9999.99), VL_PIS=v(164.99),
              VL_COFINS=v(759.99), VL_ISS=v(500))
        a.add("A170", NUM_ITEM=1, COD_ITEM="SERV001", VL_ITEM=v(9999.99), CST_PIS="01",
              VL_BC_PIS=v(9999.99), VL_PIS=v(164.99), CST_COFINS="01",
              VL_BC_COFINS=v(9999.99), VL_COFINS=v(759.99))
    a.add("A990", QTD_LIN_A="0")
    # ---- Bloco C ----
    a.add("C001", IND_MOV="0")
    for est, b in blocos.items():
        a.add("C010", CNPJ=est, IND_ESCRI="1" if b.get("consolidado") else "2")
        for d in b.get("nfs", []):
            nf(a, "C", **d)
        if b.get("consolidado"):
            a.add("C190", COD_MOD="55", DT_REF_INI=ini, DT_REF_FIN=fim, COD_ITEM="ITEM001",
                  COD_NCM="72085100", VL_TOT_ITEM=v(1000))
            a.add("C191", CNPJ_CPF_PART=ACO, CST_PIS="50", CFOP="1101", VL_ITEM=v(900),
                  VL_DESC=v(0), VL_BC_PIS=v(900), ALIQ_PIS=v(1.65, 4), VL_PIS=v(14.85))
            a.add("C191", CNPJ_CPF_PART=ACO, CST_PIS="98", CFOP="5202", VL_ITEM=v(100),
                  VL_DESC=v(0), VL_BC_PIS=v(100), ALIQ_PIS=v(1.65, 4), VL_PIS=v(1.65))
            a.add("C195", CNPJ_CPF_PART=ACO, CST_COFINS="50", CFOP="1101", VL_ITEM=v(900),
                  VL_DESC=v(0), VL_BC_COFINS=v(900), ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(68.40))
            a.add("C195", CNPJ_CPF_PART=ACO, CST_COFINS="98", CFOP="5202", VL_ITEM=v(100),
                  VL_DESC=v(0), VL_BC_COFINS=v(100), ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(7.60))
        if b.get("extras"):
            a.add("C500", COD_PART=cod(ENERGIA, "C"), COD_MOD="06", COD_SIT="00", SER="1",
                  NUM_DOC="777", DT_DOC="10012026", DT_ENT="12012026", VL_DOC=v(2000),
                  VL_ICMS=v(360), VL_PIS=v(33.00), VL_COFINS=v(152.00))
            a.add("C501", CST_PIS="50", VL_ITEM=v(2000), NAT_BC_CRED="04", VL_BC_PIS=v(2000),
                  ALIQ_PIS=v(1.65, 4), VL_PIS=v(33.00), COD_CTA="4.1.05.001")
            a.add("C505", CST_COFINS="50", VL_ITEM=v(2000), NAT_BC_CRED="04",
                  VL_BC_COFINS=v(2000), ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(152.00),
                  COD_CTA="4.1.05.001")
    a.add("C990", QTD_LIN_C="0")
    # ---- Bloco D ----
    a.add("D001", IND_MOV="0")
    for est, b in blocos.items():
        if not b.get("extras"):
            continue
        a.add("D010", CNPJ=est)
        a.add("D100", IND_OPER="0", IND_EMIT="1", COD_PART=cod(TRANSP, "C"), COD_MOD="57",
              COD_SIT="00", SER="1", NUM_DOC="888", CHV_CTE=chave(600), DT_DOC="08012026",
              DT_A_P="09012026", TP_CT_e="0", VL_DOC=v(400), VL_DESC=v(0), IND_FRT="1",
              VL_SERV=v(400), VL_BC_ICMS=v(400), VL_ICMS=v(48), VL_NT=v(0))
        a.add("D101", IND_NAT_FRT="0", VL_ITEM=v(400), CST_PIS="50", NAT_BC_CRED="07",
              VL_BC_PIS=v(400), ALIQ_PIS=v(1.65, 4), VL_PIS=v(6.60), COD_CTA="4.1.10.001")
        a.add("D105", IND_NAT_FRT="0", VL_ITEM=v(400), CST_COFINS="50", NAT_BC_CRED="07",
              VL_BC_COFINS=v(400), ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(30.40), COD_CTA="4.1.10.001")
        a.add("D500", IND_OPER="0", IND_EMIT="1", COD_PART=cod(TELECOM, "C"), COD_MOD="22",
              COD_SIT="00", SER="U", NUM_DOC="999", DT_DOC="12012026", DT_A_P="12012026",
              VL_DOC=v(250), VL_DESC=v(0), VL_SERV=v(250), VL_BC_ICMS=v(250), VL_ICMS=v(62.50),
              VL_PIS=v(4.13), VL_COFINS=v(19.00))
        a.add("D501", CST_PIS="50", VL_ITEM=v(250), NAT_BC_CRED="13", VL_BC_PIS=v(250),
              ALIQ_PIS=v(1.65, 4), VL_PIS=v(4.13), COD_CTA="4.2.08.001")
        a.add("D505", CST_COFINS="50", VL_ITEM=v(250), NAT_BC_CRED="13", VL_BC_COFINS=v(250),
              ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(19.00), COD_CTA="4.2.08.001")
    a.add("D990", QTD_LIN_D="0")
    # ---- Bloco F ----
    a.add("F001", IND_MOV="0")
    for est, b in blocos.items():
        if not b.get("extras"):
            continue
        a.add("F010", CNPJ=est)
        a.add("F100", IND_OPER="0", COD_PART=cod(ACO, "C"), DT_OPER="05012026", VL_OPER=v(3000),
              CST_PIS="50", VL_BC_PIS=v(3000), ALIQ_PIS=v(1.65, 4), VL_PIS=v(49.50),
              CST_COFINS="50", VL_BC_COFINS=v(3000), ALIQ_COFINS=v(7.6, 4), VL_COFINS=v(228.00),
              NAT_BC_CRED="05", IND_ORIG_CRED="0", COD_CTA="4.2.01.001",
              DESC_DOC_OPER="ALUGUEL GALPÃO INDUSTRIAL JAN/2026")
        a.add("F100", IND_OPER="1", COD_PART=cod(CLIENTE, "C"), DT_OPER="05012026",
              VL_OPER=v(5000), CST_PIS="01", VL_BC_PIS=v(5000), VL_PIS=v(82.50),
              CST_COFINS="01", VL_BC_COFINS=v(5000), VL_COFINS=v(380.00),
              DESC_DOC_OPER="RECEITA FINANCEIRA")
    a.add("F990", QTD_LIN_F="0")
    return a.finalizar()


def d(forn, num, n_chave, dt, dt_es, itens, **k):
    return dict(forn=forn, num=num, n_chave=n_chave, dt=dt, dt_es=dt_es, itens=itens, **k)


def gerar(pasta: str) -> dict:
    os.makedirs(pasta, exist_ok=True)
    cam = lambda nome: os.path.join(pasta, nome)
    A = d(ACO, "1001", 1, "05012026", "06012026", DOC_A)
    saida = d(CLIENTE, "2001", 20, "15012026", "15012026", DOC_F, ind_oper="1", ind_emit="0")
    cancelada = d(ACO, "1006", 6, "", "", [], cod_sit="02")

    # --- Janeiro, matriz ---
    f_jan = fiscal(MATRIZ, 1, [
        A, d(ACO, "1002", 2, "10012026", "11012026", DOC_B),
        d(ACO, "1003", 3, "12012026", "13012026", DOC_C),
        d(ACO, "1005", 5, "20012026", "20012026", DOC_E, ind_emit="0", so_c190=True),
        dict(saida, so_c190=True), cancelada], com_servicos=True)
    arquivos = {"fiscal_matriz_jan": f_jan.gravar(cam("FISCAL_MATRIZ_2026-01.txt"))}
    # mesmo conteúdo com outro nome / em outra codificação e quebra de linha
    arquivos["copia_bytes"] = f_jan.gravar(cam("COPIA_DA_FISCAL_MATRIZ_2026-01.txt"))
    arquivos["copia_utf8"] = f_jan.gravar(cam("FISCAL_MATRIZ_2026-01_utf8.txt"),
                                          encoding="utf-8", fim_de_linha="\n")

    # --- Janeiro, filial: original e retificadora ---
    H = d(ACO, "5001", 7, "15012026", "16012026", DOC_H)
    arquivos["fiscal_filial_jan"] = fiscal(FILIAL, 1, [H]).gravar(
        cam("FISCAL_FILIAL_2026-01.txt"), encoding="utf-8")
    arquivos["fiscal_filial_jan_retif"] = fiscal(
        FILIAL, 1, [dict(H, itens=DOC_H_RETIF)], finalidade="1").gravar(
        cam("FISCAL_FILIAL_2026-01_RETIFICADORA.txt"))

    # --- Janeiro, Contribuições (matriz + filial) ---
    arquivos["contrib_jan"] = contrib(1, {
        MATRIZ: {"extras": True, "nfs": [
            A, d(ACO, "1002", 2, "10012026", "11012026", DOC_B_CONTRIB),
            d(ACO, "1004", 4, "14012026", "15012026", DOC_D),
            d(ACO, "1005", 5, "20012026", "20012026", DOC_E, ind_emit="0"),
            saida, cancelada]},
        FILIAL: {"nfs": [H]},
    }).gravar(cam("CONTRIB_2026-01.txt"))

    # --- Fevereiro ---
    I = d(ACO, "1010", 8, "03022026", "04022026", DOC_I)
    arquivos["fiscal_matriz_fev"] = fiscal(
        MATRIZ, 2, [dict(I, c190_icms=120.00), A], erro_9900="C170").gravar(
        cam("FISCAL_MATRIZ_2026-02.txt"))
    J = d(ACO, "5010", 9, "10022026", "11022026", DOC_J)
    arquivos["contrib_fev"] = contrib(2, {
        MATRIZ: {"nfs": [I]},
        FILIAL: {"nfs": [J], "consolidado": True},
    }).gravar(cam("CONTRIB_2026-02.txt"))
    # segunda versão ORIGINAL do mesmo período (conflito)
    arquivos["contrib_fev_outra"] = contrib(2, {
        MATRIZ: {"nfs": [dict(I, itens=[item("ITEM002", 710.00, "1101")])]},
    }).gravar(cam("CONTRIB_2026-02_OUTRA_VERSAO.txt"))

    with open(cam("NAO_E_EFD.txt"), "w", encoding="latin-1") as f:
        f.write("|0000|LECD|01012026|31012026|EMPRESA|11222333000181|SP||3550308||0|\n")
    arquivos["invalido"] = cam("NAO_E_EFD.txt")
    return arquivos


def gerar_volume(pasta: str, docs: int, itens_por_doc: int = 4) -> dict:
    """Par Fiscal + Contribuições com `docs` NF-e de entrada idênticas nas duas."""
    os.makedirs(pasta, exist_ok=True)
    saida = {}
    for tipo, nome in (("F", "VOLUME_FISCAL.txt"), ("C", "VOLUME_CONTRIB.txt")):
        a = Arquivo(tipo)
        bloco0(a, tipo, MATRIZ, "01032026", "31032026")
        a.add("C001", IND_MOV="0")
        if tipo == "C":
            a.add("C010", CNPJ=MATRIZ, IND_ESCRI="2")
        fornecedores = (ACO, TRANSP, ENERGIA, TELECOM)
        for n in range(docs):
            # valores variados (como em um arquivo real), mas reproduzíveis
            its = [item("ITEM001" if k % 2 else "ITEM002",
                        100 + (n * 7 + k * 13) % 9000 + ((n * 31 + k) % 100) / 100,
                        "1101" if k < 2 else "2101")
                   for k in range(itens_por_doc)]
            nf(a, tipo, fornecedores[n % 4], str(100000 + n), 1_000_000 + n, "05032026",
               "06032026", its)
        a.add("C990", QTD_LIN_C="0")
        saida[tipo] = a.finalizar().gravar(os.path.join(pasta, nome))
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", nargs="?", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
    ap.add_argument("--docs", type=int, default=0, help="gera também um par de volume com N documentos")
    args = ap.parse_args()
    for nome, caminho in gerar(args.pasta).items():
        print(f"{nome:28s} {caminho}")
    if args.docs:
        for tipo, caminho in gerar_volume(args.pasta, args.docs).items():
            print(f"volume {tipo}                     {caminho}")
