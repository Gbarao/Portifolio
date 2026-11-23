import streamlit as st

from zfm import ui
from zfm.secoes import base_operacoes, entradas, saidas

ctx = ui.contexto(
    "Operações",
    "As operações lidas das EFDs, já normalizadas: saídas (receita por produto, destino e CFOP), entradas (origem, "
    "finalidade e crédito de PIS/COFINS) e a base completa usada na simulação. Devoluções abatem a operação de "
    "origem; cancelados ficam fora.", "Análise", intragrupo=True)

t1, t2, t3 = st.tabs(["Saídas", "Entradas", "Base completa"])
with t1:
    saidas.render(ctx)
with t2:
    entradas.render(ctx)
with t3:
    base_operacoes.render(ctx)
