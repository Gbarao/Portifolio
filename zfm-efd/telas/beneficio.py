import plotly.express as px
import streamlit as st

from zfm import beneficio_atual as ba
from zfm import conciliacoes, qualidade, ui

ctx = ui.contexto(
    "Benefício ZFM hoje (informativo)",
    "Informativo: quanto a ZFM reduz hoje de IPI, PIS, COFINS e ICMS (carga no regime geral − carga efetiva na "
    "ZFM). O resultado principal do estudo é a diferença To Be − As Is. Cada valor é rastreável até a linha da EFD.",
    "Análise", intragrupo=True)
con, f, raizes, nomes = ctx.con, ctx.filtro, ctx.raizes, ctx.nomes

with ui.protegido("calcular o benefício atual"):
    det = ui.calcular("beneficio", f, ctx.teses, intra=ctx.intra)
    det = det[det["raiz"].isin(raizes)] if not det.empty else det
    rec = ui.calcular("receita_incentivada", f, intra=ctx.intra)
    rec = rec[rec["raiz"].isin(raizes)]
    t1, t2, t3 = st.tabs(["Benefício nas saídas", "Compras desoneradas", "Rastreabilidade"])
    with t1:
        if det.empty:
            ui.vazio("Nenhum benefício calculado", "Verifique em Parâmetros > Produtos se os produtos incentivados "
                     "estão marcados e se os códigos de crédito estímulo estão classificados.")
        else:
            d = ui.filtros_tabela(det, {"tributo": "Tributo", "cod_item": "Produto", "cnpj_estab": "Estabelecimento"},
                                  "ben")
            obs = d[d["observacao"].fillna("").str.contains("não preenchida|não alocado|premissa|Sem registro")]
            for o, g in obs.groupby("observacao"):
                st.warning(f"{o} ({len(g)} linha(s), {ui.formatar_brl(g['beneficio'].sum())}).", icon=":material/warning:")
            q11 = conciliacoes.filtrar(conciliacoes.q11_codigos_nao_classificados(con), f)
            if not q11.empty:
                st.warning(f"{len(q11)} código(s) de ajuste do ICMS sem classificação: o benefício de ICMS pode "
                           "estar incompleto.", icon=":material/warning:")
            tot = d.groupby("tributo")["beneficio"].sum()
            ui.cartoes({**{t: tot.get(t, 0.0) for t in ba.TRIBUTOS}, "Total": tot.sum()}, destaque="Total")
            receita = rec["receita_incentivada"].sum()
            if receita:
                st.caption(f"Receita incentivada: {ui.formatar_brl(receita)} · benefício = "
                           f"{ui.formatar_num(100 * tot.sum() / receita, 2)}% da receita incentivada.")
            c1, c2 = st.columns([1.2, 1])
            with c1:
                ui.secao("Por empresa")
                r = ba.resumo_por_empresa(d, rec)
                r.insert(0, "empresa", r["raiz"].map(ctx.nome))
                ui.tabela(r.drop(columns=["raiz"]), pct=["% da receita incentivada"])
            with c2:
                m = d.groupby(["mes", "tributo"], as_index=False)["beneficio"].sum()
                m["mês"] = m["mes"].map(lambda x: qualidade.MESES[x - 1])
                ui.grafico(px.bar(m, x="mês", y="beneficio", color="tributo", labels={"beneficio": "R$", "mês": ""}),
                           300)
            ui.secao("Por tributo e mês")
            ui.tabela(ui.por_empresa(d, ["mes", "tributo"], "beneficio", nomes))
            ui.secao("Por produto")
            ui.tabela(ui.por_empresa(d.fillna({"cod_item": "(não alocado)"}), ["cod_item", "tributo"], "beneficio",
                                     nomes))
    with t2:
        ui.secao("Compras com isenção, suspensão ou alíquota zero", "Informativo: não entra no total, porque o "
                 "efeito já aparece na apuração. PIS/COFINS estimados pela alíquota do regime geral; para ICMS e IPI "
                 "só o valor das compras.")
        e = ba.entradas_desoneradas(con, f)
        e = e[e["raiz"].isin(raizes)]
        if e.empty:
            ui.vazio("Nenhuma compra desonerada")
        else:
            ui.cartoes({f"Compras desoneradas – {t}": e.loc[e.tributo == t, "valor_entradas"].sum()
                        for t in ["ICMS", "IPI", "PIS", "COFINS"]})
            ui.tabela(ui.por_empresa(e, ["tributo", "cst", "situacao"], "valor_entradas", nomes))
            ui.secao("PIS/COFINS não cobrados nas compras (estimativa)")
            ui.tabela(ui.por_empresa(e[e.tributo.isin(["PIS", "COFINS"])], ["tributo", "situacao"],
                                     "tributo_nao_cobrado_estimado", nomes))
            ui.secao("Por origem")
            ui.tabela(ui.por_empresa(e, ["tributo", "regiao_origem"], "valor_entradas", nomes))
    with t3:
        if det.empty:
            ui.vazio("Sem benefício para rastrear")
        else:
            c1, c2, c3 = st.columns(3)
            trib = c1.selectbox("Tributo", ba.TRIBUTOS)
            emp = c2.selectbox("Empresa", sorted(det["raiz"].unique()), format_func=ctx.nome)
            mes = c3.selectbox("Mês", sorted(det["mes"].unique()), format_func=lambda x: qualidade.MESES[x - 1])
            d = det[(det.tributo == trib) & (det.raiz == emp) & (det.mes == mes)]
            arqs = con.execute("SELECT arquivo_id, nome_arquivo FROM arquivos").df()
            d = d.merge(arqs, on="arquivo_id", how="left")
            st.caption(f"Soma: {ui.formatar_brl(d['beneficio'].sum())}")
            ui.tabela(d[["cnpj_estab", "cod_item", "beneficio", "base", "aliq_regime_geral", "aliq_aplicada",
                         "reg_origem", "nome_arquivo", "linha_num", "rateado", "observacao"]],
                      moeda=["beneficio", "base"], altura=380)
