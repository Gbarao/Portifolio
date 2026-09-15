"""Leitura da base de CNPJ e escrita do resultado (CSV/XLSX/TXT)."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .cnpj import normaliza

_PADRAO_CNPJ = re.compile(r"[0-9A-Za-z]{14}")


def ler_cnpjs(caminho: str | Path, coluna: str | None = None) -> list[str]:
    """Le CNPJs de .csv/.txt/.xlsx. Sem --coluna, detecta a coluna provavel."""
    caminho = Path(caminho)
    sufixo = caminho.suffix.lower()
    if sufixo in (".xlsx", ".xlsm"):
        linhas = _ler_xlsx(caminho)
    elif sufixo in (".csv", ".tsv"):
        linhas = _ler_csv(caminho)
    else:
        linhas = [
            {"cnpj": l.strip()} for l in _texto(caminho).splitlines() if l.strip()
        ]
    if not linhas:
        return []
    nome = coluna or _detecta_coluna(linhas)
    brutos = [str(l.get(nome, "") or "") for l in linhas]
    return [normaliza(b) for b in brutos if normaliza(b)]


def _texto(caminho: Path) -> str:
    dados = caminho.read_bytes()
    for codec in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return dados.decode(codec)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1", errors="replace")


def _ler_csv(caminho: Path) -> list[dict]:
    texto = _texto(caminho)
    amostra = texto[:8192]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
    return list(csv.DictReader(texto.splitlines(), dialect=dialeto))


def _ler_xlsx(caminho: Path) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except ImportError as erro:  # pragma: no cover
        raise SystemExit("para ler .xlsx instale: pip install openpyxl") from erro
    planilha = load_workbook(caminho, read_only=True, data_only=True).active
    linhas = planilha.iter_rows(values_only=True)
    cabecalho = [str(c) if c is not None else "" for c in next(linhas, [])]
    return [dict(zip(cabecalho, linha)) for linha in linhas]


def _detecta_coluna(linhas: list[dict]) -> str:
    """Prefere a coluna chamada 'cnpj'; senao, a que mais parece CNPJ."""
    colunas = [c for c in linhas[0].keys() if c]
    for coluna in colunas:
        if "cnpj" in str(coluna).lower():
            return coluna
    amostra = linhas[:200]
    melhor, pontos_max = colunas[0], -1
    for coluna in colunas:
        pontos = sum(
            1
            for l in amostra
            if _PADRAO_CNPJ.fullmatch(normaliza(str(l.get(coluna, "") or "")))
        )
        if pontos > pontos_max:
            melhor, pontos_max = coluna, pontos
    return melhor


CABECALHO_SAIDA = [
    "cnpj",
    "cnpj_formatado",
    "raiz",
    "chave_consultada",
    "status",
    "optante_simples",
    "situacao_simples",
    "optante_simei",
    "situacao_simei",
    "nome_empresarial",
    "data_consulta",
    "mensagem",
]


def escrever(caminho: str | Path, linhas: list[dict]) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.suffix.lower() in (".xlsx", ".xlsm"):
        return _escrever_xlsx(caminho, linhas)
    with caminho.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=CABECALHO_SAIDA, delimiter=";", extrasaction="ignore"
        )
        escritor.writeheader()
        escritor.writerows(linhas)
    return caminho


def _escrever_xlsx(caminho: Path, linhas: list[dict]) -> Path:
    try:
        from openpyxl import Workbook
    except ImportError as erro:  # pragma: no cover
        raise SystemExit("para gravar .xlsx instale: pip install openpyxl") from erro
    livro = Workbook()
    aba = livro.active
    aba.title = "consulta"
    aba.append(CABECALHO_SAIDA)
    for linha in linhas:
        aba.append([linha.get(c) for c in CABECALHO_SAIDA])
    aba.freeze_panes = "A2"
    livro.save(caminho)
    return caminho
