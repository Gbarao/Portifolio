"""Parsers das EFDs. A leitura e comum as duas escrituracoes (base.py); o que
muda entre EFD ICMS/IPI e EFD Contribuicoes esta nos dicionarios de layout
(zfm/layouts)."""
from .base import ErroEFD, ResultadoCarga, carregar_arquivo, listar_txt  # noqa: F401
