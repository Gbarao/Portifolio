#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Abre cada tela do programa num navegador (Playwright) e falha se alguma mostrar
erro. Usado no fluxo que gera o executável, com a base de teste já carregada.

Uso:  python testes/testar_telas.py http://localhost:8790
"""

import os
import sys

from playwright.sync_api import sync_playwright

ROTAS = ["", "carregar", "conferencias", "filtros", "auditoria"]


def main(url: str) -> int:
    problemas = []
    with sync_playwright() as p:
        caminho = os.environ.get("CHROMIUM")       # navegador já instalado, se houver
        nav = p.chromium.launch(executable_path=caminho) if caminho else p.chromium.launch()
        pagina = nav.new_page(viewport={"width": 1600, "height": 1000})
        pagina.on("pageerror", lambda e: problemas.append(f"erro no navegador: {e}"))
        for rota in ROTAS:
            pagina.goto(f"{url.rstrip('/')}/{rota}", wait_until="networkidle")
            pagina.wait_for_timeout(5000)
            titulo = pagina.locator("h1").first.inner_text(timeout=60000)
            erros = pagina.locator('[data-testid="stException"]').all_inner_texts()
            print(f"{rota or 'visao':13s} {titulo!r} erros={len(erros)}")
            problemas += [f"{rota}: {e[:500]}" for e in erros]
            if pagina.get_by_text("Page not found").count():
                problemas.append(f"{rota}: página não encontrada")
            if rota == "conferencias":
                grade = pagina.locator('[data-testid="stDataFrame"]:visible').nth(1)
                caixa = grade.bounding_box()
                pagina.mouse.click(caixa["x"] + 16, caixa["y"] + 53)
                pagina.wait_for_timeout(5000)
                dialogo = pagina.get_by_role("dialog")
                ok = dialogo.count() == 1 and "|C170|" in dialogo.inner_text()
                print(f"{'pop-up':13s} abriu com as linhas do TXT: {ok}")
                if not ok:
                    problemas.append("pop-up das conferências não abriu")
                pagina.keyboard.press("Escape")
        nav.close()
    for pr in problemas:
        print("PROBLEMA:", pr)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"))
