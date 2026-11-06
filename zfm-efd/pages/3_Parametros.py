import pandas as pd
import streamlit as st

from zfm import params, simulacao, ui

ui.cabecalho(
    "3. Parâmetros",
    "Para que serve: guardar as premissas dos cálculos (alíquotas, produtos incentivados, "
    "classificação dos códigos de ajuste etc.). O que fazer: clique em 'Preencher a partir das "
    "EFDs', revise cada aba e clique em 'Salvar'. Os valores iniciais são hipóteses para você validar. "
    "Também é possível baixar a tabela, editar no Excel e importar de volta.",
)
con = ui.conexao()
ui.seletor_empresas(con)
if con is None:
    st.stop()
tem_dados = ui.preparar(con)

c1, c2 = st.columns([1, 3])
if c1.button("Preencher a partir das EFDs", type="primary", disabled=not tem_dados):
    with ui.protegido("preencher os parâmetros a partir das EFDs"):
        n = params.preencher_a_partir_das_efds(con)
        ui.preparar(con)
        st.success("Linhas novas: " + ", ".join(f"{params.TABELAS[k].titulo}: {v}" for k, v in n.items())
                   + ". Linhas que você já editou não foram alteradas.")
c2.caption("Acrescenta empresas, produtos (0200), CFOPs e códigos de ajuste (E111/E116) "
           "encontrados nas EFDs, sem apagar o que já foi editado.")

# ---------------- Pendencias
with ui.protegido("verificar pendências"):
    prod = params.carregar("param_produtos")
    cod = params.carregar("param_codigos_ajuste_icms")
    pend = []
    if not prod.empty:
        sem_tipi = prod[prod["incentivado"] & prod["aliq_tipi_2023"].isna()]
        if len(sem_tipi):
            pend.append(f"{len(sem_tipi)} produto(s) incentivado(s) sem alíquota TIPI: o benefício de IPI "
                        "deles fica zero e o crédito presumido de CBS usa 2%.")
        pc = simulacao.produtos_com_percentuais(prod)
        risco = pc[pc["incentivado"] & pc["alerta_ibs"]]
        if len(risco):
            pend.append(f"{len(risco)} produto(s) com nível de crédito estímulo maior que o percentual do "
                        "art. 450 (candidatos a perda no IBS): veja a aba Produtos.")
    if not cod.empty and (~cod["revisado"]).any():
        pend.append(f"{int((~cod['revisado']).sum())} código(s) de ajuste do ICMS classificados "
                    "automaticamente e ainda não revisados.")
    for p in pend:
        st.warning(p)

# ---------------- Abas
ordem = ["param_empresas", "param_produtos", "param_aliquotas_cenario", "param_codigos_ajuste_icms",
         "param_regras_entradas", "param_aliquotas_regime_geral", "param_cfops", "param_municipios_zfm",
         "param_teses", "param_premissas"]
abas = st.tabs(["Premissas e alíquotas"] + [params.TABELAS[n].titulo for n in ordem])

# ---------------- Aba 0: alíquotas de referência + resumo de todas as premissas
with abas[0]:
    with ui.protegido("mostrar as premissas"):
        st.markdown("#### 1. Alíquotas de referência de CBS e IBS por cenário (%)")
        st.caption("Digite a alíquota de referência (cheia) de cada cenário e clique em 'Aplicar aos "
                   "anos'. O programa recalcula 2027–2033: em 2027–2028 CBS = referência − "
                   "'reducao_cbs_2027_2028' e IBS = 0 (teste neutro); em 2029–2032 IBS = referência × "
                   "(1 − fator do ICMS); em 2033, referência cheia. Ajustes ano a ano: aba 'Alíquotas "
                   "por cenário'. Para criar um cenário, acrescente uma linha.")
        USAR = "usar tabela de produtos"
        refs = params.aliquotas_referencia()
        refs["ipi_protegido_override"] = refs["ipi_protegido_override"].replace("", USAR).fillna(USAR)
        refs_ed = st.data_editor(
            refs, key="ed_refs", num_rows="dynamic", hide_index=True, use_container_width=True,
            column_config={
                "cenario": st.column_config.TextColumn("Cenário", required=True),
                "cbs_referencia": st.column_config.NumberColumn("CBS referência (%)", format="%.2f"),
                "ibs_referencia": st.column_config.NumberColumn("IBS referência (%)", format="%.2f"),
                "aplica_cp_450": st.column_config.CheckboxColumn("Aplica CP do art. 450"),
                "ipi_protegido_override": st.column_config.SelectboxColumn(
                    "IPI protegido", options=[USAR, "nao"],
                    help="'nao' = nenhum produto com IPI protegido (cenário adverso)"),
                "fonte": st.column_config.TextColumn("Fonte / justificativa", width="large"),
            })
        if st.button("Aplicar aos anos 2027–2033", type="primary", key="aplicar_refs"):
            r_ = pd.DataFrame(refs_ed)
            r_["ipi_protegido_override"] = r_["ipi_protegido_override"].replace(USAR, "").fillna("")
            params.aplicar_referencias(r_)
            ui.preparar(con)
            st.success("Alíquotas recalculadas para 2027–2033. A simulação já usa os novos valores.")
            st.rerun()
        st.markdown("#### 2. Todas as premissas adotadas")
        st.caption("Lista gerada a partir das tabelas de parâmetros; mostra o valor adotado, onde "
                   "alterar e a fonte. A mesma lista vai para o Excel (aba 'Premissas adotadas').")
        resumo = params.resumo_premissas()
        grupos = ["(todos)"] + list(dict.fromkeys(resumo["grupo"]))
        g = st.selectbox("Grupo", grupos, key="grupo_premissas")
        vis = resumo if g == "(todos)" else resumo[resumo.grupo == g]
        st.dataframe(vis.rename(columns={"grupo": "Grupo", "premissa": "Premissa",
                                         "valor_adotado": "Valor adotado", "onde_alterar": "Onde alterar",
                                         "fundamento_fonte": "Fundamento / fonte"}),
                     hide_index=True, use_container_width=True, height=520)

for aba, nome in zip(abas[1:], ordem):
    t = params.TABELAS[nome]
    with aba:
        st.caption(t.ajuda)
        with ui.protegido(f"mostrar {t.titulo}"):
            df = params.carregar(nome)
            cfg = {}
            if nome == "param_produtos":
                cfg["tipo_bem"] = st.column_config.SelectboxColumn(
                    options=["final", "capital", "intermediario", "informatica"])
            if nome == "param_codigos_ajuste_icms":
                cfg["classe"] = st.column_config.SelectboxColumn(options=[
                    "credito_estimulo", "credito_presumido_entrada", "fundo_FTI", "fundo_UEA",
                    "fundo_FMPES", "outros_beneficios", "outros"])
            if nome == "param_regras_entradas":
                for c in ("tratamento_cbs", "tratamento_ibs"):
                    cfg[c] = st.column_config.SelectboxColumn(options=["tributada", "aliquota_zero", "suspensa"])
            if nome == "param_teses":
                cfg["tributo"] = st.column_config.SelectboxColumn(options=["ICMS", "IPI", "PIS", "COFINS"])
                cfg["tipo_efeito"] = st.column_config.SelectboxColumn(
                    options=["valor_fixo_mensal", "credito_adicional", "reduz_base", "reduz_aliquota"])
                cfg["status"] = st.column_config.SelectboxColumn(
                    options=["ativa", "em discussão", "simulação apenas"])
            editado = st.data_editor(df, key=f"ed_{nome}", num_rows="dynamic", hide_index=True,
                                     use_container_width=True, column_config=cfg)
            b1, b2, b3 = st.columns(3)
            if b1.button("Salvar", key=f"salvar_{nome}", type="primary"):
                params.salvar(nome, pd.DataFrame(editado))
                ui.preparar(con)
                st.success("Salvo. Os cálculos já usam os novos valores.")
            b2.download_button("Baixar CSV (abre no Excel)", params.exportar_csv(nome, pd.DataFrame(editado)),
                               file_name=f"{nome}.csv", mime="text/csv", key=f"baixar_{nome}")
            arq = b3.file_uploader("Importar CSV", type=["csv"], key=f"imp_{nome}",
                                   label_visibility="collapsed")
            if arq is not None and st.button("Confirmar importação", key=f"conf_{nome}"):
                try:
                    novo = params.importar_csv(nome, arq.getvalue())
                    params.salvar(nome, novo)
                    ui.preparar(con)
                    st.success(f"Importado: {len(novo)} linhas.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if nome == "param_produtos" and not df.empty:
                st.markdown("**Percentuais calculados (art. 450)** – não editáveis")
                pc = simulacao.produtos_com_percentuais(df)
                vis = pc[["raiz_cnpj", "cod_item", "descricao", "tipo_bem", "aliq_tipi_2023",
                          "nivel_credito_estimulo", "p_ibs_450", "p_cbs_450", "alerta_ibs"]].rename(columns={
                    "p_ibs_450": "CP IBS (fração do saldo)", "p_cbs_450": "CP CBS (fração da venda)",
                    "alerta_ibs": "Crédito estímulo > CP IBS"})
                st.dataframe(vis, hide_index=True, use_container_width=True)
