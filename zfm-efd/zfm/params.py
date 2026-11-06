"""Tabelas de parametros (SPEC secao 6): CSV editaveis na tela ou no Excel.

- Modelos (sem dados reais) em params/; copias de trabalho em data/params/.
- CSV com separador ';', decimal com virgula, UTF-8 com BOM (abre direto no Excel).
- Valores iniciais sao HIPOTESES para o usuario validar.
- Percentuais em % (ex.: 11,3 = 11,3%); fatores em fracao (ex.: 0,55).
"""
from __future__ import annotations

import datetime as _dt
import io
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from . import cfop as _cfop
from .config import RAIZ_PROJETO, pasta_dados

PASTA_MODELOS = RAIZ_PROJETO / "params"


def pasta_params() -> Path:
    p = pasta_dados() / "params"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True)
class Tabela:
    nome: str
    titulo: str
    colunas: dict[str, str]          # coluna -> tipo: texto | bool | num | int
    chave: tuple[str, ...]
    ajuda: str


TABELAS: dict[str, Tabela] = {t.nome: t for t in [
    Tabela("param_empresas", "Empresas",
           {"raiz_cnpj": "texto", "razao_social": "texto", "nome_curto": "texto",
            "incluir_na_analise": "bool", "observacao": "texto"},
           ("raiz_cnpj",),
           "Uma linha por empresa (raiz do CNPJ). 'Nome curto' aparece nas telas. "
           "Desmarque 'incluir' para tirar a empresa da análise."),
    Tabela("param_produtos", "Produtos",
           {"raiz_cnpj": "texto", "cod_item": "texto", "ncm": "texto", "descricao": "texto",
            "incentivado": "bool", "tipo_bem": "texto", "aliq_tipi_2023": "num",
            "aliq_tipi_2026": "num", "produzido_zfm_2024": "bool", "eh_tic": "bool",
            "ipi_protegido": "bool", "nivel_credito_estimulo": "num", "ce_100_em_2023": "bool",
            "fonte": "texto"},
           ("raiz_cnpj", "cod_item"),
           "Uma linha por item (0200). tipo_bem: final, capital, intermediario ou informatica. "
           "Alíquotas TIPI e nível de crédito estímulo em %. Sem TIPI preenchida, o benefício "
           "de IPI do item fica zero e aparece alerta."),
    Tabela("param_aliquotas_cenario", "Alíquotas por cenário",
           {"cenario": "texto", "ano": "int", "aliq_cbs": "num", "aliq_ibs": "num",
            "fator_icms": "num", "fator_cp_entrada": "num", "aplica_cp_450": "bool",
            "ipi_protegido_override": "texto", "aliq_contrib_art457": "num", "fonte": "texto"},
           ("cenario", "ano"),
           "Alíquotas efetivas do ano em %. fator_icms: fração do ICMS que ainda existe no ano "
           "(ADCT art. 128). ipi_protegido_override: vazio = usar a tabela de produtos; "
           "'nao' = nenhum produto protegido."),
    Tabela("param_codigos_ajuste_icms", "Códigos de ajuste do ICMS",
           {"codigo": "texto", "registro": "texto", "classe": "texto", "descricao": "texto",
            "regra_automatica": "texto", "revisado": "bool"},
           ("codigo", "registro"),
           "Classes: credito_estimulo, credito_presumido_entrada, fundo_FTI, fundo_UEA, "
           "fundo_FMPES, outros_beneficios, outros. Preenchida automaticamente a partir das "
           "EFDs; marque 'revisado' ao conferir."),
    Tabela("param_aliquotas_regime_geral", "Regime geral (fora da ZFM)",
           {"tributo": "texto", "aliquota": "num", "observacao": "texto"},
           ("tributo",),
           "Alíquotas do contrafactual 'fora da ZFM', em %."),
    Tabela("param_municipios_zfm", "Municípios da ZFM",
           {"cod_ibge": "texto", "nome": "texto", "observacao": "texto"},
           ("cod_ibge",),
           "Municípios da área da Zona Franca (código IBGE de 7 dígitos)."),
    Tabela("param_cfops", "CFOPs",
           {"cfop": "texto", "categoria": "texto", "eh_receita": "bool", "automatico": "bool"},
           ("cfop",),
           "Classificação dos CFOPs encontrados nas EFDs. 'eh_receita' define o que conta "
           "como receita de venda. Ao editar, desmarque 'automatico'."),
    Tabela("param_regras_entradas", "Tratamento das entradas (pós-reforma)",
           {"origem": "texto", "tratamento_cbs": "texto", "tratamento_ibs": "texto",
            "base_cp_447": "bool", "base_cp_449": "bool", "observacao": "texto"},
           ("origem",),
           "Como cada origem de entrada é tratada na simulação: tributada, aliquota_zero ou "
           "suspensa. base_cp_447/449: entra na base dos créditos presumidos de entrada."),
    Tabela("param_teses", "Teses",
           {"tese_id": "texto", "descricao": "texto", "raiz_cnpj": "texto", "tributo": "texto",
            "tipo_efeito": "texto", "parametro": "num", "vigencia_ini": "texto",
            "vigencia_fim": "texto", "status": "texto"},
           ("tese_id",),
           "tributo: ICMS, IPI, PIS, COFINS. tipo_efeito: valor_fixo_mensal (parametro em R$/mês), "
           "credito_adicional (R$/mês), reduz_base (% da receita incentivada × alíquota do regime "
           "geral), reduz_aliquota (p.p. sobre a receita incentivada). Vigência AAAA-MM. "
           "raiz_cnpj vazio ou 'todas' = todas as empresas."),
    Tabela("param_premissas", "Premissas",
           {"chave": "texto", "valor": "texto", "descricao": "texto"},
           ("chave",),
           "Premissas gerais dos cálculos."),
]}

# ---------------------------------------------------------------------------
# Valores iniciais (hipoteses). Fontes registradas na coluna 'fonte'/'observacao'.
# ---------------------------------------------------------------------------
_FONTE_BASE = ("CBS 11,3%: TCU, out/2026 (alíquota de referência 2027); IBS 18,7%: premissa "
               "da Resolução CGIBS 14/2026 para projeção de arrecadação")
_FONTE_BAIXO = "Teto conjunto de 26,5% (LC 214/2025): CBS 8,8% + IBS 17,7% (divisão usada pelo CGIBS)"
_FONTE_ALTO = "Sensibilidade: cenário base + 1 p.p. no IBS (hipótese, sem fonte oficial)"
_FONTE_ADV = "Cenário base sem créditos presumidos do art. 450 e sem IPI protegido"
_CENARIOS = {"base": (11.3, 18.7, _FONTE_BASE), "baixo": (8.8, 17.7, _FONTE_BAIXO),
             "alto": (11.3, 19.7, _FONTE_ALTO), "adverso": (11.3, 18.7, _FONTE_ADV)}
_FATOR_ICMS = {2027: 1.0, 2028: 1.0, 2029: 0.9, 2030: 0.8, 2031: 0.7, 2032: 0.6, 2033: 0.0}


def montar_aliquotas(refs: pd.DataFrame, atual: pd.DataFrame | None = None,
                     reducao_cbs: float = 0.1) -> pd.DataFrame:
    """Gera as linhas cenario x ano (2027-2033) a partir das aliquotas de REFERENCIA.

    refs: cenario, cbs_referencia, ibs_referencia, aplica_cp_450, ipi_protegido_override, fonte.
    Mantem fator_icms, fator_cp_entrada e aliq_contrib_art457 ja editados em ``atual``.
    Regras: 2027-2028 CBS = ref − reducao, IBS = 0 (teste neutro); 2029-2032 IBS = ref ×
    (1 − fator_icms); 2033 = referencia cheia.
    """
    linhas = []
    for r in refs.itertuples():
        for ano, f_pad in _FATOR_ICMS.items():
            ant = None
            if atual is not None and not atual.empty:
                m = atual[(atual.cenario == r.cenario) & (atual.ano == ano)]
                ant = m.iloc[0] if len(m) else None
            f = float(ant.fator_icms) if ant is not None and pd.notna(ant.fator_icms) else f_pad
            fcp = float(ant.fator_cp_entrada) if ant is not None and pd.notna(ant.fator_cp_entrada) \
                else round(1 - f, 4)
            c457 = float(ant.aliq_contrib_art457) if ant is not None and pd.notna(ant.aliq_contrib_art457) else 0.0
            cbs = float(r.cbs_referencia) if pd.notna(r.cbs_referencia) else None
            ibs = float(r.ibs_referencia) if pd.notna(r.ibs_referencia) else None
            if ano <= 2028:
                a_cbs = None if cbs is None else round(cbs - reducao_cbs, 4)
                a_ibs = 0.0
                obs = (" | 2027-2028: CBS reduzida em 0,1 p.p.; IBS-teste de 0,1% compensável "
                       "com a CBS tratado como neutro")
            else:
                a_cbs = cbs
                a_ibs = None if ibs is None else round(ibs * (1 - f), 4)
                obs = " | IBS do ano = referência × (1 − fator_icms) (aproximação)" if ano < 2033 else ""
            linhas.append({
                "cenario": r.cenario, "ano": ano, "aliq_cbs": a_cbs, "aliq_ibs": a_ibs,
                "fator_icms": f, "fator_cp_entrada": fcp, "aplica_cp_450": bool(r.aplica_cp_450),
                "ipi_protegido_override": r.ipi_protegido_override or "",
                "aliq_contrib_art457": c457, "fonte": (r.fonte or "") + obs})
    return pd.DataFrame(linhas)


def _refs_padrao() -> pd.DataFrame:
    return pd.DataFrame([{"cenario": c, "cbs_referencia": cbs, "ibs_referencia": ibs,
                          "aplica_cp_450": c != "adverso",
                          "ipi_protegido_override": "nao" if c == "adverso" else "", "fonte": fonte}
                         for c, (cbs, ibs, fonte) in _CENARIOS.items()])


def _modelo_aliquotas() -> pd.DataFrame:
    return montar_aliquotas(_refs_padrao())


def aliquotas_referencia() -> pd.DataFrame:
    """Referencias por cenario lidas da tabela anual (ano 2033 = referencia cheia)."""
    a = carregar("param_aliquotas_cenario")
    linhas = []
    for c, g in a.groupby("cenario", sort=False):
        g = g.set_index("ano")
        ref = g.loc[2033] if 2033 in g.index else g.iloc[-1]
        fonte = str(ref.fonte).split(" | ")[0]
        linhas.append({"cenario": c, "cbs_referencia": ref.aliq_cbs, "ibs_referencia": ref.aliq_ibs,
                       "aplica_cp_450": bool(ref.aplica_cp_450),
                       "ipi_protegido_override": ref.ipi_protegido_override, "fonte": fonte})
    return pd.DataFrame(linhas)


def aplicar_referencias(refs: pd.DataFrame) -> pd.DataFrame:
    refs = refs.dropna(subset=["cenario"])
    refs = refs[refs["cenario"].astype(str).str.strip() != ""]
    novo = montar_aliquotas(refs, carregar("param_aliquotas_cenario"),
                            premissa_num("reducao_cbs_2027_2028", 0.1))
    salvar("param_aliquotas_cenario", novo)
    return novo


_PREMISSAS = [
    ("ano_base", "2026", "Ano das EFDs usadas como base (YTD)."),
    ("base_cbs_ibs", "liquida_sem_tributos",
     "Base da simulação: 'liquida_sem_tributos' = VL_ITEM − VL_DESC − ICMS − PIS − COFINS "
     "(ICMS por item estimado pela proporção ICMS/valor do CFOP no mês); 'valor_liquido' = "
     "VL_ITEM − VL_DESC."),
    ("anualizacao", "meses_observados_mais_media",
     "Ano simulado = meses observados de 2026 + média mensal nos meses sem dado (= média × 12)."),
    ("rateio_produto_uf", "proporcao_c190_por_cfop",
     "Saídas sem destinatário por item (C180/C181): destino rateado pela proporção do C190 + "
     "0150 da EFD ICMS/IPI no mesmo estabelecimento, mês e CFOP."),
    ("alocacao_credito_estimulo", "receita_incentivada",
     "Crédito estímulo e fundos alocados aos produtos pela receita incentivada do "
     "estabelecimento no mês."),
    ("ordem_deducao_ibs", "debito-creditos-cp447_449-cp450",
     "Débito − créditos − CP entradas (447/449) → aplica p_ibs_450 sobre o saldo devedor "
     "atribuível aos incentivados. CONFERIR na Resolução CGIBS / NT 2025.002."),
    ("prazo_cp_anos", "5", "Prazo para usar crédito presumido (art. 452)."),
    ("nivel_apuracao_cbs_ibs", "raiz", "Apuração de CBS/IBS por raiz do CNPJ."),
    ("tolerancia_conciliacao", "1,00", "Tolerância das conciliações, em R$."),
    ("cst_ipi_isento", "52", "CSTs de IPI de saída considerados isenção ZFM (separar por ;)."),
    ("ipi_sem_cst_assume_isento", "sim",
     "Saídas sem CST de IPI por item (C181): produto incentivado é tratado como isento."),
    ("aliq_pis_zfm_validas", "0,65;1,3;0", "Alíquotas de PIS aceitas nas saídas incentivadas (Q9)."),
    ("aliq_cofins_zfm_validas", "3;6;0", "Alíquotas de COFINS aceitas nas saídas incentivadas (Q9)."),
    ("beneficio_entradas_no_total", "nao", "Benefícios nas entradas entram no total? (informativo)"),
    ("reducao_cbs_2027_2028", "0,1",
     "Redução da CBS em 2027-2028, em p.p. (IBS-teste de 0,1% compensável com a CBS)."),
    ("limite_tipi_ipi", "6,5",
     "TIPI (%) a partir da qual o IPI é mantido para o produto da ZFM (art. 454); abaixo dela o "
     "crédito presumido de CBS é o maior (art. 450)."),
    ("p_cbs_450_ipi_zerado", "6", "Crédito presumido de CBS (art. 450), % da venda: produto com TIPI "
     "abaixo do limite, produzido na ZFM em 2024 e não TIC."),
    ("p_cbs_450_demais", "2", "Crédito presumido de CBS (art. 450), % da venda: demais produtos."),
    ("p_ibs_450_final", "55", "Crédito presumido de IBS (art. 450), % do saldo devedor: bens de consumo final."),
    ("p_ibs_450_capital", "75", "Idem, bens de capital."),
    ("p_ibs_450_intermediario", "90,25", "Idem, bens intermediários."),
    ("p_ibs_450_informatica_ou_ce100", "100",
     "Idem, bens de informática ou produto com crédito estímulo de 100% até 2023."),
    ("cp447_sul_sudeste_exceto_es", "7,5",
     "Crédito presumido de IBS (art. 447), % das compras com alíquota zero de Sul/Sudeste exceto ES."),
    ("cp447_demais_e_es", "13,5", "Idem, compras de Norte, Nordeste, Centro-Oeste e ES."),
    ("cp449", "7,5", "Crédito presumido de IBS (art. 449), % das compras de intermediários da ZFM."),
]

_MODELOS: dict[str, pd.DataFrame] = {
    "param_aliquotas_cenario": _modelo_aliquotas(),
    "param_aliquotas_regime_geral": pd.DataFrame([
        {"tributo": "PIS", "aliquota": 1.65, "observacao": "Não cumulativo (Lei 10.637/2002)"},
        {"tributo": "COFINS", "aliquota": 7.6, "observacao": "Não cumulativa (Lei 10.833/2003)"},
    ]),
    "param_municipios_zfm": pd.DataFrame([
        {"cod_ibge": "1302603", "nome": "Manaus", "observacao": ""},
        {"cod_ibge": "1303536", "nome": "Presidente Figueiredo", "observacao": "conferir código IBGE"},
        {"cod_ibge": "1303569", "nome": "Rio Preto da Eva", "observacao": "conferir código IBGE"},
    ]),
    "param_regras_entradas": pd.DataFrame([
        {"origem": "nacional_fora_zfm", "tratamento_cbs": "aliquota_zero",
         "tratamento_ibs": "aliquota_zero", "base_cp_447": True, "base_cp_449": False,
         "observacao": "Art. 445 (alíquota zero) e art. 447 (CP de IBS 7,5% / 13,5%)"},
        {"origem": "zfm", "tratamento_cbs": "aliquota_zero", "tratamento_ibs": "aliquota_zero",
         "base_cp_447": False, "base_cp_449": True,
         "observacao": "Arts. 448/451; CP de 7,5% do art. 449 sobre intermediários"},
        {"origem": "am_fora_zfm", "tratamento_cbs": "tributada", "tratamento_ibs": "tributada",
         "base_cp_447": False, "base_cp_449": False, "observacao": "Amazonas fora da área da ZFM"},
        {"origem": "importacao", "tratamento_cbs": "suspensa", "tratamento_ibs": "suspensa",
         "base_cp_447": False, "base_cp_449": False, "observacao": "Art. 443 (suspensão)"},
        {"origem": "servicos", "tratamento_cbs": "tributada", "tratamento_ibs": "tributada",
         "base_cp_447": False, "base_cp_449": False, "observacao": "Serviços tomados (A100/F100)"},
    ]),
    "param_premissas": pd.DataFrame(_PREMISSAS, columns=["chave", "valor", "descricao"]),
}

# ---------------------------------------------------------------------------
# Leitura / gravacao
# ---------------------------------------------------------------------------
_SIM = {"sim", "s", "true", "1", "verdadeiro", "x", "yes"}


def _para_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return False
    return str(v).strip().lower() in _SIM


def _para_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace("%", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def normalizar(nome: str, df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas e tipos da tabela (colunas extras sao descartadas)."""
    t = TABELAS[nome]
    df = df.copy()
    for c in t.colunas:
        if c not in df.columns:
            df[c] = None
    df = df[list(t.colunas)]
    for c, tipo in t.colunas.items():
        if tipo == "bool":
            df[c] = df[c].map(_para_bool).astype(bool)
        elif tipo == "num":
            df[c] = pd.to_numeric(df[c].map(_para_num), errors="coerce")
        elif tipo == "int":
            df[c] = pd.to_numeric(df[c].map(_para_num), errors="coerce").astype("Int64")
        else:
            df[c] = df[c].map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v))
                              else str(v).strip()).astype(object)
    df = df.dropna(how="all")
    chave = list(t.chave)
    vazias = df[chave].apply(lambda s: s.astype(str).str.strip().isin(["", "<NA>", "nan"])).all(axis=1)
    return df[~vazias].drop_duplicates(subset=chave, keep="last").reset_index(drop=True)


def _para_csv(nome: str, df: pd.DataFrame) -> str:
    t = TABELAS[nome]
    out = df.copy()
    for c, tipo in t.colunas.items():
        if tipo == "bool":
            out[c] = out[c].map(lambda v: "sim" if v else "nao")
    buf = io.StringIO()
    out.to_csv(buf, sep=";", decimal=",", index=False)
    return buf.getvalue()


def caminho(nome: str) -> Path:
    return pasta_params() / f"{nome}.csv"


def carregar(nome: str) -> pd.DataFrame:
    p = caminho(nome)
    if not p.exists():
        modelo = PASTA_MODELOS / f"{nome}.csv"
        if modelo.exists():
            shutil.copyfile(modelo, p)
        else:
            df = _MODELOS.get(nome, pd.DataFrame(columns=list(TABELAS[nome].colunas)))
            salvar(nome, df, registrar=False)
    df = pd.read_csv(p, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df = normalizar(nome, df)
    if nome == "param_premissas":  # premissas criadas em versoes novas entram com o valor padrao
        faltam = [x for x in _PREMISSAS if x[0] not in set(df["chave"])]
        if faltam:
            df = pd.concat([df, pd.DataFrame(faltam, columns=["chave", "valor", "descricao"])],
                           ignore_index=True)
    return df


def salvar(nome: str, df: pd.DataFrame, registrar: bool = True) -> None:
    df = normalizar(nome, df)
    caminho(nome).write_bytes(_para_csv(nome, df).encode("utf-8-sig"))
    if registrar:
        with open(pasta_params() / "historico_alteracoes.csv", "a", encoding="utf-8-sig") as f:
            f.write(f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S};{nome};{len(df)} linhas\n")


def importar_csv(nome: str, conteudo: bytes) -> pd.DataFrame:
    """Le um CSV editado no Excel (';' ou ',' como separador)."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sep = ";" if texto.count(";") >= texto.count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    faltam = [c for c in TABELAS[nome].chave if c not in df.columns]
    if faltam:
        raise ValueError(f"O arquivo não tem as colunas obrigatórias: {', '.join(faltam)}.")
    return normalizar(nome, df)


def exportar_csv(nome: str, df: pd.DataFrame) -> bytes:
    return _para_csv(nome, normalizar(nome, df)).encode("utf-8-sig")


def premissa(con_ou_df, chave: str, padrao: str = "") -> str:
    df = con_ou_df if isinstance(con_ou_df, pd.DataFrame) else carregar("param_premissas")
    s = df.loc[df["chave"] == chave, "valor"]
    return str(s.iloc[0]) if len(s) else padrao


def premissa_num(chave: str, padrao: float, df: pd.DataFrame | None = None) -> float:
    v = _para_num(premissa(df if df is not None else None, chave, ""))
    return padrao if v is None else v


def premissa_lista_num(chave: str) -> list[float]:
    return [x for x in (_para_num(p) for p in premissa(None, chave, "").split(";")) if x is not None]


# ---------------------------------------------------------------------------
# Preenchimento a partir das EFDs
# ---------------------------------------------------------------------------
_PALAVRAS = [
    (r"\bFTI\b|FOMENTO AO TURISMO|TURISMO E INTERIORIZA", "fundo_FTI", "FTI"),
    (r"\bUEA\b|UNIVERSIDADE DO ESTADO", "fundo_UEA", "UEA"),
    (r"FMPES|MICRO E PEQUENA|PEQUENAS EMPRESAS", "fundo_FMPES", "FMPES"),
    (r"EST[IÍ]MULO", "credito_estimulo", "ESTIMULO"),
    (r"PRESUMID", "credito_presumido_entrada", "PRESUMIDO"),
]
# Codigos citados em Resolucoes GSEFAZ (conferir na versao vigente da tabela 5.1.1 do AM)
_CODIGOS_CONHECIDOS = {"AM040001": "credito_estimulo", "AM040014": "credito_estimulo"}


def classificar_codigo(codigo: str, registro: str, texto: str) -> tuple[str, str]:
    """(classe, regra) para um codigo de ajuste encontrado na EFD."""
    t = (texto or "").upper()
    for padrao, classe, rotulo in _PALAVRAS:
        if re.search(padrao, t):
            return classe, f"descrição na EFD contém '{rotulo}'"
    c = (codigo or "").strip().upper()
    if c in _CODIGOS_CONHECIDOS:
        return _CODIGOS_CONHECIDOS[c], "código citado em Resolução GSEFAZ (conferir)"
    if registro == "E111" and len(c) == 8 and c[:2] == "AM" and c[2] == "0" and c[3] == "4":
        return "credito_estimulo", "dedução do ICMS próprio no AM (4º caractere = 4); conferir"
    if registro == "E111" and len(c) == 8 and c[2] == "0" and c[3] == "2":
        return "outros_beneficios", "outro crédito do ICMS próprio (4º caractere = 2); conferir"
    return "outros", "sem regra"


def preencher_a_partir_das_efds(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Acrescenta linhas novas (sem apagar edicoes do usuario). Retorna quantas por tabela."""
    novos: dict[str, int] = {}

    def mesclar(nome: str, novas: pd.DataFrame) -> None:
        atual = carregar(nome)
        chave = list(TABELAS[nome].chave)
        if novas.empty:
            novos[nome] = 0
            return
        novas = normalizar(nome, novas)
        k_atual = set(map(tuple, atual[chave].astype(str).values))
        mask = [tuple(map(str, r)) not in k_atual for r in novas[chave].values]
        add = novas[mask]
        novos[nome] = len(add)
        if len(add):
            salvar(nome, pd.concat([atual, add], ignore_index=True))

    from .empresas import empresas as _emp
    e = _emp(con)
    mesclar("param_empresas", pd.DataFrame({
        "raiz_cnpj": e["raiz"], "razao_social": e["razao_social"],
        "nome_curto": e["razao_social"].map(lambda s: " ".join(str(s).split()[:2])),
        "incluir_na_analise": e["qtd_estab_am"] > 0,
        "observacao": e["qtd_estab_am"].map(lambda n: "" if n else "sem estabelecimento no AM"),
    }) if not e.empty else pd.DataFrame())

    cfops = con.execute("""
        SELECT DISTINCT CFOP FROM (
            SELECT CFOP FROM raw_icms_c190 UNION ALL SELECT CFOP FROM raw_icms_c170
            UNION ALL SELECT CFOP FROM raw_contrib_c181 UNION ALL SELECT CFOP FROM raw_contrib_c191
            UNION ALL SELECT CFOP FROM raw_contrib_c170) WHERE CFOP IS NOT NULL""").fetchall()
    linhas = []
    for (c,) in cfops:
        cat, rec = _cfop.classificar(c)
        linhas.append({"cfop": c, "categoria": cat, "eh_receita": rec, "automatico": True})
    mesclar("param_cfops", pd.DataFrame(linhas))
    sincronizar(con)  # categorias de CFOP sao usadas abaixo (v_saidas_item)

    cods = con.execute("""
        SELECT COD_AJ_APUR AS codigo, 'E111' AS registro, string_agg(DISTINCT DESCR_COMPL_AJ, ' | ')
        FROM raw_icms_e111 JOIN arquivos USING (arquivo_id) WHERE ativo GROUP BY 1
        UNION ALL
        SELECT coalesce(COD_REC, COD_OR), 'E116', string_agg(DISTINCT coalesce(TXT_COMPL, ''), ' | ')
        FROM raw_icms_e116 JOIN arquivos USING (arquivo_id) WHERE ativo GROUP BY 1
    """).fetchall()
    linhas = []
    for cod, reg, txt in cods:
        classe, regra = classificar_codigo(cod, reg, txt)
        linhas.append({"codigo": cod, "registro": reg, "classe": classe,
                       "descricao": (txt or "")[:200], "regra_automatica": regra, "revisado": False})
    mesclar("param_codigos_ajuste_icms", pd.DataFrame(linhas))

    itens = con.execute("""
        WITH it AS (
            SELECT a.raiz, r.COD_ITEM, max(r.COD_NCM) AS ncm, max(r.DESCR_ITEM) AS descr,
                   max(r.TIPO_ITEM) AS tipo_item
            FROM raw_icms_0200 r JOIN arquivos a USING (arquivo_id) WHERE a.ativo GROUP BY 1, 2
            UNION ALL
            SELECT a.raiz, r.COD_ITEM, max(r.COD_NCM), max(r.DESCR_ITEM), max(r.TIPO_ITEM)
            FROM raw_contrib_0200 r JOIN arquivos a USING (arquivo_id) WHERE a.ativo GROUP BY 1, 2
        ), prod AS (
            SELECT DISTINCT raiz, COD_ITEM FROM v_saidas_item
            WHERE categoria_cfop = 'venda_producao'
        )
        SELECT it.raiz, it.COD_ITEM, max(ncm), max(descr), max(tipo_item),
               bool_or(prod.COD_ITEM IS NOT NULL)
        FROM it LEFT JOIN prod ON prod.raiz = it.raiz AND prod.COD_ITEM = it.COD_ITEM
        GROUP BY 1, 2
    """).fetchall()
    linhas = []
    for raiz, cod, ncm, descr, tipo_item, vende_prod in itens:
        linhas.append({
            "raiz_cnpj": raiz, "cod_item": cod, "ncm": ncm or "", "descricao": descr or "",
            "incentivado": bool(vende_prod),
            "tipo_bem": "intermediario" if tipo_item == "06" else "final",
            "aliq_tipi_2023": None, "aliq_tipi_2026": None,
            "produzido_zfm_2024": bool(vende_prod), "eh_tic": False, "ipi_protegido": False,
            "nivel_credito_estimulo": None, "ce_100_em_2023": False,
            "fonte": "automático (EFD): incentivado = vendido com CFOP de produção própria"})
    mesclar("param_produtos", pd.DataFrame(linhas))
    return novos


# ---------------------------------------------------------------------------
# Sincronizacao com o banco (as visoes usam as tabelas param_*)
# ---------------------------------------------------------------------------
def criar_tabelas_vazias(con: duckdb.DuckDBPyConnection) -> None:
    tipos = {"texto": "VARCHAR", "bool": "BOOLEAN", "num": "DOUBLE", "int": "INTEGER"}
    for t in TABELAS.values():
        cols = ", ".join(f'"{c}" {tipos[tp]}' for c, tp in t.colunas.items())
        con.execute(f"CREATE TABLE IF NOT EXISTS {t.nome} ({cols})")


def sincronizar(con: duckdb.DuckDBPyConnection) -> None:
    """Copia os CSV de parametros para o banco local (tabelas param_*)."""
    criar_tabelas_vazias(con)
    for nome in TABELAS:
        df = carregar(nome)
        tmp = f"_tmp_{nome}"
        con.register(tmp, df)
        try:
            con.execute(f"DELETE FROM {nome}")
            if len(df):
                cols = ", ".join(f'"{c}"' for c in TABELAS[nome].colunas)
                con.execute(f"INSERT INTO {nome} ({cols}) SELECT {cols} FROM {tmp}")
        finally:
            con.unregister(tmp)


def gravar_modelos(destino: Path = PASTA_MODELOS) -> None:
    """Gera os CSV modelo (sem dados reais) da pasta params/."""
    destino.mkdir(parents=True, exist_ok=True)
    for nome, t in TABELAS.items():
        df = _MODELOS.get(nome, pd.DataFrame(columns=list(t.colunas)))
        (destino / f"{nome}.csv").write_bytes(exportar_csv(nome, df))


# ---------------------------------------------------------------------------
# Resumo legivel de TODAS as premissas adotadas (aba "Premissas e alíquotas")
# ---------------------------------------------------------------------------
def resumo_premissas() -> pd.DataFrame:
    linhas: list[dict] = []

    def add(grupo, premissa, valor, onde, fundamento=""):
        linhas.append({"grupo": grupo, "premissa": premissa, "valor_adotado": valor,
                       "onde_alterar": onde, "fundamento_fonte": fundamento})

    def pct(v):
        return "-" if v is None or pd.isna(v) else f"{float(v):g}%".replace(".", ",")

    refs = aliquotas_referencia()
    for r in refs.itertuples():
        add("Alíquotas CBS/IBS", f"Cenário {r.cenario}: referência CBS / IBS",
            f"{pct(r.cbs_referencia)} / {pct(r.ibs_referencia)}"
            + ("" if r.aplica_cp_450 else " · sem CP do art. 450")
            + (" · sem IPI protegido" if str(r.ipi_protegido_override).lower() in ("nao", "não") else ""),
            "Parâmetros > Premissas e alíquotas", r.fonte)
    a = carregar("param_aliquotas_cenario")
    if not a.empty:
        f = a[a.cenario == a.cenario.iloc[0]].set_index("ano")
        add("Transição", "Fator do ICMS por ano (fração que ainda existe)",
            " · ".join(f"{ano}: {v:g}".replace(".", ",") for ano, v in f["fator_icms"].items()),
            "Parâmetros > Alíquotas por cenário", "ADCT art. 128 (redução de 10% a 40% em 2029-2032)")
        add("Transição", "Fator dos créditos presumidos de entrada (arts. 447/449)",
            " · ".join(f"{ano}: {v:g}".replace(".", ",") for ano, v in f["fator_cp_entrada"].items()),
            "Parâmetros > Alíquotas por cenário", "Inicial = proporção do IBS no ano (conferir art. 474)")
        add("Transição", "Contribuição estadual (art. 457)",
            " · ".join(f"{ano}: {pct(v)}" for ano, v in f["aliq_contrib_art457"].items()),
            "Parâmetros > Alíquotas por cenário", "LC 214/2025 art. 457 — preencher para sensibilidade")
    for r in carregar("param_aliquotas_regime_geral").itertuples():
        add("Regime geral (fora da ZFM)", r.tributo, pct(r.aliquota), "Parâmetros > Regime geral", r.observacao)
    for r in carregar("param_regras_entradas").itertuples():
        add("Entradas pós-reforma", f"Origem {r.origem}",
            f"CBS: {r.tratamento_cbs} · IBS: {r.tratamento_ibs}"
            + (" · base do CP 447" if r.base_cp_447 else "") + (" · base do CP 449" if r.base_cp_449 else ""),
            "Parâmetros > Tratamento das entradas", r.observacao)
    for r in carregar("param_premissas").itertuples():
        add("Premissas de cálculo", r.chave, r.valor, "Parâmetros > Premissas", r.descricao)
    mun = carregar("param_municipios_zfm")
    add("Perímetro", "Municípios da ZFM", ", ".join(f"{r.nome} ({r.cod_ibge})" for r in mun.itertuples()),
        "Parâmetros > Municípios da ZFM", "Destinatário/fornecedor ZFM = AM + município da lista + SUFRAMA")
    pe = carregar("param_empresas")
    if not pe.empty:
        fora = pe.loc[~pe["incluir_na_analise"], "raiz_cnpj"].tolist()
        add("Perímetro", "Empresas fora da análise", ", ".join(fora) or "nenhuma", "Parâmetros > Empresas")
    pr = carregar("param_produtos")
    if not pr.empty:
        inc = pr[pr["incentivado"]]
        add("Produtos", "Produtos incentivados", f"{len(inc)} de {len(pr)}", "Parâmetros > Produtos",
            "Automático: item vendido com CFOP de produção própria")
        add("Produtos", "Incentivados sem alíquota TIPI", str(int(inc["aliq_tipi_2023"].isna().sum())),
            "Parâmetros > Produtos", "Sem TIPI: benefício de IPI = 0 e CP de CBS no percentual menor")
    cod = carregar("param_codigos_ajuste_icms")
    if not cod.empty:
        for classe, g in cod.groupby("classe"):
            add("Códigos de ajuste do ICMS", classe, ", ".join(g["codigo"]),
                "Parâmetros > Códigos de ajuste", "Classificação automática pela descrição/estrutura do código")
    cf = carregar("param_cfops")
    if not cf.empty:
        add("CFOPs", "CFOPs tratados como receita", ", ".join(sorted(cf.loc[cf["eh_receita"], "cfop"])),
            "Parâmetros > CFOPs")
    t = carregar("param_teses")
    add("Teses", "Teses cadastradas", str(len(t)), "Parâmetros > Teses", "Aplicadas só com o filtro 'Com teses'")
    for regra, texto in [
        ("Benefício atual", "Benefício = carga no regime geral − carga efetiva na ZFM; exportações fora"),
        ("Benefício pós-reforma", "Carga total (tributo pago + embutido nas compras); créditos normais "
                                  "acima do débito considerados ressarcíveis (DECISOES D-016)"),
        ("Consolidação", "Cada empresa apurada separadamente; consolidado = soma (sem compensação)"),
    ]:
        add("Método", regra, texto, "—", "DECISOES.md")
    return pd.DataFrame(linhas)
