"""Cliente HTTP da Consulta Optantes do Simples Nacional.

O formulario nao e codificado aqui: o cliente le a pagina, descobre o form,
os campos ocultos (ASP.NET WebForms usa __VIEWSTATE e afins) e o nome do campo
de CNPJ, e so entao envia o POST. Assim a solucao nao quebra se a Receita
renomear um campo.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .parser import Resultado, parse

URL_PADRAO = "https://www8.receita.fazenda.gov.br/simplesnacional/aplicacoes.aspx?id=21"

STATUS_ERRO_REDE = "ERRO_REDE"
STATUS_ERRO_FORM = "ERRO_FORMULARIO"

_CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class ErroFormulario(RuntimeError):
    """A pagina nao tem o formulario esperado (layout mudou ou bloqueio)."""


@dataclass
class Formulario:
    url_acao: str
    campos: dict[str, str]
    campo_cnpj: str

    def payload(self, cnpj: str) -> dict[str, str]:
        dados = dict(self.campos)
        dados[self.campo_cnpj] = cnpj
        return dados


def descobre_formulario(html: str, url_base: str, campo_cnpj: str | None = None) -> Formulario:
    """Extrai action, campos ocultos e o nome do campo de CNPJ."""
    sopa = BeautifulSoup(html, "lxml")

    form = None
    for candidato in sopa.find_all("form"):
        if candidato.find("input", attrs={"type": lambda v: v in (None, "text")}):
            form = candidato
            break
    if form is None:
        raise ErroFormulario("nenhum <form> com campo de texto encontrado")

    campos: dict[str, str] = {}
    entradas_texto: list = []
    for entrada in form.find_all("input"):
        nome = entrada.get("name")
        tipo = (entrada.get("type") or "text").lower()
        if tipo in ("hidden",) and nome:
            campos[nome] = entrada.get("value", "")
        elif tipo in ("text", "search", "tel") or tipo is None:
            entradas_texto.append(entrada)
        elif tipo in ("submit", "image") and nome and "submit" not in campos:
            # o botao precisa ir no POST para o WebForms disparar o evento
            campos[nome] = entrada.get("value", "")
    for select in form.find_all("select"):
        nome = select.get("name")
        opcao = select.find("option", selected=True) or select.find("option")
        if nome and opcao is not None:
            campos[nome] = opcao.get("value", opcao.get_text(strip=True))

    campos.setdefault("__EVENTTARGET", "")
    campos.setdefault("__EVENTARGUMENT", "")

    if campo_cnpj is None:
        campo_cnpj = _escolhe_campo_cnpj(entradas_texto)
    campos.setdefault(campo_cnpj, "")

    acao = form.get("action") or ""
    return Formulario(urljoin(url_base, acao) if acao else url_base, campos, campo_cnpj)


def _escolhe_campo_cnpj(entradas: list) -> str:
    nomeados = [e for e in entradas if e.get("name")]
    if not nomeados:
        raise ErroFormulario("formulario sem campo de texto nomeado")
    for entrada in nomeados:
        alvo = f"{entrada.get('name','')} {entrada.get('id','')}".lower()
        if "cnpj" in alvo:
            return entrada["name"]
    if len(nomeados) == 1:
        return nomeados[0]["name"]
    raise ErroFormulario(
        "varios campos de texto e nenhum identificado como CNPJ; "
        "informe --campo-cnpj com o name correto"
    )


class ConsultaHTTP:
    """Consulta um CNPJ por vez, reaproveitando cookies da sessao."""

    def __init__(
        self,
        url: str = URL_PADRAO,
        *,
        timeout: float = 30.0,
        tentativas: int = 3,
        campo_cnpj: str | None = None,
        reutilizar_formulario: bool = False,
        verificar_tls: bool = True,
    ):
        self.url = url
        self.tentativas = max(1, tentativas)
        self.campo_cnpj = campo_cnpj
        self.reutilizar_formulario = reutilizar_formulario
        self._form: Formulario | None = None
        self._cliente = httpx.AsyncClient(
            headers=_CABECALHOS,
            timeout=timeout,
            follow_redirects=True,
            verify=verificar_tls,
        )

    async def __aenter__(self) -> "ConsultaHTTP":
        return self

    async def __aexit__(self, *_) -> None:
        await self._cliente.aclose()

    async def _carregar_formulario(self) -> Formulario:
        resposta = await self._cliente.get(self.url)
        resposta.raise_for_status()
        html, url_final = resposta.text, str(resposta.url)
        try:
            return descobre_formulario(html, url_final, self.campo_cnpj)
        except ErroFormulario:
            quadro = BeautifulSoup(html, "lxml").find(["iframe", "frame"], src=True)
            if not quadro:
                raise
            interna = await self._cliente.get(urljoin(url_final, quadro["src"]))
            interna.raise_for_status()
            return descobre_formulario(interna.text, str(interna.url), self.campo_cnpj)

    async def _formulario(self) -> Formulario:
        if self.reutilizar_formulario and self._form is not None:
            return self._form
        self._form = await self._carregar_formulario()
        return self._form

    async def consultar(self, cnpj: str) -> Resultado:
        """Uma consulta completa (GET do form + POST), com retentativas."""
        ultimo_erro = ""
        for tentativa in range(1, self.tentativas + 1):
            try:
                form = await self._formulario()
                resposta = await self._cliente.post(
                    form.url_acao,
                    data=form.payload(cnpj),
                    headers={"Referer": self.url},
                )
                if resposta.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"HTTP {resposta.status_code}",
                        request=resposta.request,
                        response=resposta,
                    )
                resposta.raise_for_status()
                return parse(resposta.text, cnpj)
            except ErroFormulario as erro:
                return Resultado(
                    cnpj_consultado=cnpj, status=STATUS_ERRO_FORM, mensagem=str(erro)
                )
            except (httpx.HTTPError, httpx.InvalidURL) as erro:
                ultimo_erro = f"{type(erro).__name__}: {erro}"
                self._form = None  # viewstate suspeito: recarrega na proxima
                if tentativa < self.tentativas:
                    await asyncio.sleep(2 ** tentativa + random.uniform(0, 0.5))
        return Resultado(
            cnpj_consultado=cnpj, status=STATUS_ERRO_REDE, mensagem=ultimo_erro
        )
