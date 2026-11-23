import streamlit as st

from zfm import ui
from zfm.secoes import beneficio, carga_as_is, to_be

ctx = ui.contexto(
    "Resultado As Is × To Be",
    "Carga atual lida da apuração (As Is) comparada com a carga simulada de 2027 a 2033 (To Be). Diferença = To Be − "
    "As Is: positivo = a empresa paga mais. O benefício atual da ZFM aparece à parte, só como informação.",
    "Análise", intragrupo=True)

t1, t2, t3 = st.tabs(["Diferença To Be × As Is", "Carga As Is (apuração)", "Benefício ZFM atual (informativo)"])
with t1:
    to_be.render(ctx)
with t2:
    carga_as_is.render(ctx)
with t3:
    beneficio.render(ctx)
