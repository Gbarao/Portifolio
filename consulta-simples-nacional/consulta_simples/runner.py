"""Orquestracao do lote: deduplicacao, concorrencia, cache e montagem da saida."""
from __future__ import annotations

import asyncio
import random
import sys
import time
from dataclasses import dataclass

from . import cnpj as util
from .io_tabular import CABECALHO_SAIDA
from .parser import Resultado
from .storage import Cache

STATUS_INVALIDO = "CNPJ_INVALIDO"


@dataclass
class Plano:
    """O que sera consultado de fato, depois de validar e deduplicar."""

    chave_por_cnpj: dict[str, str]  # cnpj de entrada -> chave consultada
    invalidos: list[str]
    chaves: list[str]

    @property
    def economia(self) -> int:
        return len(self.chave_por_cnpj) - len(self.chaves)


def montar_plano(
    cnpjs: list[str], *, agrupar_por_raiz: bool = True, validar: bool = True,
    usar_matriz: bool = False,
) -> Plano:
    """Uma consulta por empresa, nao por estabelecimento.

    A propria tela informa que "a opcao pelo Simples Nacional e/ou SIMEI
    abrange todos os estabelecimentos da empresa", entao filiais da mesma
    raiz herdam o resultado da consulta feita para a raiz.
    """
    chave_por_cnpj: dict[str, str] = {}
    invalidos: list[str] = []
    chave_da_raiz: dict[str, str] = {}

    # normaliza antes de deduplicar: '11.222.333/0001-81' e '11222333000181'
    # sao o mesmo CNPJ e devem virar uma unica linha/consulta
    for bruto in dict.fromkeys(util.normaliza(c) for c in cnpjs):
        if validar and not util.valido(bruto):
            invalidos.append(bruto)
            continue
        if not agrupar_por_raiz:
            chave_por_cnpj[bruto] = bruto
            continue
        raiz = util.raiz(bruto)
        if raiz not in chave_da_raiz:
            chave_da_raiz[raiz] = (
                util.matriz_da_raiz(raiz) if usar_matriz else bruto
            )
        chave_por_cnpj[bruto] = chave_da_raiz[raiz]

    return Plano(chave_por_cnpj, invalidos, list(dict.fromkeys(chave_por_cnpj.values())))


async def executar(
    plano: Plano,
    cliente,
    cache: Cache,
    *,
    concorrencia: int = 4,
    intervalo: float = 0.3,
    repetir_erros: bool = True,
    progresso: bool = True,
) -> None:
    """Consulta as chaves pendentes e grava cada resultado no cache."""
    ja_feitas = cache.concluidos(incluir_erros=not repetir_erros)
    pendentes = [c for c in plano.chaves if c not in ja_feitas]
    if progresso:
        print(
            f"chaves: {len(plano.chaves)} | em cache: {len(plano.chaves) - len(pendentes)}"
            f" | a consultar: {len(pendentes)}",
            file=sys.stderr,
        )
    if not pendentes:
        return

    limite = asyncio.Semaphore(concorrencia)
    contador = {"feitas": 0}
    inicio = time.monotonic()

    async def tarefa(chave: str) -> None:
        async with limite:
            if intervalo:
                await asyncio.sleep(random.uniform(0, intervalo))
            resultado: Resultado = await cliente.consultar(chave)
            cache.gravar(resultado, util.raiz(chave))
            contador["feitas"] += 1
            if progresso and contador["feitas"] % 25 == 0:
                decorrido = time.monotonic() - inicio
                taxa = contador["feitas"] / decorrido if decorrido else 0
                print(
                    f"  {contador['feitas']}/{len(pendentes)} "
                    f"({taxa:.1f}/s, restam ~{(len(pendentes)-contador['feitas'])/taxa/60:.1f} min)"
                    if taxa
                    else f"  {contador['feitas']}/{len(pendentes)}",
                    file=sys.stderr,
                )

    await asyncio.gather(*(tarefa(c) for c in pendentes))


def montar_saida(plano: Plano, cache: Cache) -> list[dict]:
    """Uma linha por CNPJ de entrada, com o resultado da sua chave."""
    resultados = cache.por_chave()
    linhas: list[dict] = []

    for entrada, chave in plano.chave_por_cnpj.items():
        dados = resultados.get(chave, {})
        linhas.append(
            {
                "cnpj": entrada,
                "cnpj_formatado": util.formata(entrada),
                "raiz": util.raiz(entrada),
                "chave_consultada": chave,
                "status": dados.get("status", "NAO_CONSULTADO"),
                "optante_simples": _texto_bool(dados.get("optante_simples")),
                "situacao_simples": dados.get("situacao_simples"),
                "optante_simei": _texto_bool(dados.get("optante_simei")),
                "situacao_simei": dados.get("situacao_simei"),
                "nome_empresarial": dados.get("nome_empresarial"),
                "data_consulta": dados.get("data_consulta"),
                "mensagem": dados.get("mensagem"),
            }
        )

    for invalido in plano.invalidos:
        linha = {c: None for c in CABECALHO_SAIDA}
        linha.update(
            {
                "cnpj": invalido,
                "cnpj_formatado": util.formata(invalido),
                "raiz": util.raiz(invalido),
                "status": STATUS_INVALIDO,
                "mensagem": "digitos verificadores ou tamanho invalidos",
            }
        )
        linhas.append(linha)

    return linhas


def _texto_bool(valor) -> str | None:
    if valor is None:
        return None
    return "SIM" if int(valor) else "NAO"
