"""Gerador de EFDs SINTETICAS para testes (nenhum dado real).

Cenario (SPEC secao 9): 3 empresas, uma com 2 estabelecimentos no AM e outra
com matriz em SP e filial no AM; 3 meses (jan-mar/2026); operacao entre
empresas do grupo; saida com e sem C170; entrada de SP, de PE e importacao;
saida para Manaus; codigo E111 de credito estimulo; saldo credor; opcao de
retificadora e de assinatura apos o 9999.

Os valores dos registros de totalizacao (C100, C190, E110, E520, C180/C181,
M210...) sao calculados a partir dos itens, para servir as conciliacoes.
As linhas sao montadas pelo NOME do campo usando os mesmos dicionarios de
layout do programa.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from zfm.layouts import efd_contrib, efd_icms_ipi

D = Decimal
CENT = D("0.01")
ANO = 2026
COD_VER_ICMS = "020"   # sintetico
COD_VER_CONTRIB = "006"  # sintetico
COD_AJ_CREDITO_ESTIMULO = "AM040014"  # deducao (4o caractere = 4), padrao do AM
COD_OR_FTI = "090"
COD_REC_FTI = "FTI9"


def r2(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(v, casas: int = 2) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, Decimal):
        return f"{v:.{casas}f}".replace(".", ",")
    return str(v)


def dt(dia: int, mes: int) -> str:
    return f"{dia:02d}{mes:02d}{ANO}"


def ultimo_dia(mes: int) -> int:
    return {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}[mes]


# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Part:
    cod: str
    nome: str
    cnpj: str
    cod_mun: str
    cod_pais: str = "1058"
    ie: str = ""
    suframa: str = ""


@dataclass(frozen=True)
class Item:
    cod: str
    descr: str
    ncm: str
    tipo_item: str  # 01 materia-prima, 04 produto acabado, 06 produto intermediario


@dataclass
class ItemDoc:
    cod_item: str
    vl_item: Decimal
    cfop: str
    cst_icms: str
    aliq_icms: Decimal
    cst_ipi: str
    aliq_ipi: Decimal
    cst_pis: str
    aliq_pis: Decimal
    cst_cofins: str
    aliq_cofins: Decimal
    qtd: Decimal = D("10")
    vl_desc: Decimal = D("0")

    @property
    def base(self) -> Decimal:
        return self.vl_item - self.vl_desc

    def _v(self, aliq: Decimal) -> tuple[Decimal, Decimal]:
        if aliq and aliq > 0:
            return self.base, r2(self.base * aliq / 100)
        return D("0"), D("0")

    @property
    def icms(self):
        return self._v(self.aliq_icms)

    @property
    def ipi(self):
        return self._v(self.aliq_ipi)

    @property
    def pis(self):
        return self._v(self.aliq_pis)

    @property
    def cofins(self):
        return self._v(self.aliq_cofins)


@dataclass
class Doc:
    ind_oper: str      # 0 entrada, 1 saida
    ind_emit: str      # 0 propria, 1 terceiros
    part: Part
    num: int
    dia: int
    itens: list[ItemDoc]
    com_c170: bool
    cnpj_emit: str
    cod_sit: str = "00"

    def chave(self, mes: int) -> str:
        base = f"13{ANO % 100:02d}{mes:02d}{self.cnpj_emit}55001{self.num:09d}1{self.num:08d}"
        pesos, soma = [2, 3, 4, 5, 6, 7, 8, 9], 0
        for i, ch in enumerate(reversed(base)):
            soma += int(ch) * pesos[i % 8]
        dv = 11 - soma % 11
        return base + str(0 if dv >= 10 else dv)


@dataclass
class Estab:
    cnpj: str
    ie: str
    nome: str
    uf: str
    cod_mun: str
    suframa: str
    docs: dict[int, list[Doc]] = field(default_factory=dict)  # mes -> docs
    ajustes_ce: dict[int, Decimal] = field(default_factory=dict)  # mes -> credito estimulo
    fundo_fti: dict[int, Decimal] = field(default_factory=dict)

    @property
    def raiz(self) -> str:
        return self.cnpj[:8]


@dataclass
class Empresa:
    nome: str
    matriz: Estab
    estabs: list[Estab]
    contrib_detalhada: bool = False   # True: C100/C170; False: C180-C195


# ---------------------------------------------------------------------------
# Cenario
# ---------------------------------------------------------------------------
MANAUS = "1302603"
SAO_PAULO = "3550308"
RECIFE = "2611606"

ITENS = [
    Item("PROD01", "Televisor 50 polegadas", "85287200", "04"),
    Item("PROD02", "Placa de circuito impresso montada", "85340000", "06"),
    Item("INS01", "Painel de cristal liquido", "85249100", "01"),
    Item("INS02", "Componente eletronico importado", "85423190", "01"),
]

F_SP = Part("F_SP", "Fornecedor São Paulo Ltda", "44444444000144", SAO_PAULO, ie="111111111111")
F_PE = Part("F_PE", "Fornecedor Pernambuco Ltda", "55555555000155", RECIFE, ie="222222222")
F_EXT = Part("F_EXT", "Overseas Supplier Co", "", "9999999", cod_pais="1600")
C_SP = Part("C_SP", "Varejo Paulista S.A.", "66666666000166", SAO_PAULO, ie="333333333333")
C_MAO = Part("C_MAO", "Distribuidora Manauara Ltda", "77777777000177", MANAUS,
             ie="044444444", suframa="200000017")


def _saida_icms_sp(cod_item: str, valor: Decimal) -> ItemDoc:
    # Saida interestadual de producao incentivada: ICMS 12%, IPI isento (CST 52),
    # PIS/COFINS a 0,65%/3% (CST 02)
    return ItemDoc(cod_item, valor, "6101", "000", D("12"), "52", D("0"),
                   "02", D("0.65"), "02", D("3"))


def _saida_manaus(cod_item: str, valor: Decimal) -> ItemDoc:
    return ItemDoc(cod_item, valor, "5101", "000", D("20"), "52", D("0"),
                   "06", D("0"), "06", D("0"))


def _entrada(cod_item: str, valor: Decimal, cfop: str, aliq_icms: Decimal,
             cst_icms: str = "000", cst_ipi: str = "02") -> ItemDoc:
    return ItemDoc(cod_item, valor, cfop, cst_icms, aliq_icms, cst_ipi, D("0"),
                   "72", D("0"), "72", D("0"))


def montar_cenario(meses: tuple[int, ...] = (1, 2, 3)) -> list[Empresa]:
    a1 = Estab("11111111000191", "041111111", "Alfa Eletrônicos da Amazônia Ltda", "AM", MANAUS, "210000011")
    a2 = Estab("11111111000272", "041111112", "Alfa Eletrônicos da Amazônia Ltda", "AM", MANAUS, "210000012")
    b1 = Estab("22222222000122", "042222222", "Beta Componentes Ltda", "AM", MANAUS, "220000022")
    c_mat = Estab("33333333000133", "555555555555", "Gama Indústria S.A.", "SP", SAO_PAULO, "")
    c_am = Estab("33333333000214", "043333333", "Gama Indústria S.A.", "AM", MANAUS, "230000033")

    p_a1 = Part("GRP_A1", a1.nome, a1.cnpj, MANAUS, ie=a1.ie, suframa=a1.suframa)
    p_b1 = Part("GRP_B1", b1.nome, b1.cnpj, MANAUS, ie=b1.ie, suframa=b1.suframa)

    num = {"n": 0}

    def n() -> int:
        num["n"] += 1
        return num["n"]

    for m in meses:
        f = D(1) + D("0.1") * (m - 1)
        # --- A1: entradas SP, PE, importacao; saidas SP (com C170), Manaus (sem C170),
        #         e saida para a empresa B (operacao entre empresas do grupo, sem C170)
        intra = Doc("1", "0", p_b1, n(), 20, [ItemDoc("PROD02", r2(D("30000") * f), "5101", "000",
                    D("20"), "52", D("0"), "06", D("0"), "06", D("0"))], False, a1.cnpj)
        a1.docs[m] = [
            Doc("0", "1", F_SP, n(), 3, [_entrada("INS01", r2(D("100000") * f), "2101", D("7"))],
                True, F_SP.cnpj),
            Doc("0", "1", F_PE, n(), 4, [_entrada("INS01", r2(D("20000") * f), "2101", D("12"))],
                True, F_PE.cnpj),
            Doc("0", "0", F_EXT, n(), 5, [_entrada("INS02", r2(D("50000") * f), "3101", D("0"),
                                                   cst_icms="140", cst_ipi="05")],
                True, a1.cnpj),
            Doc("1", "0", C_SP, n(), 10, [_saida_icms_sp("PROD01", r2(D("400000") * f))], True, a1.cnpj),
            Doc("1", "0", C_MAO, n(), 15, [_saida_manaus("PROD01", r2(D("80000") * f))], False, a1.cnpj),
            intra,
        ]
        # --- A2: entrada SP e saida SP sem C170
        a2.docs[m] = [
            Doc("0", "1", F_SP, n(), 6, [_entrada("INS01", r2(D("40000") * f), "2101", D("7"))],
                True, F_SP.cnpj),
            Doc("1", "0", C_SP, n(), 12, [_saida_icms_sp("PROD01", r2(D("150000") * f))], False, a2.cnpj),
        ]
        # --- B1: entrada da A1 (grupo), entrada SP grande (gera saldo credor), saida SP
        entrada_grupo = Doc("0", "1", p_a1, intra.num, intra.dia,
                            [_entrada("PROD02", intra.itens[0].vl_item, "1101", D("20"))],
                            True, a1.cnpj)
        b1.docs[m] = [
            entrada_grupo,
            Doc("0", "1", F_SP, n(), 7, [_entrada("INS01", r2(D("500000") * f), "2101", D("7"))],
                True, F_SP.cnpj),
            Doc("1", "0", C_SP, n(), 18, [_saida_icms_sp("PROD02", r2(D("100000") * f))], True, b1.cnpj),
        ]
        # --- Gama filial AM: entrada PE e saida SP com C170
        c_am.docs[m] = [
            Doc("0", "1", F_PE, n(), 8, [_entrada("INS01", r2(D("30000") * f), "2101", D("12"))],
                True, F_PE.cnpj),
            Doc("1", "0", C_SP, n(), 22, [_saida_icms_sp("PROD01", r2(D("200000") * f))], True, c_am.cnpj),
        ]
        # --- Gama matriz SP (so aparece na EFD Contribuicoes): uma venda interna SP
        c_mat.docs[m] = [
            Doc("1", "0", C_SP, n(), 25, [ItemDoc("PROD01", r2(D("10000") * f), "5102", "000", D("18"),
                                                  "50", D("15"), "01", D("1.65"), "01", D("7.6"))],
                True, c_mat.cnpj),
        ]
        # Credito estimulo (E111) e fundo FTI (E116) da A1 e da filial da Gama
        for e, pct in ((a1, D("0.55")), (c_am, D("0.75"))):
            deb = sum((i.icms[1] for d in e.docs[m] if d.ind_oper == "1" for i in d.itens), D(0))
            e.ajustes_ce[m] = r2(deb * pct)
            e.fundo_fti[m] = r2(e.ajustes_ce[m] * D("0.01"))
    return [
        Empresa("Alfa", a1, [a1, a2]),
        Empresa("Beta", b1, [b1]),
        Empresa("Gama", c_mat, [c_mat, c_am], contrib_detalhada=True),
    ]


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------
class Escritor:
    def __init__(self, registros):
        self.registros = registros
        self.linhas: list[str] = []
        self.cont: "OrderedDict[str, int]" = OrderedDict()

    def add(self, reg: str, **valores) -> None:
        if "_lista" in valores:
            vals = [reg] + [fmt(v) for v in valores["_lista"]]
        else:
            campos = self.registros[reg].versoes[0].campos
            desconhecidos = set(valores) - set(campos)
            if desconhecidos:
                raise KeyError(f"{reg}: campos desconhecidos {desconhecidos}")
            vals = [reg]
            for c in campos[1:]:
                v = valores.get(c, "")
                vals.append(fmt(*v) if isinstance(v, tuple) else fmt(v))
        self.linhas.append("|" + "|".join(vals) + "|")
        self.cont[reg] = self.cont.get(reg, 0) + 1

    def raw(self, reg: str, *vals) -> None:
        self.add(reg, _lista=list(vals))

    def qtd_bloco(self, letra: str) -> int:
        return sum(n for r, n in self.cont.items() if r[0] == letra) + 1

    def fechar(self) -> str:
        self.raw("9001", "0")
        regs = list(self.cont)
        n_9900 = len(regs) + 3  # + 9900, 9990, 9999
        for r in regs:
            self.raw("9900", r, str(self.cont[r]))
        self.raw("9900", "9900", str(n_9900))
        self.raw("9900", "9990", "1")
        self.raw("9900", "9999", "1")
        self.raw("9990", str(1 + n_9900 + 2))
        self.raw("9999", str(len(self.linhas) + 1))
        return "\r\n".join(self.linhas) + "\r\n"


def _parts_itens_docs(docs: list[Doc]) -> tuple[list[Part], list[str]]:
    parts, itens = OrderedDict(), OrderedDict()
    for d in docs:
        parts[d.part.cod] = d.part
        for i in d.itens:
            itens[i.cod_item] = True
    return list(parts.values()), list(itens)


def gerar_icms(e: Estab, mes: int, retificadora: bool = False, extra_valor: Decimal | None = None,
               sldo_ant: dict | None = None) -> str:
    sldo_ant = sldo_ant if sldo_ant is not None else {}
    w = Escritor(efd_icms_ipi.REGISTROS)
    docs = list(e.docs[mes])
    if extra_valor:
        docs.append(Doc("1", "0", C_SP, 990000 + mes, 28,
                        [_saida_icms_sp("PROD01", extra_valor)], True, e.cnpj))
    w.add("0000", COD_VER=COD_VER_ICMS, COD_FIN="1" if retificadora else "0",
          DT_INI=dt(1, mes), DT_FIN=dt(ultimo_dia(mes), mes), NOME=e.nome, CNPJ=e.cnpj, UF=e.uf,
          IE=e.ie, COD_MUN=e.cod_mun, SUFRAMA=e.suframa, IND_PERFIL="A", IND_ATIV="0")
    w.raw("0001", "0")
    parts, itens = _parts_itens_docs(docs)
    for p in parts:
        w.add("0150", COD_PART=p.cod, NOME=p.nome, COD_PAIS=p.cod_pais, CNPJ=p.cnpj, IE=p.ie,
              COD_MUN=p.cod_mun, SUFRAMA=p.suframa, END="Rua Sintetica", NUM="1")
    w.add("0190", UNID="UN", DESCR="Unidade")
    for it in ITENS:
        if it.cod in itens:
            w.add("0200", COD_ITEM=it.cod, DESCR_ITEM=it.descr, UNID_INV="UN", TIPO_ITEM=it.tipo_item,
                  COD_NCM=it.ncm)
    w.raw("0990", str(w.qtd_bloco("0")))
    w.raw("C001", "0")
    deb_icms = cred_icms = deb_ipi = cred_ipi = D(0)
    e510 = defaultdict(lambda: [D(0), D(0), D(0)])
    for d in docs:
        it = d.itens
        vl_merc = sum((i.vl_item for i in it), D(0))
        vl_desc = sum((i.vl_desc for i in it), D(0))
        bc_icms = sum((i.icms[0] for i in it), D(0))
        vl_icms = sum((i.icms[1] for i in it), D(0))
        vl_ipi = sum((i.ipi[1] for i in it), D(0))
        vl_pis = sum((i.pis[1] for i in it), D(0))
        vl_cof = sum((i.cofins[1] for i in it), D(0))
        w.add("C100", IND_OPER=d.ind_oper, IND_EMIT=d.ind_emit, COD_PART=d.part.cod, COD_MOD="55",
              COD_SIT=d.cod_sit, SER="1", NUM_DOC=str(d.num), CHV_NFE=d.chave(mes),
              DT_DOC=dt(d.dia, mes), DT_E_S=dt(d.dia, mes), VL_DOC=vl_merc - vl_desc + vl_ipi,
              IND_PGTO="1", VL_DESC=vl_desc, VL_ABAT_NT=D(0), VL_MERC=vl_merc, IND_FRT="9",
              VL_FRT=D(0), VL_SEG=D(0), VL_OUT_DA=D(0), VL_BC_ICMS=bc_icms, VL_ICMS=vl_icms,
              VL_BC_ICMS_ST=D(0), VL_ICMS_ST=D(0), VL_IPI=vl_ipi, VL_PIS=vl_pis, VL_COFINS=vl_cof,
              VL_PIS_ST=D(0), VL_COFINS_ST=D(0))
        if d.com_c170:
            for k, i in enumerate(it, 1):
                w.add("C170", NUM_ITEM=str(k), COD_ITEM=i.cod_item, QTD=(i.qtd, 5), UNID="UN",
                      VL_ITEM=i.vl_item, VL_DESC=i.vl_desc, IND_MOV="0", CST_ICMS=i.cst_icms,
                      CFOP=i.cfop, VL_BC_ICMS=i.icms[0], ALIQ_ICMS=i.aliq_icms, VL_ICMS=i.icms[1],
                      VL_BC_ICMS_ST=D(0), ALIQ_ST=D(0), VL_ICMS_ST=D(0), IND_APUR="0",
                      CST_IPI=i.cst_ipi, VL_BC_IPI=i.ipi[0], ALIQ_IPI=i.aliq_ipi, VL_IPI=i.ipi[1],
                      CST_PIS=i.cst_pis, VL_BC_PIS=i.pis[0], ALIQ_PIS=(i.aliq_pis, 4),
                      VL_PIS=i.pis[1], CST_COFINS=i.cst_cofins, VL_BC_COFINS=i.cofins[0],
                      ALIQ_COFINS=(i.aliq_cofins, 4), VL_COFINS=i.cofins[1], VL_ABAT_NT=D(0))
        grupos = OrderedDict()
        for i in it:
            g = grupos.setdefault((i.cst_icms, i.cfop, i.aliq_icms), [D(0)] * 4)
            g[0] += i.base + i.ipi[1]
            g[1] += i.icms[0]
            g[2] += i.icms[1]
            g[3] += i.ipi[1]
            x = e510[(i.cfop, i.cst_ipi)]
            x[0] += i.base + i.ipi[1]
            x[1] += i.ipi[0]
            x[2] += i.ipi[1]
        for (cst, cfop, aliq), g in grupos.items():
            w.add("C190", CST_ICMS=cst, CFOP=cfop, ALIQ_ICMS=aliq, VL_OPR=g[0], VL_BC_ICMS=g[1],
                  VL_ICMS=g[2], VL_BC_ICMS_ST=D(0), VL_ICMS_ST=D(0), VL_RED_BC=D(0), VL_IPI=g[3])
        if d.ind_oper == "1":
            deb_icms += vl_icms
            deb_ipi += vl_ipi
        else:
            cred_icms += vl_icms
            cred_ipi += vl_ipi
    w.raw("C990", str(w.qtd_bloco("C")))

    # Bloco E
    w.raw("E001", "0")
    w.add("E100", DT_INI=dt(1, mes), DT_FIN=dt(ultimo_dia(mes), mes))
    ant = sldo_ant.get("icms", D(0))
    cred_total = cred_icms + ant
    sld_apurado = max(D(0), deb_icms - cred_total)
    transp = max(D(0), cred_total - deb_icms)
    sldo_ant["icms"] = transp
    # Credito estimulo lancado como DEDUCAO (E110.VL_TOT_DED), limitado ao saldo apurado
    ce = min(e.ajustes_ce.get(mes, D(0)), sld_apurado)
    recolher = sld_apurado - ce
    w.add("E110", VL_TOT_DEBITOS=deb_icms, VL_AJ_DEBITOS=D(0), VL_TOT_AJ_DEBITOS=D(0),
          VL_ESTORNOS_CRED=D(0), VL_TOT_CREDITOS=cred_icms, VL_AJ_CREDITOS=D(0),
          VL_TOT_AJ_CREDITOS=D(0), VL_ESTORNOS_DEB=D(0), VL_SLD_CREDOR_ANT=ant,
          VL_SLD_APURADO=sld_apurado, VL_TOT_DED=ce, VL_ICMS_RECOLHER=recolher,
          VL_SLD_CREDOR_TRANSPORTAR=transp, DEB_ESP=D(0))
    if ce:
        w.add("E111", COD_AJ_APUR=COD_AJ_CREDITO_ESTIMULO,
              DESCR_COMPL_AJ="Credito estimulo (sintetico)", VL_AJ_APUR=ce)
    if recolher:
        w.add("E116", COD_OR="000", VL_OR=recolher, DT_VCTO=dt(10, mes % 12 + 1),
              COD_REC="1234", IND_PROC="", MES_REF=f"{mes:02d}{ANO}")
    if e.fundo_fti.get(mes):
        w.add("E116", COD_OR=COD_OR_FTI, VL_OR=e.fundo_fti[mes], DT_VCTO=dt(10, mes % 12 + 1),
              COD_REC=COD_REC_FTI, TXT_COMPL="Contribuicao ao FTI (sintetico)",
              MES_REF=f"{mes:02d}{ANO}")
    w.add("E500", IND_APUR="0", DT_INI=dt(1, mes), DT_FIN=dt(ultimo_dia(mes), mes))
    for (cfop, cst), x in e510.items():
        w.add("E510", CFOP=cfop, CST_IPI=cst, VL_CONT_IPI=x[0], VL_BC_IPI=x[1], VL_IPI=x[2])
    ant_ipi = sldo_ant.get("ipi", D(0))
    sc = max(D(0), cred_ipi + ant_ipi - deb_ipi)
    sldo_ant["ipi"] = sc
    w.add("E520", VL_SD_ANT_IPI=ant_ipi, VL_DEB_IPI=deb_ipi, VL_CRED_IPI=cred_ipi, VL_OD_IPI=D(0),
          VL_OC_IPI=D(0), VL_SC_IPI=sc, VL_SD_IPI=max(D(0), deb_ipi - cred_ipi - ant_ipi))
    w.raw("E990", str(w.qtd_bloco("E")))
    w.raw("H001", "1")
    w.raw("H990", "2")
    return w.fechar()


def gerar_contrib(emp: Empresa, mes: int) -> str:
    w = Escritor(efd_contrib.REGISTROS)
    m = emp.matriz
    w.add("0000", COD_VER=COD_VER_CONTRIB, TIPO_ESCRIT="0", DT_INI=dt(1, mes),
          DT_FIN=dt(ultimo_dia(mes), mes), NOME=m.nome, CNPJ=m.cnpj, UF=m.uf, COD_MUN=m.cod_mun,
          SUFRAMA=m.suframa, IND_NAT_PJ="00", IND_ATIV="0")
    w.raw("0001", "0")
    w.add("0110", COD_INC_TRIB="1", IND_APRO_CRED="1", COD_TIPO_CONT="2")
    for e in emp.estabs:
        w.add("0140", COD_EST=e.cnpj[8:12], NOME=e.nome, CNPJ=e.cnpj, UF=e.uf, IE=e.ie,
              COD_MUN=e.cod_mun, SUFRAMA=e.suframa)
        parts, itens = _parts_itens_docs(e.docs[mes])
        for p in parts:
            w.add("0150", COD_PART=p.cod, NOME=p.nome, COD_PAIS=p.cod_pais, CNPJ=p.cnpj, IE=p.ie,
                  COD_MUN=p.cod_mun, SUFRAMA=p.suframa, END="Rua Sintetica", NUM="1")
        for it in ITENS:
            if it.cod in itens:
                w.add("0200", COD_ITEM=it.cod, DESCR_ITEM=it.descr, UNID_INV="UN",
                      TIPO_ITEM=it.tipo_item, COD_NCM=it.ncm)
    w.raw("0990", str(w.qtd_bloco("0")))
    w.raw("A001", "1")
    w.raw("A990", "2")
    w.raw("C001", "0")
    pis_grupos = defaultdict(lambda: [D(0), D(0), D(0)])     # aliq -> rec, bc, valor
    cof_grupos = defaultdict(lambda: [D(0), D(0), D(0)])
    nao_trib_pis = defaultdict(lambda: D(0))
    nao_trib_cof = defaultdict(lambda: D(0))
    for e in emp.estabs:
        docs = e.docs[mes]
        w.add("C010", CNPJ=e.cnpj, IND_ESCRI="2" if emp.contrib_detalhada else "1")
        saidas = [(d, i) for d in docs if d.ind_oper == "1" for i in d.itens]
        entradas = [(d, i) for d in docs if d.ind_oper == "0" for i in d.itens]
        if emp.contrib_detalhada:
            for d in docs:
                it = d.itens
                vl_merc = sum((i.vl_item for i in it), D(0))
                vl_ipi = sum((i.ipi[1] for i in it), D(0))
                w.add("C100", IND_OPER=d.ind_oper, IND_EMIT=d.ind_emit, COD_PART=d.part.cod,
                      COD_MOD="55", COD_SIT=d.cod_sit, SER="1", NUM_DOC=str(d.num),
                      CHV_NFE=d.chave(mes), DT_DOC=dt(d.dia, mes), DT_E_S=dt(d.dia, mes),
                      VL_DOC=vl_merc + vl_ipi, IND_PGTO="1", VL_DESC=D(0), VL_ABAT_NT=D(0),
                      VL_MERC=vl_merc, IND_FRT="9", VL_FRT=D(0), VL_SEG=D(0), VL_OUT_DA=D(0),
                      VL_BC_ICMS=sum((i.icms[0] for i in it), D(0)),
                      VL_ICMS=sum((i.icms[1] for i in it), D(0)), VL_BC_ICMS_ST=D(0),
                      VL_ICMS_ST=D(0), VL_IPI=vl_ipi, VL_PIS=sum((i.pis[1] for i in it), D(0)),
                      VL_COFINS=sum((i.cofins[1] for i in it), D(0)), VL_PIS_ST=D(0),
                      VL_COFINS_ST=D(0))
                for k, i in enumerate(it, 1):
                    w.add("C170", NUM_ITEM=str(k), COD_ITEM=i.cod_item, QTD=(i.qtd, 5), UNID="UN",
                          VL_ITEM=i.vl_item, VL_DESC=i.vl_desc, IND_MOV="0", CST_ICMS=i.cst_icms,
                          CFOP=i.cfop, VL_BC_ICMS=i.icms[0], ALIQ_ICMS=i.aliq_icms,
                          VL_ICMS=i.icms[1], CST_IPI=i.cst_ipi, VL_BC_IPI=i.ipi[0],
                          ALIQ_IPI=i.aliq_ipi, VL_IPI=i.ipi[1], CST_PIS=i.cst_pis,
                          VL_BC_PIS=i.pis[0], ALIQ_PIS=(i.aliq_pis, 4), VL_PIS=i.pis[1],
                          CST_COFINS=i.cst_cofins, VL_BC_COFINS=i.cofins[0],
                          ALIQ_COFINS=(i.aliq_cofins, 4), VL_COFINS=i.cofins[1])
        else:
            por_item = OrderedDict()
            for d, i in saidas:
                por_item.setdefault(i.cod_item, []).append(i)
            for cod, lst in por_item.items():
                it = next(x for x in ITENS if x.cod == cod)
                w.add("C180", COD_MOD="55", DT_DOC_INI=dt(1, mes), DT_DOC_FIN=dt(ultimo_dia(mes), mes),
                      COD_ITEM=cod, COD_NCM=it.ncm, VL_TOT_ITEM=sum((i.vl_item for i in lst), D(0)))
                for reg, cst_a, aliq_a, val in (("C181", "cst_pis", "aliq_pis", "pis"),
                                                ("C185", "cst_cofins", "aliq_cofins", "cofins")):
                    g = OrderedDict()
                    for i in lst:
                        x = g.setdefault((getattr(i, cst_a), i.cfop, getattr(i, aliq_a)), [D(0)] * 4)
                        x[0] += i.vl_item
                        x[1] += i.vl_desc
                        x[2] += getattr(i, val)[0]
                        x[3] += getattr(i, val)[1]
                    for (cst, cfop, aliq), x in g.items():
                        sufixo = "PIS" if reg == "C181" else "COFINS"
                        w.add(reg, **{f"CST_{sufixo}": cst, "CFOP": cfop, "VL_ITEM": x[0],
                                      "VL_DESC": x[1], f"VL_BC_{sufixo}": x[2],
                                      f"ALIQ_{sufixo}": (aliq, 4), f"VL_{sufixo}": x[3]})
            por_item_e = OrderedDict()
            for d, i in entradas:
                por_item_e.setdefault(i.cod_item, []).append((d, i))
            for cod, lst in por_item_e.items():
                it = next(x for x in ITENS if x.cod == cod)
                w.add("C190", COD_MOD="55", DT_REF_INI=dt(1, mes), DT_REF_FIN=dt(ultimo_dia(mes), mes),
                      COD_ITEM=cod, COD_NCM=it.ncm,
                      VL_TOT_ITEM=sum((i.vl_item for _, i in lst), D(0)))
                for reg, sufixo, cst_a, aliq_a, val in (
                        ("C191", "PIS", "cst_pis", "aliq_pis", "pis"),
                        ("C195", "COFINS", "cst_cofins", "aliq_cofins", "cofins")):
                    for d, i in lst:
                        w.add(reg, **{"CNPJ_CPF_PART": d.part.cnpj, f"CST_{sufixo}": getattr(i, cst_a),
                                      "CFOP": i.cfop, "VL_ITEM": i.vl_item, "VL_DESC": i.vl_desc,
                                      f"VL_BC_{sufixo}": getattr(i, val)[0],
                                      f"ALIQ_{sufixo}": (getattr(i, aliq_a), 4),
                                      f"VL_{sufixo}": getattr(i, val)[1]})
        for _, i in saidas:
            if i.aliq_pis > 0:
                g = pis_grupos[i.aliq_pis]
                g[0] += i.base
                g[1] += i.pis[0]
                g[2] += i.pis[1]
            else:
                nao_trib_pis[i.cst_pis] += i.base
            if i.aliq_cofins > 0:
                g = cof_grupos[i.aliq_cofins]
                g[0] += i.base
                g[1] += i.cofins[0]
                g[2] += i.cofins[1]
            else:
                nao_trib_cof[i.cst_cofins] += i.base
    w.raw("C990", str(w.qtd_bloco("C")))
    w.raw("D001", "1")
    w.raw("D990", "2")
    w.raw("F001", "1")
    w.raw("F990", "2")
    w.raw("M001", "0")
    for reg_tot, reg_det, grupos, nao_trib, reg_nt, reg_nt_det, suf in (
            ("M200", "M210", pis_grupos, nao_trib_pis, "M400", "M410", "PIS"),
            ("M600", "M610", cof_grupos, nao_trib_cof, "M800", "M810", "COFINS")):
        total = sum((g[2] for g in grupos.values()), D(0))
        w.add(reg_tot, VL_TOT_CONT_NC_PER=total, VL_TOT_CRED_DESC=D(0), VL_TOT_CRED_DESC_ANT=D(0),
              VL_TOT_CONT_NC_DEV=total, VL_RET_NC=D(0), VL_OUT_DED_NC=D(0), VL_CONT_NC_REC=total,
              VL_TOT_CONT_CUM_PER=D(0), VL_RET_CUM=D(0), VL_OUT_DED_CUM=D(0),
              VL_CONT_CUM_REC=D(0), VL_TOT_CONT_REC=total)
        for aliq, g in sorted(grupos.items()):
            cod_cont = "01" if aliq in (D("1.65"), D("7.6")) else "02"
            w.add(reg_det, **{"COD_CONT": cod_cont, "VL_REC_BRT": g[0], "VL_BC_CONT": g[1],
                              f"VL_AJUS_ACRES_BC_{suf}": D(0), f"VL_AJUS_REDUC_BC_{suf}": D(0),
                              "VL_BC_CONT_AJUS": g[1], f"ALIQ_{suf}": (aliq, 4),
                              "VL_CONT_APUR": g[2], "VL_AJUS_ACRES": D(0), "VL_AJUS_REDUC": D(0),
                              "VL_CONT_DIFER": D(0), "VL_CONT_DIFER_ANT": D(0), "VL_CONT_PER": g[2]})
        for cst, v in sorted(nao_trib.items()):
            w.add(reg_nt, **{f"CST_{suf}": cst, "VL_TOT_REC": v})
            w.add(reg_nt_det, NAT_REC="999", VL_REC=v)
    w.raw("M990", str(w.qtd_bloco("M")))
    w.raw("1001", "1")
    w.raw("1990", "2")
    return w.fechar()


def gerar_conjunto(pasta: Path, meses: tuple[int, ...] = (1, 2, 3), retificadora: bool = False,
                   assinatura: bool = False) -> list[Path]:
    """Grava as EFDs sinteticas em ``pasta`` (Latin-1). Retorna os caminhos."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    empresas = montar_cenario(meses)
    gerados: list[Path] = []
    for emp in empresas:
        for e in emp.estabs:
            if e.uf != "AM":
                continue  # EFD ICMS/IPI de estabelecimento fora do AM nao entra no conjunto
            saldos: dict = {}
            for m in meses:
                txt = gerar_icms(e, m, sldo_ant=saldos)
                if assinatura and m == meses[0]:
                    txt += "SBRCAAEPDR\x00\x01ASSINATURA-DIGITAL-SINTETICA|0000|lixo|\r\n"
                p = pasta / f"EFD_ICMS_IPI_{e.cnpj}_{ANO}{m:02d}.txt"
                p.write_bytes(txt.encode("latin-1"))
                gerados.append(p)
        for m in meses:
            p = pasta / f"EFD_CONTRIB_{emp.matriz.cnpj}_{ANO}{m:02d}.txt"
            p.write_bytes(gerar_contrib(emp, m).encode("latin-1"))
            gerados.append(p)
    if retificadora:
        e = empresas[0].estabs[0]
        txt = gerar_icms(e, meses[0], retificadora=True, extra_valor=D("12345.67"))
        p = pasta / f"EFD_ICMS_IPI_{e.cnpj}_{ANO}{meses[0]:02d}_RETIFICADORA.txt"
        p.write_bytes(txt.encode("latin-1"))
        gerados.append(p)
    return gerados


if __name__ == "__main__":  # pragma: no cover
    import sys
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exemplo_sintetico")
    for p in gerar_conjunto(destino, retificadora=True):
        print(p)
