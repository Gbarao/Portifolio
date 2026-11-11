# -*- coding: utf-8 -*-
"""
Leitura das escriturações (EFD ICMS/IPI e EFD-Contribuições).

Cada arquivo é lido UMA vez, linha a linha, sem ser carregado na memória. O
resultado vai para três arquivos Parquet (itens, documentos e registros
analíticos) e para um dicionário de metadados com os totais de controle que a
carga no banco confere depois.

Regras de leitura
-----------------
* Só entradas: documentos com IND_OPER = 0 (C500 da Contribuições não tem
  IND_OPER: o registro só existe para aquisições; C191/C195 entram quando o
  CFOP começa com 1, 2 ou 3).
* Documentos cancelados, denegados ou inutilizados (COD_SIT 02 a 05) são
  contados e descartados: não têm valores.
* EFD Fiscal: o documento entra pelos itens (C170). Quando o C100 não tem
  C170, entra pelo analítico (C190). C500, D100 e D500 entram pelo analítico
  (C590, D190, D590). O C190 de um documento com C170 nunca é somado aos
  itens: vai para a tabela de conferência.
* EFD Contribuições: C170, A170, F100 e os pares PIS/COFINS (C501+C505,
  D101+D105, D501+D505, C191+C195), unidos em uma linha por par.

Os números entre colchetes nos comentários são as posições dos campos no
registro (campo 1 = REG), que coincidem com o índice após o split por "|".
"""

from __future__ import annotations

import hashlib
import os
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import zip_longest

import pyarrow as pa
import pyarrow.parquet as pq

from .leiautes import (ATENCAO, COLUNAS_ANA, COLUNAS_DOCS, COLUNAS_ITENS,
                       CONTRIB, FISCAL, MEDIDAS, MEDIDAS_ANA, MEDIDAS_DOCS,
                       SIT_IGNORAR, TEXTO_ANA, TEXTO_DOCS, TEXTO_ITENS,
                       TRATADOS)

LOTE = 200_000

# Registros cujo texto original é guardado (para mostrar a linha do TXT nas
# conferências). Só são guardadas as linhas dos documentos que entram na base.
REGISTROS_TEXTO = frozenset((
    "A100", "A170", "C100", "C170", "C190", "C191", "C195", "C500", "C501", "C505",
    "C590", "D100", "D101", "D105", "D190", "D500", "D501", "D505", "D590", "F100"))
COLUNAS_TXT = ["registro", "texto", "linha_doc", "linha"]
_POT = (1, 10, 100, 1000, 10_000, 100_000, 1_000_000)

# Maior posição de campo lida em cada registro. Linhas mais curtas são
# completadas com vazio; quando têm menos campos que o mínimo do leiaute, a
# ocorrência é contada como anomalia.
_LE = {
    FISCAL: {"0150": 6, "0200": 8, "C100": 27, "C170": 37, "C190": 11,
             "C500": 28, "C590": 10, "D100": 20, "D190": 8, "D500": 22,
             "D590": 10, "9900": 3},
    CONTRIB: {"0140": 4, "0150": 6, "0200": 8, "A010": 2, "C010": 3,
              "D010": 2, "F010": 2, "A100": 21, "A170": 17, "C100": 27,
              "C170": 37, "C190": 6, "C191": 12, "C195": 12, "C500": 15,
              "C501": 8, "C505": 8, "D100": 20, "D101": 9, "D105": 9,
              "D500": 22, "D501": 8, "D505": 8, "F100": 19, "9900": 3},
}
# Registros que ganharam campos ao longo das versões do leiaute: abaixo, a
# quantidade de campos da versão mais antiga aceita (ex.: o CHV_DOCe do C500).
_MINIMO_HISTORICO = {
    FISCAL: {"C500": 27},
    CONTRIB: {"C500": 14},
}


# ============================================================================
# Utilitários
# ============================================================================

def detectar_encoding(caminho: str) -> str:
    """UTF-8 (com ou sem BOM) quando a amostra decodifica; senão Latin-1."""
    with open(caminho, "rb") as f:
        amostra = f.read(1_000_000)
    if amostra.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as e:
        # corte no meio de um caractere multibyte no fim da amostra não conta
        if e.start >= len(amostra) - 4:
            return "utf-8"
        return "latin-1"


def so_digitos(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit()) if s else ""


def iso(d: str):
    """DDMMAAAA -> AAAA-MM-DD (None quando vazio ou fora do formato)."""
    if len(d) == 8 and d.isdigit():
        return d[4:] + "-" + d[2:4] + "-" + d[:2]
    return None


def _decimal_escalado(s: str, casas: int) -> int:
    t = s.strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return int(Decimal(t).scaleb(casas).to_integral_value(rounding=ROUND_HALF_UP))


_FALTA = object()


class Conversor:
    """Texto numérico do SPED (vírgula decimal) -> inteiro escalado, exato.

    Os mesmos textos se repetem muito dentro de um arquivo ("0,00", alíquotas),
    então cada conversão é guardada em um dicionário de tamanho limitado."""

    __slots__ = ("erros", "_cache")
    _LIMITE = 300_000

    def __init__(self):
        self.erros = 0
        self._cache = {2: {}, 4: {}, 5: {}}

    def esc(self, s: str, casas: int = 2):
        if not s:
            return None
        cache = self._cache[casas]
        v = cache.get(s, _FALTA)
        if v is not _FALTA:
            return v
        v = self._converter(s, casas)
        if len(cache) < self._LIMITE:
            cache[s] = v
        return v

    def _converter(self, s: str, casas: int):
        try:
            i = s.find(",")
            if i < 0:
                return int(s) * _POT[casas]
            d = s[i + 1:]
            if len(d) == casas:
                return int(s[:i] + d)
            if len(d) < casas:
                return int(s[:i] + d) * _POT[casas - len(d)]
            return _decimal_escalado(s, casas)
        except (ValueError, InvalidOperation):
            try:
                return _decimal_escalado(s, casas)
            except (ValueError, InvalidOperation):
                self.erros += 1
                return None


def chave_documento(chave, estab, cod_mod, ser, sub, num_doc, dt_iso, part_doc,
                    part_cod):
    """Identidade do documento, usada para achar repetições e parear as EFDs.

    Com chave eletrônica de 44 dígitos, ela é a identidade. Sem chave, vale o
    conjunto estabelecimento + modelo + série + número + data + participante.
    """
    if len(chave) == 44 and chave.isdigit():
        return "K" + chave
    return "D|" + "|".join((
        estab, cod_mod, ser.strip().lstrip("0"), sub.strip().lstrip("0"),
        num_doc.strip().lstrip("0"), dt_iso or "",
        part_doc or ("COD:" + part_cod)))


class Escritor:
    """Grava linhas em Parquet por lotes e acumula os totais de controle."""

    def __init__(self, caminho, colunas, textos, medidas):
        textos = set(textos)
        self.schema = pa.schema(
            [(c, pa.string() if c in textos else pa.int64()) for c in colunas])
        self.w = pq.ParquetWriter(caminho, self.schema, compression="snappy")
        self.medidas = list(medidas)
        self.idx = [colunas.index(m) for m in self.medidas]
        self.somas = [0] * len(self.medidas)
        self.buf = []
        self.n = 0

    def add(self, linha):
        self.buf.append(linha)
        if len(self.buf) >= LOTE:
            self.descarregar()

    def descarregar(self):
        if not self.buf:
            return
        cols = list(zip(*self.buf))
        for k, i in enumerate(self.idx):
            self.somas[k] += sum(v for v in cols[i] if v is not None)
        self.w.write_table(pa.Table.from_arrays(
            [pa.array(c, type=campo.type) for c, campo in zip(cols, self.schema)],
            schema=self.schema))
        self.n += len(self.buf)
        self.buf = []

    def fechar(self):
        self.descarregar()
        self.w.close()
        return {"n": self.n, "somas": dict(zip(self.medidas, self.somas))}


# ============================================================================
# Inspeção rápida (tipo, empresa, período) sem ler o arquivo inteiro
# ============================================================================

def _eh_data(s):
    return len(s) == 8 and s.isdigit()


def hash_bruto(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def hash_conteudo(caminho: str, encoding: str) -> str:
    """Hash do texto, independente de codificação, BOM e quebra de linha: o
    mesmo conteúdo regravado em UTF-8 ou com LF no lugar de CRLF dá o mesmo
    resultado."""
    h = hashlib.sha256()
    ultimo = "\n"
    with open(caminho, "r", encoding=encoding, errors="replace", newline=None) as f:
        while True:
            bloco = f.read(4 * 1024 * 1024)
            if not bloco:
                break
            h.update(bloco.encode("utf-8"))
            ultimo = bloco[-1]
    if ultimo != "\n":
        h.update(b"\n")
    return h.hexdigest()


def inspecionar(caminho: str) -> dict:
    """Lê o registro 0000 e identifica a escrituração."""
    info = {"caminho": os.path.abspath(caminho),
            "nome_arquivo": os.path.basename(caminho), "tipo": None, "erro": ""}
    try:
        info["tamanho"] = os.path.getsize(caminho)
        info["encoding"] = detectar_encoding(caminho)
        linha0 = None
        with open(caminho, "r", encoding=info["encoding"], errors="replace") as f:
            for _, linha in zip(range(50), f):
                if linha.startswith("|0000|"):
                    linha0 = linha.rstrip("\r\n")
                    break
        if linha0 is None:
            info["erro"] = "Registro 0000 não encontrado: não parece ser um arquivo do SPED."
            return info
        p = linha0.split("|") + [""] * 12
        if p[2][:4] in ("LECD", "LECF"):
            info["erro"] = "É uma ECD/ECF. Esta ferramenta lê EFD ICMS/IPI e EFD-Contribuições."
            return info
        if _eh_data(p[6]) and _eh_data(p[7]):
            # |0000|COD_VER|TIPO_ESCRIT|IND_SIT_ESP|NUM_REC_ANTERIOR|DT_INI|DT_FIN|NOME|CNPJ|UF|...
            info.update(tipo=CONTRIB, cod_ver=p[2], finalidade=p[3], dt_ini=iso(p[6]),
                        dt_fin=iso(p[7]), nome=p[8].strip(), cnpj=so_digitos(p[9]),
                        uf=p[10], ie="")
        elif _eh_data(p[4]) and _eh_data(p[5]):
            # |0000|COD_VER|COD_FIN|DT_INI|DT_FIN|NOME|CNPJ|CPF|UF|IE|...
            info.update(tipo=FISCAL, cod_ver=p[2], finalidade=p[3], dt_ini=iso(p[4]),
                        dt_fin=iso(p[5]), nome=p[6].strip(),
                        cnpj=so_digitos(p[7]) or so_digitos(p[8]), uf=p[9],
                        ie=so_digitos(p[10]))
        else:
            info["erro"] = "Registro 0000 fora do leiaute da EFD ICMS/IPI e da EFD-Contribuições."
            return info
        if not info["cnpj"]:
            info["tipo"] = None
            info["erro"] = "Registro 0000 sem CNPJ/CPF."
            return info
        info["retificadora"] = info["finalidade"] == "1"
        info["periodo"] = info["dt_ini"][:8] + "01"
        info["empresa_raiz"] = info["cnpj"][:8]
        info["hash_bruto"] = hash_bruto(caminho)
        info["hash_conteudo"] = hash_conteudo(caminho, info["encoding"])
    except OSError as e:
        info["erro"] = f"Não foi possível ler o arquivo: {e}"
    return info


def identidade(info: dict) -> tuple:
    """Chave de versão: a mesma escrituração do mesmo período."""
    return (info["tipo"], info["cnpj"], info.get("ie", ""), info["dt_ini"],
            info["dt_fin"])


# ============================================================================
# Leitor
# ============================================================================

_II = {c: i for i, c in enumerate(COLUNAS_ITENS)}
_ID = {c: i for i, c in enumerate(COLUNAS_DOCS)}
_N_ITENS = len(COLUNAS_ITENS)
_N_DOCS = len(COLUNAS_DOCS)


class Leitor:
    def __init__(self, info: dict, pasta: str):
        self.info = info
        self.fonte = info["tipo"]
        self.pasta = pasta
        self.raiz = info["empresa_raiz"]
        self.estab = info["cnpj"] if self.fonte == FISCAL else ""
        self.periodo = info["periodo"]
        self.cv = Conversor()

        self.part = {}        # (cnpj do 0140, COD_PART) -> (nome, cnpj/cpf)
        self.part_flat = {}   # COD_PART -> (nome, cnpj/cpf)
        self.part_por_doc = {}  # cnpj/cpf -> nome (para o C191/C195)
        self.itens = {}       # COD_ITEM -> (descrição, NCM)
        self.estabs = {}      # 0140: cnpj -> nome
        self.escopo = ""
        self.estabs_mov = set()
        self.ind_escri = {}

        self.doc = None
        self.descartes = {"saidas": 0, "situacao": 0, "f100_nao_aquisicao": 0,
                          "c191_c195_saida": 0}
        self.anomalias = {}
        self.exemplos = {}
        self.r9900 = {}

        os.makedirs(pasta, exist_ok=True)
        self.w_itens = Escritor(os.path.join(pasta, "itens.parquet"),
                                COLUNAS_ITENS, TEXTO_ITENS, MEDIDAS)
        self.w_docs = Escritor(os.path.join(pasta, "docs.parquet"),
                               COLUNAS_DOCS, TEXTO_DOCS, MEDIDAS_DOCS)
        self.w_txt = Escritor(os.path.join(pasta, "txt.parquet"), COLUNAS_TXT,
                              ("registro", "texto"), ())
        self._f100_aceito = -1
        self.w_ana = Escritor(os.path.join(pasta, "analitico.parquet"),
                              COLUNAS_ANA, TEXTO_ANA, MEDIDAS_ANA)

        if self.fonte == FISCAL:
            self.handlers = {
                "0150": self.h_0150, "0200": self.h_0200, "9900": self.h_9900,
                "C100": self.h_C100, "C170": self.h_C170, "C190": self.f_C190,
                "C500": self.f_C500, "C590": self.f_C590,
                "D100": self.h_D100, "D190": self.f_D190,
                "D500": self.h_D500, "D590": self.f_D590,
            }
        else:
            self.handlers = {
                "0140": self.c_0140, "0150": self.h_0150, "0200": self.h_0200,
                "9900": self.h_9900,
                "A010": self.c_x010, "C010": self.c_x010, "D010": self.c_x010,
                "F010": self.c_x010,
                "A100": self.c_A100, "A170": self.c_A170,
                "C100": self.h_C100, "C170": self.h_C170,
                "C190": self.c_C190, "C191": self.c_C191, "C195": self.c_C195,
                "C500": self.c_C500, "C501": self.c_C501, "C505": self.c_C505,
                "D100": self.h_D100, "D101": self.c_D101, "D105": self.c_D105,
                "D500": self.h_D500, "D501": self.c_D501, "D505": self.c_D505,
                "F100": self.c_F100,
            }

    # ------------------------------------------------------------ auxiliares
    def anomalia(self, tipo: str, exemplo: str = ""):
        self.anomalias[tipo] = self.anomalias.get(tipo, 0) + 1
        if exemplo:
            ex = self.exemplos.setdefault(tipo, [])
            if len(ex) < 5 and exemplo not in ex:
                ex.append(exemplo)

    def participante(self, cod: str):
        if not cod:
            return ("", "")
        achado = self.part.get((self.estab, cod)) or self.part_flat.get(cod)
        if achado is None:
            self.anomalia("COD_PART sem cadastro no 0150", cod)
            return ("", "")
        return achado

    def item(self, cod: str):
        if not cod:
            return ("", "")
        achado = self.itens.get(cod)
        if achado is None:
            self.anomalia("COD_ITEM sem cadastro no 0200", cod)
            return ("", "")
        return achado

    def confere_cfop(self, cfop: str, reg: str):
        if not (len(cfop) == 4 and cfop.isdigit()):
            self.anomalia(f"CFOP fora do formato de 4 dígitos ({reg})", cfop)

    # ---------------------------------------------------------------- bloco 0
    def h_0150(self, p, n):
        """|0150|COD_PART[2]|NOME[3]|COD_PAIS[4]|CNPJ[5]|CPF[6]|..."""
        cod = p[2]
        doc = so_digitos(p[5]) or so_digitos(p[6])
        par = (p[3].strip(), doc)
        self.part[(self.escopo, cod)] = par
        self.part_flat.setdefault(cod, par)
        if doc:
            self.part_por_doc.setdefault(doc, par[0])

    def h_0200(self, p, n):
        """|0200|COD_ITEM[2]|DESCR_ITEM[3]|...|COD_NCM[8]|..."""
        self.itens[p[2]] = (p[3].strip(), p[8])

    def h_9900(self, p, n):
        """|9900|REG_BLC[2]|QTD_REG_BLC[3]|"""
        try:
            self.r9900[p[2]] = int(p[3])
        except ValueError:
            self.anomalia("Registro 9900 com quantidade inválida", p[2])

    def c_0140(self, p, n):
        """|0140|COD_EST[2]|NOME[3]|CNPJ[4]|...  (Contribuições)"""
        self.escopo = so_digitos(p[4])
        self.estabs[self.escopo] = p[3].strip()

    def c_x010(self, p, n):
        """|A010/C010/D010/F010|CNPJ[2]|...  estabelecimento dos documentos seguintes"""
        self.fechar_doc()
        self.estab = so_digitos(p[2])
        self.estabs_mov.add(self.estab)
        if p[1] == "C010":
            self.ind_escri[self.estab] = p[3]

    # ------------------------------------------------------------ documentos
    def abrir_doc(self, reg, n, cod_mod, cod_sit, ser, sub, num_doc, chave,
                  dt_doc, dt_e_s, part_cod, cab):
        nome, pdoc = self.participante(part_cod)
        dt_iso = iso(dt_doc)
        if dt_doc and dt_iso is None:
            self.anomalia(f"Data fora do formato DDMMAAAA ({reg})", dt_doc)
        chave = chave.strip()
        if chave and reg != "A100" and not (len(chave) == 44 and chave.isdigit()):
            self.anomalia(f"Chave eletrônica fora do formato de 44 dígitos ({reg})", chave)
        did = chave_documento(chave, self.estab, cod_mod or reg, ser, sub,
                              num_doc, dt_iso, pdoc, part_cod)
        comuns = (("fonte", self.fonte), ("empresa_raiz", self.raiz),
                  ("estab_cnpj", self.estab), ("periodo", self.periodo),
                  ("cod_mod", cod_mod), ("cod_sit", cod_sit), ("ser", ser),
                  ("sub", sub), ("num_doc", num_doc), ("chave", chave),
                  ("dt_doc", dt_iso), ("dt_e_s", iso(dt_e_s)),
                  ("part_cod", part_cod), ("part_doc", pdoc),
                  ("part_nome", nome), ("doc_id", did))
        base = [None] * _N_ITENS
        linha_doc = [None] * _N_DOCS
        for k, v in comuns:
            base[_II[k]] = v
            linha_doc[_ID[k]] = v
        base[_II["linha_doc"]] = n
        linha_doc[_ID["registro"]] = reg
        linha_doc[_ID["linha_doc"]] = n
        cv = self.cv.esc
        for k, v in cab.items():
            linha_doc[_ID[k]] = cv(v)
        self.doc = {"reg": reg, "n": n, "base": base, "linha_doc": linha_doc,
                    "itens": [], "ana": [], "pis": [], "cofins": [], "txt": []}

    def _entrada_valida(self, ind_oper, cod_sit) -> bool:
        if ind_oper != "0":
            self.descartes["saidas"] += 1
            return False
        if cod_sit in SIT_IGNORAR:
            self.descartes["situacao"] += 1
            return False
        return True

    def h_C100(self, p, n):
        """|C100|IND_OPER[2]|IND_EMIT[3]|COD_PART[4]|COD_MOD[5]|COD_SIT[6]|SER[7]|
        NUM_DOC[8]|CHV_NFE[9]|DT_DOC[10]|DT_E_S[11]|VL_DOC[12]|...|VL_BC_ICMS[21]|
        VL_ICMS[22]|VL_BC_ICMS_ST[23]|VL_ICMS_ST[24]|VL_IPI[25]|VL_PIS[26]|
        VL_COFINS[27]|...   (mesmo leiaute nas duas escriturações)"""
        self.fechar_doc()
        sit = p[6].zfill(2)
        if not self._entrada_valida(p[2], sit):
            return
        self.abrir_doc("C100", n, p[5], sit, p[7], "", p[8], p[9], p[10], p[11],
                       p[4], {"vl_doc": p[12], "vl_bc_icms": p[21],
                              "vl_icms": p[22], "vl_bc_icms_st": p[23],
                              "vl_icms_st": p[24], "vl_ipi": p[25],
                              "vl_pis": p[26], "vl_cofins": p[27]})

    def h_C170(self, p, n):
        """|C170|NUM_ITEM[2]|COD_ITEM[3]|DESCR_COMPL[4]|QTD[5]|UNID[6]|VL_ITEM[7]|
        VL_DESC[8]|IND_MOV[9]|CST_ICMS[10]|CFOP[11]|COD_NAT[12]|VL_BC_ICMS[13]|
        ALIQ_ICMS[14]|VL_ICMS[15]|VL_BC_ICMS_ST[16]|ALIQ_ST[17]|VL_ICMS_ST[18]|
        IND_APUR[19]|CST_IPI[20]|COD_ENQ[21]|VL_BC_IPI[22]|ALIQ_IPI[23]|VL_IPI[24]|
        CST_PIS[25]|VL_BC_PIS[26]|ALIQ_PIS[27]|QUANT_BC_PIS[28]|ALIQ_PIS_QUANT[29]|
        VL_PIS[30]|CST_COFINS[31]|VL_BC_COFINS[32]|ALIQ_COFINS[33]|
        QUANT_BC_COFINS[34]|ALIQ_COFINS_QUANT[35]|VL_COFINS[36]|COD_CTA[37]|"""
        d = self.doc
        if d is None or d["reg"] != "C100":
            return
        cv = self.cv.esc
        I = _II
        r = d["base"].copy()
        cod = p[3]
        descr, ncm = self.item(cod)
        cfop = p[11]
        self.confere_cfop(cfop, "C170")
        r[I["registro"]] = "C170"
        r[I["linha"]] = n
        r[I["num_item"]] = p[2]
        r[I["cod_item"]] = cod
        r[I["descr_item"]] = descr
        r[I["ncm"]] = ncm
        r[I["qtd_e5"]] = cv(p[5], 5)
        r[I["unid"]] = p[6]
        r[I["vl_item"]] = cv(p[7])
        r[I["vl_desc"]] = cv(p[8])
        r[I["cst_icms"]] = p[10]
        r[I["cfop"]] = cfop
        r[I["vl_bc_icms"]] = cv(p[13])
        r[I["aliq_icms_e2"]] = cv(p[14])
        r[I["vl_icms"]] = cv(p[15])
        r[I["vl_bc_icms_st"]] = cv(p[16])
        r[I["vl_icms_st"]] = cv(p[18])
        r[I["vl_ipi"]] = cv(p[24])
        r[I["cst_pis"]] = p[25]
        r[I["vl_bc_pis"]] = cv(p[26])
        r[I["aliq_pis_e4"]] = cv(p[27], 4)
        r[I["vl_pis"]] = cv(p[30])
        r[I["cst_cofins"]] = p[31]
        r[I["vl_bc_cofins"]] = cv(p[32])
        r[I["aliq_cofins_e4"]] = cv(p[33], 4)
        r[I["vl_cofins"]] = cv(p[36])
        r[I["cod_cta"]] = p[37]
        d["itens"].append(r)

    def h_D100(self, p, n):
        """|D100|IND_OPER[2]|IND_EMIT[3]|COD_PART[4]|COD_MOD[5]|COD_SIT[6]|SER[7]|
        SUB[8]|NUM_DOC[9]|CHV_CTE[10]|DT_DOC[11]|DT_A_P[12]|TP_CT-e[13]|
        CHV_CTE_REF[14]|VL_DOC[15]|VL_DESC[16]|IND_FRT[17]|VL_SERV[18]|
        VL_BC_ICMS[19]|VL_ICMS[20]|...   (mesmo início nas duas escriturações)"""
        self.fechar_doc()
        sit = p[6].zfill(2)
        if not self._entrada_valida(p[2], sit):
            return
        self.abrir_doc("D100", n, p[5], sit, p[7], p[8], p[9], p[10], p[11],
                       p[12], p[4], {"vl_doc": p[15], "vl_bc_icms": p[19],
                                     "vl_icms": p[20]})

    def h_D500(self, p, n):
        """|D500|IND_OPER[2]|IND_EMIT[3]|COD_PART[4]|COD_MOD[5]|COD_SIT[6]|SER[7]|
        SUB[8]|NUM_DOC[9]|DT_DOC[10]|DT_A_P[11]|VL_DOC[12]|...|VL_BC_ICMS[18]|
        VL_ICMS[19]|COD_INF[20]|VL_PIS[21]|VL_COFINS[22]|..."""
        self.fechar_doc()
        sit = p[6].zfill(2)
        if not self._entrada_valida(p[2], sit):
            return
        self.abrir_doc("D500", n, p[5], sit, p[7], p[8], p[9], "", p[10], p[11],
                       p[4], {"vl_doc": p[12], "vl_bc_icms": p[18],
                              "vl_icms": p[19], "vl_pis": p[21],
                              "vl_cofins": p[22]})

    # ------------------------------------------------- EFD Fiscal: analíticos
    def _analitico(self, pai, reg, n, cst, cfop, aliq, opr, bc, icms, bc_st, st,
                   red, ipi):
        d = self.doc
        if d is None or d["reg"] != pai:
            return
        cv = self.cv.esc
        self.confere_cfop(cfop, reg)
        d["ana"].append((reg, n, cst, cfop, cv(aliq), cv(opr), cv(bc), cv(icms),
                         cv(bc_st) if bc_st is not None else None,
                         cv(st) if st is not None else None,
                         cv(red), cv(ipi) if ipi is not None else None))

    def f_C190(self, p, n):
        """|C190|CST_ICMS[2]|CFOP[3]|ALIQ_ICMS[4]|VL_OPR[5]|VL_BC_ICMS[6]|VL_ICMS[7]|
        VL_BC_ICMS_ST[8]|VL_ICMS_ST[9]|VL_RED_BC[10]|VL_IPI[11]|COD_OBS[12]|"""
        self._analitico("C100", "C190", n, p[2], p[3], p[4], p[5], p[6], p[7],
                        p[8], p[9], p[10], p[11])

    def f_C500(self, p, n):
        """|C500|IND_OPER[2]|IND_EMIT[3]|COD_PART[4]|COD_MOD[5]|COD_SIT[6]|SER[7]|
        SUB[8]|COD_CONS[9]|NUM_DOC[10]|DT_DOC[11]|DT_E_S[12]|VL_DOC[13]|...|
        VL_BC_ICMS[19]|VL_ICMS[20]|VL_BC_ICMS_ST[21]|VL_ICMS_ST[22]|COD_INF[23]|
        VL_PIS[24]|VL_COFINS[25]|TP_LIGACAO[26]|COD_GRUPO_TENSAO[27]|CHV_DOCe[28]|...
        (EFD Fiscal)"""
        self.fechar_doc()
        sit = p[6].zfill(2)
        if not self._entrada_valida(p[2], sit):
            return
        self.abrir_doc("C500", n, p[5], sit, p[7], p[8], p[10], p[28], p[11],
                       p[12], p[4], {"vl_doc": p[13], "vl_bc_icms": p[19],
                                     "vl_icms": p[20], "vl_bc_icms_st": p[21],
                                     "vl_icms_st": p[22], "vl_pis": p[24],
                                     "vl_cofins": p[25]})

    def f_C590(self, p, n):
        """|C590|CST_ICMS[2]|CFOP[3]|ALIQ_ICMS[4]|VL_OPR[5]|VL_BC_ICMS[6]|VL_ICMS[7]|
        VL_BC_ICMS_ST[8]|VL_ICMS_ST[9]|VL_RED_BC[10]|COD_OBS[11]|"""
        self._analitico("C500", "C590", n, p[2], p[3], p[4], p[5], p[6], p[7],
                        p[8], p[9], p[10], None)

    def f_D190(self, p, n):
        """|D190|CST_ICMS[2]|CFOP[3]|ALIQ_ICMS[4]|VL_OPR[5]|VL_BC_ICMS[6]|VL_ICMS[7]|
        VL_RED_BC[8]|COD_OBS[9]|"""
        self._analitico("D100", "D190", n, p[2], p[3], p[4], p[5], p[6], p[7],
                        None, None, p[8], None)

    def f_D590(self, p, n):
        """|D590|CST_ICMS[2]|CFOP[3]|ALIQ_ICMS[4]|VL_OPR[5]|VL_BC_ICMS[6]|VL_ICMS[7]|
        VL_BC_ICMS_UF[8]|VL_ICMS_UF[9]|VL_RED_BC[10]|COD_OBS[11]|"""
        self._analitico("D500", "D590", n, p[2], p[3], p[4], p[5], p[6], p[7],
                        None, None, p[10], None)

    # ------------------------------------------------- EFD Contribuições
    def c_A100(self, p, n):
        """|A100|IND_OPER[2]|IND_EMIT[3]|COD_PART[4]|COD_SIT[5]|SER[6]|SUB[7]|
        NUM_DOC[8]|CHV_NFSE[9]|DT_DOC[10]|DT_EXE_SERV[11]|VL_DOC[12]|IND_PGTO[13]|
        VL_DESC[14]|VL_BC_PIS[15]|VL_PIS[16]|VL_BC_COFINS[17]|VL_COFINS[18]|
        VL_PIS_RET[19]|VL_COFINS_RET[20]|VL_ISS[21]|"""
        self.fechar_doc()
        sit = p[5].zfill(2)
        if not self._entrada_valida(p[2], sit):
            return
        self.abrir_doc("A100", n, "", sit, p[6], p[7], p[8], p[9], p[10], p[11],
                       p[4], {"vl_doc": p[12], "vl_pis": p[16],
                              "vl_cofins": p[18], "vl_iss": p[21]})

    def c_A170(self, p, n):
        """|A170|NUM_ITEM[2]|COD_ITEM[3]|DESCR_COMPL[4]|VL_ITEM[5]|VL_DESC[6]|
        NAT_BC_CRED[7]|IND_ORIG_CRED[8]|CST_PIS[9]|VL_BC_PIS[10]|ALIQ_PIS[11]|
        VL_PIS[12]|CST_COFINS[13]|VL_BC_COFINS[14]|ALIQ_COFINS[15]|VL_COFINS[16]|
        COD_CTA[17]|COD_CCUS[18]|"""
        d = self.doc
        if d is None or d["reg"] != "A100":
            return
        cv = self.cv.esc
        I = _II
        r = d["base"].copy()
        descr, ncm = self.item(p[3])
        r[I["registro"]] = "A170"
        r[I["linha"]] = n
        r[I["num_item"]] = p[2]
        r[I["cod_item"]] = p[3]
        r[I["descr_item"]] = descr
        r[I["ncm"]] = ncm
        r[I["vl_item"]] = cv(p[5])
        r[I["vl_desc"]] = cv(p[6])
        r[I["nat_bc_cred"]] = p[7]
        r[I["cst_pis"]] = p[9]
        r[I["vl_bc_pis"]] = cv(p[10])
        r[I["aliq_pis_e4"]] = cv(p[11], 4)
        r[I["vl_pis"]] = cv(p[12])
        r[I["cst_cofins"]] = p[13]
        r[I["vl_bc_cofins"]] = cv(p[14])
        r[I["aliq_cofins_e4"]] = cv(p[15], 4)
        r[I["vl_cofins"]] = cv(p[16])
        r[I["cod_cta"]] = p[17]
        d["itens"].append(r)

    def c_C190(self, p, n):
        """|C190|COD_MOD[2]|DT_REF_INI[3]|DT_REF_FIN[4]|COD_ITEM[5]|COD_NCM[6]|
        EX_IPI[7]|VL_TOT_ITEM[8]|   (Contribuições: consolidação de NF-e por item)"""
        self.fechar_doc()
        base = [None] * _N_ITENS
        descr, ncm = self.item(p[5])
        for k, v in (("fonte", self.fonte), ("empresa_raiz", self.raiz),
                     ("estab_cnpj", self.estab), ("periodo", self.periodo),
                     ("cod_mod", p[2]), ("cod_item", p[5]),
                     ("descr_item", descr), ("ncm", p[6] or ncm),
                     ("linha_doc", n)):
            base[_II[k]] = v
        self.doc = {"reg": "C190", "n": n, "base": base, "linha_doc": None,
                    "itens": [], "ana": [], "pis": [], "cofins": [], "txt": []}

    def _c19x(self, p, n, lado):
        """|C191/C195|CNPJ_CPF_PART[2]|CST[3]|CFOP[4]|VL_ITEM[5]|VL_DESC[6]|
        VL_BC[7]|ALIQ[8]|QUANT_BC[9]|ALIQ_QUANT[10]|VL_PIS ou VL_COFINS[11]|
        COD_CTA[12]|"""
        d = self.doc
        if d is None or d["reg"] != "C190":
            return
        cv = self.cv.esc
        self.confere_cfop(p[4], p[1])
        d[lado].append({"n": n, "chave": (so_digitos(p[2]), p[4]), "cst": p[3],
                        "vl_item": cv(p[5]), "vl_desc": cv(p[6]), "bc": cv(p[7]),
                        "aliq": cv(p[8], 4), "vl": cv(p[11]), "cta": p[12],
                        "nat": None})

    def c_C191(self, p, n):
        self._c19x(p, n, "pis")

    def c_C195(self, p, n):
        self._c19x(p, n, "cofins")

    def c_C500(self, p, n):
        """|C500|COD_PART[2]|COD_MOD[3]|COD_SIT[4]|SER[5]|SUB[6]|NUM_DOC[7]|DT_DOC[8]|
        DT_ENT[9]|VL_DOC[10]|VL_ICMS[11]|COD_INF[12]|VL_PIS[13]|VL_COFINS[14]|
        CHV_DOCe[15]|   (Contribuições: só aquisições, não há IND_OPER)"""
        self.fechar_doc()
        sit = p[4].zfill(2)
        if sit in SIT_IGNORAR:
            self.descartes["situacao"] += 1
            return
        self.abrir_doc("C500", n, p[3], sit, p[5], p[6], p[7], p[15], p[8], p[9],
                       p[2], {"vl_doc": p[10], "vl_icms": p[11],
                              "vl_pis": p[13], "vl_cofins": p[14]})

    def _detalhe(self, pai, lado, n, cst, vl_item, nat, bc, aliq, vl, cta,
                 chave=None):
        d = self.doc
        if d is None or d["reg"] != pai:
            return
        cv = self.cv.esc
        d[lado].append({"n": n, "chave": chave, "cst": cst, "vl_item": cv(vl_item),
                        "vl_desc": None, "bc": cv(bc), "aliq": cv(aliq, 4),
                        "vl": cv(vl), "cta": cta, "nat": nat})

    def c_C501(self, p, n):
        """|C501|CST_PIS[2]|VL_ITEM[3]|NAT_BC_CRED[4]|VL_BC_PIS[5]|ALIQ_PIS[6]|
        VL_PIS[7]|COD_CTA[8]|"""
        self._detalhe("C500", "pis", n, p[2], p[3], p[4], p[5], p[6], p[7], p[8])

    def c_C505(self, p, n):
        """|C505|CST_COFINS[2]|VL_ITEM[3]|NAT_BC_CRED[4]|VL_BC_COFINS[5]|
        ALIQ_COFINS[6]|VL_COFINS[7]|COD_CTA[8]|"""
        self._detalhe("C500", "cofins", n, p[2], p[3], p[4], p[5], p[6], p[7], p[8])

    def c_D101(self, p, n):
        """|D101|IND_NAT_FRT[2]|VL_ITEM[3]|CST_PIS[4]|NAT_BC_CRED[5]|VL_BC_PIS[6]|
        ALIQ_PIS[7]|VL_PIS[8]|COD_CTA[9]|"""
        self._detalhe("D100", "pis", n, p[4], p[3], p[5], p[6], p[7], p[8], p[9],
                      chave=p[2])

    def c_D105(self, p, n):
        """|D105|IND_NAT_FRT[2]|VL_ITEM[3]|CST_COFINS[4]|NAT_BC_CRED[5]|
        VL_BC_COFINS[6]|ALIQ_COFINS[7]|VL_COFINS[8]|COD_CTA[9]|"""
        self._detalhe("D100", "cofins", n, p[4], p[3], p[5], p[6], p[7], p[8],
                      p[9], chave=p[2])

    def c_D501(self, p, n):
        """|D501|CST_PIS[2]|VL_ITEM[3]|NAT_BC_CRED[4]|VL_BC_PIS[5]|ALIQ_PIS[6]|
        VL_PIS[7]|COD_CTA[8]|"""
        self._detalhe("D500", "pis", n, p[2], p[3], p[4], p[5], p[6], p[7], p[8])

    def c_D505(self, p, n):
        """|D505|CST_COFINS[2]|VL_ITEM[3]|NAT_BC_CRED[4]|VL_BC_COFINS[5]|
        ALIQ_COFINS[6]|VL_COFINS[7]|COD_CTA[8]|"""
        self._detalhe("D500", "cofins", n, p[2], p[3], p[4], p[5], p[6], p[7], p[8])

    def c_F100(self, p, n):
        """|F100|IND_OPER[2]|COD_PART[3]|COD_ITEM[4]|DT_OPER[5]|VL_OPER[6]|CST_PIS[7]|
        VL_BC_PIS[8]|ALIQ_PIS[9]|VL_PIS[10]|CST_COFINS[11]|VL_BC_COFINS[12]|
        ALIQ_COFINS[13]|VL_COFINS[14]|NAT_BC_CRED[15]|IND_ORIG_CRED[16]|COD_CTA[17]|
        COD_CCUS[18]|DESC_DOC_OPER[19]|
        IND_OPER = 0: aquisição, custo, despesa ou encargo (o que interessa aqui)."""
        self.fechar_doc()
        if p[2] != "0":
            self.descartes["f100_nao_aquisicao"] += 1
            return
        self._f100_aceito = n
        cv = self.cv.esc
        I = _II
        nome, pdoc = self.participante(p[3])
        descr, ncm = self.item(p[4])
        r = [None] * _N_ITENS
        for k, v in (("fonte", self.fonte), ("registro", "F100"), ("linha", n),
                     ("linha_doc", n), ("empresa_raiz", self.raiz),
                     ("estab_cnpj", self.estab), ("periodo", self.periodo),
                     ("dt_doc", iso(p[5])), ("part_cod", p[3]),
                     ("part_doc", pdoc), ("part_nome", nome),
                     ("cod_item", p[4]),
                     ("descr_item", descr or p[19].strip()), ("ncm", ncm),
                     ("vl_item", cv(p[6])), ("cst_pis", p[7]),
                     ("vl_bc_pis", cv(p[8])), ("aliq_pis_e4", cv(p[9], 4)),
                     ("vl_pis", cv(p[10])), ("cst_cofins", p[11]),
                     ("vl_bc_cofins", cv(p[12])),
                     ("aliq_cofins_e4", cv(p[13], 4)),
                     ("vl_cofins", cv(p[14])), ("nat_bc_cred", p[15]),
                     ("cod_cta", p[17])):
            r[I[k]] = v
        self.w_itens.add(r)

    # ---------------------------------------------------------- fechamento
    @staticmethod
    def _pares(pis, cofins, por_chave):
        """Casa cada detalhe de PIS com o de COFINS do mesmo documento."""
        if not por_chave:
            return list(zip_longest(pis, cofins))
        grupos = {}
        for lado, lista in ((0, pis), (1, cofins)):
            for x in lista:
                grupos.setdefault(x["chave"], ([], []))[lado].append(x)
        pares = []
        for a, b in grupos.values():
            pares.extend(zip_longest(a, b))
        return pares

    def _linhas_pares(self, d, rotulo, por_chave):
        I = _II
        linhas = []
        for k, (pi, co) in enumerate(self._pares(d["pis"], d["cofins"], por_chave), 1):
            x = pi or co
            r = d["base"].copy()
            r[I["registro"]] = rotulo
            r[I["linha"]] = x["n"]
            r[I["num_item"]] = str(k)
            r[I["vl_item"]] = x["vl_item"]
            r[I["vl_desc"]] = x["vl_desc"]
            r[I["nat_bc_cred"]] = x["nat"]
            r[I["cod_cta"]] = x["cta"]
            if pi:
                r[I["cst_pis"]] = pi["cst"]
                r[I["vl_bc_pis"]] = pi["bc"]
                r[I["aliq_pis_e4"]] = pi["aliq"]
                r[I["vl_pis"]] = pi["vl"]
            if co:
                r[I["cst_cofins"]] = co["cst"]
                r[I["vl_bc_cofins"]] = co["bc"]
                r[I["aliq_cofins_e4"]] = co["aliq"]
                r[I["vl_cofins"]] = co["vl"]
            if rotulo == "C191+C195":
                doc, cfop = x["chave"]
                if cfop[:1] not in ("1", "2", "3"):
                    self.descartes["c191_c195_saida"] += 1
                    continue
                r[I["part_doc"]] = doc
                r[I["part_nome"]] = self.part_por_doc.get(doc, "")
                r[I["cfop"]] = cfop
            linhas.append(r)
        return linhas

    def _ratear_iss(self, d):
        """VL_ISS do A100 distribuído entre os A170 na proporção do VL_ITEM,
        em centavos inteiros; o último item recebe o resíduo, então a soma dos
        itens é exatamente o VL_ISS do documento."""
        total = d["linha_doc"][_ID["vl_iss"]]
        itens = d["itens"]
        if total is None or not itens:
            return
        i_item, i_iss = _II["vl_item"], _II["vl_iss"]
        base = sum((r[i_item] or 0) for r in itens)
        if base <= 0:
            itens[0][i_iss] = total
            for r in itens[1:]:
                r[i_iss] = 0
            return
        acumulado = 0
        for r in itens[:-1]:
            parcela = (2 * total * (r[i_item] or 0) + base) // (2 * base)
            r[i_iss] = parcela
            acumulado += parcela
        itens[-1][i_iss] = total - acumulado

    def fechar_doc(self):
        d = self.doc
        if d is None:
            return
        self.doc = None
        for registro, texto, linha in d["txt"]:
            self.w_txt.add([registro, texto, d["n"], linha])
        reg = d["reg"]
        I = _II
        if self.fonte == FISCAL:
            for a in d["ana"]:
                self.w_ana.add([a[0], a[2], a[3], a[1], d["n"], a[4], a[5], a[6],
                                a[7], a[8], a[9], a[10], a[11]])
            if reg == "C100" and d["itens"]:
                linhas = d["itens"]
            else:
                linhas = []
                for a in d["ana"]:
                    r = d["base"].copy()
                    r[I["registro"]] = a[0]
                    r[I["linha"]] = a[1]
                    r[I["cst_icms"]] = a[2]
                    r[I["cfop"]] = a[3]
                    r[I["aliq_icms_e2"]] = a[4]
                    r[I["vl_opr"]] = a[5]
                    r[I["vl_bc_icms"]] = a[6]
                    r[I["vl_icms"]] = a[7]
                    r[I["vl_bc_icms_st"]] = a[8]
                    r[I["vl_icms_st"]] = a[9]
                    r[I["vl_red_bc"]] = a[10]
                    r[I["vl_ipi"]] = a[11]
                    linhas.append(r)
        elif reg == "C100":
            linhas = d["itens"]
        elif reg == "A100":
            self._ratear_iss(d)
            linhas = d["itens"]
        elif reg == "C500":
            linhas = self._linhas_pares(d, "C501+C505", False)
        elif reg == "D100":
            linhas = self._linhas_pares(d, "D101+D105", True)
        elif reg == "D500":
            linhas = self._linhas_pares(d, "D501+D505", False)
        else:  # C190 da Contribuições (consolidação por item)
            linhas = self._linhas_pares(d, "C191+C195", True)
        for r in linhas:
            self.w_itens.add(r)
        if d["linha_doc"] is not None:
            d["linha_doc"][_ID["n_itens"]] = len(linhas)
            self.w_docs.add(d["linha_doc"])

    # ---------------------------------------------------------------- leitura
    def ler(self) -> dict:
        t0 = time.time()
        caminho = self.info["caminho"]
        handlers = self.handlers
        le = _LE[self.fonte]
        minimo = _MINIMO_HISTORICO[self.fonte]
        contagem = {}
        campos = {}
        fora = 0
        n = 0
        with open(caminho, "r", encoding=self.info["encoding"], errors="replace",
                  newline="") as f:
            for n, linha in enumerate(f, 1):
                linha = linha.rstrip("\r\n")
                if linha[:1] != "|":
                    if linha.strip():
                        fora += 1
                    continue
                reg = linha[1:5]
                contagem[reg] = contagem.get(reg, 0) + 1
                h = handlers.get(reg)
                if h is None:
                    continue
                p = linha.split("|")
                qtd = len(p) - 2
                cr = campos.setdefault(reg, {})
                cr[qtd] = cr.get(qtd, 0) + 1
                falta = le.get(reg, 0) + 1 - len(p)
                if falta > 0:
                    p.extend([""] * falta)
                    esperado = minimo.get(reg, le[reg])
                    if qtd < esperado:
                        self.anomalia(f"Registro {reg} com menos campos que o "
                                      f"leiaute (esperado ao menos {esperado})",
                                      f"linha {n}: {qtd} campos")
                h(p, n)
                if reg in REGISTROS_TEXTO:
                    d = self.doc
                    if d is not None:
                        d["txt"].append((reg, linha, n))
                    elif reg == "F100" and self._f100_aceito == n:
                        self.w_txt.add([reg, linha, n, n])
        self.fechar_doc()

        if fora:
            self.anomalias["Linhas que não começam com '|'"] = fora
        if self.cv.erros:
            self.anomalias["Campos numéricos com conteúdo inválido"] = self.cv.erros

        divergencias_9900 = {r: (q, contagem.get(r, 0))
                             for r, q in self.r9900.items()
                             if contagem.get(r, 0) != q}
        tratados = set(TRATADOS[self.fonte]) | set(handlers)
        atencao = {r: {"linhas": contagem[r], "descricao": desc}
                   for r, desc in ATENCAO[self.fonte].items() if contagem.get(r)}

        meta = dict(self.info)
        meta.update(
            linhas=n,
            contagem=contagem,
            campos_por_registro={r: {str(k): v for k, v in c.items()}
                                 for r, c in campos.items()},
            tem_9900=bool(self.r9900),
            divergencias_9900={r: list(v) for r, v in divergencias_9900.items()},
            registros_tratados=sorted(r for r in contagem if r in tratados),
            registros_atencao=atencao,
            descartes=self.descartes,
            anomalias=self.anomalias,
            exemplos_anomalias=self.exemplos,
            estabelecimentos=self.estabs,
            estabs_com_movimento=sorted(self.estabs_mov),
            ind_escri=self.ind_escri,
            controle={"itens": self.w_itens.fechar(),
                      "docs": self.w_docs.fechar(),
                      "analitico": self.w_ana.fechar(),
                      "txt": self.w_txt.fechar()},
            pasta=self.pasta,
            segundos=round(time.time() - t0, 2),
        )
        return meta


def processar_arquivo(info: dict, pasta: str) -> dict:
    """Ponto de entrada (também usado pelos processos paralelos)."""
    try:
        return Leitor(info, pasta).ler()
    except Exception as e:  # o erro volta ao processo principal como dado
        meta = dict(info)
        meta["erro"] = f"Falha na leitura: {type(e).__name__}: {e}"
        return meta
