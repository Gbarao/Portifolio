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
           {"raiz_cnpj": "texto", "cod_item": "texto", "descricao": "texto", "ncm": "texto",
            "incentivado": "bool", "tipo_bem": "texto", "aliq_ipi": "num", "fonte_aliq_ipi": "texto",
            "produzido_zfm_2024": "bool", "eh_tic": "bool", "ce_100_em_2023": "bool",
            "nivel_credito_estimulo": "num", "excluido_art441": "texto", "origem": "texto",
            "consumo_produtivo_comprovado": "texto", "revisado": "bool", "observacao": "texto"},
           ("raiz_cnpj", "cod_item"),
           "Uma linha por item do 0200. aliq_ipi: alíquota do IPI lida da própria EFD (C170) — usada como TIPI do "
           "produto; corrija só se a EFD estiver errada ou vazia. tipo_bem: final, capital, intermediario ou "
           "informatica. produzido_zfm_2024: industrializado na ZFM em 2024 ou projeto aprovado pelo CAS entre "
           "01/01/2022 e 16/01/2025 (art. 454). excluido_art441, origem e consumo_produtivo_comprovado: vazio = "
           "não validado."),
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
           "fundo_FMPES, outros_beneficios, outros, nao_classificado. Preenchida automaticamente "
           "a partir das EFDs; código sem regra fica 'nao_classificado' e gera alerta até ser "
           "classificado. Marque 'revisado' ao conferir."),
    Tabela("param_aliquotas_regime_geral", "Regime geral (fora da ZFM)",
           {"tributo": "texto", "aliquota": "num", "observacao": "texto"},
           ("tributo",),
           "Alíquotas do contrafactual 'fora da ZFM', em %."),
    Tabela("param_municipios_zfm", "Municípios da ZFM",
           {"cod_ibge": "texto", "nome": "texto", "observacao": "texto"},
           ("cod_ibge",),
           "Municípios da área da Zona Franca (código IBGE de 7 dígitos)."),
    Tabela("param_cfops", "CFOPs",
           {"cfop": "texto", "categoria": "texto", "eh_receita": "bool", "devolucao_de": "texto",
            "automatico": "bool"},
           ("cfop",),
           "Classificação dos CFOPs encontrados nas EFDs. 'eh_receita' define o que conta "
           "como receita de venda. 'devolucao_de' indica a operação de origem que a devolução "
           "abate (ex.: 1201 abate venda_producao; 5201 abate compra_industrializacao). "
           "Ao editar, desmarque 'automatico'."),
    Tabela("param_teses", "Teses",
           {"tese_id": "texto", "descricao": "texto", "raiz_cnpj": "texto", "tributo": "texto",
            "tipo_efeito": "texto", "parametro": "num", "vigencia_ini": "texto",
            "vigencia_fim": "texto", "status": "texto"},
           ("tese_id",),
           "tributo: ICMS, IPI, PIS, COFINS. tipo_efeito: valor_fixo_mensal (parametro em R$/mês), "
           "credito_adicional (R$/mês), reduz_base (% da receita incentivada × alíquota do regime "
           "geral), reduz_aliquota (p.p. sobre a receita incentivada). Vigência AAAA-MM. "
           "raiz_cnpj vazio ou 'todas' = todas as empresas."),
    Tabela("param_empresas_zfm", "Empresas ZFM (tipo e regime)",
           {"cnpj": "texto", "raiz": "texto", "nome": "texto", "origem": "texto", "uf": "texto",
            "cod_mun": "texto", "suframa": "texto", "tipo": "texto", "regime": "texto",
            "status_habilitacao": "texto", "validade_fim": "texto", "revisado": "bool",
            "regra_automatica": "texto", "observacao": "texto"},
           ("cnpj",),
           "Uma linha por CNPJ (estabelecimentos do grupo e participantes do Amazonas). tipo: "
           "industria_incentivada (Suframa + projeto com PPB aprovado), habilitado (Suframa sem projeto "
           "industrial: comércio/serviço) ou nao_habilitado. regime: regular ou simples. status_habilitacao: "
           "ativa, suspensa, cancelada ou vazio. validade_fim em AAAA-MM-DD. O campo SUFRAMA da EFD não prova a "
           "habilitação: sem 'revisado', o requisito fica 'não comprovado'."),
    Tabela("param_regras_cenario", "Regras To Be por cenário",
           {"cenario": "texto", "descricao": "texto", "sentido": "texto", "cbs_debito": "num",
            "ibs_debito": "num", "cbs_entrada": "num", "ibs_entrada": "num", "entrada_creditavel": "texto",
            "cbs_credito_fornecedor": "num", "ibs_credito_fornecedor": "num", "cp_cbs_450": "bool",
            "cp_ibs_450": "bool", "cp_ibs_entrada": "texto", "base_legal": "texto",
            "observacao": "texto"},
           ("cenario",),
           "Tratamento simulado de cada cenário (frações da alíquota do ano, 1 = integral, 0 = zero). "
           "*_debito: débito sobre a venda. *_entrada: tributo devido pela empresa na entrada "
           "(importação, IBS de 70% do art. 446). entrada_creditavel: sim, nao ou regime (só regime "
           "regular credita). *_credito_fornecedor: crédito do tributo cobrado pelo fornecedor. "
           "cp_ibs_entrada: 447, 449 ou 444. Os PERCENTUAIS (447: 7,5/13,5%; 449: 7,5%; 444: 50%; IBS de entrada do "
           "art. 446: 70%) e as vigências vêm de Regras legais, não desta tabela."),
    Tabela("param_conferencia_cenario", "Conferências As Is por cenário",
           {"cenarios": "texto", "tributo": "texto", "regra": "texto", "valores": "texto", "mensagem": "texto"},
           ("cenarios", "tributo", "regra"),
           "Alerta quando o escriturado diverge do esperado para o cenário. cenarios: lista separada por ';'. "
           "regra: aliquota_em (alíquota deve estar na lista), cst_em (CST na lista) ou valor_zero "
           "(o tributo não deveria estar destacado)."),
    Tabela("param_regras_legais", "Regras legais (versionadas)",
           {"codigo": "texto", "tributo": "texto", "dispositivo": "texto", "tipo_regra": "texto",
            "descricao": "texto", "percentual": "num", "inicio_vigencia": "texto", "fim_vigencia": "texto",
            "versao": "texto", "fonte_normativa": "texto", "data_atualizacao": "texto", "status": "texto",
            "observacao": "texto"},
           ("codigo",),
           "Percentuais, prazos e vigências da LC 214/2025 usados nos cálculos. status: vigente, futura, "
           "revogada ou pendente_regulamentacao (regra pendente ou revogada não é aplicada). Datas em AAAA-MM-DD; "
           "a regra vale nos anos entre o início e o fim da vigência. Alíquotas gerais de CBS/IBS NÃO ficam aqui: "
           "são premissas de simulação (aba Alíquotas por ano)."),
    Tabela("param_projetos_suframa", "Projetos SUFRAMA",
           {"cnpj": "texto", "projeto": "texto", "data_aprovacao_cas": "texto", "vigencia_ini": "texto",
            "vigencia_fim": "texto", "cod_item": "texto", "ncm": "texto", "ppb": "texto", "capacidade": "texto",
            "status": "texto", "observacao": "texto"},
           ("cnpj", "projeto", "cod_item", "ncm"),
           "Uma linha por produto aprovado no projeto (cod_item ou NCM; NCM pode ser prefixo). status: aprovado, "
           "suspenso, cancelado. Sem projeto cadastrado para o estabelecimento, o requisito fica 'não comprovado' "
           "(nunca presumido)."),
    Tabela("param_internamento", "Controle de internamento",
           {"chv_nfe": "texto", "data_ingresso": "texto", "status": "texto", "protocolo": "texto",
            "confirmacao_suframa": "texto", "cnpj_destino": "texto", "evidencia": "texto"},
           ("chv_nfe",),
           "Comprovação de ingresso na ZFM por NF-e. status: confirmado, pendente ou negado. Sem linha = não "
           "comprovado (crédito presumido do art. 447 e alíquota zero ficam em risco de estorno)."),
    Tabela("param_servicos_zfm", "Serviços prestados na ZFM",
           {"cnpj_estab": "texto", "documento": "texto", "municipio_prestacao": "texto",
            "local_fisico_zfm": "texto", "nfse": "texto", "tomador": "texto", "natureza": "texto",
            "evidencia": "texto"},
           ("cnpj_estab", "documento"),
           "Evidência de prestação física do serviço na ZFM (art. 451). documento = número ou chave da NFS-e do "
           "A100. local_fisico_zfm: sim, nao ou vazio. Endereço do prestador ou do tomador não é prova."),
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
                     reducao_cbs: float = 0.1, ibs_teste: float = 0.1) -> pd.DataFrame:
    """Gera as linhas cenario x ano (2027-2033) a partir das aliquotas de REFERENCIA.

    refs: cenario, cbs_referencia, ibs_referencia, aplica_cp_450, ipi_protegido_override, fonte.
    Mantem fator_icms, fator_cp_entrada e aliq_contrib_art457 ja editados em ``atual``.
    Regras: 2027-2028 CBS = ref − reducao e IBS = aliquota de teste (0,1%); 2029-2032
    IBS = ref × (1 − fator_icms); 2033 = referencia cheia.
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
                a_ibs = ibs_teste
                obs = (" | 2027-2028: CBS = referência − 0,1 p.p. e IBS de teste de 0,1% "
                       "(sem crédito presumido do art. 450 de IBS antes de 2029)")
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
                            premissa_num("reducao_cbs_2027_2028", 0.1), premissa_num("aliq_ibs_teste", 0.1))
    salvar("param_aliquotas_cenario", novo)
    return novo


_PREMISSAS = [
    ("ano_base", "auto",
     "Ano das EFDs usadas como base (YTD). 'auto' = ano mais recente carregado. Se o ano informado "
     "não tiver arquivo, o programa usa o mais recente."),
    ("base_cbs_ibs", "liquida_sem_tributos",
     "Base da simulação: 'liquida_sem_tributos' = VL_ITEM − VL_DESC − ICMS − PIS − COFINS "
     "(ICMS por item estimado pela proporção ICMS/valor do CFOP no mês); 'valor_liquido' = "
     "VL_ITEM − VL_DESC."),
    ("ordem_deducao_ibs", "debito-creditos-cp447_449-cp450",
     "Ordem de dedução do IBS: 'debito-creditos-cp447_449-cp450' (CP de entrada antes; o art. 450 "
     "incide sobre o saldo que sobra) ou 'debito-creditos-cp450-cp447_449' (art. 450 sobre o saldo "
     "após créditos; CP de entrada depois). CONFERIR na Resolução CGIBS / NT 2025.002."),
    ("prazo_cp_anos", "5", "Prazo para usar crédito presumido (art. 452)."),
    ("nivel_apuracao_cbs_ibs", "raiz",
     "Apuração de CBS/IBS: 'raiz' (empresa, centralizada) ou 'estabelecimento' (CNPJ completo). "
     "Conferir a regra de centralização na LC 214/2025."),
    ("tolerancia_conciliacao", "1,00", "Tolerância das conciliações (R1, R2, R4, R5), em R$ por estabelecimento/mês."),
    ("cst_ipi_isento", "52", "CSTs de IPI de saída considerados isenção ZFM (separar por ;)."),
    ("ipi_sem_cst_assume_isento", "sim",
     "Saídas sem CST de IPI por item (C181): produto incentivado é tratado como isento."),
    ("zfm_exige_suframa", "sim",
     "Destinatário/fornecedor só é tratado como ZFM se tiver SUFRAMA no cadastro 0150 (sim/nao)."),
    ("abater_devolucoes", "sim",
     "Devoluções de venda abatem as saídas de origem e devoluções de compra abatem as entradas (sim/nao)."),
    ("transferencias_na_base_cbs_ibs", "nao",
     "Transferências entre estabelecimentos entram como débito/crédito de CBS/IBS? (sim/nao). "
     "Padrão 'nao' (conferir o tratamento na LC 214/2025). Sempre mostradas à parte."),
    ("tolerancia_receita_pct", "0,5", "Tolerância das conciliações de receita (R3), em % do valor."),
    ("carga_icms_as_is", "e110_mais_excesso_e116",
     "Carga de ICMS As Is: 'e110_mais_excesso_e116' = ICMS a recolher + débitos especiais (E110) + "
     "obrigações do E116 além desse total (ex.: fundos pagos à parte); 'e110_mais_fundos' = E110 + "
     "fundos classificados; 'somente_e110' = só o E110."),
    ("rateio_pis_cofins_am", "receita",
     "A EFD Contribuições é da empresa inteira (inclui estabelecimentos fora do AM). 'receita' = "
     "PIS/COFINS do bloco M rateados pela receita dos estabelecimentos do AM; 'nenhum' = valor inteiro."),
    ("teses_ativas_ja_na_apuracao", "sim",
     "Teses com status 'ativa' já estão refletidas na apuração (não ajustam a carga As Is)."),
    ("anualizacao_mensal", "perfil_observado",
     "Perfil mês a mês do ano simulado: 'perfil_observado' (meses de 2026 + média nos demais) ou "
     "'media_constante' (sensibilidade sem sazonalidade). O total anual é sempre média × 12."),
    ("revenda_presencial", "sim",
     "Importações de mercadoria para revenda por habilitado são 'revenda presencial' (C1b, art. 444)? sim/nao."),
    ("c3a_intermediario", "compra_industrializacao",
     "Quando a compra na ZFM é 'bem intermediário' (C3a): 'compra_industrializacao' (CFOP de compra para "
     "industrialização ou tipo_bem intermediário) ou 'tipo_bem' (só pelo tipo de bem do item)."),
    ("fator_ipi_proprio", "0",
     "Fração do IPI próprio a recolher (E520) que permanece no To Be (0 = IPI zerado/ZFM isenta)."),
    ("aliq_ibs_teste", "0,1", "IBS de teste em 2027-2028, em % (LC 214/2025: 0,05% estadual + 0,05% municipal)."),
    ("reducao_cbs_2027_2028", "0,1",
     "Redução da CBS em 2027-2028, em p.p. (IBS-teste de 0,1% compensável com a CBS)."),
    ("tratamento_nao_confirmados", "estimativa_com_incentivo",
     "Operações 'potencialmente elegíveis' ou com 'informação insuficiente': 'estimativa_com_incentivo' (calcula "
     "o incentivo e mostra o valor em risco) ou 'regra_geral' (conservador). Não elegíveis vão sempre à regra geral."),
    ("taxa_juros_acrescimos_mes", "",
     "Acréscimos legais (art. 29, § 2º) para estornos/recuperações: juros em % ao mês. Vazio = pendente "
     "(acréscimos não calculados e sinalizados)."),
    ("multa_acrescimos_pct", "", "Multa de mora em % para estornos/recuperações. Vazio = pendente."),
]


def _r(cen, desc, sentido, base_legal, obs="", cbs_d=0.0, ibs_d=0.0, cbs_e=0.0, ibs_e=0.0, cred="regime",
       cbs_f=0.0, ibs_f=0.0, cp_cbs=False, cp_ibs=False, cp_ent=""):
    return {"cenario": cen, "descricao": desc, "sentido": sentido, "cbs_debito": cbs_d, "ibs_debito": ibs_d,
            "cbs_entrada": cbs_e, "ibs_entrada": ibs_e, "entrada_creditavel": cred,
            "cbs_credito_fornecedor": cbs_f, "ibs_credito_fornecedor": ibs_f, "cp_cbs_450": cp_cbs,
            "cp_ibs_450": cp_ibs, "cp_ibs_entrada": cp_ent, "base_legal": base_legal,
            "observacao": obs}


_REGRAS_CENARIO = [
    _r("C1a", "Importação para indústria incentivada", "entrada", "LC 214/2025, art. 443",
       "CBS/IBS suspensos -> isenção quando consumidos na produção ou após 48 meses no ativo. Sem crédito. "
       "Não vale para bens excluídos (art. 441) nem uso e consumo pessoal."),
    _r("C1b", "Importação por habilitado (revenda presencial)", "entrada", "LC 214/2025, art. 444",
       "CBS integral (creditável no regime regular); IBS devido menos crédito presumido de 50% da alíquota.",
       cbs_e=1, ibs_e=1, cp_ent="444"),
    _r("C1c", "Importação fora dos arts. 443/444 (regra geral)", "entrada", "LC 214/2025, art. 453",
       "CBS e IBS integrais na importação, creditáveis no regime regular; sem crédito presumido.", cbs_e=1, ibs_e=1),
    _r("C2a", "Compra de outro Estado por indústria incentivada", "entrada", "LC 214/2025, arts. 445 e 447",
       "CBS/IBS zero; crédito presumido de IBS 7,5% (S/SE exc. ES) ou 13,5% (demais e ES) a partir de 2029.",
       cp_ent="447"),
    _r("C2b", "Compra de outro Estado por habilitado (regime regular)", "entrada",
       "LC 214/2025, arts. 445, 446 e 447",
       "CBS/IBS zero na compra; IBS na entrada no AM conforme art. 446 (70% da alíquota, em Regras legais); "
       "crédito presumido do art. 447 (percentuais em Regras legais).", ibs_e=1, cp_ent="447"),
    _r("C2c", "Compra de outro Estado por habilitado do Simples", "entrada", "LC 214/2025, arts. 445 e 446",
       "CBS/IBS zero; IBS na entrada conforme art. 446 (percentual em Regras legais); sem crédito presumido do "
       "art. 447.", ibs_e=1),
    _r("C3a", "Compra na ZFM: intermediário de indústria incentivada para indústria incentivada", "entrada",
       "LC 214/2025, arts. 448 e 449",
       "CBS/IBS zero; compradora do regime regular recebe crédito presumido de IBS de 7,5%.", cp_ent="449"),
    _r("C3b", "Compra dentro da ZFM de fornecedor da ZFM (art. 451)", "entrada", "LC 214/2025, art. 451",
       "CBS zero; IBS pela regra geral (cobrado pelo fornecedor e creditado no regime regular).", ibs_f=1),
    _r("C4a", "Venda para fora da ZFM a contribuinte regular", "saida", "LC 214/2025, art. 450",
       "CBS/IBS integrais; crédito presumido de CBS 6%/2% e de IBS sobre o saldo devedor.",
       cbs_d=1, ibs_d=1, cp_cbs=True, cp_ibs=True),
    _r("C4b", "Venda para fora da ZFM a consumidor final ou não contribuinte", "saida", "LC 214/2025, art. 450",
       "CBS/IBS integrais; créditos presumidos do art. 450.", cbs_d=1, ibs_d=1, cp_cbs=True, cp_ibs=True),
    _r("C4c", "Venda dentro da ZFM para PJ (bem final)", "saida", "LC 214/2025, arts. 450 e 451",
       "CBS zero (sem crédito presumido de CBS); IBS com crédito presumido do art. 450.",
       ibs_d=1, cp_ibs=True),
    _r("C4d", "Venda dentro da ZFM de intermediário para indústria incentivada", "saida",
       "LC 214/2025, art. 448", "CBS/IBS zero; sem crédito presumido do art. 450."),
    _r("C5M", "Venda dentro da ZFM de bem de origem nacional (art. 451)", "saida", "LC 214/2025, art. 451",
       "CBS zero (créditos de CBS mantidos); IBS pela regra geral. Fornecedor PJ na ZFM e adquirente na ZFM.",
       ibs_d=1),
    _r("C5S", "Serviço prestado fisicamente na ZFM (art. 451)", "saida", "LC 214/2025, art. 451",
       "CBS zero; IBS pela regra geral. Exige evidência do local físico da prestação (não basta o endereço).",
       ibs_d=1),
    _r("GER_S", "Saída pela regra geral (art. 453)", "saida", "LC 214/2025, art. 453",
       "Operação não contemplada ou requisito não atendido: CBS e IBS integrais, sem crédito presumido.",
       cbs_d=1, ibs_d=1),
    _r("GER_E", "Entrada pela regra geral (art. 453)", "entrada", "LC 214/2025, art. 453",
       "Crédito do tributo cobrado pelo fornecedor (regime regular).", cbs_f=1, ibs_f=1),
    _r("EXP", "Exportação (fora do escopo; sem débito nos dois regimes)", "saida", "Imunidade"),
    _r("TR", "Transferência entre estabelecimentos (à parte)", "ambos", "Conferir LC 214/2025"),
    _r("REM", "Remessas, retornos e outras operações sem receita/crédito", "ambos", "—"),
    _r("SRV", "Serviços tomados", "entrada", "Regra geral", "Crédito do tributo cobrado pelo prestador.",
       cbs_f=1, ibs_f=1),
    _r("NC_S", "Saída com informação insuficiente para classificar", "saida", "—",
       "Simulada pela regra geral (débito integral) até a classificação. Ver Não classificados.", cbs_d=1, ibs_d=1),
    _r("NC_E", "Entrada com informação insuficiente para classificar", "entrada", "—",
       "Simulada pela regra geral (crédito do fornecedor) até a classificação.", cbs_f=1, ibs_f=1),
]

_CONFERENCIAS = [
    ("C4a;C4b", "PIS", "aliquota_em", "0,65;1,3",
     "Venda incentivada para fora da ZFM com PIS diferente de 0,65% ou 1,3% (Decreto 5.310/2004)"),
    ("C4a;C4b", "COFINS", "aliquota_em", "3;6",
     "Venda incentivada para fora da ZFM com COFINS diferente de 3% ou 6% (Decreto 5.310/2004)"),
    ("C4c;C4d", "PIS", "aliquota_em", "0;0,65;1,3", "Venda incentivada na ZFM com alíquota de PIS fora do esperado"),
    ("C4c;C4d", "COFINS", "aliquota_em", "0;3;6", "Venda incentivada na ZFM com alíquota de COFINS fora do esperado"),
    ("C4a;C4b;C4c;C4d", "IPI", "cst_em", "52", "Venda incentivada com CST de IPI diferente de isenção (52)"),
    ("C1a;C1b;C1c", "IPI", "valor_zero", "", "Importação com IPI destacado (esperado isento, DL 288/1967, art. 3º)"),
    ("C2a;C2b;C2c", "IPI", "valor_zero", "", "Entrada C2 com IPI destacado (esperado isento, DL 288/1967, art. 4º)"),
    ("C2a;C2b;C2c", "PIS", "aliquota_em", "0", "Entrada C2 com PIS diferente de zero (Lei 10.996/2004, art. 2º)"),
    ("C2a;C2b;C2c", "COFINS", "aliquota_em", "0", "Entrada C2 com COFINS diferente de zero (Lei 10.996/2004, art. 2º)"),
    ("C3a;C3b", "IPI", "valor_zero", "", "Compra na ZFM com IPI destacado (esperado isento, DL 288/1967, art. 9º)"),
]

_FONTE_LC = "LC 214/2025 (redação vigente); conferir alterações da LC 227/2026 no texto oficial"
_ATUALIZ = "2026-11-23"


def _rl(cod, trib, disp, tipo, desc, pct, ini, fim="", status="vigente", obs=""):
    return {"codigo": cod, "tributo": trib, "dispositivo": disp, "tipo_regra": tipo, "descricao": desc,
            "percentual": pct, "inicio_vigencia": ini, "fim_vigencia": fim, "versao": "1",
            "fonte_normativa": _FONTE_LC, "data_atualizacao": _ATUALIZ, "status": status, "observacao": obs}


_A_CONFERIR = "Vigência a conferir no art. 544 da LC 214/2025."
_REGRAS_LEGAIS = [
    _rl("ART441_EXCLUSAO", "IBS/CBS", "art. 441", "exclusao",
        "Produtos não contemplados pelo regime da ZFM (lista no cadastro jurídico do produto: excluido_art441)",
        None, "2027-01-01", obs="Lista não é fixada no código: validar produto a produto. " + _A_CONFERIR),
    _rl("ART443_SUSPENSAO", "IBS/CBS", "art. 443", "suspensao",
        "Importação por indústria incentivada para utilização na ZFM: suspensão convertida em isenção",
        None, "2027-01-01", obs=_A_CONFERIR),
    _rl("ART443_PRAZO_MESES", "IBS/CBS", "art. 443", "prazo",
        "Conversão em isenção do ativo: depreciação integral ou permanência na ZFM (meses), o que ocorrer primeiro",
        48, "2027-01-01", obs=_A_CONFERIR),
    _rl("ART444_CP_IBS", "IBS", "art. 444", "credito_presumido",
        "Importação para revenda presencial por habilitado: crédito presumido de IBS, % da alíquota de IBS na importação",
        50, "2027-01-01"),
    _rl("ART445_ALIQ_ZERO", "IBS/CBS", "art. 445", "aliquota_zero",
        "Venda de bem industrializado de origem nacional de outra UF a contribuinte habilitado na ZFM", None,
        "2027-01-01", obs=_A_CONFERIR),
    _rl("ART446_IBS_ENTRADA", "IBS", "art. 446", "percentual_debito",
        "IBS na entrada no AM, % da alíquota (não se aplica a indústria incentivada com utilização na ZFM)",
        70, "2029-01-01"),
    _rl("ART447_SS", "IBS", "art. 447", "credito_presumido",
        "Crédito presumido de IBS do adquirente regular: origem Sul/Sudeste exceto ES, % do valor da operação",
        7.5, "2029-01-01"),
    _rl("ART447_DEMAIS", "IBS", "art. 447", "credito_presumido",
        "Idem, origem Norte, Nordeste, Centro-Oeste ou Espírito Santo", 13.5, "2029-01-01"),
    _rl("ART448_ALIQ_ZERO", "IBS/CBS", "art. 448", "aliquota_zero",
        "Bem intermediário de indústria incentivada para indústria incentivada na ZFM", None, "2027-01-01",
        obs=_A_CONFERIR),
    _rl("ART449_CP_IBS", "IBS", "art. 449", "credito_presumido",
        "Crédito presumido de IBS do adquirente nas operações do art. 448, % do valor da operação", 7.5,
        "2029-01-01", obs="Exige incorporação ou consumo na produção de bem final."),
    _rl("ART450_IBS_FINAL", "IBS", "art. 450", "credito_presumido",
        "Crédito presumido de IBS, % do saldo devedor: bem de consumo final", 55, "2029-01-01"),
    _rl("ART450_IBS_CAPITAL", "IBS", "art. 450", "credito_presumido", "Idem, bem de capital", 75, "2029-01-01"),
    _rl("ART450_IBS_INTERMEDIARIO", "IBS", "art. 450", "credito_presumido", "Idem, bem intermediário", 90.25,
        "2029-01-01"),
    _rl("ART450_IBS_INFORMATICA", "IBS", "art. 450", "credito_presumido", "Idem, bem de informática", 100,
        "2029-01-01"),
    _rl("ART450_IBS_CE100", "IBS", "art. 450", "credito_presumido",
        "Idem, produto com crédito estímulo de ICMS de 100% no AM em 31/12/2023", 100, "2029-01-01"),
    _rl("ART450_CBS_454", "CBS", "art. 450", "credito_presumido",
        "Crédito presumido de CBS, % do valor da operação: produto enquadrado no art. 454", 6, "2027-01-01"),
    _rl("ART450_CBS_DEMAIS", "CBS", "art. 450", "credito_presumido",
        "Crédito presumido de CBS, % do valor da operação: demais produtos elegíveis", 2, "2027-01-01"),
    _rl("ART450_TRAVA_448", "IBS/CBS", "art. 450 (LC 227/2026)", "exclusao",
        "Operações do art. 448 não recebem o crédito presumido do art. 450", None, "2027-01-01",
        obs="Conferir a redação dada pela LC 227/2026 no texto oficial."),
    _rl("ART450_SALDO_DEVEDOR", "IBS", "art. 450, § 6º (LC 227/2026)", "metodo",
        "Crédito presumido de IBS sobre o saldo devedor do período, apurado por faixa de percentual", None,
        "2029-01-01", obs="Critério de alocação dos créditos: premissa criterio_alocacao_450. Conferir o § 6º."),
    _rl("ART451_CBS_ZERO", "CBS", "art. 451", "aliquota_zero",
        "Venda dentro da ZFM de bem de origem nacional ou serviço prestado fisicamente na ZFM", None,
        "2027-01-01", obs=_A_CONFERIR),
    _rl("ART454_LIMITE_TIPI", "IPI", "art. 454", "limite",
        "Alíquota da TIPI em 31/12/2023 abaixo da qual o IPI é reduzido a zero (produto industrializado na ZFM)",
        6.5, "2027-01-01"),
    _rl("ART454_JANELA_CAS", "IPI", "art. 454", "janela",
        "Projeto técnico-econômico aprovado pelo CAS neste período (alternativa a 'industrializado em 2024')",
        None, "2022-01-01", "2025-01-16"),
    _rl("ART455_CP_CBS", "CBS", "art. 455", "credito_presumido",
        "Produção futura sem similar nacional — alternativa A: crédito presumido de CBS, % da operação", 6,
        "2027-01-01", status="pendente_regulamentacao", obs="Depende de ato do Poder Executivo."),
    _rl("ART455_IPI_MIN", "IPI", "art. 455", "limite",
        "Produção futura sem similar nacional — alternativa B: alíquota de IPI de no mínimo", 6.5, "2027-01-01",
        status="pendente_regulamentacao", obs="Depende de ato do Poder Executivo; não cumulativa com a A."),
]

_MODELOS: dict[str, pd.DataFrame] = {
    "param_regras_legais": pd.DataFrame(_REGRAS_LEGAIS),
    "param_regras_cenario": pd.DataFrame(_REGRAS_CENARIO),
    "param_conferencia_cenario": pd.DataFrame(_CONFERENCIAS,
                                              columns=["cenarios", "tributo", "regra", "valores", "mensagem"]),
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


def _migrar_colunas(nome: str, df: pd.DataFrame) -> pd.DataFrame:
    """Converte CSVs de versoes anteriores para o modelo enxuto (sem perder o que o usuario editou)."""
    if nome == "param_produtos" and "aliq_ipi" not in df.columns and not df.empty:
        df = df.copy()
        a26 = df.get("aliq_tipi_2026", pd.Series("", index=df.index)).fillna("")
        a23 = df.get("aliq_tipi_2023", pd.Series("", index=df.index)).fillna("")
        df["aliq_ipi"] = a23.where(a23.str.strip() != "", a26)
        df["fonte_aliq_ipi"] = df["aliq_ipi"].map(lambda v: "informada pelo usuário (versão anterior)" if str(v).strip() else "")
        if "projeto_cas_2022_2025" in df.columns:
            cas = df["projeto_cas_2022_2025"].astype(str).str.lower().eq("sim")
            df.loc[cas, "produzido_zfm_2024"] = "sim"
        if "classificacao_aprovada" in df.columns:
            df["revisado"] = df["classificacao_aprovada"]
        obs = df.get("fonte", pd.Series("", index=df.index)).fillna("")
        if "motivo_exclusao" in df.columns:
            obs = (obs + " " + df["motivo_exclusao"].fillna("")).str.strip()
        df["observacao"] = obs
    if nome == "param_empresas_zfm" and "evidencia" in df.columns and not df.empty:
        df = df.copy()
        ev = df["evidencia"].fillna("")
        df["observacao"] = (df.get("observacao", pd.Series("", index=df.index)).fillna("") + " " + ev).str.strip()
    return df


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
    df = _migrar_colunas(nome, df)
    df = normalizar(nome, df)
    if nome == "param_cfops" and not df.empty:  # versao anterior nao tinha 'devolucao_de'
        vazio = df["automatico"] & (df["devolucao_de"] == "")
        df.loc[vazio, "devolucao_de"] = df.loc[vazio, "cfop"].map(_cfop.devolucao_de)
    if nome == "param_codigos_ajuste_icms" and not df.empty:
        # versao anterior gravava 'outros' para codigo sem regra: vira 'nao_classificado' (alerta)
        velho = (df["classe"] == "outros") & (df["regra_automatica"] == "sem regra") & ~df["revisado"]
        df.loc[velho, "classe"] = "nao_classificado"
    if nome == "param_regras_cenario" and not df.empty:
        # versao anterior gravava a fracao do art. 446 (0,7) na regra; agora o percentual vem de Regras legais
        m = df["cenario"].isin(["C2b", "C2c"]) & (df["ibs_entrada"].round(4) == 0.7)
        df.loc[m, "ibs_entrada"] = 1.0
        faltam = [x for x in _REGRAS_CENARIO if x["cenario"] not in set(df["cenario"])]
        if faltam:
            df = pd.concat([df, normalizar(nome, pd.DataFrame(faltam))], ignore_index=True)
    if nome == "param_regras_legais" and not df.empty:
        faltam = [x for x in _REGRAS_LEGAIS if x["codigo"] not in set(df["codigo"])]
        if faltam:
            df = pd.concat([df, normalizar(nome, pd.DataFrame(faltam))], ignore_index=True)
    if nome == "param_premissas" and not df.empty:  # premissas removidas (sem efeito no calculo) saem
        df = df[df["chave"].isin({x[0] for x in _PREMISSAS})].reset_index(drop=True)
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


def classificar_codigo(codigo: str, registro: str, texto: str, cod_or: str = "") -> tuple[str, str]:
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
    if registro == "E116" and str(cod_or or "").strip() == "000":
        return "outros", "E116 com COD_OR 000: ICMS próprio a recolher (não é ajuste)"
    return "nao_classificado", "sem regra: classificar manualmente"


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
        linhas.append({"cfop": c, "categoria": cat, "eh_receita": rec,
                       "devolucao_de": _cfop.devolucao_de(c), "automatico": True})
    mesclar("param_cfops", pd.DataFrame(linhas))
    from . import visoes
    visoes.preparar(con)  # categorias de CFOP sao usadas abaixo (visoes materializadas)

    cods = con.execute("""
        SELECT COD_AJ_APUR AS codigo, 'E111' AS registro, string_agg(DISTINCT DESCR_COMPL_AJ, ' | '),
               NULL AS cod_or
        FROM raw_icms_e111 JOIN arquivos USING (arquivo_id) WHERE ativo GROUP BY 1
        UNION ALL
        SELECT coalesce(COD_REC, COD_OR), 'E116', string_agg(DISTINCT coalesce(TXT_COMPL, ''), ' | '),
               CASE WHEN count(DISTINCT COD_OR) = 1 THEN max(COD_OR) END
        FROM raw_icms_e116 JOIN arquivos USING (arquivo_id) WHERE ativo GROUP BY 1
    """).fetchall()
    linhas = []
    for linha in cods:
        cod, reg, txt = linha[0], linha[1], linha[2]
        cod_or = linha[3] if len(linha) > 3 else ""
        classe, regra = classificar_codigo(cod, reg, txt, cod_or)
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
            "aliq_ipi": None, "fonte_aliq_ipi": "",
            "produzido_zfm_2024": bool(vende_prod), "eh_tic": False,
            "nivel_credito_estimulo": None, "ce_100_em_2023": False, "revisado": False,
            "observacao": "automático (EFD): incentivado = vendido com CFOP de produção própria"})
    mesclar("param_produtos", pd.DataFrame(linhas))
    preencher_aliquota_ipi(con)
    visoes.preparar(con)

    # Empresas ZFM: estabelecimentos do grupo no AM + participantes do AM
    grupo = con.execute("""
        SELECT e.cnpj, e.raiz, e.nome, e.uf, e.cod_mun, e.suframa,
               EXISTS (SELECT 1 FROM v_saidas_item s WHERE s.cnpj_estab = e.cnpj
                       AND s.categoria_cfop = 'venda_producao') AS vende_producao
        FROM v_estabelecimentos e WHERE e.no_amazonas""").fetchall()
    linhas = []
    for cnpj, raiz, nome, uf, cod_mun, suframa, vende in grupo:
        if vende:
            tipo, regra = "industria_incentivada", "grupo: vende produção própria (confirmar projeto com PPB)"
        elif suframa:
            tipo, regra = "habilitado", "grupo: inscrição Suframa sem venda de produção própria"
        else:
            tipo, regra = "nao_habilitado", "grupo: sem inscrição Suframa no cadastro"
        linhas.append({"cnpj": cnpj, "raiz": raiz, "nome": nome, "origem": "grupo", "uf": uf,
                       "cod_mun": cod_mun or "", "suframa": suframa or "", "tipo": tipo, "regime": "regular",
                       "regra_automatica": regra, "revisado": False})
    cnpjs_grupo = {g[0] for g in grupo}
    parts = con.execute("""
        SELECT cnpj_part, any_value(nome_part), any_value(uf), any_value(cod_mun),
               max(nullif(suframa, '')), bool_or(municipio_zfm)
        FROM (SELECT cnpj_part, nome_part, uf, cod_mun, suframa, municipio_zfm FROM v_participantes
              UNION ALL
              SELECT cnpj_part, nome_part, uf, cod_mun, suframa, municipio_zfm FROM v_participantes_contrib)
        WHERE uf = 'AM' AND nullif(cnpj_part, '') IS NOT NULL GROUP BY 1""").fetchall()
    for cnpj, nome, uf, cod_mun, suframa, mun_zfm in parts:
        if cnpj in cnpjs_grupo:
            continue
        if mun_zfm and suframa:
            tipo, regra = "habilitado", "participante: SUFRAMA no 0150 e município da ZFM (projeto industrial a confirmar)"
        else:
            tipo, regra = "nao_habilitado", "participante: sem SUFRAMA ou fora dos municípios da ZFM"
        linhas.append({"cnpj": cnpj, "raiz": cnpj[:8], "nome": nome, "origem": "participante", "uf": uf,
                       "cod_mun": cod_mun or "", "suframa": suframa or "", "tipo": tipo, "regime": "regular",
                       "regra_automatica": regra, "revisado": False})
    mesclar("param_empresas_zfm", pd.DataFrame(linhas))
    visoes.preparar(con)
    return novos


def aliquotas_ipi_da_efd(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Aliquota do IPI de cada item lida da propria escrituracao (C170, campo ALIQ_IPI), na ordem:
    1) saidas do item na EFD Contribuicoes (C170); 2) saidas do item na EFD ICMS/IPI (C170);
    3) qualquer C170 do item (entradas); 4) outro item com o mesmo NCM. So aliquotas maiores que zero
    (saida isenta da ZFM costuma vir com aliquota zero e nao informa a TIPI)."""
    return con.execute("""
        WITH c AS (
            SELECT a.raiz, i.COD_ITEM AS cod_item, CAST(i.ALIQ_IPI AS DOUBLE) AS aliq, d.IND_OPER AS ind_oper,
                   'Contribuições' AS efd
            FROM raw_contrib_c170 i JOIN raw_contrib_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
            JOIN arquivos a ON a.arquivo_id = i.arquivo_id WHERE a.ativo AND i.ALIQ_IPI > 0
            UNION ALL
            SELECT a.raiz, i.COD_ITEM, CAST(i.ALIQ_IPI AS DOUBLE), d.IND_OPER, 'ICMS/IPI'
            FROM raw_icms_c170 i JOIN raw_icms_c100 d ON d.arquivo_id = i.arquivo_id AND d.linha_num = i.pai_linha
            JOIN arquivos a ON a.arquivo_id = i.arquivo_id WHERE a.ativo AND i.ALIQ_IPI > 0),
        r AS (SELECT raiz, cod_item, ind_oper, efd, mode(aliq) AS aliq, count(*) AS n FROM c GROUP BY ALL)
        SELECT raiz, cod_item,
               arg_min(aliq, CASE WHEN ind_oper = '1' AND efd = 'Contribuições' THEN 1
                                  WHEN ind_oper = '1' THEN 2 ELSE 3 END) AS aliq,
               arg_min(CASE WHEN ind_oper = '1' THEN 'saídas' ELSE 'entradas' END || ' do item (C170 da EFD ' || efd || ')',
                       CASE WHEN ind_oper = '1' AND efd = 'Contribuições' THEN 1
                            WHEN ind_oper = '1' THEN 2 ELSE 3 END) AS fonte
        FROM r GROUP BY ALL""").df()


def preencher_aliquota_ipi(con: duckdb.DuckDBPyConnection) -> int:
    """Preenche aliq_ipi dos produtos ainda nao revisados com a aliquota lida da EFD (o que o usuario ja
    revisou nao e alterado). Sem aliquota do item, usa a de outro item com o mesmo NCM."""
    prod = carregar("param_produtos")
    if prod.empty:
        return 0
    efd = aliquotas_ipi_da_efd(con)
    por_item = {(r.raiz, r.cod_item): (r.aliq, r.fonte) for r in efd.itertuples()}
    ncm_de = prod.set_index(["raiz_cnpj", "cod_item"])["ncm"].to_dict()
    por_ncm: dict[str, float] = {}
    for (raiz, cod), (aliq, _) in por_item.items():
        n = ncm_de.get((raiz, cod), "")
        if n:
            por_ncm.setdefault(n, aliq)
    n = 0
    for i, r in prod.iterrows():
        if r["revisado"] or (pd.notna(r["aliq_ipi"]) and str(r["fonte_aliq_ipi"]).startswith("informada")):
            continue
        achou = por_item.get((r["raiz_cnpj"], r["cod_item"]))
        if achou:
            prod.at[i, "aliq_ipi"], prod.at[i, "fonte_aliq_ipi"] = achou[0], "EFD: " + achou[1]
        elif r["ncm"] and r["ncm"] in por_ncm:
            prod.at[i, "aliq_ipi"] = por_ncm[r["ncm"]]
            prod.at[i, "fonte_aliq_ipi"] = "EFD: outro item com o mesmo NCM"
        elif pd.isna(r["aliq_ipi"]):
            prod.at[i, "fonte_aliq_ipi"] = "não encontrada na EFD (saída isenta sem alíquota): informe a TIPI"
            continue
        n += 1
    salvar("param_produtos", prod)
    return n


# ---------------------------------------------------------------------------
# Sincronizacao com o banco (as visoes usam as tabelas param_*)
# ---------------------------------------------------------------------------
def criar_tabelas_vazias(con: duckdb.DuckDBPyConnection) -> None:
    """Cria as tabelas param_* no banco. Tabela com estrutura de versao anterior e recriada
    (o conteudo e sempre copiado dos CSV em sincronizar)."""
    tipos = {"texto": "VARCHAR", "bool": "BOOLEAN", "num": "DOUBLE", "int": "INTEGER"}
    existentes = {}
    for nome, col in con.execute("""SELECT table_name, column_name FROM information_schema.columns
                                    WHERE table_schema = 'main' AND table_name LIKE 'param_%'""").fetchall():
        existentes.setdefault(nome, []).append(col.lower())
    for t in TABELAS.values():
        cols = ", ".join(f'"{c}" {tipos[tp]}' for c, tp in t.colunas.items())
        atual = existentes.get(t.nome)
        if atual is not None and sorted(atual) != sorted(c.lower() for c in t.colunas):
            con.execute(f"DROP TABLE {t.nome}")
        con.execute(f"CREATE TABLE IF NOT EXISTS {t.nome} ({cols})")


def esquema_ok(con: duckdb.DuckDBPyConnection) -> bool:
    """As tabelas param_* existem com as colunas da versao atual?"""
    existentes: dict[str, list[str]] = {}
    for nome, col in con.execute("""SELECT table_name, column_name FROM information_schema.columns
                                    WHERE table_schema = 'main' AND table_name LIKE 'param_%'""").fetchall():
        existentes.setdefault(nome, []).append(col.lower())
    return all(sorted(existentes.get(t.nome, [])) == sorted(c.lower() for c in t.colunas)
               for t in TABELAS.values())


def ano_base(con: duckdb.DuckDBPyConnection | None = None) -> int:
    """Ano-base das EFDs. Premissa 'ano_base': numero ou 'auto' (ano mais recente carregado).
    Se o ano informado nao tiver arquivo carregado, usa o ano mais recente (evita telas vazias)."""
    v = _para_num(premissa(None, "ano_base", "auto"))
    if con is None:
        return int(v or 2026)
    anos = [r[0] for r in con.execute(
        "SELECT DISTINCT year(dt_ini) FROM arquivos WHERE ativo ORDER BY 1").fetchall() if r[0]]
    if v and int(v) in anos:
        return int(v)
    return int(anos[-1]) if anos else int(v or 2026)


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
            "Cadastros > Premissas e alíquotas", r.fonte)
    a = carregar("param_aliquotas_cenario")
    if not a.empty:
        f = a[a.cenario == a.cenario.iloc[0]].set_index("ano")
        add("Transição", "Fator do ICMS por ano (fração que ainda existe)",
            " · ".join(f"{ano}: {v:g}".replace(".", ",") for ano, v in f["fator_icms"].items()),
            "Cadastros > Alíquotas por cenário", "ADCT art. 128 (redução de 10% a 40% em 2029-2032)")
        add("Transição", "Fator dos créditos presumidos de entrada (arts. 447/449)",
            " · ".join(f"{ano}: {v:g}".replace(".", ",") for ano, v in f["fator_cp_entrada"].items()),
            "Cadastros > Alíquotas por cenário", "Inicial = proporção do IBS no ano (conferir art. 474)")
        add("Transição", "Contribuição estadual (art. 457)",
            " · ".join(f"{ano}: {pct(v)}" for ano, v in f["aliq_contrib_art457"].items()),
            "Cadastros > Alíquotas por cenário", "LC 214/2025 art. 457 — preencher para sensibilidade")
    for r in carregar("param_regras_legais").itertuples():
        add("Regras legais (LC 214/2025)", f"{r.codigo} – {r.descricao}",
            (pct(r.percentual) if r.percentual is not None and not pd.isna(r.percentual) else "—")
            + f" · vigência {r.inicio_vigencia or '—'} a {r.fim_vigencia or 'indeterminado'} · {r.status}",
            "Cadastros > Regras legais", f"{r.dispositivo}; {r.fonte_normativa}. {r.observacao}".strip())
    for r in carregar("param_aliquotas_regime_geral").itertuples():
        add("Regime geral (fora da ZFM)", r.tributo, pct(r.aliquota), "Cadastros > Regime geral", r.observacao)
    def fr(v):
        return "-" if v is None or pd.isna(v) else f"{float(v):g}".replace(".", ",")

    for r in carregar("param_regras_cenario").itertuples():
        partes = []
        if r.sentido == "saida":
            partes.append(f"débito CBS {fr(r.cbs_debito)} · IBS {fr(r.ibs_debito)}")
        else:
            if (r.cbs_entrada or 0) or (r.ibs_entrada or 0):
                partes.append(f"devido na entrada CBS {fr(r.cbs_entrada)} · IBS {fr(r.ibs_entrada)} "
                              f"(creditável: {r.entrada_creditavel})")
            if (r.cbs_credito_fornecedor or 0) or (r.ibs_credito_fornecedor or 0):
                partes.append(f"crédito do fornecedor CBS {fr(r.cbs_credito_fornecedor)} · "
                              f"IBS {fr(r.ibs_credito_fornecedor)}")
        if r.cp_cbs_450 or r.cp_ibs_450:
            partes.append("CP art. 450: " + "/".join(x for x, y in (("CBS", r.cp_cbs_450), ("IBS", r.cp_ibs_450)) if y))
        if r.cp_ibs_entrada:
            partes.append(f"CP IBS de entrada art. {r.cp_ibs_entrada}"
                          )
        add("Regras por cenário", f"{r.cenario} – {r.descricao}", "; ".join(partes) or "sem CBS/IBS",
            "Cadastros > Regras por cenário", r.base_legal)
    ez = carregar("param_empresas_zfm")
    if not ez.empty:
        cont = ez["tipo"].value_counts()
        add("Perímetro", "Tipo ZFM dos CNPJs (grupo e participantes do AM)",
            " · ".join(f"{k}: {v}" for k, v in cont.items()) + f" · revisados: {int(ez['revisado'].sum())}",
            "Cadastros > Empresas ZFM", "Pré-preenchido pelas EFDs (0000/0005, 0150 SUFRAMA e município)")
    for r in carregar("param_premissas").itertuples():
        add("Premissas de cálculo", r.chave, r.valor, "Cadastros > Premissas", r.descricao)
    mun = carregar("param_municipios_zfm")
    add("Perímetro", "Municípios da ZFM", ", ".join(f"{r.nome} ({r.cod_ibge})" for r in mun.itertuples()),
        "Cadastros > Municípios da ZFM", "Destinatário/fornecedor ZFM = AM + município da lista + SUFRAMA")
    pe = carregar("param_empresas")
    if not pe.empty:
        fora = pe.loc[~pe["incluir_na_analise"], "raiz_cnpj"].tolist()
        add("Perímetro", "Empresas fora da análise", ", ".join(fora) or "nenhuma", "Cadastros > Empresas")
    pr = carregar("param_produtos")
    if not pr.empty:
        inc = pr[pr["incentivado"]]
        add("Produtos", "Produtos incentivados", f"{len(inc)} de {len(pr)}", "Cadastros > Produtos",
            "Automático: item vendido com CFOP de produção própria")
        add("Produtos", "Incentivados sem alíquota de IPI", str(int(inc["aliq_ipi"].isna().sum())),
            "Cadastros > Produtos", "Sem TIPI: benefício de IPI = 0 e CP de CBS no percentual menor")
    cod = carregar("param_codigos_ajuste_icms")
    if not cod.empty:
        for classe, g in cod.groupby("classe"):
            add("Códigos de ajuste do ICMS", classe, ", ".join(g["codigo"]),
                "Cadastros > Códigos de ajuste", "Classificação automática pela descrição/estrutura do código")
    cf = carregar("param_cfops")
    if not cf.empty:
        add("CFOPs", "CFOPs tratados como receita", ", ".join(sorted(cf.loc[cf["eh_receita"], "cfop"])),
            "Cadastros > CFOPs")
    t = carregar("param_teses")
    add("Teses", "Teses cadastradas", str(len(t)), "Cadastros > Teses", "Aplicadas só com o filtro 'Com teses'")
    for regra, texto in [
        ("Resultado principal", "Diferença = carga To Be − carga As Is, por empresa, ano e tributo "
                                "(positivo = aumento de carga/perda) — DECISOES D-023"),
        ("Carga As Is", "Lida da apuração, sem recálculo (E110/E111/E116, E520, M200/M600), anualizada: "
                        "soma do período ÷ meses com arquivo × 12"),
        ("Carga To Be", "CBS/IBS sobre a base de operações, mês a mês, por unidade de apuração; ICMS = As Is × "
                        "fator do ano; IPI próprio = As Is × fator_ipi_proprio; PIS/COFINS extintos em 2027"),
        ("Reconciliação", "R5: carga recalculada pela base × apuração; diferença vira 'ajuste de reconciliação'"),
        ("Vantagem competitiva", "IPI do concorrente (receita incentivada × TIPI) hoje − no To Be; separado da "
                                 "carga própria"),
        ("Consolidação", "Cada empresa apurada separadamente; consolidado = soma (sem compensação)"),
        ("Benefício ZFM hoje", "Informativo: carga no regime geral − carga efetiva na ZFM; não entra na diferença"),
    ]:
        add("Método", regra, texto, "—", "DECISOES.md")
    return pd.DataFrame(linhas)
