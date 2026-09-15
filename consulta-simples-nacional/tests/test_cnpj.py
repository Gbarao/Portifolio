import pytest

from consulta_simples import cnpj


@pytest.mark.parametrize(
    "valor", ["56.228.356/0001-31", "56228356000131", "11222333000181", "00000000000191"]
)
def test_validos(valor):
    assert cnpj.valido(valor)


@pytest.mark.parametrize(
    "valor", ["56228356000132", "123", "", "1122233300018", "11111111111111", None]
)
def test_invalidos(valor):
    assert not cnpj.valido(valor)


def test_digitos_verificadores_do_exemplo_real():
    # CNPJ usado na tela da Receita: 56.228.356/0001-31
    assert cnpj.digitos_verificadores("562283560001") == "31"


def test_raiz_e_matriz():
    assert cnpj.raiz("56.228.356/0002-12") == "56228356"
    assert cnpj.matriz_da_raiz("56228356") == "56228356000131"


def test_formata():
    assert cnpj.formata("56228356000131") == "56.228.356/0001-31"
    assert cnpj.formata("123") == "123"
