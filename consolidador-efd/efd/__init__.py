"""Consolidador EFD: cruza a EFD ICMS/IPI (Fiscal) com a EFD-Contribuições."""

import sys

__version__ = "1.1.0"


def empacotado() -> bool:
    """True quando roda dentro do executável gerado pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def comando_modulo(modulo: str, *args: str) -> list[str]:
    """Comando para rodar um módulo do pacote em outro processo.

    No Python normal: python -m efd.trabalhador ...
    No executável:    ConsolidadorEFD.exe --trabalhador ...  (o executável
    não aceita -m; o ponto de entrada reconhece a opção e chama o módulo).
    """
    if empacotado():
        return [sys.executable, "--" + modulo.rsplit(".", 1)[-1], *args]
    return [sys.executable, "-m", modulo, *args]
