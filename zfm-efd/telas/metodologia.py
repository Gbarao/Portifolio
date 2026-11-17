import streamlit as st

from zfm import conciliacoes, metodologia, ui

ctx = ui.contexto(
    "Metodologia e cruzamentos",
    "Como cada cenário é identificado, quais registros e campos das EFDs são capturados, como o As Is e o To Be "
    "são calculados (com os parâmetros em uso) e quais cruzamentos validam cada informação.", "Análise")
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("montar a metodologia"):
    cen = metodologia.cenarios()
    mat = ui.calcular("matriz", f)
    tot = mat.groupby("cenario")[["valor", "documentos", "linhas"]].sum() if not mat.empty else None
    abas = st.tabs(["Cenários", "Registros capturados", "Cruzamentos", "De onde vem cada dado"])

    with abas[0]:
        ui.secao("Visão geral", "Cada operação cai em um cenário. Escolha um cenário abaixo para ver como é "
                 "identificado, o que é capturado e como é calculado. O texto do To Be é montado a partir de "
                 "Parâmetros > Regras por cenário e Premissas: muda quando os parâmetros mudam.")
        v = cen[["cenario", "descricao", "sentido", "base_legal"]].copy()
        if tot is not None:
            v["valor"] = v["cenario"].map(tot["valor"]).fillna(0.0)
            v["documentos"] = v["cenario"].map(tot["documentos"]).fillna(0).astype(int)
        st.dataframe(v, hide_index=True, width="stretch", height=36 * (len(v) + 1) + 4, column_config={
            "cenario": "Cenário", "descricao": "Descrição", "sentido": "Sentido", "base_legal": "Base legal",
            "valor": st.column_config.NumberColumn("Valor no período (R$)", format="localized"),
            "documentos": st.column_config.NumberColumn("Documentos", format="localized")})

        ui.secao("Detalhe do cenário")
        escolha = st.selectbox("Cenário", list(cen["cenario"]),
                               format_func=lambda c: f"{c} – {cen.set_index('cenario').loc[c, 'descricao']}",
                               key="met_cen")
        r = cen.set_index("cenario").loc[escolha]
        if tot is not None and escolha in tot.index:
            ui.cartoes({"Valor no período": float(tot.loc[escolha, "valor"]),
                        "Documentos": ui.formatar_num(int(tot.loc[escolha, "documentos"])),
                        "Linhas da base": ui.formatar_num(int(tot.loc[escolha, "linhas"]))})
        blocos = [("Como é identificado", r["como_identifica"]),
                  ("Registros e campos capturados", r["dados_lidos"]),
                  ("As Is (o que é lido da escrituração)", r["as_is"]),
                  ("To Be (simulação, com os parâmetros atuais)", r["to_be"]),
                  ("ICMS e IPI no To Be", r["ICMS e IPI no To Be"]),
                  ("Conferências do escriturado (alertas)", r["conferencias_as_is"]),
                  ("Cruzamentos que validam os dados", r["cruzamentos"]),
                  ("Base legal", r["base_legal"]), ("Observação", r["observacao"])]
        for titulo, texto in blocos:
            if texto:
                with st.container(border=True):
                    st.markdown(f"**{titulo}**")
                    st.write(texto)

    with abas[1]:
        ui.secao("Registros capturados por cenário", "As linhas da base de operações que caíram no cenário, com o "
                 "registro de origem, o arquivo e a linha do .txt, e os campos usados na classificação.")
        escolha2 = st.selectbox("Cenário", list(cen["cenario"][cen["cenario"] != "C5"]), key="met_cen2",
                                format_func=lambda c: f"{c} – {cen.set_index('cenario').loc[c, 'descricao']}")
        cond = f"cenario = '{escolha2}' AND {f.sql()}"
        ui.secao("Por CFOP e origem/destino")
        ui.tabela(con.execute(f"""
            SELECT cfop, categoria_origem AS finalidade_cfop, coalesce(tipo_operacao, origem) AS destino_origem,
                   uf_part AS uf_participante, tipo_zfm_part AS tipo_zfm_participante, count(*) AS linhas,
                   sum(valor) AS valor
            FROM v_cenarios WHERE {cond} GROUP BY ALL ORDER BY valor DESC""").df(), moeda=["valor"])
        n = con.execute(f"SELECT count(*) FROM v_cenarios WHERE {cond}").fetchall()[0][0]
        reg = con.execute(f"""
            SELECT c.reg_origem AS registro, a.nome_arquivo AS arquivo, c.linha_num AS linha, c.cnpj_estab, c.mes,
                   c.natureza, c.cfop, c.categoria_origem AS finalidade_cfop, c.cod_item, c.ncm_produto AS ncm,
                   c.incentivado, c.tipo_bem, c.cnpj_part, c.uf_part, c.tipo_zfm_part, c.contribuinte,
                   c.tipo_estab, c.regime_estab, coalesce(c.tipo_operacao, c.origem) AS destino_origem,
                   c.rateado, c.valor, c.icms, c.ipi, c.pis, c.cofins, c.motivo
            FROM v_cenarios c JOIN arquivos a USING (arquivo_id)
            WHERE c.cenario = '{escolha2}' AND {f.sql('c.raiz', 'c.cnpj_estab', 'c.mes')}
            ORDER BY abs(c.valor) DESC LIMIT 2000""").df()
        st.caption(f"Maiores {ui.formatar_num(len(reg))} de {ui.formatar_num(n)} linhas (por valor).")
        ui.tabela(reg, moeda=["valor", "icms", "ipi", "pis", "cofins"], altura=420)
        ui.baixar_csv(reg, f"registros_{escolha2}")

    with abas[2]:
        ui.secao("Cruzamentos entre registros e entre as duas EFDs", "Situação atual no período e empresas "
                 "selecionados. O detalhe de cada divergência está em Dados > Qualidade e reconciliação.")
        cz = metodologia.cruzamentos()
        sit = {}
        for cod in conciliacoes.CHECAGENS:
            d = ui.calcular("conciliacao", f, q=cod)
            sit[cod] = "OK" if d.empty else f"{len(d)} divergência(s)"
        r5 = ui.calcular("r5", f)
        sit["R5"] = "OK" if r5.empty or r5["fecha"].all() else f"{int((~r5['fecha']).sum())} não fecham"
        cz.insert(2, "situacao", cz["codigo"].map(sit).fillna("ver tela"))
        st.dataframe(cz, hide_index=True, width="stretch", height=560, column_config={
            "codigo": "Código", "cruzamento": "Cruzamento", "situacao": "Situação",
            "lado_a": st.column_config.TextColumn("Lado A", width="medium"),
            "lado_b": st.column_config.TextColumn("Lado B", width="medium"),
            "ligacao": st.column_config.TextColumn("Ligação (chave)", width="medium"),
            "tolerancia": "Tolerância",
            "o_que_indica": st.column_config.TextColumn("O que indica / impacto", width="large")})
        with st.expander("Como as duas EFDs são ligadas (mecânica do sped_analytics_app)", expanded=True):
            st.markdown(
                "1. **Empresa e filial:** empresa = raiz do CNPJ. Filial = CNPJ do 0000 na EFD ICMS/IPI e do "
                "0140/C010 na EFD Contribuições.\n"
                "2. **Fornecedor/cliente:** CNPJ/CPF do 0150 de cada arquivo (o COD_PART é interno e não é comparado).\n"
                "3. **Documento, vínculo 1:1:** 1º pela chave da NF-e, em qualquer competência; 2º sem chave num dos "
                "lados, por filial + competência + fornecedor + modelo + série + número. Um documento de uma EFD nunca "
                "alimenta dois da outra.\n"
                "4. **Itens das entradas:** C170 do SPED Fiscal; se a nota não tem C170 (Exceção 2), os itens do C170 da "
                "EFD Contribuições do documento vinculado, com valor, ICMS e IPI rateados ao C190 do mesmo CFOP.\n"
                "5. **PIS/COFINS das entradas** vem sempre da EFD Contribuições, por nível:")
            from zfm.vinculo import NIVEIS
            st.dataframe([{"Nível": k, "Como casa": v} for k, v in NIVEIS.items()], hide_index=True, width="stretch")
            st.markdown(
                "6. **Garantias:** nada some (Q18: todo PIS/COFINS da EFD termina em exatamente uma linha da base), "
                "nada duplica (cada item da EFD é usado no máximo uma vez), nada vai para o item errado (a posição "
                "sozinha não basta para casar).\n"
                "7. **Saídas:** produto e receita da EFD Contribuições; destino do C190 + 0150 da EFD ICMS/IPI, ligados por "
                "estabelecimento, mês e CFOP (Q15 confere os CFOPs do documento vinculado).\n"
                "8. **Não lido nesta versão:** C500/D100/D500 (energia, frete, telecom) e F120/F130 (ativo).")
    with abas[3]:
        ui.secao("De onde vem cada dado usado nos cálculos")
        st.dataframe(metodologia.fontes(), hide_index=True, width="stretch", column_config={
            "dado": "Dado", "efd": "EFD", "registros": "Registros",
            "campos": st.column_config.TextColumn("Campos", width="large"),
            "usado_em": st.column_config.TextColumn("Usado em", width="large")})
