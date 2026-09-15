"""Extracao do resultado da tela 'Consulta Optantes'."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict

from bs4 import BeautifulSoup

STATUS_OK = "OK"
STATUS_SEM_RESULTADO = "SEM_RESULTADO"


@dataclass
class Resultado:
    cnpj_consultado: str
    status: str = STATUS_OK
    cnpj_retornado: str | None = None
    nome_empresarial: str | None = None
    situacao_simples: str | None = None
    situacao_simei: str | None = None
    optante_simples: bool | None = None
    optante_simei: bool | None = None
    data_consulta: str | None = None
    mensagem: str | None = None

    def como_dict(self) -> dict:
        return asdict(self)


def _sem_acento(texto: str) -> str:
    """Minusculas e sem acento, preservando o comprimento e os indices.

    A preservacao de indices permite casar o padrao no texto normalizado e
    recortar o valor no texto original, com acentos e caixa intactos.
    """
    saida = []
    for c in texto:
        base = "".join(
            ch
            for ch in unicodedata.normalize("NFD", c)
            if unicodedata.category(ch) != "Mn"
        )
        saida.append(base.lower() if len(base) == 1 else c.lower())
    return "".join(saida)


def texto_visivel(html: str) -> str:
    """HTML -> texto plano, uma linha por bloco, sem espacos duplicados."""
    sopa = BeautifulSoup(html, "lxml")
    for tag in sopa(["script", "style"]):
        tag.decompose()
    linhas = [
        re.sub(r"\s+", " ", linha).strip() for linha in sopa.get_text("\n").splitlines()
    ]
    return "\n".join(l for l in linhas if l)


def _campo(texto: str, rotulo: str) -> str | None:
    """Captura o valor de 'Rotulo: valor'.

    O valor pode estar na mesma linha ou na linha seguinte, porque no HTML da
    Receita o rotulo e o valor sao nos irmaos (<b>valor</b>).
    """
    plano = _sem_acento(texto)
    padrao = re.compile(rf"(?<![a-z]){re.escape(_sem_acento(rotulo))}\s*:[ \t]*")
    for m in padrao.finditer(plano):
        resto = texto[m.end():]
        for linha in resto.splitlines():
            if linha.strip():
                return linha.strip()
    return None


def _interpreta(valor: str | None, palavra_positiva: str) -> bool | None:
    """'NAO optante...' -> False; 'Optante...' -> True; desconhecido -> None."""
    if not valor:
        return None
    v = _sem_acento(valor).strip()
    if v.startswith("nao"):
        return False
    if palavra_positiva in v:
        return True
    return None


def parse(html: str, cnpj_consultado: str) -> Resultado:
    """Le o HTML da resposta e devolve o Resultado estruturado."""
    texto = texto_visivel(html)
    situacao_simples = _campo(texto, "Situacao no Simples Nacional")
    situacao_simei = _campo(texto, "Situacao no SIMEI")

    if not situacao_simples and not situacao_simei:
        return Resultado(
            cnpj_consultado=cnpj_consultado,
            status=STATUS_SEM_RESULTADO,
            mensagem=_trecho(texto),
        )

    return Resultado(
        cnpj_consultado=cnpj_consultado,
        status=STATUS_OK,
        cnpj_retornado=_campo(texto, "CNPJ"),
        nome_empresarial=_campo(texto, "Nome Empresarial"),
        situacao_simples=situacao_simples,
        situacao_simei=situacao_simei,
        optante_simples=_interpreta(situacao_simples, "optante"),
        optante_simei=_interpreta(situacao_simei, "enquadrado"),
        data_consulta=_campo(texto, "Data da consulta"),
    )


def _trecho(texto: str, limite: int = 300) -> str:
    """Guarda um pedaco da pagina para diagnosticar respostas inesperadas."""
    corpo = " | ".join(texto.splitlines()[:12])
    return corpo[:limite]
