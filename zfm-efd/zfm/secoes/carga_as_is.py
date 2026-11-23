"""Seção 'carga_as_is' (antes uma tela própria). render(ctx) desenha o conteúdo dentro da tela que a chama."""
import plotly.express as px
import streamlit as st
from zfm import as_is, conciliacoes, qualidade, ui


def render(ctx):
    con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

    with ui.protegido("ler a carga As Is"):
        m = ui.calcular("carga_mensal", f)
        if m.empty:
            ui.vazio("Sem apuração para o filtro escolhido")
            return
        tribs = st.multiselect("Tributos", as_is.TRIBUTOS, default=as_is.TRIBUTOS, key="asis_trib")
        m = m[m.tributo.isin(tribs)]
        anual = ui.calcular("carga_anual", f, ctx.teses)
        anual = anual[anual.tributo.isin(tribs)]
        ui.cartoes({**{t: anual.loc[anual.tributo == t, "as_is"].sum() for t in tribs},
                    "Total anualizado": anual["as_is"].sum()}, destaque="Total anualizado")
        if ctx.teses and anual["teses"].abs().sum():
            st.info(f"Teses aplicadas (não ativas): redução de {ui.formatar_brl(anual['teses'].sum())} por ano.",
                    icon=":material/info:")

        t1, t2, t3, t4 = st.tabs(["Carga por tributo", "Composição", "ICMS: estímulo e fundos", "Saldos e R5"])
        with t1:
            c1, c2 = st.columns([1.3, 1])
            with c1:
                ui.secao("Carga anualizada por tributo")
                ui.tabela(ui.por_empresa(anual, ["tributo"], "as_is", nomes))
            with c2:
                g = m.groupby(["mes", "tributo"], as_index=False)["carga"].sum()
                g["mês"] = g["mes"].map(lambda x: qualidade.MESES[x - 1])
                ui.grafico(px.bar(g, x="mês", y="carga", color="tributo", labels={"carga": "R$", "mês": ""}), 300)
            ui.secao("Carga mensal do período")
            ui.tabela(ui.por_empresa(m, ["tributo", "mes"], "carga", nomes))
        with t2:
            ui.secao("Saídas × entradas × deduções", "Débitos sobre as saídas, créditos das entradas, deduções "
                     "(inclui crédito estímulo), fundos fora da apuração e efeito de saldo credor.")
            visao = st.radio("Visão", ui.VISOES, horizontal=True, key="asis_visao")
            comp = m.melt(id_vars=["raiz", "tributo", "mes"],
                          value_vars=["saidas_debitos", "entradas_creditos", "deducoes_beneficios",
                                      "fundos_fora_apuracao", "efeito_saldo"], var_name="componente")
            comp["lado"] = comp["componente"].map({"saidas_debitos": "Saídas", "entradas_creditos": "Entradas"}).fillna(
                "Deduções, fundos e saldos")
            if visao == "Só saídas":
                comp = comp[comp.lado == "Saídas"]
            elif visao == "Só entradas":
                comp = comp[comp.lado == "Entradas"]
            comp["componente"] = comp["componente"].map({
                "saidas_debitos": "Débitos sobre saídas", "entradas_creditos": "Créditos das entradas",
                "deducoes_beneficios": "Deduções (inclui crédito estímulo)",
                "fundos_fora_apuracao": "Fundos/obrigações fora da apuração", "efeito_saldo": "Efeito de saldo credor"})
            ui.tabela(ui.por_empresa(comp, ["tributo", "lado", "componente"], "value", nomes))
        with t3:
            icms = m[m.tributo == "ICMS"]
            ui.secao("Crédito estímulo e fundos (informativo)")
            ui.tabela(ui.por_empresa(icms.melt(id_vars=["raiz", "mes"], value_vars=["credito_estimulo",
                                                                                    "fundos_classificados"],
                                               var_name="item"), ["item", "mes"], "value", nomes))
            aj = conciliacoes.filtrar(con.execute("SELECT * FROM v_ajustes_icms").df(), f)
            ui.secao("Ajustes E111/E116 por classe e código")
            ui.tabela(ui.por_empresa(aj, ["registro", "classe", "codigo"], "valor", nomes))
            if not aj.empty and aj["nao_classificado"].any():
                st.warning("Há códigos de ajuste sem classificação: classifique em Cadastros > Códigos de ajuste.",
                           icon=":material/warning:")
        with t4:
            ui.secao("Saldos credores no fim do período", "Informação para a transição.")
            sl = ui.calcular("saldos", f)
            if not sl.empty:
                sl = sl.copy()
                sl.insert(0, "empresa", sl["raiz"].map(ctx.nome))
            ui.tabela(sl)
            ui.secao("R5 – A base de operações explica a apuração?")
            r5 = ui.calcular("r5", f)
            r5 = r5[r5.tributo.isin(tribs)] if not r5.empty else r5
            if r5.empty or r5["fecha"].all():
                st.success("Sim: a carga recalculada pela base de operações bate com a apuração.",
                           icon=":material/check_circle:")
            else:
                dif = r5[~r5.fecha]
                st.warning(f"{len(dif)} combinação(ões) não fecham. A diferença entra como 'ajuste de reconciliação'.",
                           icon=":material/warning:")
                ui.tabela(dif)
        with st.expander("Registros da apuração (mensal, todas as colunas)"):
            ui.tabela(m, altura=400)
            ui.baixar_csv(m, "carga_as_is_mensal")
