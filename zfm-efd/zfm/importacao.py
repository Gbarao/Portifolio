"""Importacao em segundo plano.

A leitura roda numa thread propria do programa, independente da tela aberta: trocar de
tela, recarregar a pagina ou fechar a aba do navegador NAO interrompe. So para se o
programa for fechado (janela preta) ou se o usuario clicar em "Cancelar".

Cada arquivo e gravado numa transacao: se a leitura for interrompida, nada daquele
arquivo fica no banco (os ja concluidos permanecem).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import duckdb

from .config import logger
from .parsers.base import ImportacaoCancelada, ResultadoCarga, carregar_arquivo

# Trava de escrita no banco: importacao e reconstrucao das visoes nunca rodam juntas.
TRAVA_BANCO = threading.RLock()


@dataclass
class StatusArquivo:
    nome: str
    caminho: str
    tamanho_mb: float
    tamanho_bytes: int = 0
    situacao: str = "na fila"        # na fila | lendo | carregado | duplicado | erro | cancelado
    progresso: float = 0.0
    mensagem: str = ""
    avisos: list[str] = field(default_factory=list)
    segundos: float = 0.0


class Importacao:
    def __init__(self, caminhos: list[Path], abrir_conexao: Callable[[], duckdb.DuckDBPyConnection],
                 ao_final: Callable[[duckdb.DuckDBPyConnection], None] | None = None):
        self.arquivos = [StatusArquivo(p.name, str(p), round(p.stat().st_size / 1e6, 1), p.stat().st_size)
                         for p in caminhos]
        self._abrir = abrir_conexao
        self._ao_final = ao_final
        self._cancelar = threading.Event()
        self._trava = threading.Lock()
        self.inicio = time.time()
        self.fim: float | None = None
        self.etapa = "na fila"
        self.erro_final = ""
        self._thread = threading.Thread(target=self._rodar, name="importacao-efd", daemon=True)

    # ------------------------------------------------------------------ API
    def iniciar(self) -> None:
        self._thread.start()

    def cancelar(self) -> None:
        self._cancelar.set()

    @property
    def rodando(self) -> bool:
        return self._thread.is_alive()

    @property
    def concluida(self) -> bool:
        return self.fim is not None

    def resumo(self) -> dict:
        with self._trava:
            total_mb = sum(a.tamanho_bytes for a in self.arquivos) or 1
            feito_mb = sum(a.tamanho_bytes * (1.0 if a.situacao in ("carregado", "duplicado", "erro", "cancelado")
                                                else a.progresso) for a in self.arquivos)
            atual = next((a for a in self.arquivos if a.situacao == "lendo"), None)
            return {
                "rodando": self.rodando, "etapa": self.etapa,
                "progresso": min(feito_mb / total_mb, 1.0),
                "n_total": len(self.arquivos),
                "n_feitos": sum(a.situacao in ("carregado", "duplicado", "erro", "cancelado") for a in self.arquivos),
                "n_carregados": sum(a.situacao == "carregado" for a in self.arquivos),
                "n_erros": sum(a.situacao == "erro" for a in self.arquivos),
                "atual": atual.nome if atual else "",
                "atual_progresso": atual.progresso if atual else 0.0,
                "decorrido": (self.fim or time.time()) - self.inicio,
                "erro_final": self.erro_final,
            }

    # ------------------------------------------------------------- execucao
    def _rodar(self) -> None:
        log = logger()
        con = None
        try:
            con = self._abrir()
            self.etapa = "lendo arquivos"
            for a in self.arquivos:
                if self._cancelar.is_set():
                    a.situacao, a.mensagem = "cancelado", "Não lido (importação cancelada)."
                    continue
                with self._trava:
                    a.situacao = "lendo"
                t0 = time.time()

                def prog(frac: float, _txt: str, a=a) -> None:
                    a.progresso = frac
                    if self._cancelar.is_set():
                        raise ImportacaoCancelada()

                with TRAVA_BANCO:
                    r: ResultadoCarga = carregar_arquivo(con, Path(a.caminho), progresso=prog)
                with self._trava:
                    a.situacao, a.mensagem, a.avisos = r.situacao, r.mensagem, r.avisos
                    a.progresso, a.segundos = 1.0, round(time.time() - t0, 1)
                log.info("Importacao: %s -> %s em %.1fs", a.nome, r.situacao, a.segundos)
            if self._ao_final and any(a.situacao == "carregado" for a in self.arquivos):
                self.etapa = "preparando as análises"
                with TRAVA_BANCO:
                    self._ao_final(con)
            self.etapa = "concluída"
        except Exception as e:  # noqa: BLE001
            log.exception("Falha na importacao em segundo plano")
            self.erro_final = f"{type(e).__name__}: veja data/logs/zfm.log"
            self.etapa = "interrompida por erro"
        finally:
            self.fim = time.time()
            if con is not None:
                try:
                    con.close()
                except Exception:  # noqa: BLE001
                    pass


class Gerenciador:
    """Uma importacao por vez, compartilhada por todas as telas e abas do navegador."""

    def __init__(self):
        self.atual: Importacao | None = None
        self._trava = threading.Lock()

    def iniciar(self, caminhos: list[Path], abrir_conexao, ao_final=None) -> Importacao:
        with self._trava:
            if self.atual and self.atual.rodando:
                raise RuntimeError("Já existe uma importação em andamento.")
            self.atual = Importacao(caminhos, abrir_conexao, ao_final)
            self.atual.iniciar()
            return self.atual

    @property
    def rodando(self) -> bool:
        return bool(self.atual and self.atual.rodando)
