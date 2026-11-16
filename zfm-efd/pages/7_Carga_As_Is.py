import streamlit as st

from zfm import as_is, conciliacoes, qualidade, ui

ctx = ui.contexto(
    "7. Carga As Is (apuração)",
    "Para que serve: mostrar a carga atual de ICMS, IPI, PIS e COFINS lida da apuração, sem "
    "recálculo (E110/E111/E116, E520, M200/M600). O que fazer: confira a carga por tributo e "
    "empresa; veja na seção R5 se a base de operações explica a apuração.",
)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("ler a carga As Is"):
    m = as_is.carga_mensal(con, f)
    if m.empty:
        st.warning("Sem apuração para o filtro escolhido.")
        st.stop()
    tribs = st.multiselect("Tributos", as_is.TRIBUTOS, default=as_is.TRIBUTOS, key="asis_trib")
    m = m[m.tributo.isin(tribs)]
    anual = as_is.carga_anual(con, f, ctx.teses)
    anual = anual[anual.tributo.isin(tribs)]
    meses = as_is.meses_observados(con, f)
    n = meses.groupby("raiz")["mes"].nunique().to_dict()

    ui.cartoes({**{f"{t} (anualizado)": anual.loc[anual.tributo == t, "as_is"].sum() for t in tribs},
                "Total anualizado": anual["as_is"].sum()})
    st.caption("Anualização: soma do período ÷ meses com arquivo × 12. Meses por empresa: "
               + ", ".join(f"{nomes.get(r, r)}: {k}" for r, k in n.items()))
    if ctx.teses and anual["teses"].abs().sum():
        st.info(f"Teses aplicadas (não ativas): redução de {ui.formatar_brl(anual['teses'].sum())} por ano.")

    st.subheader("Carga anualizada por tributo (uma coluna por empresa)")
    ui.tabela(ui.por_empresa(anual, ["tributo"], "as_is", nomes))
    st.subheader("Carga mensal (período selecionado)")
    ui.tabela(ui.por_empresa(m, ["tributo", "mes"], "carga", nomes))

    st.subheader("Composição: saídas × entradas")
    visao = st.radio("Visão", ui.VISOES, horizontal=True, key="asis_visao")
    comp = m.melt(id_vars=["raiz", "tributo", "mes"],
                  value_vars=["saidas_debitos", "entradas_creditos", "deducoes_beneficios",
                              "fundos_fora_apuracao", "efeito_saldo"], var_name="componente")
    lados = {"saidas_debitos": "Saídas", "entradas_creditos": "Entradas"}
    comp["lado"] = comp["componente"].map(lados).fillna("Deduções, fundos e saldos")
    if visao == "Só saídas":
        comp = comp[comp.lado == "Saídas"]
    elif visao == "Só entradas":
        comp = comp[comp.lado == "Entradas"]
    nomes_comp = {"saidas_debitos": "Débitos sobre saídas", "entradas_creditos": "Créditos das entradas",
                  "deducoes_beneficios": "Deduções (inclui crédito estímulo)",
                  "fundos_fora_apuracao": "Fundos/obrigações fora da apuração",
                  "efeito_saldo": "Efeito de saldo credor"}
    comp["componente"] = comp["componente"].map(nomes_comp)
    ui.tabela(ui.por_empresa(comp, ["tributo", "lado", "componente"], "value", nomes))

    st.subheader("ICMS: crédito estímulo e fundos (informativo)")
    icms = m[m.tributo == "ICMS"]
    ui.tabela(ui.por_empresa(icms.melt(id_vars=["raiz", "mes"], value_vars=["credito_estimulo",
                                                                            "fundos_classificados"],
                                       var_name="item"), ["item", "mes"], "value", nomes))
    aj = conciliacoes.filtrar(con.execute("SELECT * FROM v_ajustes_icms").df(), f)
    with st.expander("Ajustes E111/E116 por classe e código"):
        ui.tabela(ui.por_empresa(aj, ["registro", "classe", "codigo"], "valor", nomes))
    if not aj.empty and aj["nao_classificado"].any():
        st.warning("Há códigos de ajuste sem classificação: classifique em Parâmetros > Códigos de ajuste.")

    st.subheader("Saldos credores no fim do período (informação para a transição)")
    sl = as_is.saldos_credores_finais(con, f)
    sl.insert(0, "empresa", sl["raiz"].map(lambda r: nomes.get(r, r)))
    ui.tabela(sl)

    st.subheader("R5 – A base de operações explica a apuração?")
    r5 = as_is.reconciliacao_r5(con, f)
    r5 = r5[r5.tributo.isin(tribs)]
    if r5.empty or r5["fecha"].all():
        st.success("Sim: a carga recalculada a partir da base de operações bate com a apuração.")
    else:
        dif = r5[~r5.fecha]
        st.error(f"{len(dif)} combinação(ões) empresa/estabelecimento × mês × tributo não fecham. "
                 "A diferença entra no relatório como 'ajuste de reconciliação' (tela 8).")
        ui.tabela(dif)
    with st.expander("R5 completo"):
        ui.tabela(r5)
    with st.expander("Registros da apuração (arquivo e linha)"):
        ui.tabela(m, altura=400)
        ui.baixar_csv(m, "carga_as_is_mensal")
    st.caption("Meses: " + ", ".join(qualidade.MESES[x - 1] for x in f.meses))
