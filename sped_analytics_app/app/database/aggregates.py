"""Tabelas agregadas (pré-somadas) da fato e roteador de consultas.

Objetivo: o relatório nunca varre a tabela de itens quando a pergunta pode ser respondida por um resumo menor.
Do menor para o maior; o roteador escolhe o primeiro que contém todas as colunas necessárias:

    agg_filial      competência + filial + CFOP + atributos de baixa cardinalidade (CST, origem, status...)
    agg_fornecedor  idem + fornecedor
    agg_produto     idem + item (código, NCM, descrição, conta contábil), sem fornecedor
    agg_item        idem + fornecedor + item
    fato            linha a linha (documento, datas, chaves, filtros sobre valores)

As agregadas são mantidas de forma incremental, por competência, ao final de cada consolidação.
"""
from __future__ import annotations

FATO = "fato_entradas_consolidadas"
FATO_VERSION = "3"   # altere ao mudar o esquema/lógica da fato: força recriação + reconsolidação ao abrir

MEASURES = ["qtd", "vl_item", "vl_desc", "vl_rateio_c190", "vl_contabil", "vl_bc_icms", "vl_icms", "vl_bc_icms_st",
            "vl_icms_st", "vl_fcp", "vl_fcp_st", "vl_bc_ipi", "vl_ipi", "vl_bc_pis", "vl_pis", "vl_bc_cofins",
            "vl_cofins", "vl_trib_recuperaveis", "vl_custo_liquido"]

_BASE = ["competencia", "cnpj_filial", "nome_filial", "uf_filial", "raiz_cnpj_filial", "cfop", "cst_icms",
         "aliq_icms", "cst_ipi", "cst_pis", "cst_cofins", "nat_bc_cred", "nat_bc_cred_origem", "tipo_item", "unid",
         "cod_mod", "reg_doc", "ind_emit", "origem", "status_efd", "nivel_cruzamento_efd", "flag_item_sintetico",
         "flag_sem_c190"]
_FORN = ["cnpj_cpf_fornecedor", "raiz_cnpj_fornecedor", "razao_social_fornecedor", "uf_fornecedor"]
_ITEM = ["cod_item", "cod_item_unificado", "chave_item_global", "descr_item", "cod_ncm", "cest", "cod_cta",
         "aliq_pis", "aliq_cofins", "aliq_ipi"]

# (tabela, dimensões, tabela de origem para a carga) — ordem: da menor para a maior
AGGREGATES: list[tuple[str, list[str], str]] = [
    ("agg_filial", _BASE, "agg_fornecedor"),
    ("agg_fornecedor", _BASE + _FORN, "agg_item"),
    ("agg_produto", _BASE + _ITEM, "agg_item"),
    ("agg_item", _BASE + _FORN + _ITEM, FATO),
]
_DIMS = {name: set(dims) for name, dims, _ in AGGREGATES}
_MEAS = set(MEASURES) | {"n_linhas"}
_SORT = {"agg_filial": "competencia, cnpj_filial, cfop",
         "agg_fornecedor": "competencia, cnpj_filial, cnpj_cpf_fornecedor",
         "agg_produto": "competencia, cnpj_filial, cod_item_unificado",
         "agg_item": "competencia, cnpj_filial, cnpj_cpf_fornecedor, cod_item_unificado"}


def _select(dims: list[str], source: str) -> str:
    cnt = "count(*)" if source == FATO else "sum(n_linhas)"
    ms = ", ".join(f"CAST(sum({m}) AS DECIMAL(18,{5 if m == 'qtd' else 2})) AS {m}" for m in MEASURES)
    return f"SELECT {', '.join(dims)}, {ms}, CAST({cnt} AS BIGINT) AS n_linhas FROM {source}"


def ddl() -> list[str]:
    """CREATE TABLE das agregadas (derivado da fato, sem dados)."""
    return [f"CREATE TABLE IF NOT EXISTS {name} AS {_select(dims, FATO)} WHERE 1 = 0 GROUP BY {', '.join(dims)}"
            for name, dims, _ in AGGREGATES]


def refresh_steps() -> list[tuple[str, str]]:
    """Recarga incremental das agregadas para as competências de _scope (da maior para a menor)."""
    steps = []
    for name, dims, source in reversed(AGGREGATES):
        steps.append((f"agregada_{name}",
                      f"DELETE FROM {name} WHERE competencia IN (SELECT competencia FROM _scope);\n"
                      f"INSERT INTO {name} {_select(dims, source)} "
                      f"WHERE competencia IN (SELECT competencia FROM _scope) "
                      f"GROUP BY {', '.join(dims)} ORDER BY {_SORT[name]}"))
    return steps


def pick_source(filter_columns: set[str], metric_columns: set[str] = frozenset(), needs_rows: bool = False) -> str:
    """Menor tabela capaz de responder a consulta.

    filter_columns: colunas usadas em agrupamentos e filtros — precisam ser dimensões da agregada (um filtro
                    sobre valor, ex. VL_ICMS > 0, é condição por linha e por isso só a fato responde);
    metric_columns: colunas somadas — podem ser medidas ou dimensões;
    needs_rows:     força a fato (ex.: contagem distinta de documentos).
    """
    if not needs_rows:
        for name, _, _ in AGGREGATES:
            if filter_columns <= _DIMS[name] and metric_columns <= (_DIMS[name] | _MEAS):
                return name
    return FATO
