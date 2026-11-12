"""Identificação automática SPED Fiscal x EFD-Contribuições (registro 0000) e hash SHA-256."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from app import config
from app.parser.layouts import EC, SF, index_of
from app.parser.normalizer import split_line

TIPO_FISCAL = "ICMS_IPI"
TIPO_CONTRIB = "CONTRIB"

_DATE = re.compile(r"^\d{8}$")
_SF0000 = index_of(SF["0000"])
_EC0000 = index_of(EC["0000"])


@dataclass
class SpedHeader:
    path: str
    tipo: str | None  # ICMS_IPI | CONTRIB | None (não reconhecido)
    cnpj: str = ""
    nome: str = ""
    uf: str = ""
    dt_ini: str = ""  # AAAA-MM-DD
    dt_fin: str = ""
    competencia: str = ""  # AAAA-MM
    finalidade: str = ""  # ORIGINAL | RETIFICADORA
    cod_ver: str = ""
    sha256: str = ""
    tamanho: int = 0
    erro: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _iso(d: str) -> str:
    return f"{d[4:8]}-{d[2:4]}-{d[0:2]}" if _DATE.match(d or "") else ""


def read_header(path: str | Path) -> SpedHeader:
    p = Path(path)
    h = SpedHeader(path=str(p), tipo=None)
    try:
        with open(p, "r", encoding=config.FILE_ENCODING, errors="replace") as f:
            first = ""
            for _ in range(5):  # tolera BOM/linhas em branco iniciais
                first = f.readline().lstrip("﻿\xef\xbb\xbf")
                if first.strip():
                    break
    except OSError as e:
        h.erro = str(e)
        return h
    parts = split_line(first)
    if not parts or parts[0] != "0000":
        h.erro = "Primeira linha não é o registro 0000"
        return h

    def g(idx: dict, name: str) -> str:
        i = idx[name]
        return parts[i].strip() if i < len(parts) else ""

    # SPED Fiscal: DT_INI na 4ª posição (após COD_VER, COD_FIN). EFD-Contribuições: DT_INI na 6ª.
    if len(parts) > 3 and _DATE.match(parts[3].strip()):
        h.tipo = TIPO_FISCAL
        h.cod_ver = g(_SF0000, "COD_VER")
        h.finalidade = "RETIFICADORA" if g(_SF0000, "COD_FIN") == "1" else "ORIGINAL"
        h.dt_ini, h.dt_fin = _iso(g(_SF0000, "DT_INI")), _iso(g(_SF0000, "DT_FIN"))
        h.nome, h.cnpj, h.uf = g(_SF0000, "NOME"), g(_SF0000, "CNPJ") or g(_SF0000, "CPF"), g(_SF0000, "UF")
    elif len(parts) > 5 and _DATE.match(parts[5].strip()):
        h.tipo = TIPO_CONTRIB
        h.cod_ver = g(_EC0000, "COD_VER")
        h.finalidade = "RETIFICADORA" if g(_EC0000, "TIPO_ESCRIT") == "1" else "ORIGINAL"
        h.dt_ini, h.dt_fin = _iso(g(_EC0000, "DT_INI")), _iso(g(_EC0000, "DT_FIN"))
        h.nome, h.cnpj, h.uf = g(_EC0000, "NOME"), g(_EC0000, "CNPJ"), g(_EC0000, "UF")
    else:
        h.erro = "Registro 0000 com leiaute não reconhecido"
        return h
    h.competencia = h.dt_ini[:7]
    return h


def sha256_file(path: str | Path, chunk: int = 8 * 1024 * 1024) -> tuple[str, int]:
    hsh = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            hsh.update(b)
            size += len(b)
    return hsh.hexdigest(), size


def inspect_file(path: str | Path) -> dict:
    """Etapa 1 do pipeline (executada em paralelo): cabeçalho + hash."""
    h = read_header(path)
    if h.tipo:
        try:
            h.sha256, h.tamanho = sha256_file(path)
        except OSError as e:
            h.erro = str(e)
    return h.as_dict()


def discover_files(root: str | Path) -> list[Path]:
    """Varre pasta (e subpastas) buscando .txt; aceita também caminho de arquivo único."""
    r = Path(root)
    if r.is_file():
        return [r]
    return sorted(p for p in r.rglob("*") if p.is_file() and p.suffix.lower() == ".txt")
