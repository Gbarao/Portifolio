from pathlib import Path

from consulta_simples.parser import parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_nao_optante():
    r = parse((FIXTURES / "resultado_nao_optante.html").read_text(), "56228356000131")
    assert r.status == "OK"
    assert r.optante_simples is False
    assert r.optante_simei is False
    assert r.nome_empresarial == "CRBS S/A"
    assert r.cnpj_retornado == "56.228.356/0001-31"
    assert r.data_consulta == "15/09/2026 09:04:38"


def test_optante():
    r = parse((FIXTURES / "resultado_optante.html").read_text(), "11222333000181")
    assert r.optante_simples is True
    assert "desde 01/01/2020" in r.situacao_simples
    assert r.optante_simei is False


def test_pagina_inesperada_vira_sem_resultado():
    r = parse("<html><body>Servico indisponivel</body></html>", "11222333000181")
    assert r.status == "SEM_RESULTADO"
    assert "indispon" in r.mensagem
