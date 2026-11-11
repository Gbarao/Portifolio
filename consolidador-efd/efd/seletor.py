# -*- coding: utf-8 -*-
"""
Janela nativa de seleção de arquivos (tkinter.filedialog).

Roda em um processo separado (python -m efd.seletor) porque o tkinter precisa
da thread principal, e a interface web roda os scripts em outra thread. O
resultado sai em JSON na saída padrão.
"""

import json
import sys


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "arquivos"
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print(json.dumps({"erro": "tkinter não está disponível neste computador."}))
        return 1
    try:
        raiz = tk.Tk()
    except Exception as e:                       # sem ambiente gráfico
        print(json.dumps({"erro": f"Não foi possível abrir a janela de seleção: {e}"}))
        return 1
    raiz.withdraw()
    raiz.attributes("-topmost", True)
    if modo == "pasta":
        escolhido = filedialog.askdirectory(title="Selecione a pasta com as EFDs")
        caminhos = [escolhido] if escolhido else []
    elif modo == "backup":
        escolhido = filedialog.askopenfilename(
            title="Selecione o arquivo de backup",
            filetypes=[("Backup do Consolidador EFD", "*.duckdb"), ("Todos", "*.*")])
        caminhos = [escolhido] if escolhido else []
    elif modo == "planilha":
        escolhido = filedialog.askopenfilename(
            title="Selecione a planilha",
            filetypes=[("Planilhas e textos", "*.xlsx *.xls *.csv *.txt"), ("Todos", "*.*")])
        caminhos = [escolhido] if escolhido else []
    else:
        caminhos = list(filedialog.askopenfilenames(
            title="Selecione as EFDs (ICMS/IPI e Contribuições)",
            filetypes=[("Arquivos do SPED (*.txt)", "*.txt"), ("Todos", "*.*")]))
    raiz.destroy()
    print(json.dumps({"caminhos": caminhos}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
