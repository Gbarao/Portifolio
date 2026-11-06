import plotly.graph_objects as go
import streamlit as st

from zfm import params, simulacao, ui

ui.cabecalho(
    "8. Simulação e cenários",
    "Para que serve: simular a mesma base de operações de 2026 no regime pós-reforma (CBS, IBS, "
    "IPI residual e ICMS em extinção) e comparar com o benefício de hoje. O que fazer: escolha o "
    "cenário e o ano. As alíquotas de cada cenário ficam em Parâmetros > Alíquotas por cenário.",
)
con = ui.conexao()
sel = ui.seletor_empresas(con)
if con is None:
    st.stop()
if not ui.preparar(con):
    ui.aviso_sem_dados()
    st.stop()
teses, intra = ui.filtros_globais()
visao = ui.seletor_visao()
raizes = ui.raizes_analise(con, sel)
ui.exigir_empresas(raizes)
nomes = ui.nomes_empresas()

with ui.protegido("rodar a simulação"):
    with st.spinner("Simulando..."):
        anual, mensal = simulacao.simular(con, com_teses=teses, eliminar_intragrupo=intra)
    if anual.empty:
        st.warning("Sem dados para simular.")
        st.stop()
    anual = anual[anual.raiz.isin(raizes)]
    mensal = mensal[mensal.raiz.isin(raizes)]
    c1, c2 = st.columns(2)
    cenario = c1.selectbox("Cenário", list(anual["cenario"].unique()))
    ano = c2.select_slider("Ano", options=simulacao.ANOS, value=2033)
    cen = params.carregar("param_aliquotas_cenario")
    linha = cen[(cen.cenario == cenario) & (cen.ano == ano)]
    if not linha.empty:
        l0 = linha.iloc[0]
        n = lambda x: f"{x:.2f}".replace(".", ",")  # noqa: E731
        st.caption(f"CBS {n(l0.aliq_cbs)}% · IBS {n(l0.aliq_ibs)}% · fator ICMS {n(l0.fator_icms)} · "
                   f"CP art. 450: {'sim' if l0.aplica_cp_450 else 'não'} · Fonte: {l0.fonte}")
        if not l0.aliq_cbs or (ano >= 2029 and not l0.aliq_ibs):
            st.warning("Alíquota não preenchida para este cenário/ano.")
    # Visao: completa / so saidas / so entradas (hoje, o beneficio calculado e todo de saidas)
    col_pos = {"Completa": "beneficio_pos", "Só saídas": "beneficio_saidas",
               "Só entradas": "beneficio_entradas"}[visao]
    anual = anual.assign(
        v_pos=anual[col_pos],
        v_hoje=anual["beneficio_hoje"] if visao != "Só entradas" else 0.0)
    anual["v_delta"] = anual["v_pos"] - anual["v_hoje"]
    if visao != "Completa":
        st.info({"Só saídas": "Visão só de saídas: efeito sobre as vendas – CBS/IBS zero nas vendas "
                              "para a ZFM, créditos presumidos do art. 450, ICMS residual, IPI protegido "
                              "e contribuição do art. 457. Comparado com todo o benefício de hoje.",
                 "Só entradas": "Visão só de entradas: créditos presumidos de IBS sobre as compras "
                                "(arts. 447 e 449) efetivamente usados. Hoje o benefício nas compras é "
                                "informativo (tela 7, visão 'Só entradas'), por isso 'hoje' = 0."}[visao])
    a = anual[(anual.cenario == cenario) & (anual.ano == ano)]
    s = a.sum(numeric_only=True)
    s["beneficio_hoje"], s["beneficio_pos"], s["delta"] = s["v_hoje"], s["v_pos"], s["v_delta"]
    k1, k2, k3 = st.columns(3)
    k1.metric("Benefício hoje (anualizado)", ui.formatar_brl_curto(s["beneficio_hoje"]),
              help=ui.formatar_brl(s["beneficio_hoje"]))
    k2.metric("Benefício pós-reforma", ui.formatar_brl_curto(s["beneficio_pos"]),
              help=ui.formatar_brl(s["beneficio_pos"]))
    k3.metric("Δ (pós − hoje)", ui.formatar_brl_curto(s["delta"]), help=ui.formatar_brl(s["delta"]))

    st.subheader("Ponte do benefício de hoje ao pós-reforma")
    p = simulacao.ponte(anual, cenario, ano, raizes)
    if visao == "Só saídas":
        p = p[p.etapa != "+ CP de entrada 447/449 (entradas)"].copy()
        p.loc[p.medida == "total", "valor"] = s["v_pos"]
        p.loc[p.medida == "total", "etapa"] = "Benefício pós-reforma (saídas)"
    elif visao == "Só entradas":
        p = p[p.etapa.isin(["+ CP de entrada 447/449 (entradas)"])].copy()
        p.loc[len(p)] = ["Benefício pós-reforma (entradas)", s["v_pos"], "total"]
    fig = go.Figure(go.Waterfall(x=p["etapa"], y=p["valor"], measure=p["medida"],
                                 text=[ui.formatar_brl_curto(v) for v in p["valor"]], textposition="outside"))
    fig.update_layout(height=480, margin=dict(t=30))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Δ por empresa (do maior ganho à maior perda)")
    r = a[["raiz", "v_hoje", "v_pos", "v_delta", "beneficio_saidas", "beneficio_entradas",
           "beneficio_cbs", "beneficio_ibs", "beneficio_icms", "beneficio_ipi", "beneficio_contrib_457",
           "beneficio_teses"]].rename(columns={"v_hoje": "beneficio_hoje", "v_pos": "beneficio_pos",
                                               "v_delta": "delta"}).copy()
    r.insert(0, "empresa", r["raiz"].map(lambda x: nomes.get(x, x)))
    r = r.sort_values("delta", ascending=False)
    if len(r) > 1:
        tot = r.sum(numeric_only=True)
        tot["empresa"], tot["raiz"] = "Total (consolidado)", ""
        r.loc[len(r) + 1000] = tot
    ui.tabela(r)

    st.subheader("Evolução 2027–2033")
    ev = anual[anual.cenario == cenario].groupby("ano", as_index=False)[["v_hoje", "v_pos", "v_delta"]].sum() \
        .rename(columns={"v_hoje": "beneficio_hoje", "v_pos": "beneficio_pos", "v_delta": "delta"})
    st.plotly_chart(go.Figure([go.Bar(x=ev["ano"], y=ev["beneficio_pos"], name="Pós-reforma"),
                               go.Scatter(x=ev["ano"], y=ev["beneficio_hoje"], name="Hoje",
                                          mode="lines+markers")]), use_container_width=True)
    ui.tabela(ev)
    st.subheader("Comparação de cenários (ano selecionado)")
    comp = anual[anual.ano == ano].groupby("cenario", as_index=False)[["v_hoje", "v_pos", "v_delta"]].sum() \
        .rename(columns={"v_hoje": "beneficio_hoje", "v_pos": "beneficio_pos", "v_delta": "delta"})
    ui.tabela(comp)

    st.subheader("Teste de absorção dos créditos presumidos (por empresa)")
    st.caption("Crédito presumido gerado × utilizado × expirado. O crédito não usado no prazo "
               "(Parâmetros > Premissas > prazo_cp_anos) expira, sem ressarcimento.")
    ab = anual[anual.cenario == cenario][["raiz", "ano", "cp_cbs_gerado", "cp_cbs_usado",
                                          "cp_cbs_expirado", "cp_entrada_gerado", "cp_entrada_usado",
                                          "cp_entrada_expirado", "meses_saldo_credor",
                                          "beneficio_cbs_teorico", "beneficio_cbs",
                                          "beneficio_ibs_teorico", "beneficio_ibs"]].copy()
    ab.insert(0, "empresa", ab["raiz"].map(lambda x: nomes.get(x, x)))
    ui.tabela(ab, moeda=[c for c in ab.columns if c not in ("empresa", "raiz", "ano", "meses_saldo_credor")])
    estr = ab[ab["meses_saldo_credor"] >= 12]
    if not estr.empty:
        st.warning("Saldo credor estrutural (12 meses no ano com saldo de crédito): "
                   + ", ".join(sorted({f"{nomes.get(x, x)} ({y})" for x, y in zip(estr.raiz, estr.ano)})))
    with st.expander("Mês a mês"):
        mm = mensal[mensal.cenario == cenario]
        ui.tabela(mm.drop(columns=["cenario"]), altura=400,
                  moeda=[c for c in mm.columns if c not in ("cenario", "ano", "mes", "raiz", "observado",
                                                            "saldo_credor")])
