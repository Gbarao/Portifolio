"""Fallback com navegador (Playwright).

Usar somente se o modo HTTP falhar: e ~10x mais lento e consome muito mais
memoria. Serve para o caso de a pagina passar a depender de JavaScript.
Instalacao: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import asyncio

from .parser import Resultado, parse
from .scraper import URL_PADRAO

STATUS_ERRO_BROWSER = "ERRO_BROWSER"


class ConsultaBrowser:
    def __init__(
        self,
        url: str = URL_PADRAO,
        *,
        timeout: float = 45.0,
        seletor_cnpj: str | None = None,
        seletor_botao: str | None = None,
    ):
        self.url = url
        self.timeout_ms = int(timeout * 1000)
        self.seletor_cnpj = seletor_cnpj
        self.seletor_botao = seletor_botao
        self._pw = None
        self._navegador = None

    async def __aenter__(self) -> "ConsultaBrowser":
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._navegador = await self._pw.chromium.launch(headless=True)
        return self

    async def __aexit__(self, *_) -> None:
        if self._navegador:
            await self._navegador.close()
        if self._pw:
            await self._pw.stop()

    async def consultar(self, cnpj: str) -> Resultado:
        pagina = await self._navegador.new_page()
        try:
            await pagina.goto(self.url, timeout=self.timeout_ms)
            campo = (
                pagina.locator(self.seletor_cnpj)
                if self.seletor_cnpj
                else pagina.locator("input[type=text]").first
            )
            await campo.fill(cnpj, timeout=self.timeout_ms)
            botao = (
                pagina.locator(self.seletor_botao)
                if self.seletor_botao
                else pagina.get_by_role("button", name="Consultar")
            )
            await botao.click(timeout=self.timeout_ms)
            await pagina.wait_for_load_state("networkidle", timeout=self.timeout_ms)
            return parse(await pagina.content(), cnpj)
        except Exception as erro:  # playwright levanta tipos proprios
            return Resultado(
                cnpj_consultado=cnpj,
                status=STATUS_ERRO_BROWSER,
                mensagem=f"{type(erro).__name__}: {erro}",
            )
        finally:
            await pagina.close()
            await asyncio.sleep(0)
