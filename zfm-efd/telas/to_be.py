import plotly.graph_objects as go
import streamlit as st

from zfm import params, simulacao, ui

ctx = ui.contexto(
    "To Be e diferença",
    "Carga 2027–2033 (CBS, IBS, ICMS residual, IPI e contribuição do art. 457) simulada sobre a base de "
    "operações e comparada com a carga As Is da apuração. Diferença = To Be − As Is: positivo = a empresa paga "
    "mais; negativo = paga menos.", "Análise")
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("rodar a simulação"):
    with st.spinner("Simulando..."):
        anual, mensal = ui.calcular("simular", f, ctx.teses)
    if anual.empty:
        ui.vazio("Sem dados para simular")
        st.stop()
    cenarios = sorted(dict.fromkeys(anual["cenario"]), key=lambda c: (c != "base", c))
    c1, c2, c3 = st.columns([1, 2, 2])
    cenario = c1.selectbox("Cenário de alíquotas", cenarios, key="tb_cen")
    ano = c2.select_slider("Ano", options=simulacao.ANOS, value=2033, key="tb_ano")
    visao = c3.radio("Visão", ui.VISOES, horizontal=True, key="tb_visao",
                     help="Só saídas: débitos e créditos presumidos de saída. Só entradas: créditos das entradas "
                          "e créditos presumidos de entrada.")
    tribs_todos = ["ICMS", "IPI", "PIS", "COFINS", "CBS", "IBS", "Contribuição art. 457"]
    tribs = st.multiselect("Tributos", tribs_todos, default=tribs_todos, key="tb_tribs")

    cen = params.carregar("param_aliquotas_cenario")
    lc = cen[(cen.cenario == cenario) & (cen.ano == ano)]
    if not lc.empty:
        l0 = lc.iloc[0]
        n = lambda x: f"{x or 0:.2f}".replace(".", ",")  # noqa: E731
        st.caption(f"CBS {n(l0.aliq_cbs)}% · IBS {n(l0.aliq_ibs)}% · fator ICMS {n(l0.fator_icms)} · "
                   f"CP art. 450: {'sim' if l0.aplica_cp_450 else 'não'} · Fonte: {l0.fonte}")

    sel = anual[(anual.cenario == cenario) & (anual.ano == ano)]
    dif = simulacao.diferenca_por_tributo(sel)
    dif = dif[dif.tributo.isin(tribs)]
    if visao != "Completa":
        comp = ui.calcular("composicao", f, ctx.teses, cenario=cenario, ano=int(ano))
        lado = "saidas" if visao == "Só saídas" else "entradas"
        comp = comp[(comp.lado == lado) & comp.tributo.isin(tribs)]
        piv = comp.pivot_table(index=["raiz", "tributo"], columns="regime", values="valor", aggfunc="sum",
                               fill_value=0.0).reset_index()
        for col in ("As Is", "To Be"):
            if col not in piv.columns:
                piv[col] = 0.0
        dif = piv.rename(columns={"As Is": "as_is", "To Be": "to_be"})
        dif["diferenca"] = dif["to_be"] - dif["as_is"]
    tot_as, tot_tb = dif["as_is"].sum(), dif["to_be"].sum()
    ui.cartoes({"Carga As Is (anualizada)": tot_as, f"Carga To Be {ano}": tot_tb})
    ui.cartoes({"Diferença": (tot_tb - tot_as, "+ paga mais · − paga menos"),
                "Perda de vantagem competitiva (IPI)": (float(sel["perda_vantagem_ipi"].sum()),
                                                        "métrica separada da carga própria")}, sinal=True)
    aj = sel["ajuste_reconciliacao_total"].sum()
    if abs(aj) > params.premissa_num("tolerancia_conciliacao", 1.0):
        st.warning(f"Ajuste de reconciliação de {ui.formatar_brl(aj)} por ano: a base de operações não explica toda "
                   "a apuração (R5). Essa parte da diferença vem da base, não da reforma.", icon=":material/warning:")

    t1, t2, t3, t4 = st.tabs(["Diferença e ponte", "Evolução e cenários", "Absorção dos créditos", "Vantagem IPI"])
    with t1:
        c1, c2 = st.columns([1, 1.2])
        with c1:
            ui.secao("Diferença por tributo")
            ui.tabela(ui.por_empresa(dif, ["tributo"], "diferenca", nomes))
            ui.secao("Ranking das empresas")
            r = dif.groupby("raiz", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
            r.insert(0, "empresa", r["raiz"].map(ctx.nome))
            ui.tabela(r.sort_values("diferenca", ascending=False).drop(columns=["raiz"]))
        with c2:
            if visao == "Completa":
                ui.secao("Ponte da carga: As Is → To Be", "Vermelho = aumento; verde = redução.")
                p = simulacao.ponte(anual, cenario, ano, ctx.raizes)
                fig = go.Figure(go.Waterfall(
                    x=p["etapa"], y=p["valor"], measure=p["medida"],
                    text=[ui.formatar_brl_curto(v) for v in p["valor"]], textposition="outside",
                    increasing={"marker": {"color": "#B42318"}}, decreasing={"marker": {"color": "#1E7B4F"}},
                    totals={"marker": {"color": "#1E5A8A"}}, connector={"line": {"color": "#C9D3DF"}}))
                fig.update_layout(showlegend=False)
                ui.grafico(fig, 460)
            else:
                st.info({"Só saídas": "Débitos sobre as vendas, créditos presumidos de saída (art. 450) e "
                                      "contribuição do art. 457.",
                         "Só entradas": "Créditos das compras e créditos presumidos de entrada (arts. 447/449). "
                                        "Valores negativos reduzem a carga."}[visao], icon=":material/info:")
        with st.expander("As Is e To Be por tributo e empresa"):
            d2 = dif.copy()
            d2.insert(0, "empresa", d2["raiz"].map(ctx.nome))
            ui.tabela(d2)
    with t2:
        ev = simulacao.diferenca_por_tributo(anual[anual.cenario == cenario])
        ev = ev[ev.tributo.isin(tribs)].groupby("ano", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
        ui.secao("Evolução 2027–2033")
        fig = go.Figure([go.Bar(x=ev["ano"].astype(str), y=ev["to_be"], name="Carga To Be", marker_color="#1E5A8A"),
                         go.Scatter(x=ev["ano"].astype(str), y=ev["as_is"], name="Carga As Is", mode="lines+markers",
                                    line={"color": "#D98E04", "width": 3})])
        fig.update_xaxes(type="category")
        ui.grafico(fig, 340)
        ui.tabela(ev)
        ui.secao(f"Comparação de cenários de alíquotas ({ano})")
        cp = simulacao.diferenca_por_tributo(anual[anual.ano == ano])
        ui.tabela(cp[cp.tributo.isin(tribs)].groupby("cenario", as_index=False)[["as_is", "to_be", "diferenca"]].sum())
    with t3:
        ui.secao("Art. 450 de IBS por faixa: saldo devedor e crédito presumido",
                 "O crédito presumido de IBS incide sobre o saldo devedor do período (nunca sobre a receita), separado "
                 "por faixa de percentual. Os créditos do período são alocados às faixas na proporção dos débitos "
                 "(premissa criterio_alocacao_450). A parcela não elegível fica sem crédito presumido.")
        fx = anual[anual.cenario == cenario][["raiz", "ano"] + [c for c in anual.columns
                                                              if c.startswith("sd_") or c.startswith("cp450_")]].copy()
        if not fx.empty:
            fx.insert(0, "empresa", fx["raiz"].map(ctx.nome))
            fx = fx.drop(columns=["raiz"]).rename(columns={
                "sd_55": "Saldo devedor – final", "cp450_55": "CP 55%", "sd_75": "Saldo devedor – capital",
                "cp450_75": "CP 75%", "sd_90_25": "Saldo devedor – intermediário", "cp450_90_25": "CP 90,25%",
                "sd_100": "Saldo devedor – informática/CE 100%", "cp450_100": "CP 100%"})
            ui.tabela(fx.astype({"ano": str}))
        ui.secao("Teste de absorção dos créditos presumidos", "O crédito presumido só abate CBS/IBS da própria "
                 "empresa, não é ressarcido e vence no prazo 'prazo_cp_anos'. Teórico = todo crédito aproveitado; "
                 "realizável = o que de fato abate a carga.")
        ab = anual[anual.cenario == cenario][["raiz", "ano", "cp_cbs_gerado", "cp_cbs_usado", "cp_cbs_expirado",
                                              "cp_entrada_gerado", "cp_entrada_usado", "cp_entrada_expirado",
                                              "cp_ibs_450", "meses_saldo_credor", "to_be_total",
                                              "to_be_total_teorico", "diferenca_total",
                                              "diferenca_total_teorica"]].copy()
        ab.insert(0, "empresa", ab["raiz"].map(ctx.nome))
        ui.tabela(ab.drop(columns=["raiz"]).rename(columns={
            "to_be_total": "To Be realizável", "to_be_total_teorico": "To Be teórico",
            "diferenca_total": "Diferença realizável", "diferenca_total_teorica": "Diferença teórica"}),
            moeda=["cp_cbs_gerado", "cp_cbs_usado", "cp_cbs_expirado", "cp_entrada_gerado", "cp_entrada_usado",
                   "cp_entrada_expirado", "cp_ibs_450", "To Be realizável", "To Be teórico",
                   "Diferença realizável", "Diferença teórica"])
        estr = ab[ab["meses_saldo_credor"] >= 12]
        if not estr.empty:
            st.warning("Saldo credor estrutural (12 meses no ano com saldo de crédito): "
                       + ", ".join(sorted({f"{ctx.nome(x)} ({y})" for x, y in zip(estr.raiz, estr.ano)})),
                       icon=":material/warning:")
        with st.expander("Mês a mês"):
            mm = mensal[mensal.cenario == cenario]
            ui.tabela(mm.drop(columns=["cenario"]), altura=400,
                      moeda=[c for c in mm.columns if c not in ("cenario", "ano", "mes", "raiz", "observado",
                                                                "saldo_credor")])
            ui.baixar_csv(mm, "absorcao_mensal")
    with t4:
        ui.secao("Carga própria × vantagem competitiva (IPI)", "A carga própria de IPI da empresa da ZFM é zero antes "
                 "e depois. O efeito do IPI é concorrencial: nos produtos sem IPI protegido, o concorrente de fora "
                 "deixa de pagar. Detalhe por produto em Análise > Cenários ZFM > IPI por produto.")
        v = sel[["raiz", "diferenca_total", "ipi_conc_as_is", "ipi_conc_to_be", "perda_vantagem_ipi"]].copy()
        v.insert(0, "empresa", v["raiz"].map(ctx.nome))
        ui.tabela(v.drop(columns=["raiz"]).rename(columns={
            "diferenca_total": "Diferença de carga própria", "ipi_conc_as_is": "IPI do concorrente hoje",
            "ipi_conc_to_be": f"IPI do concorrente em {ano}", "perda_vantagem_ipi": "Perda de vantagem"}),
            moeda=["Diferença de carga própria", "IPI do concorrente hoje", f"IPI do concorrente em {ano}",
                   "Perda de vantagem"])
