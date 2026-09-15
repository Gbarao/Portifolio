"""Servidor local que imita o formulario WebForms da Consulta Optantes.

Usado nos testes para exercitar o fluxo completo (GET do form -> POST ->
parse) sem depender da rede.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

FORMULARIO = """<html><body>
<form method="post" action="./aplicacoes.aspx?id=21" id="form1">
<input type="hidden" name="__VIEWSTATE" value="/wEPDwUKMTIzNDU2Nzg5" />
<input type="hidden" name="__VIEWSTATEGENERATOR" value="A1B2C3" />
<input type="hidden" name="__EVENTVALIDATION" value="/wEdAAQx" />
<label>CNPJ</label>
<input name="ctl00$ContentPlaceHolder1$txtCNPJ" id="txtCNPJ" type="text" maxlength="14" />
<input type="submit" name="ctl00$ContentPlaceHolder1$btConsultar" value="Consultar" />
</form></body></html>"""

RESULTADO = """<html><body>
<p><b>Data da consulta:</b> 15/09/2026 09:04:38</p>
<div>Identifica&ccedil;&atilde;o do Contribuinte - CNPJ Matriz</div>
<div>CNPJ: <b>{cnpj_formatado}</b></div>
<div>Nome Empresarial: <b>{nome}</b></div>
<div>Situa&ccedil;&atilde;o no Simples Nacional: <b>{simples}</b></div>
<div>Situa&ccedil;&atilde;o no SIMEI: <b>{simei}</b></div>
</body></html>"""

OPTANTES = {"11222333000181"}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):  # silencia o log nos testes
        pass

    def _responde(self, corpo: str) -> None:
        dados = corpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        self._responde(FORMULARIO)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        campos = parse_qs(self.rfile.read(tamanho).decode("utf-8"))
        if "__VIEWSTATE" not in campos:  # WebForms recusa POST sem viewstate
            self.send_error(500, "viewstate ausente")
            return
        cnpj = campos.get("ctl00$ContentPlaceHolder1$txtCNPJ", [""])[0]
        optante = cnpj in OPTANTES
        self._responde(
            RESULTADO.format(
                cnpj_formatado=f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}",
                nome="EMPRESA TESTE LTDA",
                simples="Optante pelo Simples Nacional desde 01/01/2020"
                if optante
                else "N&Atilde;O optante pelo Simples Nacional",
                simei="N&Atilde;O enquadrado no SIMEI",
            )
        )


class ServidorFalso:
    def __init__(self):
        self.servidor = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        porta = self.servidor.server_address[1]
        return f"http://127.0.0.1:{porta}/simplesnacional/aplicacoes.aspx?id=21"

    def __enter__(self) -> "ServidorFalso":
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.servidor.shutdown()
        self.servidor.server_close()
