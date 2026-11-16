import streamlit as st

from zfm import ui

ctx = ui.contexto(
    "4. Base de operações",
    "Para que serve: ver a base única de operações usada na simulação, com uma linha por item "
    "(ou por consolidação, quando não há item). Saídas por produto vêm da EFD Contribuições; "
    "entradas, da EFD ICMS/IPI. Devoluções aparecem com valor negativo e abatem a operação de "
    "origem. O que fazer: use os filtros para conferir operações; baixe o CSV se precisar.",
)
con, f, nomes = ctx.con, ctx.filtro, ctx.nomes

with ui.protegido("montar a base de operações"):
    b = con.execute(f"""
        SELECT raiz, cnpj_estab, mes, sentido, natureza, cfop, categoria_origem, cod_item,
               ncm_produto AS ncm, incentivado, tipo_bem, tipo_operacao, origem, uf_part AS uf,
               eh_grupo, valor, icms, ipi, pis, cofins, cst_icms, cst_ipi, cst_pis, aliq_pis,
               cst_cofins, aliq_cofins, rateado, reg_origem, chv_nfe, arquivo_id, linha_num
        FROM v_base_operacoes WHERE {f.sql()}""").df()
    if b.empty:
        st.warning("Base vazia para o filtro escolhido.")
        st.stop()
    b["empresa"] = b["raiz"].map(lambda r: nomes.get(r, r))
    st.subheader("Filtros")
    b = ui.filtros_tabela(b, {
        "sentido": "Sentido", "natureza": "Natureza", "cfop": "CFOP", "tipo_operacao": "Destino (saídas)",
        "origem": "Origem (entradas)", "uf": "UF do participante", "cod_item": "Produto", "ncm": "NCM",
        "incentivado": "Incentivado", "eh_grupo": "Empresa do grupo", "rateado": "Destino rateado",
        "reg_origem": "Registro de origem"}, "base")

    sai = b[b.sentido == "saida"]
    ent = b[b.sentido == "entrada"]
    ui.cartoes({"Saídas (líquidas de devoluções)": sai["valor"].sum(),
                "Devoluções de venda": sai.loc[sai.natureza == "devolucao_venda", "valor"].sum(),
                "Entradas (líquidas)": ent["valor"].sum(),
                "Transferências (saídas)": sai.loc[sai.natureza == "transferencia", "valor"].sum()}, por_linha=2)

    st.subheader("Resumo por sentido, natureza e empresa")
    ui.tabela(ui.por_empresa(b, ["sentido", "natureza"], "valor", nomes))
    st.subheader("Transferências entre estabelecimentos (tratadas à parte)")
    st.caption("Por padrão ficam fora da base de CBS/IBS (Parâmetros > Premissas > "
               "transferencias_na_base_cbs_ibs). Conferir o tratamento na LC 214/2025.")
    ui.tabela(ui.por_empresa(b[b.natureza == "transferencia"], ["sentido", "cnpj_estab", "cfop"], "valor", nomes))
    st.subheader("Registros (até 5.000 linhas na tela; o CSV traz todos)")
    ui.tabela(b.head(5000), moeda=["valor", "icms", "ipi", "pis", "cofins"], altura=420)
    ui.baixar_csv(b, "base_de_operacoes")
