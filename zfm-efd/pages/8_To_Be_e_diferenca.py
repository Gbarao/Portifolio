import plotly.graph_objects as go
import streamlit as st

from zfm import params, simulacao, ui

ctx = ui.contexto(
    "8. To Be e diferença",
    "Para que serve: simular a carga 2027–2033 (CBS, IBS, ICMS residual, IPI e contribuição do "
    "art. 457) sobre a base de operações de 2026 e comparar com a carga As Is da apuração. "
    "Diferença = To Be − As Is: positivo = aumento de carga (perda); negativo = redução (ganho). "
    "O que fazer: escolha cenário, ano e tributos; veja a ponte e o ranking.",
)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("rodar a simulação"):
    with st.spinner("Simulando..."):
        anual, mensal = simulacao.simular(con, f, ctx.teses)
    if anual.empty:
        st.warning("Sem dados para simular.")
        st.stop()
    cenarios = list(dict.fromkeys(anual["cenario"]))
    c1, c2, c3 = st.columns([1, 2, 2])
    cenario = c1.selectbox("Cenário", cenarios, key="tb_cen")
    ano = c2.select_slider("Ano", options=simulacao.ANOS, value=2033, key="tb_ano")
    visao = c3.radio("Visão", ui.VISOES, horizontal=True, key="tb_visao",
                     help="Só saídas: débitos e créditos presumidos de saída. Só entradas: créditos das "
                          "entradas e créditos presumidos de entrada.")
    tribs_todos = ["ICMS", "IPI", "PIS", "COFINS", "CBS", "IBS", "Contribuição art. 457"]
    tribs = st.multiselect("Tributos", tribs_todos, default=tribs_todos, key="tb_tribs")

    cen = params.carregar("param_aliquotas_cenario")
    lc = cen[(cen.cenario == cenario) & (cen.ano == ano)]
    if not lc.empty:
        l0 = lc.iloc[0]
        n = lambda x: f"{x:.2f}".replace(".", ",")  # noqa: E731
        st.caption(f"CBS {n(l0.aliq_cbs or 0)}% · IBS {n(l0.aliq_ibs or 0)}% · fator ICMS {n(l0.fator_icms or 0)} · "
                   f"CP art. 450: {'sim' if l0.aplica_cp_450 else 'não'} · Fonte: {l0.fonte}")

    sel = anual[(anual.cenario == cenario) & (anual.ano == ano)]
    dif = simulacao.diferenca_por_tributo(sel)
    dif = dif[dif.tributo.isin(tribs)]
    if visao != "Completa":
        comp = simulacao.composicao(sel, con, f)
        lado = "saidas" if visao == "Só saídas" else "entradas"
        comp = comp[(comp.lado == lado) & comp.tributo.isin(tribs)]
        piv = comp.pivot_table(index=["raiz", "tributo"], columns="regime", values="valor",
                               aggfunc="sum", fill_value=0.0).reset_index()
        for col in ("As Is", "To Be"):
            if col not in piv.columns:
                piv[col] = 0.0
        dif = piv.rename(columns={"As Is": "as_is", "To Be": "to_be"})
        dif["diferenca"] = dif["to_be"] - dif["as_is"]
        st.info({"Só saídas": "Visão só de saídas: débitos sobre as vendas e créditos presumidos de saída "
                              "(art. 450), contribuição do art. 457.",
                 "Só entradas": "Visão só de entradas: créditos das compras e créditos presumidos de "
                                "entrada (arts. 447/449). Valores negativos reduzem a carga."}[visao])
    tot_as, tot_tb = dif["as_is"].sum(), dif["to_be"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Carga As Is (anualizada)", ui.formatar_brl_curto(tot_as), help=ui.formatar_brl(tot_as))
    k2.metric(f"Carga To Be {ano}", ui.formatar_brl_curto(tot_tb), help=ui.formatar_brl(tot_tb))
    k3.metric("Diferença (+ perda / − ganho)", ui.formatar_brl_curto(tot_tb - tot_as),
              help=ui.formatar_brl(tot_tb - tot_as), delta_color="inverse",
              delta=ui.formatar_brl_curto(tot_tb - tot_as))

    aj = sel["ajuste_reconciliacao_total"].sum()
    if abs(aj) > params.premissa_num("tolerancia_conciliacao", 1.0):
        st.warning(f"Ajuste de reconciliação de {ui.formatar_brl(aj)} por ano: a base de operações não "
                   "explica toda a apuração (R5, tela 7). Essa parte da diferença vem da base, não da reforma.")

    st.subheader("Diferença por tributo (uma coluna por empresa)")
    ui.tabela(ui.por_empresa(dif, ["tributo"], "diferenca", nomes))
    with st.expander("As Is e To Be por tributo e empresa"):
        d2 = dif.copy()
        d2.insert(0, "empresa", d2["raiz"].map(lambda r: nomes.get(r, r)))
        ui.tabela(d2)

    if visao == "Completa":
        st.subheader("Ponte da carga: As Is → To Be")
        p = simulacao.ponte(anual, cenario, ano, ctx.raizes)
        fig = go.Figure(go.Waterfall(x=p["etapa"], y=p["valor"], measure=p["medida"],
                                     text=[ui.formatar_brl_curto(v) for v in p["valor"]], textposition="outside",
                                     increasing={"marker": {"color": "#C62828"}},
                                     decreasing={"marker": {"color": "#2E7D32"}}))
        fig.update_layout(height=480, margin=dict(t=30))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Vermelho = aumento de carga; verde = redução.")

    st.subheader("Ranking das empresas (da maior perda ao maior ganho)")
    r = dif.groupby("raiz", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
    r = r.merge(sel[["raiz", "ajuste_reconciliacao_total", "perda_vantagem_ipi"]], on="raiz", how="left")
    r.insert(0, "empresa", r["raiz"].map(lambda x: nomes.get(x, x)))
    r = r.sort_values("diferenca", ascending=False)
    ui.tabela(r.rename(columns={"ajuste_reconciliacao_total": "ajuste_reconciliacao (base×apuração)",
                                "perda_vantagem_ipi": "perda_vantagem_competitiva_ipi"}))

    st.subheader("Duas métricas: carga própria × vantagem competitiva (IPI)")
    st.caption("A carga própria de IPI da empresa da ZFM é zero antes e depois. O efeito do IPI é "
               "concorrencial: nos produtos sem IPI protegido, o concorrente de fora deixa de pagar. "
               "Perda de vantagem = IPI que o concorrente pagava − IPI que continua pagando.")
    v = sel[["raiz", "diferenca_total", "ipi_conc_as_is", "ipi_conc_to_be", "perda_vantagem_ipi"]].copy()
    v.insert(0, "empresa", v["raiz"].map(lambda x: nomes.get(x, x)))
    ui.tabela(v.rename(columns={"diferenca_total": "diferença de carga própria",
                                "ipi_conc_as_is": "IPI do concorrente hoje",
                                "ipi_conc_to_be": f"IPI do concorrente em {ano}",
                                "perda_vantagem_ipi": "perda de vantagem competitiva"}))
    with st.expander("Vantagem competitiva por produto"):
        pp = con.execute(f"""
            SELECT b.raiz, b.cod_item, b.ncm_produto AS ncm, b.aliq_tipi, b.ipi_protegido,
                   sum(b.valor) AS receita_incentivada, sum(b.valor * b.aliq_tipi / 100) AS ipi_concorrente_hoje
            FROM v_base_operacoes b
            WHERE b.sentido = 'saida' AND b.incentivado AND b.tipo_operacao <> 'exportacao' AND {f.sql('b.raiz', 'b.cnpj_estab', 'b.mes')}
            GROUP BY ALL ORDER BY ipi_concorrente_hoje DESC NULLS LAST""").df()
        pp = pp[pp.raiz.isin(ctx.raizes)]
        if not pp.empty:
            lim = params.premissa_num("limite_tipi_ipi", 6.5)
            sem_ipi = str(lc.iloc[0].ipi_protegido_override).lower() in ("nao", "não") if not lc.empty else False
            pp["mantido_to_be"] = pp["ipi_protegido"] & (pp["aliq_tipi"] >= lim) & (not sem_ipi)
            st.caption("Valores do período filtrado (não anualizados). Sem TIPI preenchida, o produto aparece vazio.")
        ui.tabela(pp)

    st.subheader("Evolução 2027–2033")
    ev = simulacao.diferenca_por_tributo(anual[anual.cenario == cenario])
    ev = ev[ev.tributo.isin(tribs)].groupby("ano", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
    st.plotly_chart(go.Figure([go.Bar(x=ev["ano"], y=ev["to_be"], name="Carga To Be"),
                               go.Scatter(x=ev["ano"], y=ev["as_is"], name="Carga As Is", mode="lines+markers")]),
                    use_container_width=True)
    ui.tabela(ev)
    st.subheader("Comparação de cenários (ano selecionado)")
    cp = simulacao.diferenca_por_tributo(anual[anual.ano == ano])
    cp = cp[cp.tributo.isin(tribs)].groupby("cenario", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
    ui.tabela(cp)

    st.subheader("Teste de absorção dos créditos presumidos (por empresa)")
    st.caption("O crédito presumido só abate CBS/IBS da própria empresa, não é ressarcido e vence em "
               "Parâmetros > Premissas > prazo_cp_anos. 'Teórico' = todo crédito gerado aproveitado; "
               "'realizável' = o que de fato abate a carga.")
    ab = anual[anual.cenario == cenario][["raiz", "ano", "cp_cbs_gerado", "cp_cbs_usado", "cp_cbs_expirado",
                                          "cp_entrada_gerado", "cp_entrada_usado", "cp_entrada_expirado",
                                          "cp_ibs_450", "meses_saldo_credor", "to_be_total", "to_be_total_teorico",
                                          "diferenca_total", "diferenca_total_teorica"]].copy()
    ab.insert(0, "empresa", ab["raiz"].map(lambda x: nomes.get(x, x)))
    ui.tabela(ab.rename(columns={"to_be_total": "carga To Be (realizável)",
                                 "to_be_total_teorico": "carga To Be (teórica)",
                                 "diferenca_total": "diferença (realizável)",
                                 "diferenca_total_teorica": "diferença (teórica)"}),
              moeda=[c for c in ab.columns if c not in ("empresa", "raiz", "ano", "meses_saldo_credor")]
              + ["carga To Be (realizável)", "carga To Be (teórica)", "diferença (realizável)", "diferença (teórica)"])
    estr = ab[ab["meses_saldo_credor"] >= 12]
    if not estr.empty:
        st.warning("Saldo credor estrutural (12 meses no ano com saldo de crédito): "
                   + ", ".join(sorted({f"{nomes.get(x, x)} ({y})" for x, y in zip(estr.raiz, estr.ano)})))
    with st.expander("Mês a mês"):
        mm = mensal[mensal.cenario == cenario]
        ui.tabela(mm.drop(columns=["cenario"]), altura=400,
                  moeda=[c for c in mm.columns if c not in ("cenario", "ano", "mes", "raiz", "observado",
                                                            "saldo_credor")])
        ui.baixar_csv(mm, "absorcao_mensal")
