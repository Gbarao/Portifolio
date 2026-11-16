import streamlit as st

from zfm import ui

ctx = ui.contexto(
    "Base de operações",
    "Base única usada na simulação: uma linha por item (ou consolidação, quando não há item). Saídas por "
    "produto vêm da EFD Contribuições; entradas, da EFD ICMS/IPI. Devoluções têm valor negativo e abatem a "
    "operação de origem; documentos cancelados ficam fora.", "Operações", intragrupo=True)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("montar a base de operações"):
    onde = f.sql() + (" AND NOT coalesce(eh_grupo, false)" if ctx.intra else "")
    with st.expander("Filtros", expanded=False, icon=":material/filter_alt:"):
        extra = ui.filtros_sql(con, "v_base_operacoes", {
            "sentido": "Sentido", "natureza": "Natureza", "cfop": "CFOP", "tipo_operacao": "Destino (saídas)",
            "origem": "Origem (entradas)", "uf_part": "UF do participante", "cod_item": "Produto",
            "ncm_produto": "NCM", "incentivado": "Incentivado", "eh_grupo": "Empresa do grupo",
            "rateado": "Destino rateado", "reg_origem": "Registro de origem"}, "base", onde)
    cond = f"{onde} AND {extra}"
    tot = con.execute(f"""
        SELECT coalesce(sum(valor) FILTER (WHERE sentido = 'saida'), 0),
               coalesce(sum(valor) FILTER (WHERE natureza = 'devolucao_venda'), 0),
               coalesce(sum(valor) FILTER (WHERE sentido = 'entrada'), 0),
               coalesce(sum(valor) FILTER (WHERE natureza = 'transferencia'), 0), count(*)
        FROM v_base_operacoes WHERE {cond}""").fetchall()[0]
    if tot[4] == 0:
        ui.vazio("Base vazia para o filtro escolhido",
                 "Confira o período e as empresas na barra lateral e a classificação dos CFOPs em Parâmetros.")
        st.stop()
    ui.cartoes({"Saídas (líquidas)": tot[0], "Devoluções de venda": tot[1], "Entradas (líquidas)": tot[2],
                "Transferências": tot[3], "Linhas": ui.formatar_num(tot[4])})

    t1, t2, t3 = st.tabs(["Resumo", "Transferências", "Registros"])
    with t1:
        ui.secao("Por sentido, natureza e empresa")
        r = con.execute(f"""SELECT sentido, natureza, raiz, sum(valor) AS valor FROM v_base_operacoes
                            WHERE {cond} GROUP BY ALL ORDER BY 1, 2""").df()
        ui.tabela(ui.por_empresa(r, ["sentido", "natureza"], "valor", nomes))
        ui.secao("Por mês")
        r = con.execute(f"""SELECT mes, sentido, raiz, sum(valor) AS valor FROM v_base_operacoes
                            WHERE {cond} GROUP BY ALL ORDER BY 1, 2""").df()
        ui.tabela(ui.por_empresa(r, ["mes", "sentido"], "valor", nomes))
    with t2:
        ui.secao("Transferências entre estabelecimentos", "Ficam fora da base de CBS/IBS por padrão (premissa "
                 "transferencias_na_base_cbs_ibs).")
        r = con.execute(f"""SELECT sentido, cnpj_estab, cfop, raiz, sum(valor) AS valor FROM v_base_operacoes
                            WHERE {cond} AND natureza = 'transferencia' GROUP BY ALL ORDER BY 1, 2, 3""").df()
        ui.tabela(ui.por_empresa(r, ["sentido", "cnpj_estab", "cfop"], "valor", nomes))
    with t3:
        lim = 5000
        reg = con.execute(f"""
            SELECT raiz, cnpj_estab, mes, sentido, natureza, cfop, categoria_origem, cod_item, ncm_produto AS ncm,
                   incentivado, tipo_bem, tipo_operacao, origem, uf_part AS uf, eh_grupo, valor, icms, ipi, pis,
                   cofins, cst_icms, cst_ipi, cst_pis, aliq_pis, cst_cofins, aliq_cofins, rateado, reg_origem,
                   chv_nfe, arquivo_id, linha_num
            FROM v_base_operacoes WHERE {cond} ORDER BY abs(valor) DESC LIMIT {lim}""").df()
        st.caption(f"Maiores {ui.formatar_num(min(lim, tot[4]))} de {ui.formatar_num(tot[4])} linhas (por valor). "
                   "O CSV abaixo traz todas as linhas do filtro.")
        ui.tabela(reg, moeda=["valor", "icms", "ipi", "pis", "cofins"], altura=440, limite=lim)
        if st.button("Preparar CSV com todas as linhas", icon=":material/download:"):
            with st.spinner("Gerando..."):
                st.session_state["_csv_base"] = con.execute(
                    f"SELECT * FROM v_base_operacoes WHERE {cond}").df()
        if st.session_state.get("_csv_base") is not None:
            ui.baixar_csv(st.session_state.pop("_csv_base"), "base_de_operacoes")
