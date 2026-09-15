"""Cruzamento offline com o arquivo 'Simples' dos Dados Abertos do CNPJ (RFB).

A RFB publica mensalmente a tabela completa de opcao pelo Simples/SIMEI de
todas as empresas do pais. Baixar esse arquivo uma vez e cruzar localmente
resolve milhares de CNPJ em segundos, sem nenhuma requisicao ao site.

Contrapartida: a base tem a data de extracao do mes, nao o "agora" da consulta
online. Para conferencia pontual ou prova documental, use o modo `consultar`.

O layout nao e fixado em codigo: as colunas sao detectadas a partir do
conteudo (raiz de 8 digitos, colunas S/N, datas AAAAMMDD), de modo que uma
mudanca de ordem das colunas nao produz resultado errado em silencio.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path

from . import cnpj as util

_RAIZ = re.compile(r"^\d{8}$")
_DATA = re.compile(r"^\d{8}$")
_SN = {"S", "N", ""}


def _abrir(caminho: Path) -> io.TextIOWrapper:
    """Abre o .zip (primeiro membro) ou o .csv ja extraido, em latin-1."""
    if caminho.suffix.lower() == ".zip":
        arquivo = zipfile.ZipFile(caminho)
        nome = arquivo.namelist()[0]
        return io.TextIOWrapper(arquivo.open(nome), encoding="latin-1", newline="")
    return caminho.open(encoding="latin-1", newline="")


def detecta_colunas(amostra: list[list[str]]) -> dict[str, int]:
    """Descobre os indices de raiz, opcao simples/MEI e datas."""
    if not amostra:
        raise ValueError("arquivo do Simples vazio")
    largura = max(len(l) for l in amostra)

    def todas(indice: int, teste) -> bool:
        valores = [l[indice].strip().strip('"') for l in amostra if len(l) > indice]
        return bool(valores) and all(teste(v) for v in valores)

    idx_raiz = next(
        (i for i in range(largura) if todas(i, lambda v: bool(_RAIZ.match(v)))), None
    )
    if idx_raiz is None:
        raise ValueError("nenhuma coluna com raiz de CNPJ (8 digitos) encontrada")

    sn = [i for i in range(largura) if i != idx_raiz and todas(i, lambda v: v in _SN)]
    if len(sn) < 2:
        raise ValueError(
            f"esperadas 2 colunas S/N (Simples e MEI), encontradas {len(sn)}"
        )
    datas = [
        i
        for i in range(largura)
        if i != idx_raiz and todas(i, lambda v: v in ("", "0", "00000000") or bool(_DATA.match(v)))
        and i not in sn
    ]
    colunas = {"raiz": idx_raiz, "opcao_simples": sn[0], "opcao_mei": sn[1]}
    apos_simples = [i for i in datas if i > sn[0] and i < sn[1]]
    apos_mei = [i for i in datas if i > sn[1]]
    if len(apos_simples) >= 2:
        colunas["data_opcao_simples"], colunas["data_exclusao_simples"] = apos_simples[:2]
    if len(apos_mei) >= 2:
        colunas["data_opcao_mei"], colunas["data_exclusao_mei"] = apos_mei[:2]
    return colunas


def carregar(caminho: Path, raizes: set[str]) -> dict[str, dict]:
    """Le o arquivo em streaming e retorna so as raizes pedidas."""
    encontrados: dict[str, dict] = {}
    with _abrir(caminho) as fluxo:
        leitor = csv.reader(fluxo, delimiter=";", quotechar='"')
        amostra = []
        for linha in leitor:
            amostra.append(linha)
            if len(amostra) >= 50:
                break
        colunas = detecta_colunas(amostra)

        def processa(linha: list[str]) -> None:
            if len(linha) <= max(colunas.values()):
                return
            raiz = linha[colunas["raiz"]].strip().strip('"')
            if raiz in raizes:
                encontrados[raiz] = {
                    nome: linha[i].strip().strip('"') for nome, i in colunas.items()
                }

        for linha in amostra:
            processa(linha)
        for linha in leitor:
            processa(linha)
    return encontrados


def consultar_offline(cnpjs: list[str], caminho_simples: Path) -> list[dict]:
    """Devolve uma linha por CNPJ de entrada, no mesmo formato do modo online."""
    normalizados = list(dict.fromkeys(util.normaliza(c) for c in cnpjs))
    raizes = {util.raiz(c) for c in normalizados}
    base = carregar(Path(caminho_simples), raizes)

    linhas = []
    for c in normalizados:
        dados = base.get(util.raiz(c))
        optante = None if dados is None else dados["opcao_simples"] == "S"
        mei = None if dados is None else dados["opcao_mei"] == "S"
        linhas.append(
            {
                "cnpj": c,
                "cnpj_formatado": util.formata(c),
                "raiz": util.raiz(c),
                "chave_consultada": util.raiz(c),
                "status": "OK" if dados else "NAO_ENCONTRADO",
                "optante_simples": None if optante is None else ("SIM" if optante else "NAO"),
                "situacao_simples": _descricao(dados, "simples") if dados else None,
                "optante_simei": None if mei is None else ("SIM" if mei else "NAO"),
                "situacao_simei": _descricao(dados, "mei") if dados else None,
                "nome_empresarial": None,
                "data_consulta": None,
                "mensagem": None if dados else "raiz ausente do arquivo da RFB",
            }
        )
    return linhas


def _descricao(dados: dict, tipo: str) -> str:
    optante = dados.get(f"opcao_{'simples' if tipo == 'simples' else 'mei'}") == "S"
    rotulo = "Simples Nacional" if tipo == "simples" else "SIMEI"
    texto = f"{'Optante' if optante else 'NAO optante'} pelo {rotulo}"
    entrada = _data(dados.get(f"data_opcao_{tipo}"))
    saida = _data(dados.get(f"data_exclusao_{tipo}"))
    if optante and entrada:
        texto += f" desde {entrada}"
    if not optante and saida:
        texto += f" (excluido em {saida})"
    return texto


def _data(valor: str | None) -> str | None:
    if not valor or not _DATA.match(valor) or valor == "00000000":
        return None
    return f"{valor[6:]}/{valor[4:6]}/{valor[:4]}"
