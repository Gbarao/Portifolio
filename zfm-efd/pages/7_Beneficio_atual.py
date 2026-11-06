import plotly.express as px
import streamlit as st

from zfm import beneficio_atual as ba
from zfm import conciliacoes, qualidade, ui

ui.cabecalho(
    "7. Benefício atual",
    "Para que serve: quantificar o benefício da ZFM hoje (2026 acumulado no ano) em IPI, PIS, "
    "COFINS e ICMS. Benefício = carga no regime geral − carga efetiva na ZFM. O que fazer: confira "
    "os totais e os alertas; cada valor pode ser rastreado até a linha da EFD (no fim da tela).",
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

if visao == "Só entradas":
    with ui.protegido("montar a visão das entradas"):
        st.subheader("Visão só de entradas – compras com isenção, suspensão ou alíquota zero")
        st.info("Informativo: o benefício nas compras não entra no total, porque o mesmo efeito já "
                "aparece na apuração (premissa 'beneficio_entradas_no_total'). Para PIS/COFINS, o "
                "tributo não cobrado é estimado pela alíquota do regime geral; para ICMS e IPI, só o "
                "valor das compras é mostrado (a alíquota depende do produto e da origem).")
        e = ba.entradas_desoneradas(con)
        e = e[e["raiz"].isin(raizes)]
        if e.empty:
            st.caption("Nenhuma compra com isenção, suspensão ou alíquota zero.")
            st.stop()
        cols = st.columns(4)
        for c, t in zip(cols, ["ICMS", "IPI", "PIS", "COFINS"]):
            d = e[e.tributo == t]
            c.metric(f"Compras desoneradas – {t}", ui.formatar_brl_curto(d["valor_entradas"].sum()),
                     help=ui.formatar_brl(d["valor_entradas"].sum()))
        st.markdown("**Por tributo, situação e empresa (valor das compras)**")
        ui.tabela(ui.por_empresa(e, ["tributo", "cst", "situacao"], "valor_entradas", nomes))
        st.markdown("**PIS/COFINS não cobrados nas compras (estimativa)**")
        ui.tabela(ui.por_empresa(e[e.tributo.isin(["PIS", "COFINS"])], ["tributo", "situacao"],
                                 "tributo_nao_cobrado_estimado", nomes))
        st.markdown("**Por origem**")
        ui.tabela(ui.por_empresa(e, ["tributo", "regiao_origem"], "valor_entradas", nomes))
        with st.expander("Registros de origem (arquivo e linha)"):
            ui.tabela(e, moeda=["valor_entradas", "tributo_nao_cobrado_estimado"], altura=400)
    st.stop()
if visao == "Só saídas":
    st.caption("Visão só de saídas: todo o benefício atual calculado (IPI, PIS, COFINS e ICMS) vem "
               "das vendas; é igual à visão completa.")

with ui.protegido("calcular o benefício atual"):
    det = ba.calcular(con, com_teses=teses, eliminar_intragrupo=intra)
    det = det[det["raiz"].isin(raizes)] if not det.empty else det
    rec = ba.receita_incentivada(con, intra)
    rec = rec[rec["raiz"].isin(raizes)]
    if det.empty:
        st.warning("Nenhum benefício calculado. Verifique em Parâmetros > Produtos se os produtos "
                   "incentivados estão marcados e se os códigos de crédito estímulo estão classificados.")
        st.stop()
    # ---- alertas
    obs = det[det["observacao"].fillna("").str.contains("não preenchida|não alocado|premissa|Sem registro")]
    for o, g in obs.groupby("observacao"):
        st.warning(f"{o} ({len(g)} linha(s), {ui.formatar_brl(g['beneficio'].sum())} no benefício).")
    if det["rateado"].fillna(False).astype(bool).any():
        st.info("Parte do cálculo usa rateio (destino por CFOP ou alocação do ICMS por receita). "
                "Veja as premissas em Parâmetros > Premissas.")
    q11 = conciliacoes.q11_codigos_nao_classificados(con)
    if not q11.empty:
        st.warning(f"{len(q11)} código(s) de ajuste do ICMS sem classificação: o benefício de ICMS "
                   "pode estar incompleto.")

    tot = det.groupby("tributo")["beneficio"].sum()
    cols = st.columns(5)
    for c, t in zip(cols, ba.TRIBUTOS):
        c.metric(t, ui.formatar_brl_curto(tot.get(t, 0.0)), help=ui.formatar_brl(tot.get(t, 0.0)))
    cols[4].metric("Total", ui.formatar_brl_curto(tot.sum()), help=ui.formatar_brl(tot.sum()))
    receita = rec["receita_incentivada"].sum()
    st.caption(f"Receita de saídas incentivadas: {ui.formatar_brl(receita)} · "
               f"Benefício = {100 * tot.sum() / receita:,.2f}% da receita incentivada".replace(".", ",")
               if receita else "Sem receita incentivada.")

    st.subheader("Por empresa")
    r = ba.resumo_por_empresa(det, rec)
    r.insert(0, "empresa", r["raiz"].map(lambda x: nomes.get(x, x)))
    ui.tabela(r, pct=["% da receita incentivada"])
    st.subheader("Por tributo (uma coluna por empresa)")
    ui.tabela(ui.por_empresa(det, ["tributo"], "beneficio", nomes))
    st.subheader("Por mês")
    m = det.groupby(["mes", "tributo", "raiz"], as_index=False)["beneficio"].sum()
    visao = st.radio("Gráfico", ["Total", "Por empresa"], horizontal=True, key="g_ben")
    m["empresa"] = m["raiz"].map(lambda x: nomes.get(x, x))
    m["mês"] = m["mes"].map(lambda x: qualidade.MESES[x - 1])
    st.plotly_chart(px.bar(m, x="mês", y="beneficio", color="tributo" if visao == "Total" else "empresa",
                           labels={"beneficio": "R$"}), use_container_width=True)
    ui.tabela(ui.por_empresa(det, ["mes", "tributo"], "beneficio", nomes))
    st.subheader("Por produto")
    ui.tabela(ui.por_empresa(det.fillna({"cod_item": "(não alocado)"}), ["cod_item", "tributo"],
                             "beneficio", nomes))

    st.subheader("Rastreabilidade: registros que compõem o valor")
    c1, c2, c3 = st.columns(3)
    trib = c1.selectbox("Tributo", ba.TRIBUTOS)
    emp = c2.selectbox("Empresa", sorted(det["raiz"].unique()), format_func=lambda x: nomes.get(x, x))
    mes = c3.selectbox("Mês", sorted(det["mes"].unique()), format_func=lambda x: qualidade.MESES[x - 1])
    d = det[(det.tributo == trib) & (det.raiz == emp) & (det.mes == mes)]
    arqs = con.execute("SELECT arquivo_id, nome_arquivo FROM arquivos").df()
    d = d.merge(arqs, on="arquivo_id", how="left")
    st.caption(f"Soma: {ui.formatar_brl(d['beneficio'].sum())}")
    ui.tabela(d[["cnpj_estab", "cod_item", "beneficio", "base", "aliq_regime_geral", "aliq_aplicada",
                 "reg_origem", "nome_arquivo", "linha_num", "rateado", "observacao"]],
              moeda=["beneficio", "base"], altura=350)
