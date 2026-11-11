#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testes de ponta a ponta do consolidador, com EFDs sintéticas de valores
conhecidos (ver gerar_sinteticos.py).

Uso:  python testes/test_consolidador.py
Sai com código 0 quando todas as verificações passam.
"""

import json
import os
import shutil
import sys
import tempfile
from decimal import Decimal as D

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)

from efd import base, consulta  # noqa: E402
from efd.leiautes import CONTRIB, FISCAL  # noqa: E402
import gerar_sinteticos as gs  # noqa: E402

FALHAS = []
TOTAL = [0]


def check(nome, condicao, detalhe=""):
    TOTAL[0] += 1
    if condicao:
        print(f"[ OK  ] {nome}")
    else:
        print(f"[FALHA] {nome}  {detalhe}")
        FALHAS.append(nome)


def igual(nome, obtido, esperado):
    check(nome, obtido == esperado, f"obtido={obtido!r} esperado={esperado!r}")


def acoes(plano):
    return {p["info"]["nome_arquivo"]: p["acao"] for p in plano}


def totais(con, fonte, so_validos=True):
    cond = "AND NOT repetido" if so_validos else ""
    r = con.execute(f"""
        SELECT count(*), sum(vl_item), sum(vl_opr), sum(vl_bc_icms), sum(vl_icms),
               sum(vl_icms_st), sum(vl_ipi), sum(vl_pis), sum(vl_cofins), sum(vl_iss)
        FROM itens WHERE fonte = ? {cond}""", [fonte]).fetchone()
    nomes = ("n", "vl_item", "vl_opr", "vl_bc_icms", "vl_icms", "vl_icms_st", "vl_ipi",
             "vl_pis", "vl_cofins", "vl_iss")
    return dict(zip(nomes, r))


def main():
    raiz = tempfile.mkdtemp(prefix="efd_teste_")
    pasta_base = os.path.join(raiz, "base")
    arq = gs.gerar(os.path.join(raiz, "dados"))
    con = base.abrir(os.path.join(pasta_base, "efd.duckdb"))
    nome = lambda k: os.path.basename(arq[k])

    # ------------------------------------------------------------------ 1
    print("\n== 1. Carga inicial (5 escriturações, leitura em paralelo) ==")
    lote = [arq[k] for k in ("fiscal_matriz_jan", "fiscal_filial_jan", "contrib_jan",
                             "fiscal_matriz_fev", "contrib_fev")]
    plano = base.planejar(con, lote)
    igual("plano: todos para carregar", set(acoes(plano).values()), {"CARREGAR"})
    res = base.carregar(con, plano, pasta_base, processos=2)
    check("5 arquivos carregados e conferidos", all(r["ok"] for r in res) and len(res) == 5,
          str([r["mensagem"] for r in res if not r["ok"]]))
    igual("cada arquivo foi lido em um processo próprio",
          {r.get("modo_leitura") for r in res}, {"processo próprio"})
    ver = base.ultimas_verificacoes(con)
    check("todas as verificações de integridade passam", all(v["ok"] for v in ver),
          str([v for v in ver if not v["ok"]]))
    igual("tipos identificados pelo registro 0000",
          con.execute("SELECT tipo, count(*) FROM arquivos GROUP BY 1 ORDER BY 1").fetchall(),
          [("CONTRIB", 2), ("FISCAL", 3)])
    igual("codificação detectada (latin-1 e utf-8)",
          con.execute("SELECT DISTINCT encoding FROM arquivos ORDER BY 1").fetchall(),
          [("latin-1",), ("utf-8",)])

    f = totais(con, FISCAL)
    igual("Fiscal: 10 linhas válidas", f["n"], 10)
    igual("Fiscal: VL_ITEM (C170) = 5.700,00", f["vl_item"], D("5700.00"))
    igual("Fiscal: VL_OPR (C190 sem C170 + C590 + D190 + D590) = 3.450,00", f["vl_opr"], D("3450.00"))
    igual("Fiscal: VL_BC_ICMS = 8.850,00", f["vl_bc_icms"], D("8850.00"))
    igual("Fiscal: VL_ICMS = 1.514,50 (antes da retificadora)", f["vl_icms"], D("1514.50"))
    igual("Fiscal: VL_ICMS_ST = 25,00", f["vl_icms_st"], D("25.00"))
    igual("Fiscal: VL_IPI = 50,00", f["vl_ipi"], D("50.00"))
    c = totais(con, CONTRIB)
    igual("Contribuições: 15 linhas", c["n"], 15)
    igual("Contribuições: VL_ITEM = 14.300,00", c["vl_item"], D("14300.00"))
    igual("Contribuições: VL_PIS = 222,76", c["vl_pis"], D("222.76"))
    igual("Contribuições: VL_COFINS = 1.026,00", c["vl_cofins"], D("1026.00"))
    igual("Contribuições: VL_ICMS (C170) = 1.133,00", c["vl_icms"], D("1133.00"))
    igual("Contribuições: VL_ISS = 50,01 (rateio fecha com o A100)", c["vl_iss"], D("50.01"))
    igual("ISS rateado em centavos exatos (16,67 + 33,34)",
          con.execute("SELECT vl_iss FROM itens WHERE registro = 'A170' ORDER BY vl_item").fetchall(),
          [(D("16.67"),), (D("33.34"),)])

    print("\n== 2. Repetição de documento entre períodos ==")
    igual("NF-e 1001 repetida na Fiscal de fevereiro: 2 itens fora dos totais",
          con.execute("SELECT count(*), sum(vl_item) FROM itens WHERE repetido").fetchone(),
          (2, D("1500.00")))
    rep = base.repeticoes(con)
    igual("lista de repetições mostra as 2 ocorrências", len(rep), 2)
    igual("vale a ocorrência do período da data de entrada (janeiro)",
          rep[rep["ocorrencia"] == 1]["periodo"].iloc[0].strftime("%Y-%m"), "2026-01")
    igual("total SEM excluir repetições seria maior (prova de que a exclusão atua)",
          totais(con, FISCAL, so_validos=False)["vl_item"], D("7200.00"))

    print("\n== 3. Mesmo conteúdo com outro nome / outra codificação ==")
    plano = base.planejar(con, [arq["copia_bytes"], arq["copia_utf8"]])
    igual("cópia de bytes e cópia UTF-8/LF reconhecidas como já carregadas",
          set(acoes(plano).values()), {"JA_CARREGADO"})
    base.carregar(con, plano, pasta_base, processos=0)
    igual("nada mudou na base", totais(con, FISCAL)["vl_item"], D("5700.00"))

    print("\n== 4. Retificadora ==")
    plano = base.planejar(con, [arq["fiscal_filial_jan_retif"]])
    igual("retificadora entra no lugar do original", acoes(plano)[nome("fiscal_filial_jan_retif")], "CARREGAR")
    igual("o original está marcado para sair", len(plano[0]["substitui"]), 1)
    res = base.carregar(con, plano, pasta_base, processos=0)     # leitura no mesmo processo
    check("retificadora carregada", res[0]["ok"], res[0]["mensagem"])
    igual("continua havendo 5 escriturações", con.execute("SELECT count(*) FROM arquivos").fetchone()[0], 5)
    igual("o original saiu da base",
          con.execute("SELECT count(*) FROM arquivos WHERE nome_arquivo = ?", [nome("fiscal_filial_jan")]).fetchone()[0], 0)
    igual("Fiscal: VL_ICMS = 1.526,50 (com a retificadora)", totais(con, FISCAL)["vl_icms"], D("1526.50"))
    plano = base.planejar(con, [arq["fiscal_filial_jan"]])
    igual("recarregar o original é recusado (a base já tem a retificadora)",
          acoes(plano)[nome("fiscal_filial_jan")], "IGNORADO")

    print("\n== 5. Versões em conflito e arquivo inválido ==")
    plano = base.planejar(con, [arq["contrib_fev_outra"], arq["invalido"]])
    igual("segunda versão original do mesmo período: bloqueada",
          acoes(plano)[nome("contrib_fev_outra")], "CONFLITO")
    igual("arquivo que não é EFD: recusado", acoes(plano)[nome("invalido")], "INVALIDO")
    base.carregar(con, plano, pasta_base)
    igual("a base não mudou", totais(con, CONTRIB)["vl_item"], D("14300.00"))

    con2 = base.abrir(os.path.join(raiz, "base2", "efd.duckdb"))
    plano = base.planejar(con2, [arq["fiscal_filial_jan"], arq["fiscal_filial_jan_retif"],
                                 arq["copia_bytes"], arq["copia_utf8"], arq["fiscal_matriz_jan"],
                                 arq["contrib_fev"], arq["contrib_fev_outra"]])
    a = acoes(plano)
    igual("lote: original + retificadora -> só a retificadora carrega",
          (a[nome("fiscal_filial_jan")], a[nome("fiscal_filial_jan_retif")]), ("IGNORADO", "CARREGAR"))
    igual("lote: 3 arquivos de mesmo conteúdo -> 1 carrega",
          sorted([a[nome("copia_bytes")], a[nome("copia_utf8")], a[nome("fiscal_matriz_jan")]]),
          ["CARREGAR", "IGNORADO", "IGNORADO"])
    igual("lote: dois originais do mesmo período -> os dois bloqueados",
          (a[nome("contrib_fev")], a[nome("contrib_fev_outra")]), ("CONFLITO", "CONFLITO"))
    con2.close()

    print("\n== 6. Totais de controle (carga corrompida é desfeita) ==")
    from efd.leitor import inspecionar, processar_arquivo
    info = inspecionar(arq["contrib_fev_outra"])
    meta = processar_arquivo(info, os.path.join(raiz, "adulterado"))
    meta["controle"]["itens"]["somas"]["vl_pis"] += 1          # 1 centavo de diferença
    antes = con.execute("SELECT count(*) FROM itens_base").fetchone()[0]
    try:
        base._carregar_um(con, meta, [])
        check("diferença de 1 centavo no controle desfaz a carga", False)
    except base.ErroDeCarga as e:
        check("diferença de 1 centavo no controle desfaz a carga", "vl_pis" in str(e))
    igual("nenhuma linha ficou gravada", con.execute("SELECT count(*) FROM itens_base").fetchone()[0], antes)
    igual("nenhum arquivo ficou registrado", con.execute("SELECT count(*) FROM arquivos").fetchone()[0], 5)

    print("\n== 7. Pareamento Fiscal x Contribuições ==")
    par = dict(((r[0], r[1]), r[2]) for r in con.execute(
        "SELECT fonte, pareamento, count(*) FROM itens WHERE NOT repetido GROUP BY ALL").fetchall())
    igual("situação das linhas nas duas EFDs", par, {
        (FISCAL, "AMBAS"): 9, (FISCAL, "SO_FISCAL"): 1,
        (CONTRIB, "AMBAS"): 9, (CONTRIB, "SO_CONTRIB"): 1,
        (CONTRIB, "NAO_SE_APLICA"): 4, (CONTRIB, "SEM_CONTRAPARTE"): 1})
    igual("documento sem chave eletrônica pareado por modelo/série/número/data/participante",
          con.execute("SELECT DISTINCT pareamento FROM itens WHERE registro IN ('C590', 'D590', 'C501+C505', 'D501+D505')").fetchall(),
          [("AMBAS",)])
    igual("CFOP conciliado: energia, frete e telecom da Contribuições recebem o CFOP da Fiscal",
          con.execute("SELECT registro, cfop, cfop_conc FROM itens WHERE fonte = 'CONTRIB' AND cfop = '' AND cfop_conc <> '' ORDER BY 1").fetchall(),
          [("C501+C505", "", "1253"), ("D101+D105", "", "1352"), ("D501+D505", "", "1303")])
    igual("fornecedor unificado pelo CNPJ (códigos diferentes nas duas EFDs)",
          con.execute("SELECT count(DISTINCT part_cod) FILTER (WHERE part_cod <> ''), count(DISTINCT part_doc) FROM itens WHERE part_doc = ?", [gs.ACO]).fetchone(),
          (2, 1))
    div = base.divergencias_itens(con)
    igual("2 itens divergentes entre as EFDs (NF 1002 e NF 5001)", sorted(div["num_doc"]), ["1002", "5001"])
    b = div[div["num_doc"] == "1002"].iloc[0]
    igual("NF 1002: CFOP 1101 x 1102 e ICMS 360 x 350",
          (b["cfop_fiscal"], b["cfop_contrib"], float(b["vl_icms_fiscal"]), float(b["vl_icms_contrib"])),
          ("1101", "1102", 360.0, 350.0))

    print("\n== 8. Conferências internas ==")
    resumo, difs = base.conf_c190(con)
    igual("C190 x C170: 6 grupos, 5 iguais", (resumo["grupos"], resumo["iguais"]), (6, 5))
    igual("o grupo que não fecha é a NF 1010 (126,00 x 120,00)",
          (difs["num_doc"].iloc[0], float(difs["icms_c170"].iloc[0]), float(difs["icms_c190"].iloc[0])),
          ("1010", 126.0, 120.0))
    cab = base.conf_cabecalho(con)
    igual("cabeçalho x detalhes: tudo fecha (prova das posições de campo)",
          int(cab["diferentes"].sum()), 0)
    check("cabeçalho x detalhes cobre as duas escriturações",
          set(cab["fonte"]) == {FISCAL, CONTRIB} and int(cab["documentos"].sum()) > 20)
    metas = {m["nome_arquivo"]: m for m in base.metas(con)}
    igual("registro 9900 adulterado é detectado",
          metas[nome("fiscal_matriz_fev")]["divergencias_9900"], {"C170": [4, 3]})
    igual("demais arquivos: 9900 confere com a contagem",
          [m["divergencias_9900"] for n, m in metas.items() if n != nome("fiscal_matriz_fev")],
          [{}, {}, {}, {}])
    d = metas[nome("contrib_jan")]["descartes"]
    igual("descartes da Contribuições de janeiro (2 saídas, 1 cancelada, 1 F100 de receita)",
          (d["saidas"], d["situacao"], d["f100_nao_aquisicao"]), (2, 1, 1))
    igual("C191/C195 de devolução (CFOP 5202) fica de fora",
          metas[nome("contrib_fev")]["descartes"]["c191_c195_saida"], 1)
    igual("nenhuma anomalia de leiaute ou de formato nos arquivos sintéticos",
          [m["anomalias"] for m in metas.values()], [{}, {}, {}, {}, {}])

    print("\n== 9. Visão consolidada ==")
    M = [("vl_item", FISCAL), ("vl_icms", FISCAL), ("vl_item", CONTRIB), ("vl_pis", CONTRIB),
         ("vl_cofins", CONTRIB)]
    r = consulta.consolidar(con, ["empresa", "fornecedor", "cfop", "item"], M)
    igual("sem filtro de documento a consulta usa a tabela pré-agregada", r["tabela"], "visao")
    t = r["totais"]
    igual("totais da visão = totais conhecidos",
          (t["vl_item__fiscal"], t["vl_icms__fiscal"], t["vl_item__contrib"], t["vl_pis__contrib"], t["vl_cofins__contrib"]),
          (D("5700.00"), D("1526.50"), D("14300.00"), D("222.76"), D("1026.00")))
    df = r["dados"]
    linha = df[(df["fornecedor"] == gs.ACO) & (df["cfop"] == "1101") & (df["item"] == "ITEM001")].iloc[0]
    igual("Aço / CFOP 1101 / ITEM001: Fiscal 3.000,00 e Contribuições 2.300,00 na MESMA linha",
          (float(linha["vl_item__fiscal"]), float(linha["vl_item__contrib"])), (3000.0, 2300.0))
    igual("nome do fornecedor e descrição do item acompanham o grupo",
          (linha["part_nome"], linha["descr_item"], linha["empresa_nome"]),
          ("FORNECEDOR AÇO LTDA", "CHAPA DE AÇO 3MM", "INDÚSTRIA EXEMPLO S.A."))
    igual("soma das linhas da visão = total geral",
          (round(df["vl_item__fiscal"].sum(), 2), round(df["vl_pis__contrib"].sum(), 2)), (5700.0, 222.76))

    tudo = [{"grupo": 1, "campo": "num_doc", "operador": "vazio"},
            {"grupo": 2, "campo": "num_doc", "operador": "nao_vazio"}]
    r2 = consulta.consolidar(con, ["empresa", "fornecedor", "cfop", "item"], M, filtros=[tudo])
    igual("com filtro de documento a consulta usa os itens", r2["tabela"], "itens")
    igual("os dois caminhos (pré-agregado e itens) dão o mesmo resultado",
          (r2["totais"], r2["total_grupos"]), (r["totais"], r["total_grupos"]))
    r3 = consulta.consolidar(con, ["cfop_conc"], [("vl_pis", CONTRIB)])
    por_cfop = dict(zip(r3["dados"]["cfop_conc"], r3["dados"]["vl_pis__contrib"].round(2)))
    igual("PIS por CFOP conciliado: energia 1253 = 33,00; frete 1352 = 6,60; telecom 1303 = 4,13",
          (por_cfop["1253"], por_cfop["1352"], por_cfop["1303"]), (33.0, 6.6, 4.13))

    print("\n== 10. Filtros criados pelo usuário ==")
    def total(filtros, medida=("vl_pis", CONTRIB), dims=("fornecedor",)):
        x = consulta.consolidar(con, list(dims), [medida], filtros=filtros)
        return x["totais"][consulta.col_medida(*medida)], x["totais"]["n_linhas"]

    igual("CNPJ digitado com pontuação é aceito",
          total([[{"campo": "fornecedor", "operador": "igual", "valor": "99.888.777/0001-66"}]]),
          (D("162.53"), 17))
    igual("nome do fornecedor 'contém' sem diferenciar maiúsculas",
          total([[{"campo": "fornecedor_nome", "operador": "contem", "valor": "transportadora"}]]),
          (D("6.60"), 2))
    igual("lista de CFOP com pontuação (1.101; 2.101)",
          total([[{"campo": "cfop", "operador": "em", "valor": "1.101; 2.101"}]], ("vl_item", FISCAL)),
          (D("5400.00"), 12))
    igual("período por MM/AAAA",
          total([[{"campo": "periodo", "operador": "igual", "valor": "02/2026"}]]),
          (D("28.88"), 4))
    igual("filtro numérico por linha (VL_ICMS da linha maior que 100)",
          total([[{"campo": "vl_icms", "operador": "maior", "valor": "100,00"}]], ("vl_icms", FISCAL)),
          (D("1326.00"), 11))
    igual("grupos: (CST 70) OU (CFOP 1949) -> a mesma linha não conta duas vezes",
          total([[{"grupo": 1, "campo": "cst_pis", "operador": "igual", "valor": "70"},
                  {"grupo": 2, "campo": "cfop", "operador": "igual", "valor": "1949"}]],
                ("vl_item", CONTRIB))[1], 2)
    igual("dois filtros salvos aplicados juntos são ligados por E",
          total([[{"campo": "cst_pis", "operador": "entre", "valor": "50;56"}],
                 [{"campo": "registro", "operador": "igual", "valor": "F100"}]]),
          (D("49.50"), 1))
    for ruim, rotulo in (
            ([{"campo": "nao_existe", "operador": "igual", "valor": "1"}], "campo desconhecido"),
            ([{"campo": "cfop", "operador": "DROP", "valor": "1"}], "operador desconhecido"),
            ([{"campo": "vl_icms", "operador": "maior", "valor": "abc"}], "número inválido"),
            ([{"campo": "periodo", "operador": "igual", "valor": "ontem"}], "data inválida"),
            ([{"campo": "cfop", "operador": "entre", "valor": "1"}], "'entre' sem dois valores")):
        try:
            consulta.consolidar(con, ["cfop"], M, filtros=[ruim])
            check(f"filtro inválido recusado: {rotulo}", False)
        except consulta.FiltroInvalido:
            check(f"filtro inválido recusado: {rotulo}", True)
    antes = con.execute("SELECT count(*) FROM itens").fetchone()[0]
    x = consulta.consolidar(con, ["cfop"], M, filtros=[[
        {"campo": "fornecedor_nome", "operador": "igual", "valor": "x'; DROP TABLE itens; --"}]])
    igual("tentativa de injeção vira valor de comparação (0 linhas, tabela intacta)",
          (x["total_grupos"], con.execute("SELECT count(*) FROM itens").fetchone()[0]), (0, antes))

    print("\n== 11. Campos calculados ==")
    calc = {"Aliq": "VL_PIS_CONTRIB / VL_BC_PIS_CONTRIB * 100",
            "Soma": "vl_pis_contrib + VL_COFINS_CONTRIB",
            "Zero": "VL_PIS_CONTRIB / (VL_PIS_FISCAL - VL_PIS_FISCAL)"}
    x = consulta.consolidar(con, ["empresa"], [("vl_pis", CONTRIB)], calculados=calc)
    nomes = {v: k for k, v in x["nomes_calc"].items()}
    igual("alíquota efetiva de PIS = 1,65%", round(x["totais"][nomes["Aliq"]], 2), 1.65)
    igual("PIS + COFINS = 1.248,76", round(x["totais"][nomes["Soma"]], 2), 1248.76)
    igual("divisão por zero vira vazio, não erro", x["totais"][nomes["Zero"]], None)
    for formula in ("__import__('os').system('x')", "VL_PIS_CONTRIB; DROP TABLE itens",
                    "NAO_EXISTE * 2", "VL_PIS_CONTRIB ** 2", "(SELECT 1)", ""):
        try:
            consulta.formula_para_sql(formula)
            check(f"fórmula recusada: {formula!r}", False)
        except consulta.FiltroInvalido:
            check(f"fórmula recusada: {formula!r}", True)

    print("\n== 12. Detalhe, exportação e tabelas auxiliares ==")
    det = consulta.detalhar(con, chaves={"fornecedor": gs.ACO, "cfop": "1101", "item": "ITEM001"})
    igual("detalhe do grupo: 5 linhas (2 da Fiscal, 3 da Contribuições)",
          det["Escrituração"].value_counts().to_dict(), {"CONTRIB": 3, "FISCAL": 2})
    r = consulta.consolidar(con, ["empresa", "fornecedor", "cfop", "item"], M,
                            calculados={"Soma": "VL_PIS_CONTRIB + VL_COFINS_CONTRIB"})
    rot = consulta.rotulos(r["colunas"], M, {"Soma": "VL_PIS_CONTRIB + VL_COFINS_CONTRIB"}, r["nomes_calc"])
    check("toda coluna exportada tem rótulo com a origem",
          all(("Reg." in v or "Cálculo" in v or "contagem" in v or "tabela de CFOP" in v) for v in rot.values()),
          str([v for v in rot.values() if "Reg." not in v]))
    xlsx = consulta.para_excel(r["dados"], rot, notas=[("Teste", "ok")])
    import openpyxl, io
    wb = openpyxl.load_workbook(io.BytesIO(xlsx))
    ws = wb.worksheets[0]
    igual("Excel: cabeçalho com origem e uma linha por grupo",
          (ws.cell(1, 1).value, ws.max_row - 1), (rot["empresa"], len(r["dados"])))
    check("CSV com separador ; e vírgula decimal",
          b";" in consulta.para_csv(r["dados"], rot).splitlines()[0])

    cfop_csv = os.path.join(raiz, "cfop.csv")
    with open(cfop_csv, "w", encoding="utf-8") as fh:
        fh.write("Código;Descrição\n")
        for i, cod in enumerate(("1.101", "1.102", "1.253", "1.303", "1.352", "1.556", "1.949",
                                 "2.101", "2.102", "5.101", "5.202")):
            fh.write(f"{cod};Descrição de teste do CFOP {cod}\n")
    igual("tabela de CFOP fornecida pelo usuário: 11 códigos", base.carregar_cfop(con, cfop_csv), 11)
    x = consulta.consolidar(con, ["cfop"], M)
    igual("descrição do CFOP aparece ao lado do código",
          x["dados"].set_index("cfop")["cfop_descricao"]["1101"], "Descrição de teste do CFOP 1.101")
    igual("a junção com a tabela de CFOP não altera os totais", x["totais"]["vl_item__fiscal"], D("5700.00"))

    reg_csv = os.path.join(raiz, "regime.csv")
    with open(reg_csv, "w", encoding="utf-8") as fh:
        fh.write("ano,cnpj,cnpj_da_scp,forma_de_tributacao,quantidade_de_escrituracoes\n")
        fh.write("2024,99.888.777/0001-66,0,LUCRO REAL,1\n2020,99888777000166,0,LUCRO PRESUMIDO,1\n")
        fh.write("2024,123456000199,0,LUCRO REAL,1\n")       # CNPJ que perdeu os zeros à esquerda
    base.carregar_regimes(con, reg_csv, "LUCRO REAL")
    igual("regime do fornecedor pela raiz do CNPJ, ano mais recente",
          con.execute("SELECT DISTINCT regime FROM itens WHERE part_doc = ?", [gs.ACO]).fetchall(),
          [("LUCRO REAL",)])
    igual("CNPJ numérico sem zeros à esquerda é recomposto",
          con.execute("SELECT count(*) FROM regimes WHERE raiz = '00123456'").fetchone()[0], 1)
    check("verificações continuam passando depois das tabelas auxiliares",
          all(v["ok"] for v in base.ultimas_verificacoes(con)))

    print("\n== 13. Remoção de arquivo ==")
    aid = con.execute("SELECT arquivo_id FROM arquivos WHERE nome_arquivo = ?", [nome("fiscal_matriz_fev")]).fetchone()[0]
    base.remover_arquivo(con, aid)
    igual("sem a Fiscal de fevereiro não há mais repetição",
          con.execute("SELECT count(*) FROM itens WHERE repetido").fetchone()[0], 0)
    igual("a NF 1010 da Contribuições passa a 'outra EFD não carregada'",
          con.execute("SELECT DISTINCT pareamento FROM itens WHERE num_doc = '1010'").fetchall(),
          [("SEM_CONTRAPARTE",)])
    check("verificações passam depois da remoção", all(v["ok"] for v in base.ultimas_verificacoes(con)))

    con.close()
    shutil.rmtree(raiz, ignore_errors=True)
    print(f"\n{TOTAL[0] - len(FALHAS)} de {TOTAL[0]} verificações passaram.")
    if FALHAS:
        print("FALHARAM:")
        for f in FALHAS:
            print("  -", f)
    return 1 if FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
