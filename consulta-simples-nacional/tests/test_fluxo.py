"""Fluxo completo contra um servidor local que imita o WebForms da Receita."""
import asyncio
from pathlib import Path

from consulta_simples.io_tabular import escrever
from consulta_simples.runner import executar, montar_plano, montar_saida
from consulta_simples.scraper import ConsultaHTTP, descobre_formulario
from consulta_simples.storage import Cache

from .servidor_falso import FORMULARIO, ServidorFalso


def test_descoberta_de_formulario():
    form = descobre_formulario(FORMULARIO, "https://exemplo/aplicacoes.aspx?id=21")
    assert form.campo_cnpj == "ctl00$ContentPlaceHolder1$txtCNPJ"
    assert form.campos["__VIEWSTATE"] == "/wEPDwUKMTIzNDU2Nzg5"
    assert "ctl00$ContentPlaceHolder1$btConsultar" in form.campos
    assert form.url_acao.endswith("/aplicacoes.aspx?id=21")


def test_lote_ponta_a_ponta(tmp_path: Path):
    entrada = [
        "56228356000131",
        "56228356000212",  # filial da mesma raiz: nao gera nova consulta
        "11222333000181",
        "123",  # invalido
    ]
    plano = montar_plano(entrada)
    assert plano.chaves == ["56228356000131", "11222333000181"]
    assert plano.invalidos == ["123"]

    cache = Cache(tmp_path / "cache.sqlite")
    with ServidorFalso() as servidor:

        async def roda():
            async with ConsultaHTTP(servidor.url) as cliente:
                await executar(plano, cliente, cache, concorrencia=2, intervalo=0,
                               progresso=False)

        asyncio.run(roda())

    linhas = {l["cnpj"]: l for l in montar_saida(plano, cache)}
    assert linhas["11222333000181"]["optante_simples"] == "SIM"
    assert linhas["56228356000131"]["optante_simples"] == "NAO"
    # a filial herda o resultado da raiz
    assert linhas["56228356000212"]["optante_simples"] == "NAO"
    assert linhas["56228356000212"]["chave_consultada"] == "56228356000131"
    assert linhas["123"]["status"] == "CNPJ_INVALIDO"

    saida = escrever(tmp_path / "res.csv", list(linhas.values()))
    assert "optante_simples" in saida.read_text(encoding="utf-8-sig")
    cache.fechar()


def test_cache_evita_reconsulta(tmp_path: Path):
    plano = montar_plano(["11222333000181"])
    cache = Cache(tmp_path / "c.sqlite")
    with ServidorFalso() as servidor:

        async def roda():
            async with ConsultaHTTP(servidor.url) as cliente:
                await executar(plano, cliente, cache, intervalo=0, progresso=False)
                assert cache.concluidos() == {"11222333000181"}
                # segunda rodada: nada pendente
                await executar(plano, cliente, cache, intervalo=0, progresso=False)

        asyncio.run(roda())
    assert cache.contagem_por_status() == {"OK": 1}
    cache.fechar()


def test_erro_de_rede_vira_status_recuperavel(tmp_path: Path):
    plano = montar_plano(["11222333000181"])
    cache = Cache(tmp_path / "c.sqlite")

    async def roda():
        async with ConsultaHTTP(
            "http://127.0.0.1:9/aplicacoes.aspx", tentativas=1, timeout=2
        ) as cliente:
            await executar(plano, cliente, cache, intervalo=0, progresso=False)

    asyncio.run(roda())
    assert set(cache.contagem_por_status()) == {"ERRO_REDE"}
    # erros nao entram no conjunto de concluidos: a proxima execucao tenta de novo
    assert cache.concluidos() == set()
    cache.fechar()
