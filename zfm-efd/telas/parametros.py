import pandas as pd
import streamlit as st

from zfm import params, simulacao, ui

ui.marca()
con = ui.conexao()
if con is None:
    st.stop()
ui.seletor_empresas(con)
tem_dados = ui.preparar(con)
ui.cabecalho("Cadastros",
             "O que o programa não consegue tirar sozinho das EFDs. Tudo vem pré-preenchido a partir das EFDs ao fim de "
             "cada importação; você só confirma ou corrige. Comece pelas três primeiras abas. As demais são opcionais.",
             "Dados")

# ---------------------------------------------------------------- o que falta
with ui.protegido("verificar pendências"):
    prod = params.carregar("param_produtos")
    ez = params.carregar("param_empresas_zfm")
    grupo = ez[ez["origem"] == "grupo"] if not ez.empty else ez
    inc = prod[prod["incentivado"]] if not prod.empty else prod
    sem_ipi = int(inc["aliq_ipi"].isna().sum()) if not inc.empty else 0
    ui.passos([
        ("1. Empresas ZFM: confirmar o tipo (indústria incentivada, habilitado, não habilitado) e o regime dos "
         "estabelecimentos do grupo", not grupo.empty and bool(grupo["revisado"].all()),
         f"{int((~grupo['revisado']).sum())} estabelecimento(s) a confirmar" if not grupo.empty else "sem dados"),
        ("2. Produtos: conferir os incentivados, o tipo de bem e a alíquota do IPI (lida da EFD)", sem_ipi == 0
         and not inc.empty and bool(inc["revisado"].all()),
         (f"{sem_ipi} incentivado(s) sem alíquota de IPI na EFD; " if sem_ipi else "")
         + (f"{int((~inc['revisado']).sum())} a confirmar" if not inc.empty else "sem produtos")),
        ("3. Alíquotas de CBS e IBS: conferir as premissas de simulação", True, "valores iniciais de pesquisa (fonte na tabela)"),
        ("4. Comprovações (opcional): projetos SUFRAMA e internamento — sem elas, os incentivos ficam como "
         "'potencialmente elegíveis'", not params.carregar("param_projetos_suframa").empty, ""),
    ])
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if c1.button("Reler as EFDs", disabled=not tem_dados or ui.importacao_rodando(), icon=":material/auto_fix_high:",
                 width="stretch", help="Acrescenta o que for novo e relê as alíquotas de IPI; não apaga o que foi editado."):
        from zfm.importacao import TRAVA_BANCO
        with st.spinner("Lendo cadastros das EFDs..."), TRAVA_BANCO:
            n = params.preencher_a_partir_das_efds(con)
        st.success("Linhas novas: " + ", ".join(f"{params.TABELAS[k].titulo}: {v}" for k, v in n.items() if v) or "nenhuma")
    c2.caption("Roda sozinho ao fim de cada importação. Linhas marcadas como 'revisado' não são alteradas.")

SELECOES = {
    "param_empresas_zfm": {"tipo": ["industria_incentivada", "habilitado", "nao_habilitado"],
                           "regime": ["regular", "simples"], "status_habilitacao": ["", "ativa", "suspensa", "cancelada"]},
    "param_produtos": {"tipo_bem": ["final", "capital", "intermediario", "informatica"],
                       "origem": ["", "nacional", "importada"], "excluido_art441": ["", "sim", "nao"],
                       "consumo_produtivo_comprovado": ["", "sim", "nao"]},
    "param_projetos_suframa": {"status": ["aprovado", "suspenso", "cancelado"]},
    "param_internamento": {"status": ["confirmado", "pendente", "negado"]},
    "param_servicos_zfm": {"local_fisico_zfm": ["", "sim", "nao"]},
    "param_regras_legais": {"status": ["vigente", "futura", "revogada", "pendente_regulamentacao"]},
    "param_regras_cenario": {"entrada_creditavel": ["sim", "nao", "regime"], "cp_ibs_entrada": ["", "447", "449", "444"],
                             "sentido": ["entrada", "saida"]},
    "param_conferencia_cenario": {"tributo": ["ICMS", "IPI", "PIS", "COFINS"],
                                  "regra": ["aliquota_em", "cst_em", "valor_zero"]},
    "param_codigos_ajuste_icms": {"classe": ["credito_estimulo", "credito_presumido_entrada", "fundo_FTI", "fundo_UEA",
                                             "fundo_FMPES", "outros_beneficios", "outros", "nao_classificado"]},
    "param_teses": {"tributo": ["ICMS", "IPI", "PIS", "COFINS"],
                    "tipo_efeito": ["valor_fixo_mensal", "credito_adicional", "reduz_base", "reduz_aliquota"],
                    "status": ["ativa", "em discussão", "simulação apenas"]},
}
ESSENCIAIS = {
    "param_empresas_zfm": ["cnpj", "nome", "uf", "suframa", "tipo", "regime", "status_habilitacao", "validade_fim",
                           "revisado", "regra_automatica"],
    "param_produtos": ["raiz_cnpj", "cod_item", "descricao", "ncm", "incentivado", "tipo_bem", "aliq_ipi", "fonte_aliq_ipi",
                       "produzido_zfm_2024", "excluido_art441", "revisado"],
}
ROT = {"raiz_cnpj": "Empresa (raiz CNPJ)", "cnpj": "CNPJ", "nome": "Nome", "uf": "UF", "suframa": "SUFRAMA (EFD)", "tipo": "Tipo ZFM", "regime": "Regime",
       "status_habilitacao": "Habilitação", "validade_fim": "Válida até", "revisado": "Revisado",
       "regra_automatica": "Por que o programa sugeriu", "cod_item": "Código", "descricao": "Descrição", "ncm": "NCM",
       "incentivado": "Incentivado", "tipo_bem": "Tipo de bem", "aliq_ipi": "IPI (%)",
       "fonte_aliq_ipi": "Origem da alíquota de IPI", "produzido_zfm_2024": "Industrializado na ZFM em 2024",
       "excluido_art441": "Excluído (art. 441)"}


def editor(nome: str, mascara: pd.Series | None = None, chave: str = "") -> None:
    """Editor de uma tabela de cadastro. mascara: linhas mostradas (as demais são mantidas ao salvar)."""
    t = params.TABELAS[nome]
    df = params.carregar(nome)
    vis = (df[mascara] if mascara is not None and not df.empty else df).reset_index(drop=True)
    todas = True
    if nome in ESSENCIAIS:
        todas = st.toggle("Mostrar todas as colunas", key=f"todas_{nome}{chave}")
    with st.expander("O que é cada coluna"):
        st.caption(t.ajuda)
    cfg = {c: st.column_config.SelectboxColumn(ROT.get(c, c), options=o) for c, o in SELECOES.get(nome, {}).items()}
    for c, r in ROT.items():
        if c in df.columns and c not in cfg:
            cfg[c] = st.column_config.Column(r, disabled=c in ("fonte_aliq_ipi", "regra_automatica"))
    ordem = None if todas else ESSENCIAIS[nome]
    editado = st.data_editor(vis, key=f"ed_{nome}{chave}", num_rows="dynamic", hide_index=True, width="stretch",
                             column_config=cfg, column_order=ordem, height=min(38 * (len(vis) + 2), 520))
    b1, b2, b3 = st.columns([1, 1, 2])
    if b1.button("Salvar", key=f"salvar_{nome}{chave}", type="primary", icon=":material/save:", width="stretch"):
        novo = pd.DataFrame(editado)
        for c in df.columns:  # colunas ocultas (column_order) voltam com o valor original
            if c not in novo.columns:
                novo[c] = vis[c].reindex(novo.index) if c in vis else None
        if mascara is not None:
            novo = pd.concat([df[~mascara], novo], ignore_index=True)
        params.salvar(nome, novo)
        st.success("Salvo. Os cálculos já usam os novos valores.")
    b2.download_button("Baixar CSV", params.exportar_csv(nome, df), file_name=f"{nome}.csv", mime="text/csv",
                       key=f"baixar_{nome}{chave}", icon=":material/download:", width="stretch")
    with b3.popover("Importar CSV editado no Excel", icon=":material/upload:"):
        arq = st.file_uploader("Arquivo CSV", type=["csv"], key=f"imp_{nome}{chave}")
        if arq is not None and st.button("Confirmar importação", key=f"conf_{nome}{chave}"):
            try:
                novo = params.importar_csv(nome, arq.getvalue())
                params.salvar(nome, novo)
                st.success(f"Importado: {len(novo)} linhas.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


abas = st.tabs(["1. Empresas ZFM", "2. Produtos", "3. Alíquotas CBS/IBS", "4. Comprovações (opcional)", "Avançado",
                "Premissas adotadas"])

with abas[0]:
    with ui.protegido("mostrar Empresas ZFM"):
        ui.secao("Estabelecimentos do grupo e participantes do Amazonas",
                 "O tipo define o cenário de cada operação. O SUFRAMA da EFD é só indício: confirme e marque "
                 "'Revisado'. Validade e situação da habilitação são opcionais.")
        part = st.toggle("Mostrar também os participantes do Amazonas (clientes e fornecedores)", key="ez_part")
        df_ez = params.carregar("param_empresas_zfm")
        editor("param_empresas_zfm", None if part or df_ez.empty else df_ez["origem"] == "grupo")

with abas[1]:
    with ui.protegido("mostrar Produtos"):
        ui.secao("Produtos", "A alíquota do IPI é lida da própria EFD (C170) e vale como a TIPI do produto; a coluna "
                 "'Origem' mostra de onde veio. Saída isenta da ZFM costuma vir sem alíquota: nesse caso, informe a "
                 "TIPI. Confira também 'Incentivado' e 'Tipo de bem' (define o percentual do art. 450).")
        c1, c2 = st.columns([1, 3], vertical_alignment="center")
        so_inc = c1.toggle("Só produtos incentivados", value=True, key="pr_inc")
        if c2.button("Reler as alíquotas de IPI da EFD", icon=":material/refresh:"):
            n = params.preencher_aliquota_ipi(con)
            st.success(f"{n} produto(s) atualizado(s). Produtos marcados como 'Revisado' não são alterados.")
        df_pr = params.carregar("param_produtos")
        editor("param_produtos", df_pr["incentivado"] if so_inc and not df_pr.empty else None)
        if not df_pr.empty:
            with st.expander("Percentuais calculados (art. 450) e enquadramento no art. 454"):
                pc = simulacao.produtos_com_percentuais(df_pr[df_pr["incentivado"]])
                if not pc.empty:
                    v = pc[["cod_item", "descricao", "tipo_bem", "aliq_ipi", "art454", "p_ibs_450", "p_cbs_450",
                            "nivel_credito_estimulo", "alerta_ibs"]].copy()
                    v["p_ibs_450"] *= 100
                    v["p_cbs_450"] *= 100
                    ui.tabela(v.rename(columns={"art454": "Art. 454 (IPI zera)", "p_ibs_450": "CP IBS (% do saldo)",
                                                "p_cbs_450": "CP CBS (% da venda)",
                                                "alerta_ibs": "Crédito estímulo > CP IBS"}),
                              moeda=[], pct=["CP IBS (% do saldo)", "CP CBS (% da venda)"])

with abas[2]:
    with ui.protegido("mostrar as alíquotas"):
        ui.secao("Alíquotas de referência de CBS e IBS por cenário (%)",
                 "São premissas de simulação (não há alíquota definitiva em lei). Digite a alíquota cheia de cada "
                 "cenário e clique em Aplicar: o programa monta 2027–2033 (teste de 0,1% em 2027–2028 e transição do "
                 "IBS até 2033).")
        USAR = "usar tabela de produtos"
        refs = params.aliquotas_referencia()
        refs["ipi_protegido_override"] = refs["ipi_protegido_override"].replace("", USAR).fillna(USAR)
        refs_ed = st.data_editor(
            refs, key="ed_refs", num_rows="dynamic", hide_index=True, width="stretch",
            column_config={
                "cenario": st.column_config.TextColumn("Cenário", required=True),
                "cbs_referencia": st.column_config.NumberColumn("CBS referência (%)", format="%.2f"),
                "ibs_referencia": st.column_config.NumberColumn("IBS referência (%)", format="%.2f"),
                "aplica_cp_450": st.column_config.CheckboxColumn("Aplica CP do art. 450"),
                "ipi_protegido_override": st.column_config.SelectboxColumn(
                    "IPI do concorrente", options=[USAR, "nao"], help="'nao' = nenhum produto mantém IPI (adverso)"),
                "fonte": st.column_config.TextColumn("Fonte / justificativa", width="large"),
            })
        if st.button("Aplicar aos anos 2027–2033", type="primary", key="aplicar_refs"):
            r_ = pd.DataFrame(refs_ed)
            r_["ipi_protegido_override"] = r_["ipi_protegido_override"].replace(USAR, "").fillna("")
            params.aplicar_referencias(r_)
            st.success("Alíquotas recalculadas para 2027–2033.")
            st.rerun()
        with st.expander("Ver ou ajustar ano a ano"):
            editor("param_aliquotas_cenario", chave="_ano")

with abas[3]:
    with ui.protegido("mostrar as comprovações"):
        ui.secao("Comprovações", "Opcionais. Sem elas, as operações incentivadas ficam como 'potencialmente elegíveis' "
                 "(o incentivo é calculado como estimativa e o valor em risco aparece em Cenários ZFM > Pendências).")
        qual = st.radio("Cadastro", ["Projetos SUFRAMA", "Internamento (ingresso na ZFM)", "Serviços prestados na ZFM"],
                        horizontal=True, key="comp_qual")
        editor({"Projetos SUFRAMA": "param_projetos_suframa", "Internamento (ingresso na ZFM)": "param_internamento",
                "Serviços prestados na ZFM": "param_servicos_zfm"}[qual])

with abas[4]:
    with ui.protegido("mostrar os cadastros avançados"):
        ui.secao("Cadastros avançados", "Regras e tabelas de apoio já preenchidas com valores iniciais. Só altere se "
                 "precisar mudar uma regra de cálculo.")
        AV = {"Regras legais (percentuais e vigências da LC 214/2025)": "param_regras_legais",
              "Tratamento de cada cenário": "param_regras_cenario",
              "Conferências do escriturado": "param_conferencia_cenario", "CFOPs": "param_cfops",
              "Códigos de ajuste do ICMS": "param_codigos_ajuste_icms", "Empresas do grupo (nomes)": "param_empresas",
              "Municípios da ZFM": "param_municipios_zfm", "Regime geral (fora da ZFM)": "param_aliquotas_regime_geral",
              "Teses": "param_teses", "Premissas de cálculo": "param_premissas"}
        qual = st.selectbox("Tabela", list(AV), key="av_qual")
        editor(AV[qual], chave="_av")

with abas[5]:
    with ui.protegido("mostrar as premissas"):
        ui.secao("Todas as premissas adotadas", "Valor adotado, onde alterar e fonte. A mesma lista vai para o Excel.")
        resumo = params.resumo_premissas()
        grupos = ["(todos)"] + list(dict.fromkeys(resumo["grupo"]))
        g = st.selectbox("Grupo", grupos, key="grupo_premissas")
        vis = resumo if g == "(todos)" else resumo[resumo.grupo == g]
        st.dataframe(vis.rename(columns={"grupo": "Grupo", "premissa": "Premissa", "valor_adotado": "Valor adotado",
                                         "onde_alterar": "Onde alterar", "fundamento_fonte": "Fundamento / fonte"}),
                     hide_index=True, width="stretch", height=480)
