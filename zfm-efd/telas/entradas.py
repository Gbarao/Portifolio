import plotly.express as px
import streamlit as st

from zfm import ui

ctx = ui.contexto(
    "Entradas",
    "Compras por região de origem (base dos créditos presumidos dos arts. 447 e 449), importações, "
    "fornecedores da ZFM, CSTs e devoluções de compra. A origem do fornecedor depende do município no 0150.",
    "Operações", intragrupo=True)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

REGIAO = """CASE origem WHEN 'importacao' THEN 'Importação' WHEN 'zfm' THEN 'ZFM'
                  WHEN 'am_fora_zfm' THEN 'Amazonas fora da ZFM' WHEN 'servicos' THEN 'Serviços tomados'
                  ELSE CASE WHEN coalesce(sul_sudeste_exceto_es, false) THEN 'Sul/Sudeste exceto ES'
                            ELSE 'Norte, Nordeste, Centro-Oeste e ES' END END"""
with ui.protegido("montar a tela de entradas"):
    intra = " AND NOT coalesce(eh_grupo, false)" if ctx.intra else ""
    fonte = f"(SELECT *, {REGIAO} AS regiao_origem FROM v_base_operacoes WHERE sentido = 'entrada')"
    o = f"{f.sql()}{intra}"
    with st.expander("Filtros", icon=":material/filter_alt:"):
        x = ui.filtros_sql(con, fonte, {"regiao_origem": "Origem", "categoria_origem": "Finalidade",
                                        "natureza": "Natureza", "uf_part": "UF do fornecedor", "cfop": "CFOP",
                                        "cod_item": "Produto", "eh_grupo": "Empresa do grupo"}, "ent", o)
    o = f"{o} AND {x}"

    def q(sql: str):
        return con.execute(f"WITH e AS (SELECT * FROM {fonte} WHERE {o}) {sql}").df()

    k = q("""SELECT coalesce(sum(valor), 0) AS t, coalesce(sum(valor) FILTER (WHERE origem = 'importacao'), 0) AS i,
                    coalesce(sum(valor) FILTER (WHERE origem = 'zfm'), 0) AS z,
                    coalesce(sum(valor) FILTER (WHERE natureza = 'devolucao_compra'), 0) AS d, count(*) AS n
             FROM e""").iloc[0]
    if k["n"] == 0:
        ui.vazio("Sem entradas para o filtro escolhido")
        st.stop()
    ui.cartoes({"Entradas (líquidas)": float(k["t"]), "Importações": float(k["i"]), "Fornecedores ZFM": float(k["z"]),
                "Devoluções de compra": float(k["d"]), "Linhas": ui.formatar_num(int(k["n"]))})

    t1, t2, t3, t4 = st.tabs(["Origem e finalidade", "Fornecedores", "CST", "Registros"])
    with t1:
        g = q("SELECT regiao_origem, raiz, sum(valor) AS valor FROM e GROUP BY ALL")
        c1, c2 = st.columns([1.2, 1])
        with c1:
            ui.secao("Por região de origem")
            ui.tabela(ui.por_empresa(g, ["regiao_origem"], "valor", nomes))
        with c2:
            gg = g.groupby("regiao_origem", as_index=False)["valor"].sum().sort_values("valor")
            ui.grafico(px.bar(gg, x="valor", y="regiao_origem", orientation="h",
                              labels={"valor": "R$", "regiao_origem": ""}), 300)
        ui.secao("Por finalidade (CFOP de origem)", "Uso e consumo e ativo ficam separados; transferências e "
                 "remessas não geram crédito. Devoluções de compra abatem a compra de origem.")
        ui.tabela(ui.por_empresa(q("SELECT categoria_origem, natureza, raiz, sum(valor) AS valor FROM e "
                                   "GROUP BY ALL ORDER BY 1, 2"), ["categoria_origem", "natureza"], "valor", nomes))
    with t2:
        ui.secao("Fornecedores da ZFM (base do art. 449)")
        ui.tabela(ui.por_empresa(q("SELECT cnpj_part, tipo_zfm_part, categoria_origem, raiz, sum(valor) AS valor "
                                   "FROM e WHERE origem = 'zfm' GROUP BY ALL ORDER BY 1"),
                                 ["cnpj_part", "tipo_zfm_part", "categoria_origem"], "valor", nomes))
        ui.secao("Maiores fornecedores")
        ui.tabela(q("""SELECT cnpj_part, uf_part, regiao_origem, tipo_zfm_part, regime_part, sum(valor) AS valor,
                              count(*) AS linhas FROM e GROUP BY ALL ORDER BY valor DESC LIMIT 200"""),
                  moeda=["valor"])
        ui.secao("Importações (CFOP 3xxx) por mês")
        ui.tabela(ui.por_empresa(q("SELECT mes, raiz, sum(valor) AS valor FROM e WHERE origem = 'importacao' "
                                   "GROUP BY ALL ORDER BY 1"), ["mes"], "valor", nomes))
    with t3:
        ui.secao("PIS/COFINS das entradas por nível de cruzamento",
                 "Vem da EFD Contribuições, ligado ao item do SPED Fiscal (ver Qualidade > Fiscal × Contribuições).")
        from zfm.vinculo import NIVEIS
        nv = con.execute(f"""SELECT nivel_cruzamento, count(*) AS linhas, sum(valor) AS valor,
                                    sum(coalesce(vl_pis, 0)) AS pis, sum(coalesce(vl_cofins, 0)) AS cofins
                             FROM v_entradas_item WHERE {f.sql()} GROUP BY ALL ORDER BY linhas DESC""").df()
        if not nv.empty:
            nv.insert(1, "descricao", nv["nivel_cruzamento"].map(NIVEIS).fillna(""))
        ui.tabela(nv, moeda=["valor", "pis", "cofins"])
        ui.secao("CST nas entradas")
        ui.tabela(q("SELECT cst_icms, cst_ipi, cst_pis, cst_cofins, sum(valor) AS valor FROM e GROUP BY ALL "
                    "ORDER BY valor DESC"), moeda=["valor"])
    with t4:
        reg = q("""SELECT raiz, cnpj_estab, mes, chv_nfe, cod_item, cfop, natureza, valor, cnpj_part, uf_part,
                          regiao_origem, reg_origem, arquivo_id, linha_num FROM e ORDER BY abs(valor) DESC LIMIT 3000""")
        st.caption(f"Maiores {ui.formatar_num(len(reg))} de {ui.formatar_num(int(k['n']))} linhas (por valor).")
        ui.tabela(reg, moeda=["valor"], altura=440)
        ui.baixar_csv(reg, "entradas")
