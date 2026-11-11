# -*- coding: utf-8 -*-
"""
Consultas: visão consolidada, filtros criados pelo usuário e campos calculados.

Segurança e correção
--------------------
* O usuário nunca escreve SQL. Um filtro é uma lista de condições
  (campo, operador, valor); o campo e o operador vêm de listas fechadas e o
  valor entra na consulta como parâmetro.
* A visão consolidada não junta as tabelas de fatos das duas escriturações:
  agrupa a união delas e soma cada coluna de valor com um filtro por fonte
  (`sum(x) FILTER (WHERE fonte = ...)`). Uma linha nunca é multiplicada.
* Quando o filtro e o agrupamento só usam colunas da tabela pré-agregada
  (`visao`), a consulta roda sobre ela; senão, sobre os itens. O resultado é
  o mesmo (isso é verificado a cada carga), muda só a velocidade.
"""

from __future__ import annotations

import ast
import datetime as dt
import io
import json
import os
import re

from .base import DIMENSOES_VISAO
from .leiautes import (CONTRIB, FISCAL, MEDIDAS, NOME_FONTE, ROTULO_MEDIDA,
                       ROTULO_PAREAMENTO, SUFIXO_FONTE)

# ----------------------------------------------------------------------------
# Catálogo de campos (dimensões e campos de filtro)
#   sql     expressão sobre a tabela
#   tipo    texto | numero | data
#   visao   True se existe na tabela pré-agregada
#   dim     True se pode ser nível de agrupamento
#   junto   colunas descritivas exibidas junto (dependem do campo)
#   digitos True para códigos em que a pontuação digitada deve ser ignorada
# ----------------------------------------------------------------------------
_ORIGEM_CFOP = ("CASE substr({c}, 1, 1) WHEN '1' THEN '1 - Entrada do próprio estado' "
                "WHEN '2' THEN '2 - Entrada de outro estado' "
                "WHEN '3' THEN '3 - Entrada do exterior' "
                "WHEN '' THEN '(registro sem CFOP)' ELSE 'Outros' END")

CAMPOS = {
    "empresa": dict(sql="empresa_raiz", tipo="texto", visao=True, dim=True, digitos=True,
                    junto=["empresa_nome"],
                    rotulo="Empresa (raiz do CNPJ · Reg. 0000)"),
    "estab": dict(sql="estab_cnpj", tipo="texto", visao=True, dim=True, digitos=True,
                  rotulo="Estabelecimento (CNPJ · Reg. 0000 da EFD Fiscal; A010/C010/D010/F010 da EFD Contribuições)"),
    "periodo": dict(sql="periodo", tipo="data", visao=True, dim=True,
                    rotulo="Período de apuração (DT_INI · Reg. 0000)"),
    "fornecedor": dict(sql="part_doc", tipo="texto", visao=True, dim=True, digitos=True,
                       junto=["part_nome"],
                       rotulo="Fornecedor (CNPJ/CPF · Reg. 0150; CNPJ_CPF_PART no C191/C195)"),
    "fornecedor_nome": dict(sql="part_nome", tipo="texto", visao=True, dim=False,
                            rotulo="Nome do fornecedor (NOME · Reg. 0150)"),
    "cfop": dict(sql="cfop", tipo="texto", visao=True, dim=True, digitos=True,
                 junto=["cfop_descricao"],
                 rotulo="CFOP (Reg. C170/C190/C590/D190/D590 da EFD Fiscal; C170/C191/C195 da EFD Contribuições)"),
    "cfop_conc": dict(sql="cfop_conc", tipo="texto", visao=True, dim=True, digitos=True,
                      junto=["cfop_conc_descricao"],
                      rotulo="CFOP conciliado (o do registro; onde a EFD Contribuições não tem o campo, o do mesmo documento na EFD Fiscal)"),
    "cfop_origem": dict(sql=_ORIGEM_CFOP.format(c="cfop_conc"), tipo="texto", visao=True, dim=True,
                        rotulo="Origem da operação (1º dígito do CFOP conciliado)"),
    "item": dict(sql="cod_item", tipo="texto", visao=True, dim=True, junto=["descr_item"],
                 rotulo="Item (COD_ITEM · Reg. C170/A170/F100; C190 da Contribuições)"),
    "item_descricao": dict(sql="descr_item", tipo="texto", visao=True, dim=False,
                           rotulo="Descrição do item (DESCR_ITEM · Reg. 0200)"),
    "ncm": dict(sql="ncm", tipo="texto", visao=True, dim=True, digitos=True,
                rotulo="NCM (COD_NCM · Reg. 0200)"),
    "cst_icms": dict(sql="cst_icms", tipo="texto", visao=True, dim=True,
                     rotulo="CST ICMS (CST_ICMS · Reg. C170/C190/C590/D190/D590)"),
    "cst_pis": dict(sql="cst_pis", tipo="texto", visao=True, dim=True,
                    rotulo="CST PIS (CST_PIS · Reg. C170/A170/C501/D101/D501/C191/F100)"),
    "cst_cofins": dict(sql="cst_cofins", tipo="texto", visao=True, dim=True,
                       rotulo="CST COFINS (CST_COFINS · Reg. C170/A170/C505/D105/D505/C195/F100)"),
    "nat_bc_cred": dict(sql="nat_bc_cred", tipo="texto", visao=True, dim=True,
                        rotulo="Natureza da base do crédito (NAT_BC_CRED · Reg. A170/C501/D101/D501/F100)"),
    "cod_mod": dict(sql="cod_mod", tipo="texto", visao=True, dim=True,
                    rotulo="Modelo do documento (COD_MOD · Reg. C100/C500/D100/D500)"),
    "registro": dict(sql="registro", tipo="texto", visao=True, dim=True,
                     rotulo="Registro de origem da linha"),
    "fonte": dict(sql="fonte", tipo="texto", visao=True, dim=True,
                  rotulo="Escrituração de origem (FISCAL ou CONTRIB)"),
    "pareamento": dict(sql="pareamento", tipo="texto", visao=True, dim=True,
                       rotulo="Situação do documento nas duas escriturações"),
    "regime": dict(sql="regime", tipo="texto", visao=True, dim=True,
                   rotulo="Regime tributário do fornecedor (planilha externa · forma_de_tributacao)"),
    # ---- campos do documento (só na tabela de itens) ----
    "num_doc": dict(sql="num_doc", tipo="texto", visao=False, dim=True, junto=["chave"],
                    rotulo="Número do documento (NUM_DOC · Reg. C100/C500/D100/D500/A100)"),
    "chave": dict(sql="chave", tipo="texto", visao=False, dim=False, digitos=True,
                  rotulo="Chave eletrônica (CHV_NFE/CHV_CTE/CHV_DOCe/CHV_NFSE)"),
    "dt_doc": dict(sql="dt_doc", tipo="data", visao=False, dim=True,
                   rotulo="Data do documento (DT_DOC; DT_OPER no F100)"),
    "dt_e_s": dict(sql="dt_e_s", tipo="data", visao=False, dim=False,
                   rotulo="Data de entrada (DT_E_S/DT_ENT/DT_A_P/DT_EXE_SERV)"),
    "cod_sit": dict(sql="cod_sit", tipo="texto", visao=False, dim=True,
                    rotulo="Situação do documento (COD_SIT)"),
    "cod_cta": dict(sql="cod_cta", tipo="texto", visao=False, dim=True,
                    rotulo="Conta contábil (COD_CTA)"),
    "aliq_icms": dict(sql="aliq_icms", tipo="numero", visao=False, dim=True,
                      rotulo="Alíquota do ICMS % (ALIQ_ICMS)"),
    "aliq_pis": dict(sql="aliq_pis", tipo="numero", visao=False, dim=True,
                     rotulo="Alíquota do PIS % (ALIQ_PIS)"),
    "aliq_cofins": dict(sql="aliq_cofins", tipo="numero", visao=False, dim=True,
                        rotulo="Alíquota da COFINS % (ALIQ_COFINS)"),
}
# valores por linha, usáveis em filtros (ex.: VL_ICMS da linha maior que zero)
for _m in MEDIDAS:
    CAMPOS[_m] = dict(sql=_m, tipo="numero", visao=False, dim=False,
                      rotulo=f"{_m.upper()} da linha (valor do registro)")

ROTULO_JUNTO = {
    "empresa_nome": "Nome da empresa (NOME · Reg. 0000)",
    "part_nome": "Nome do fornecedor (NOME · Reg. 0150)",
    "descr_item": "Descrição do item (DESCR_ITEM · Reg. 0200; no F100 sem item, DESC_DOC_OPER)",
    "cfop_descricao": "Descrição do CFOP (tabela de CFOP carregada pelo usuário)",
    "cfop_conc_descricao": "Descrição do CFOP conciliado (tabela de CFOP carregada pelo usuário)",
    "chave": "Chave eletrônica (CHV_NFE/CHV_CTE/CHV_DOCe/CHV_NFSE)",
}

DIMENSOES = [k for k, c in CAMPOS.items() if c["dim"]]
DIMENSOES_PADRAO = ["empresa", "fornecedor", "cfop", "item"]

OPERADORES = {
    "igual": "é igual a",
    "diferente": "é diferente de",
    "em": "está na lista",
    "nao_em": "não está na lista",
    "contem": "contém",
    "nao_contem": "não contém",
    "comeca": "começa com",
    "maior": "é maior que",
    "maior_igual": "é maior ou igual a",
    "menor": "é menor que",
    "menor_igual": "é menor ou igual a",
    "entre": "está entre (dois valores separados por ;)",
    "vazio": "está vazio",
    "nao_vazio": "não está vazio",
}
_COMPARA = {"igual": "=", "diferente": "<>", "maior": ">", "maior_igual": ">=",
            "menor": "<", "menor_igual": "<="}


class FiltroInvalido(ValueError):
    pass


# ----------------------------------------------------------------------------
# Medidas
# ----------------------------------------------------------------------------

def medidas_disponiveis():
    """[(medida, fonte)] na ordem de exibição."""
    return [(m, f) for f in (FISCAL, CONTRIB) for m in MEDIDAS if f in ROTULO_MEDIDA[m]]


def col_medida(medida: str, fonte: str) -> str:
    return f"{medida}__{SUFIXO_FONTE[fonte]}"


def nome_variavel(medida: str, fonte: str) -> str:
    """Nome usado nas fórmulas dos campos calculados (ex.: VL_PIS_CONTRIB)."""
    return f"{medida}_{SUFIXO_FONTE[fonte]}".upper()


VARIAVEIS = {nome_variavel(m, f): (m, f) for m, f in medidas_disponiveis()}


# ----------------------------------------------------------------------------
# Filtros
# ----------------------------------------------------------------------------

def _numero(txt: str) -> float:
    t = str(txt).strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        raise FiltroInvalido(f"'{txt}' não é um número.")


def _data(txt: str) -> dt.date:
    t = str(txt).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d%m%Y"):
        try:
            return dt.datetime.strptime(t, formato).date()
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)
    if m:
        return dt.date(int(m.group(2)), int(m.group(1)), 1)
    raise FiltroInvalido(f"'{txt}' não é uma data (use DD/MM/AAAA ou MM/AAAA).")


def _valor(campo: dict, txt):
    if campo["tipo"] == "numero":
        return _numero(txt)
    if campo["tipo"] == "data":
        return _data(txt)
    t = str(txt).strip()
    if campo.get("digitos"):
        so = re.sub(r"\D", "", t)
        return so if so else t
    return t


def _lista(txt) -> list[str]:
    if isinstance(txt, (list, tuple)):
        return [str(x) for x in txt if str(x).strip()]
    return [p for p in re.split(r"[;\n]", str(txt or "")) if p.strip()]


def _condicao(cond: dict):
    campo_id, op = cond.get("campo"), cond.get("operador")
    if campo_id not in CAMPOS:
        raise FiltroInvalido(f"Campo desconhecido: {campo_id}")
    if op not in OPERADORES:
        raise FiltroInvalido(f"Operador desconhecido: {op}")
    campo = CAMPOS[campo_id]
    sql = campo["sql"]
    bruto = cond.get("valor")
    if op in ("vazio", "nao_vazio"):
        vazio = f"({sql} IS NULL)" if campo["tipo"] != "texto" else f"(coalesce({sql}, '') = '')"
        return (vazio if op == "vazio" else f"(NOT {vazio})"), []
    if bruto is None or str(bruto).strip() == "":
        raise FiltroInvalido(f"Falta o valor do filtro '{campo['rotulo']}'.")
    if op in _COMPARA:
        return f"({sql} {_COMPARA[op]} ?)", [_valor(campo, bruto)]
    if op in ("em", "nao_em"):
        valores = [_valor(campo, x) for x in _lista(bruto)]
        if not valores:
            raise FiltroInvalido("A lista de valores está vazia.")
        marcas = ", ".join("?" for _ in valores)
        return f"({sql} {'NOT ' if op == 'nao_em' else ''}IN ({marcas}))", valores
    if op == "entre":
        partes = _lista(bruto)
        if len(partes) != 2:
            raise FiltroInvalido("O operador 'entre' pede dois valores separados por ponto e vírgula.")
        return f"({sql} BETWEEN ? AND ?)", [_valor(campo, partes[0]), _valor(campo, partes[1])]
    if campo["tipo"] != "texto":
        raise FiltroInvalido(f"O operador '{OPERADORES[op]}' só vale para campos de texto.")
    texto = str(bruto).strip()
    if campo.get("digitos") and re.sub(r"\D", "", texto):
        texto = re.sub(r"\D", "", texto)
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    if op == "comeca":
        return f"({sql} ILIKE ? ESCAPE '\\')", [escapado + "%"]
    padrao = "%" + escapado + "%"
    if op == "contem":
        return f"({sql} ILIKE ? ESCAPE '\\')", [padrao]
    return f"(coalesce({sql}, '') NOT ILIKE ? ESCAPE '\\')", [padrao]


def montar_where(condicoes) -> tuple[str, list, bool]:
    """Condições do mesmo grupo são ligadas por E; grupos diferentes, por OU.
    Devolve (sql, parâmetros, usa_só_colunas_da_visão)."""
    grupos, so_visao = {}, True
    for c in condicoes or []:
        if not c or not c.get("campo"):
            continue
        sql, params = _condicao(c)
        try:
            g = int(c.get("grupo") or 1)
        except (TypeError, ValueError):
            g = 1
        grupos.setdefault(g, []).append((sql, params))
        so_visao = so_visao and CAMPOS[c["campo"]]["visao"]
    if not grupos:
        return "", [], True
    partes, params = [], []
    for g in sorted(grupos):
        partes.append("(" + " AND ".join(s for s, _ in grupos[g]) + ")")
        for _, p in grupos[g]:
            params.extend(p)
    return "(" + " OR ".join(partes) + ")", params, so_visao


def combinar(*listas):
    """Junta vários filtros (cada um uma lista de condições) com E.
    Devolve (sql, parâmetros, usa_só_colunas_da_visão)."""
    sqls, params, so_visao = [], [], True
    for condicoes in listas:
        s, p, v = montar_where(condicoes)
        if s:
            sqls.append(s)
            params.extend(p)
            so_visao = so_visao and v
    return " AND ".join(sqls), params, so_visao


# ----------------------------------------------------------------------------
# Campos calculados (fórmulas sobre os totais do grupo)
# ----------------------------------------------------------------------------

def formula_para_sql(formula: str) -> tuple[str, list[tuple[str, str]]]:
    """Traduz uma fórmula aritmética (ex.: VL_PIS_CONTRIB / VL_BC_PIS_CONTRIB * 100)
    para SQL. Só aceita números, nomes de medidas, + - * / e parênteses."""
    texto = re.sub(r"(?<=\d),(?=\d)", ".", str(formula or "").strip())
    if not texto:
        raise FiltroInvalido("A fórmula está vazia.")
    try:
        arvore = ast.parse(texto, mode="eval")
    except SyntaxError:
        raise FiltroInvalido("A fórmula tem erro de sintaxe.")
    usadas = []

    def visita(no):
        if isinstance(no, ast.Expression):
            return visita(no.body)
        if isinstance(no, ast.BinOp) and isinstance(no.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visita(no.left), visita(no.right)
            if isinstance(no.op, ast.Div):
                return f"({a} / NULLIF({b}, 0))"
            simbolo = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}[type(no.op)]
            return f"({a} {simbolo} {b})"
        if isinstance(no, ast.UnaryOp) and isinstance(no.op, (ast.USub, ast.UAdd)):
            return f"({'-' if isinstance(no.op, ast.USub) else '+'}{visita(no.operand)})"
        if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)) \
                and not isinstance(no.value, bool):
            return repr(float(no.value))
        if isinstance(no, ast.Name):
            nome = no.id.upper()
            if nome not in VARIAVEIS:
                raise FiltroInvalido(f"'{no.id}' não é uma medida conhecida. "
                                     "Veja a lista de nomes aceitos.")
            medida, fonte = VARIAVEIS[nome]
            if (medida, fonte) not in usadas:
                usadas.append((medida, fonte))
            return f"CAST(coalesce({col_medida(medida, fonte)}, 0) AS DOUBLE)"
        raise FiltroInvalido("A fórmula só aceita números, nomes de medidas, + - * / e parênteses.")

    return visita(arvore), usadas


# ----------------------------------------------------------------------------
# Visão consolidada
# ----------------------------------------------------------------------------

def _seletor_dims(dims):
    selecao, grupo, saida = [], [], []
    for d in dims:
        campo = CAMPOS[d]
        selecao.append(f"{campo['sql']} AS {d}")
        grupo.append(campo["sql"])
        saida.append(d)
        for j in campo.get("junto", []):
            if j in ("cfop_descricao", "cfop_conc_descricao"):
                continue          # vem da tabela de CFOP, depois de agregar
            selecao.append(f"max({j}) AS {j}")
            saida.append(j)
    return selecao, grupo, saida


def _fonte_dados(dims, so_visao_filtros):
    usa_visao = so_visao_filtros and all(CAMPOS[d]["visao"] for d in dims)
    if usa_visao:
        return "visao", "CAST(coalesce(sum(n_linhas), 0) AS BIGINT)", ""
    return "itens", "count(*)", "NOT repetido"


def consolidar(con, dims, medidas, filtros=(), calculados=None, ordem=None,
               decrescente=True, limite=5000):
    """Executa a visão consolidada.

    dims        níveis de agrupamento (ids de CAMPOS), na ordem desejada
    medidas     [(medida, fonte)] a exibir
    filtros     listas de condições (ligadas por E entre si)
    calculados  {nome: fórmula}
    Devolve dict com: dados (DataFrame), total_grupos, totais (dict),
    colunas (ordem), tabela (visao|itens), segundos.
    """
    import time
    t0 = time.time()
    calculados = calculados or {}
    where, params, so_visao = combinar(*filtros)
    tabela, contagem, fixo = _fonte_dados(dims, so_visao)
    condicoes = [c for c in (fixo, where) if c]
    where_sql = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""

    formulas, extras = {}, []
    for nome, formula in calculados.items():
        sql, usadas = formula_para_sql(formula)
        formulas[nome] = sql
        extras += [u for u in usadas if u not in medidas and u not in extras]

    def soma(m, f):
        return f"sum({m}) FILTER (WHERE fonte = '{f}') AS {col_medida(m, f)}"

    selecao, grupo, cols_dim = _seletor_dims(dims)
    somas = [soma(m, f) for m, f in list(medidas) + extras]
    campos = ", ".join(selecao + [f"{contagem} AS n_linhas"] + somas)
    group_by = ("GROUP BY " + ", ".join(grupo)) if grupo else ""
    cte = f"WITH g AS (SELECT {campos} FROM {tabela} {where_sql} {group_by})"

    cols_calc = [f"{sql} AS \"calc_{i}\"" for i, sql in enumerate(formulas.values())]
    nomes_calc = {f"calc_{i}": nome for i, nome in enumerate(formulas)}
    juncoes, cols_extra = "", []
    for d, apelido in (("cfop", "cfop_descricao"), ("cfop_conc", "cfop_conc_descricao")):
        if d in dims:
            juncoes += f" LEFT JOIN cfop t_{d} ON t_{d}.cfop = g.{d}"
            cols_extra.append(f"coalesce(t_{d}.descricao, '') AS {apelido}")
    cols_med = [col_medida(m, f) for m, f in medidas]
    ordem_col = ordem if ordem in cols_dim + cols_med + ["n_linhas"] + list(nomes_calc) else None
    if ordem_col is None:
        ordem_col = cols_med[0] if cols_med else (cols_dim[0] if cols_dim else "n_linhas")
    direcao = "DESC NULLS LAST" if decrescente else "ASC NULLS LAST"
    desempate = (", " + ", ".join(f"g.{c}" for c in dims)) if dims else ""
    saida = ", ".join([f"g.{c}" for c in cols_dim] + cols_extra + ["g.n_linhas"]
                      + [f"g.{c}" for c in cols_med] + cols_calc)
    cur = con.cursor()
    dados = cur.execute(
        f"{cte} SELECT {saida} FROM g{juncoes} ORDER BY \"{ordem_col}\" {direcao}{desempate} "
        f"LIMIT {int(limite)}", params).df()
    total_grupos = cur.execute(f"{cte} SELECT count(*) FROM g", params).fetchone()[0]

    # totais gerais (uma única linha, mesmos filtros)
    campos_tot = ", ".join([f"{contagem} AS n_linhas"] + somas)
    cte_tot = f"WITH g AS (SELECT {campos_tot} FROM {tabela} {where_sql})"
    linha = cur.execute(
        f"{cte_tot} SELECT {', '.join(['n_linhas'] + cols_med + cols_calc)} FROM g",
        params).fetchone()
    nomes_tot = ["n_linhas"] + cols_med + list(nomes_calc)
    totais = dict(zip(nomes_tot, linha)) if linha else {}

    ordem_cols = list(dados.columns)
    return {"dados": dados, "total_grupos": total_grupos, "totais": totais,
            "colunas": ordem_cols, "nomes_calc": nomes_calc, "tabela": tabela,
            "segundos": round(time.time() - t0, 3)}


def rotulos(colunas, medidas, calculados=None, nomes_calc=None) -> dict:
    """Rótulo de origem de cada coluna do resultado."""
    calculados, nomes_calc = calculados or {}, nomes_calc or {}
    r = {}
    por_col = {col_medida(m, f): ROTULO_MEDIDA[m][f] for m, f in medidas_disponiveis()}
    for c in colunas:
        if c in CAMPOS:
            r[c] = CAMPOS[c]["rotulo"]
        elif c in ROTULO_JUNTO:
            r[c] = ROTULO_JUNTO[c]
        elif c in por_col:
            r[c] = por_col[c]
        elif c == "n_linhas":
            r[c] = "Linhas somadas (contagem de registros)"
        elif c in nomes_calc:
            nome = nomes_calc[c]
            r[c] = f"{nome} (Cálculo: {calculados.get(nome, '')})"
        else:
            r[c] = c
    return r


# ----------------------------------------------------------------------------
# Detalhe (documentos e itens de um grupo)
# ----------------------------------------------------------------------------
COLUNAS_DETALHE = [
    ("fonte", "Escrituração"), ("registro", "Registro"),
    ("estab_cnpj", "Estabelecimento (CNPJ)"), ("periodo", "Período"),
    ("num_doc", "NUM_DOC"), ("ser", "SER"), ("dt_doc", "DT_DOC"), ("dt_e_s", "Data de entrada"),
    ("chave", "Chave eletrônica"), ("part_doc", "Fornecedor (CNPJ/CPF)"),
    ("part_nome", "Fornecedor (nome)"), ("num_item", "NUM_ITEM"), ("cod_item", "COD_ITEM"),
    ("descr_item", "Descrição"), ("ncm", "NCM"), ("cfop", "CFOP"), ("cst_icms", "CST_ICMS"),
    ("cst_pis", "CST_PIS"), ("cst_cofins", "CST_COFINS"), ("qtd", "QTD"), ("unid", "UNID"),
    ("vl_item", "VL_ITEM"), ("vl_opr", "VL_OPR"), ("vl_bc_icms", "VL_BC_ICMS"),
    ("aliq_icms", "ALIQ_ICMS"), ("vl_icms", "VL_ICMS"), ("vl_icms_st", "VL_ICMS_ST"),
    ("vl_ipi", "VL_IPI"), ("vl_bc_pis", "VL_BC_PIS"), ("aliq_pis", "ALIQ_PIS"),
    ("vl_pis", "VL_PIS"), ("vl_bc_cofins", "VL_BC_COFINS"), ("aliq_cofins", "ALIQ_COFINS"),
    ("vl_cofins", "VL_COFINS"), ("vl_iss", "VL_ISS"), ("cod_cta", "COD_CTA"),
    ("pareamento", "Situação nas duas EFDs"), ("nome_arquivo", "Arquivo"),
    ("linha", "Linha no arquivo"),
]


def detalhar(con, filtros=(), chaves=None, limite=2000):
    """Linhas de item por trás de um grupo da visão. `chaves` = {dimensão: valor}."""
    where, params, _ = combinar(*filtros)
    condicoes = ["NOT repetido"]
    if where:
        condicoes.append(where)
    for d, valor in (chaves or {}).items():
        sql = CAMPOS[d]["sql"]
        if valor is None or valor != valor:          # None, NaN ou NaT
            condicoes.append(f"({sql} IS NULL)")
            continue
        if hasattr(valor, "to_pydatetime"):
            valor = valor.to_pydatetime().date()
        elif hasattr(valor, "item"):
            valor = valor.item()
        condicoes.append(f"({sql} = ?)")
        params.append(valor)
    cols = ", ".join(("a." if c == "nome_arquivo" else "i.") + c for c, _ in COLUNAS_DETALHE)
    # o filtro roda só sobre a tabela de itens; o nome do arquivo entra depois,
    # pela chave única arquivo_id
    sql = (f"SELECT {cols} FROM (SELECT * FROM itens WHERE {' AND '.join(condicoes)} "
           f"ORDER BY fonte, periodo, num_doc, linha LIMIT {int(limite)}) i "
           f"JOIN arquivos a ON a.arquivo_id = i.arquivo_id "
           f"ORDER BY i.fonte, i.periodo, i.num_doc, i.linha")
    df = con.cursor().execute(sql, params).df()
    return df.rename(columns=dict(COLUNAS_DETALHE))


def valores_distintos(con, campo_id: str, limite=2000):
    """Valores existentes de um campo (para as listas de seleção dos filtros)."""
    campo = CAMPOS[campo_id]
    tabela = "visao" if campo["visao"] else "itens"
    junto = campo.get("junto", [])
    extra = junto[0] if junto and not junto[0].startswith("cfop") else None
    if extra:
        sql = (f"SELECT {campo['sql']} AS v, max({extra}) AS d FROM {tabela} "
               f"GROUP BY 1 ORDER BY 1 LIMIT {int(limite)}")
    else:
        sql = f"SELECT DISTINCT {campo['sql']} AS v, NULL AS d FROM {tabela} ORDER BY 1 LIMIT {int(limite)}"
    return con.cursor().execute(sql).fetchall()


# ----------------------------------------------------------------------------
# Exportação
# ----------------------------------------------------------------------------
LIMITE_EXCEL = 1_048_575


def para_excel(df, rotulos_col: dict, titulo="Consolidado", notas=None) -> bytes:
    """Planilha com o cabeçalho de origem em cada coluna (em memória)."""
    import decimal
    import numbers

    import pandas as pd
    import xlsxwriter
    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {"in_memory": True, "nan_inf_to_errors": True})
    fmt_cab = book.add_format({"bold": True, "bg_color": "#1F4E5F", "font_color": "#FFFFFF",
                               "text_wrap": True, "valign": "vcenter", "border": 1})
    fmt_num = book.add_format({"num_format": "#,##0.00"})
    fmt_data = book.add_format({"num_format": "dd/mm/yyyy"})
    ws = book.add_worksheet(titulo[:31])
    for j, c in enumerate(df.columns):
        ws.write(0, j, rotulos_col.get(c, c), fmt_cab)
        numerica = pd.api.types.is_numeric_dtype(df[c]) and c != "n_linhas"
        ws.set_column(j, j, 18 if numerica else 26, fmt_num if numerica else None)
    ws.set_row(0, 75)
    for i, linha in enumerate(df.itertuples(index=False), start=1):
        for j, valor in enumerate(linha):
            if valor is None or valor is pd.NaT:
                continue
            if isinstance(valor, bool):
                ws.write_string(i, j, "Sim" if valor else "Não")
            elif isinstance(valor, (numbers.Number, decimal.Decimal)):
                if valor == valor:                       # ignora NaN
                    ws.write_number(i, j, float(valor))
            elif isinstance(valor, (dt.date, dt.datetime)):
                ws.write_datetime(i, j, valor, fmt_data)
            else:
                ws.write_string(i, j, str(valor))
    ws.freeze_panes(1, 0)
    if len(df):
        ws.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
    if notas:
        wn = book.add_worksheet("Sobre")
        wn.set_column(0, 0, 34)
        wn.set_column(1, 1, 120)
        fk = book.add_format({"bold": True, "valign": "top"})
        fv = book.add_format({"text_wrap": True, "valign": "top"})
        for i, (k, val) in enumerate(notas):
            wn.write(i, 0, k, fk)
            wn.write(i, 1, str(val), fv)
    book.close()
    return buffer.getvalue()


def para_csv(df, rotulos_col: dict) -> bytes:
    saida = df.rename(columns=rotulos_col)
    return saida.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig")


# ----------------------------------------------------------------------------
# Filtros e campos calculados salvos pelo usuário (arquivo JSON)
# ----------------------------------------------------------------------------
EXEMPLOS = {
    "filtros": {
        "Exemplo: PIS/COFINS com CST de crédito (50 a 56)": [
            {"grupo": 1, "campo": "cst_pis", "operador": "entre", "valor": "50;56"}],
        "Exemplo: compras para industrialização ou revenda": [
            {"grupo": 1, "campo": "cfop_conc", "operador": "em",
             "valor": "1101;1102;2101;2102;3101;3102"}],
        "Exemplo: documentos que só estão em uma das EFDs": [
            {"grupo": 1, "campo": "pareamento", "operador": "em",
             "valor": "SO_FISCAL;SO_CONTRIB"}],
    },
    "calculados": {
        "Alíquota efetiva de PIS % (Contribuições)": "VL_PIS_CONTRIB / VL_BC_PIS_CONTRIB * 100",
        "PIS + COFINS (Contribuições)": "VL_PIS_CONTRIB + VL_COFINS_CONTRIB",
        "Diferença de ICMS (Fiscal - Contribuições)": "VL_ICMS_FISCAL - VL_ICMS_CONTRIB",
    },
}


def carregar_config(caminho: str) -> dict:
    if os.path.isfile(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.setdefault("filtros", {})
            cfg.setdefault("calculados", {})
            return cfg
        except (OSError, ValueError):
            pass
    return json.loads(json.dumps(EXEMPLOS))


def salvar_config(caminho: str, cfg: dict):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)


def validar_config(cfg: dict) -> list[str]:
    """Erros de um arquivo de configuração importado (lista vazia = válido)."""
    erros = []
    for nome, conds in (cfg.get("filtros") or {}).items():
        try:
            montar_where(conds)
        except FiltroInvalido as e:
            erros.append(f"Filtro '{nome}': {e}")
    for nome, formula in (cfg.get("calculados") or {}).items():
        try:
            formula_para_sql(formula)
        except FiltroInvalido as e:
            erros.append(f"Campo calculado '{nome}': {e}")
    return erros
