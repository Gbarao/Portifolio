import plotly.graph_objects as go
import streamlit as st

from zfm import cenarios as cz
from zfm import simulacao, ui

ctx = ui.contexto(
    "Cenários ZFM (C1–C5)",
    "Cada entrada e saída é classificada num cenário (importação, compra de outro Estado, compra na ZFM, venda "
    "a partir da ZFM, IPI por produto). Para cada cenário: tratamento As Is escriturado, simulação To Be e "
    "diferença por tributo, empresa e ano. Diferença = To Be − As Is (positivo = a empresa paga mais).",
    "Análise")
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes
desc = cz.descricoes()


def rot(c) -> str:
    return f"{c} – {desc.get(c, '')}" if c in desc and c != cz.NAO_ATRIBUIDO else str(c)


with ui.protegido("montar a análise por cenário"):
    with st.spinner("Classificando operações e simulando..."):
        mat = ui.calcular("matriz", f)
    if mat.empty:
        ui.vazio("Sem operações classificadas", "Confira o período e as empresas na barra lateral.")
        st.stop()
    abas = st.tabs(["Matriz", "As Is × To Be", "Ponte e ranking", "IPI por produto (C5)", "Alertas",
                    "Não classificados"])

    # ------------------------------------------------------------------ 1. matriz
    with abas[0]:
        ui.secao("Matriz cenário × empresa", "Valor das operações do período (líquido de devoluções) e número de "
                 "documentos. Cancelados ficam fora; transferências (TR) e operações com empresas do grupo são "
                 "sinalizadas.")
        c1, c2 = st.columns([1, 3])
        med = c1.radio("Mostrar", ["Valor (R$)", "Documentos"], horizontal=True, key="cz_med")
        sent = c2.radio("Sentido", ["Todos", "Entradas", "Saídas"], horizontal=True, key="cz_sent")
        m = mat if sent == "Todos" else mat[mat.sentido == ("entrada" if sent == "Entradas" else "saida")]
        col = "valor" if med.startswith("Valor") else "documentos"
        pv = ui.por_empresa(m, ["cenario"], col, nomes)
        if not pv.empty:
            pv = cz.ordenar(pv)
            pv.insert(1, "descricao", pv["cenario"].map(lambda c: desc.get(c, "")))
            pv["cenario"] = pv["cenario"].astype(str)
            intra = m.groupby("cenario", observed=True)["tem_intragrupo"].any()
            pv.insert(2, "intragrupo", pv["cenario"].map(intra).fillna(False).astype(bool))
            ui.tabela(pv, moeda=[c for c in pv.columns if c not in ("cenario", "descricao", "intragrupo")],
                      altura=min(36 * (len(pv) + 1) + 4, 700))
        nc = mat[mat.cenario.isin(["NC_S", "NC_E"])]
        if not nc.empty:
            st.warning(f"{ui.formatar_brl(nc['valor'].sum())} em {int(nc['linhas'].sum())} linha(s) não "
                       "classificadas: veja a aba 'Não classificados'.", icon=":material/warning:")

    # ------------------------------------------------------------------ 2. As Is x To Be
    res = None
    with abas[1]:
        with st.spinner("Simulando por cenário..."):
            res = ui.calcular("resultado_cenarios", f, ctx.teses)
        if res.empty:
            ui.vazio("Sem resultado")
        else:
            c1, c2, c3 = st.columns([1, 2, 2])
            cens_aliq = sorted(dict.fromkeys(res["cenario_aliq"]), key=lambda c: (c != "base", c))
            ca = c1.selectbox("Cenário de alíquotas", cens_aliq, key="cz_ca")
            ano = c2.select_slider("Ano", options=simulacao.ANOS, value=2033, key="cz_ano")
            tribs = c3.multiselect("Tributos", cz.TRIBUTOS, default=cz.TRIBUTOS, key="cz_trib")
            r = res[(res.cenario_aliq == ca) & (res.ano == ano) & res.tributo.isin(tribs)]
            ui.cartoes({"As Is (anualizado)": r["as_is"].sum(), f"To Be {ano}": r["to_be"].sum()})
            ui.cartoes({"Diferença": (r["diferenca"].sum(), "+ paga mais · − paga menos")}, sinal=True)
            ui.secao("Por cenário", "'Não atribuído' = ajustes da apuração, saldos credores, absorção dos créditos "
                     "presumidos e teses: fecha a soma com a carga total da empresa.")
            t = r.groupby("cenario", as_index=False, observed=True)[["as_is", "to_be", "diferenca"]].sum()
            t = cz.ordenar(t)
            t["cenario"] = t["cenario"].astype(str)
            t.insert(1, "descricao", t["cenario"].map(lambda c: desc.get(c, "")))
            ui.tabela(t)
            ui.secao("Diferença por cenário e tributo")
            p = r.pivot_table(index="cenario", columns="tributo", values="diferenca", aggfunc="sum",
                              fill_value=0.0, observed=True).reset_index()
            p = cz.ordenar(p)
            p["cenario"] = p["cenario"].astype(str)
            p["Total"] = p.drop(columns=["cenario"]).sum(axis=1)
            ui.tabela(p)
            ui.secao("Diferença por cenário e empresa")
            ui.tabela(cz.ordenar(ui.por_empresa(r, ["cenario"], "diferenca", nomes)).astype({"cenario": str}))
            with st.expander("As Is e To Be por cenário, tributo e empresa"):
                d = r.copy()
                d.insert(0, "empresa", d["raiz"].map(ctx.nome))
                d = cz.ordenar(d)
                ui.tabela(d.drop(columns=["cenario_aliq", "ano"]).astype({"cenario": str}))
                ui.baixar_csv(d, "cenarios_as_is_to_be")
            ui.secao("Evolução 2027–2033 por cenário (diferença)")
            ev = res[(res.cenario_aliq == ca) & res.tributo.isin(tribs)].pivot_table(
                index="cenario", columns="ano", values="diferenca", aggfunc="sum", fill_value=0.0,
                observed=True).reset_index()
            ev = cz.ordenar(ev)
            ev["cenario"] = ev["cenario"].astype(str)
            ev.columns = [str(c) for c in ev.columns]
            ui.tabela(ev)

    # ------------------------------------------------------------------ 3. ponte e ranking
    with abas[2]:
        if res is None or res.empty:
            ui.vazio("Sem resultado")
        else:
            ca = st.session_state.get("cz_ca", "base")
            if ca not in set(res["cenario_aliq"]):
                ca = res["cenario_aliq"].iloc[0]
            ano = st.session_state.get("cz_ano", 2033)
            tribs = st.session_state.get("cz_trib", cz.TRIBUTOS)
            st.caption(f"Cenário de alíquotas {ca} · ano {ano} (escolha na aba As Is × To Be).")
            r = res[(res.cenario_aliq == ca) & (res.ano == ano) & res.tributo.isin(tribs)]
            t = cz.ordenar(r.groupby("cenario", as_index=False, observed=True)[["as_is", "to_be", "diferenca"]].sum())
            t = t[t["diferenca"].abs() > 0.005]
            ini, fim = r["as_is"].sum(), r["to_be"].sum()
            x = ["As Is"] + ["Não atribuído" if c == cz.NAO_ATRIBUIDO else str(c) for c in t["cenario"]] + [f"To Be {ano}"]
            y = [ini] + list(t["diferenca"]) + [fim]
            fig = go.Figure(go.Waterfall(
                x=x, y=y, measure=["absolute"] + ["relative"] * len(t) + ["total"],
                text=[ui.formatar_brl_curto(v) for v in y], textposition="outside",
                increasing={"marker": {"color": "#B42318"}}, decreasing={"marker": {"color": "#1E7B4F"}},
                totals={"marker": {"color": "#1E5A8A"}}, connector={"line": {"color": "#C9D3DF"}}))
            fig.update_layout(showlegend=False, yaxis_title="R$")
            ui.secao("Ponte As Is → To Be por cenário", "Vermelho = aumento de carga; verde = redução.")
            ui.grafico(fig, 460)
            c1, c2 = st.columns(2)
            with c1:
                ui.secao("Ranking de cenários (maior perda primeiro)")
                rk = t.sort_values("diferenca", ascending=False).copy()
                rk["cenario"] = rk["cenario"].astype(str)
                rk.insert(1, "descricao", rk["cenario"].map(lambda c: desc.get(c, "")))
                ui.tabela(rk[["cenario", "descricao", "diferenca"]])
            with c2:
                ui.secao("Ranking de empresas")
                re_ = r.groupby("raiz", as_index=False)[["as_is", "to_be", "diferenca"]].sum()
                re_.insert(0, "empresa", re_["raiz"].map(ctx.nome))
                ui.tabela(re_.sort_values("diferenca", ascending=False).drop(columns=["raiz"]))

    # ------------------------------------------------------------------ 4. IPI por produto
    with abas[3]:
        ui.secao("IPI por produto (C5)", "Duas métricas separadas: carga própria de IPI (zero na ZFM antes e depois) "
                 "e vantagem competitiva (IPI que o concorrente de fora paga). TIPI ≥ 6,5% em 31/12/2023: IPI mantido "
                 "para o concorrente; TIPI < 6,5% e produzido na ZFM em 2024: IPI zero para todos (vantagem perdida; "
                 "o comprador também perde o crédito de IPI). TIC: análise manual.")
        sem = st.toggle("Simular sem IPI protegido (cenário adverso)", key="cz_sem_ipi")
        ip = ui.calcular("ipi_produto", f, sem_protegido=sem)
        ip = ip[ip.raiz.isin(ctx.raizes)] if not ip.empty else ip
        if ip.empty:
            ui.vazio("Sem vendas de produtos incentivados (C4)")
        else:
            ui.cartoes({"Carga própria de IPI": (0.0, "igual antes e depois"),
                        "Vantagem competitiva hoje": float(ip["vantagem_hoje"].sum()),
                        "Vantagem competitiva To Be": float(ip["vantagem_to_be"].sum()),
                        "Perda de vantagem": float(ip["perda_vantagem"].sum())})
            al = int(ip["alerta_credito_estimulo"].sum())
            if al:
                st.warning(f"{al} produto(s) com crédito estímulo atual maior que o crédito presumido do art. 450: "
                           "candidatos a perda no IBS.", icon=":material/warning:")
            ui.secao("Resumo por situação do IPI")
            ui.tabela(ip.groupby("classe_ipi", as_index=False)[["receita_anual", "vantagem_hoje", "vantagem_to_be",
                                                                 "perda_vantagem"]].sum())
            ui.secao("Por produto")
            v = ip.copy()
            v.insert(0, "empresa", v["raiz"].map(ctx.nome))
            ui.tabela(v.sort_values("perda_vantagem", ascending=False).drop(columns=["raiz"]),
                      moeda=["receita_anual", "carga_propria_ipi", "vantagem_hoje", "vantagem_to_be", "perda_vantagem"],
                      pct=["cp_cbs_pct", "cp_ibs_pct"], altura=420)
            ui.baixar_csv(v, "ipi_por_produto")
            st.caption("Valores anualizados. TIPI, produção em 2024, TIC e nível de crédito estímulo são editados em "
                       "Parâmetros > Produtos.")

    # ------------------------------------------------------------------ 5. alertas
    with abas[4]:
        al = ui.calcular("alertas", f)
        if al.empty:
            st.success("Nenhum alerta.", icon=":material/check_circle:")
        else:
            al = al.copy()
            al.insert(3, "empresa", al["raiz"].map(lambda x: nomes.get(x, x) if x else "todas"))
            k = al["gravidade"].value_counts()
            ui.cartoes({"Alta": ui.formatar_num(int(k.get("alta", 0))), "Média": ui.formatar_num(int(k.get("média", 0))),
                        "Baixa": ui.formatar_num(int(k.get("baixa", 0)))})
            al = ui.filtros_tabela(al, {"gravidade": "Gravidade", "tipo": "Tipo", "empresa": "Empresa",
                                        "cenario": "Cenário"}, "cz_al")
            ui.tabela(al.drop(columns=["raiz"]), moeda=["valor"], altura=460)
            ui.baixar_csv(al, "alertas")

    # ------------------------------------------------------------------ 6. nao classificados
    with abas[5]:
        ui.secao("Operações não classificadas", "Entram na simulação com a regra conservadora (saída tributada, "
                 "entrada com crédito do fornecedor). Para classificar: revise o tipo ZFM e o regime do CNPJ "
                 "(Parâmetros > Empresas ZFM), a finalidade do CFOP (Parâmetros > CFOPs) ou o produto.")
        nc = con.execute(f"""
            SELECT cenario, motivo, cfop, categoria_cfop, cnpj_part, uf_part, tipo_zfm_part, cod_item, raiz,
                   count(*) AS linhas, sum(valor) AS valor, min(arquivo_id) AS arquivo_exemplo,
                   min(linha_num) AS linha_exemplo
            FROM v_cenarios WHERE cenario IN ('NC_S', 'NC_E') AND {f.sql()}
            GROUP BY ALL ORDER BY valor DESC LIMIT 5000""").df()
        if nc.empty:
            st.success("Todas as operações foram classificadas.", icon=":material/check_circle:")
        else:
            nc.insert(0, "empresa", nc["raiz"].map(ctx.nome))
            ui.tabela(nc.groupby(["cenario", "motivo"], as_index=False)[["linhas", "valor"]].sum(), moeda=["valor"])
            ui.tabela(nc.drop(columns=["raiz"]), moeda=["valor"], altura=420)
            ui.baixar_csv(nc, "nao_classificados")
