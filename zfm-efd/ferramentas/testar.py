"""Roda os testes automaticos e mostra o resumo em portugues (testar.bat)."""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> int:
    logs = RAIZ / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"testes_{_dt.datetime.now():%Y%m%d_%H%M%S}.log"
    print("Rodando os testes automaticos (inclui um teste de desempenho de ~1 milhao de linhas).")
    print("Isso pode levar alguns minutos...")
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rf"], cwd=RAIZ,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    saida = (p.stdout or "") + (p.stderr or "")
    log.write_text(saida, encoding="utf-8")
    def num(chave: str) -> int:
        m = re.search(rf"(\d+) {chave}", saida)
        return int(m.group(1)) if m else 0

    passou, falhou, erros = num("passed"), num("failed"), num("error")
    print()
    print("=" * 60)
    print(f"Testes que passaram: {passou}")
    print(f"Testes que falharam: {falhou + erros}")
    print("=" * 60)
    if falhou or erros or p.returncode != 0:
        print("Lista dos que falharam:")
        for linha in saida.splitlines():
            if linha.startswith(("FAILED", "ERROR")):
                print("  " + linha)
        print(f"Detalhes gravados em: {log}")
        print("Envie esse arquivo ao Claude Code.")
        return 1
    print("Tudo certo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
