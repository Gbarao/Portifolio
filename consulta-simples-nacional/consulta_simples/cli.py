"""Interface de linha de comando."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .io_tabular import escrever, ler_cnpjs
from .runner import executar, montar_plano, montar_saida
from .scraper import URL_PADRAO, ConsultaHTTP
from .storage import Cache


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="consulta-simples",
        description="Consulta em lote de optantes do Simples Nacional / SIMEI.",
    )
    sub = p.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("consultar", help="consulta a base no site da Receita")
    c.add_argument("entrada", help="arquivo .csv, .xlsx ou .txt com os CNPJ")
    c.add_argument("-s", "--saida", default="resultado.csv", help="csv ou xlsx")
    c.add_argument("--coluna", help="nome da coluna de CNPJ (padrao: detecta)")
    c.add_argument("--db", default="cache/consultas.sqlite", help="cache SQLite")
    c.add_argument("--url", default=URL_PADRAO)
    c.add_argument("-c", "--concorrencia", type=int, default=4)
    c.add_argument("--intervalo", type=float, default=0.3, help="jitter em segundos")
    c.add_argument("--timeout", type=float, default=30.0)
    c.add_argument("--tentativas", type=int, default=3)
    c.add_argument("--campo-cnpj", help="name do input, se a deteccao falhar")
    c.add_argument(
        "--sem-agrupar",
        action="store_true",
        help="consulta cada estabelecimento (padrao: uma consulta por raiz)",
    )
    c.add_argument(
        "--matriz",
        action="store_true",
        help="consulta o CNPJ da matriz calculado a partir da raiz",
    )
    c.add_argument("--sem-validacao", action="store_true", help="nao checa os DV")
    c.add_argument(
        "--modo", choices=("http", "browser"), default="http",
        help="browser usa Playwright (lento); use so se o http falhar",
    )
    c.add_argument("--limite", type=int, help="processa apenas os N primeiros")

    d = sub.add_parser(
        "diagnostico", help="mostra o formulario detectado e testa um CNPJ"
    )
    d.add_argument("--url", default=URL_PADRAO)
    d.add_argument("--cnpj", help="se informado, executa uma consulta real")
    d.add_argument("--timeout", type=float, default=30.0)

    o = sub.add_parser(
        "offline", help="cruza a base com o arquivo Simples dos Dados Abertos da RFB"
    )
    o.add_argument("entrada", help="arquivo .csv, .xlsx ou .txt com os CNPJ")
    o.add_argument("simples", help="Simples.zip / .csv baixado do site da RFB")
    o.add_argument("-s", "--saida", default="resultado_offline.csv")
    o.add_argument("--coluna")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.comando == "consultar":
        return asyncio.run(_consultar(args))
    if args.comando == "diagnostico":
        return asyncio.run(_diagnostico(args))
    if args.comando == "offline":
        return _offline(args)
    return 1


async def _consultar(args) -> int:
    cnpjs = ler_cnpjs(args.entrada, args.coluna)
    if args.limite:
        cnpjs = cnpjs[: args.limite]
    if not cnpjs:
        print("nenhum CNPJ lido da entrada", file=sys.stderr)
        return 1

    plano = montar_plano(
        cnpjs,
        agrupar_por_raiz=not args.sem_agrupar,
        validar=not args.sem_validacao,
        usar_matriz=args.matriz,
    )
    print(
        f"entrada: {len(cnpjs)} | unicos: {len(plano.chave_por_cnpj)} | "
        f"consultas necessarias: {len(plano.chaves)} | invalidos: {len(plano.invalidos)}",
        file=sys.stderr,
    )

    cache = Cache(args.db)
    try:
        if args.modo == "browser":
            from .browser import ConsultaBrowser

            async with ConsultaBrowser(args.url, timeout=args.timeout) as cliente:
                await executar(
                    plano, cliente, cache,
                    concorrencia=min(args.concorrencia, 4), intervalo=args.intervalo,
                )
        else:
            async with ConsultaHTTP(
                args.url,
                timeout=args.timeout,
                tentativas=args.tentativas,
                campo_cnpj=args.campo_cnpj,
            ) as cliente:
                await executar(
                    plano, cliente, cache,
                    concorrencia=args.concorrencia, intervalo=args.intervalo,
                )
        linhas = montar_saida(plano, cache)
        destino = escrever(args.saida, linhas)
    finally:
        contagem = cache.contagem_por_status()
        cache.fechar()

    print(f"saida: {destino}", file=sys.stderr)
    print(f"status das consultas: {contagem}", file=sys.stderr)
    return 0 if contagem.get("OK") else 2


async def _diagnostico(args) -> int:
    async with ConsultaHTTP(args.url, timeout=args.timeout) as cliente:
        try:
            form = await cliente._formulario()
        except Exception as erro:
            print(f"falha ao ler o formulario: {type(erro).__name__}: {erro}")
            return 1
        print(f"action......: {form.url_acao}")
        print(f"campo CNPJ..: {form.campo_cnpj}")
        print(f"campos......: {len(form.campos)}")
        for nome, valor in form.campos.items():
            print(f"  - {nome} = {str(valor)[:60]}")
        if args.cnpj:
            resultado = await cliente.consultar(args.cnpj)
            print("\nresultado da consulta de teste:")
            for chave, valor in resultado.como_dict().items():
                print(f"  {chave}: {valor}")
    return 0


def _offline(args) -> int:
    from .dados_abertos import consultar_offline

    cnpjs = ler_cnpjs(args.entrada, args.coluna)
    linhas = consultar_offline(cnpjs, Path(args.simples))
    destino = escrever(args.saida, linhas)
    print(f"saida: {destino}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
