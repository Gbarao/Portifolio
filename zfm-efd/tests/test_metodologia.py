"""Metodologia: todo cenario das regras esta documentado e o texto acompanha os parametros."""
from __future__ import annotations

from zfm import conciliacoes, metodologia, params


def test_todos_os_cenarios_documentados():
    regras = set(params.carregar("param_regras_cenario")["cenario"])
    doc = set(metodologia.cenarios()["cenario"])
    assert regras <= doc and "C6" in doc


def test_to_be_acompanha_os_parametros():
    antes = metodologia.cenarios().set_index("cenario").loc["C2b", "to_be"]
    assert "70%" in antes and "art. 447" in antes and "7,5%" in antes
    rl = params.carregar("param_regras_legais")
    rl.loc[rl.codigo == "ART446_IBS_ENTRADA", "percentual"] = 50
    params.salvar("param_regras_legais", rl)
    depois = metodologia.cenarios().set_index("cenario").loc["C2b", "to_be"]
    assert "50%" in depois and "70%" not in depois


def test_catalogo_cobre_todas_as_conciliacoes():
    codigos = set(metodologia.cruzamentos()["codigo"])
    assert set(conciliacoes.CHECAGENS) <= codigos and "R5" in codigos
