"""Guarda TODAS as linhas do arquivo SPED como estão no TXT (consulta sem cruzamento nas telas SPED Fiscal / EFD).

Para cada linha registra:
  line_no     número da linha no arquivo (igual ao de um editor de texto)
  reg         código do registro (C100, C170, E110...)
  cnpj_estab  unidade a que a linha pertence
                - SPED Fiscal: CNPJ (ou CPF) do registro 0000 (um arquivo por estabelecimento)
                - EFD-Contribuições: CNPJ do 0140 (cadastros do Bloco 0) ou do A010/C010/D010/F010/I010/P010
                  (movimento); nos demais blocos (M, 1...), o CNPJ da matriz (0000)
  doc_line    linha do registro "documento" a que a linha pertence — o registro de código terminado em "00" mais
              recente do mesmo bloco (C100 para C170/C190/C191/C197, D100 para D190, E100 para E110, M100 para M105...),
              além das consolidações que têm filhos (C190 da EFD-Contribuições para C191/C195, C180, C490...).
              Reinicia a cada troca de estabelecimento (A010/C010/D010/F010) e de bloco.
              Serve apenas para mostrar o contexto (número, chave, participante) ao lado de registros filhos.
  linha       texto original completo da linha (sem a quebra de linha)
"""
from __future__ import annotations

from pathlib import Path

from app import config
from app.parser.normalizer import SinkSet, split_line

TABLE = {"ICMS_IPI": "sf_linhas", "CONTRIB": "ec_linhas"}
_EC_ESTAB_REGS = {"A010", "C010", "D010", "F010", "I010", "P010"}
# Registros que também são "pais" de outros, apesar de não terminarem em "00"
_EXTRA_DOCS = {
    "ICMS_IPI": {"C350", "D350"},
    "CONTRIB": {"C180", "C190", "C380", "C395", "C490", "D350"},
}


class RawLineTracker:
    """Acompanha bloco/documento/estabelecimento corrente e grava cada linha no sink de linhas originais."""

    def __init__(self, tipo: str, sinks: SinkSet, file_id: int):
        self.tipo = tipo
        self.table = TABLE[tipo]
        self.sinks = sinks
        self.file_id = file_id
        self.doc_line: int | None = None
        self.bloco = ""
        self.matriz = ""
        self.estab = ""
        self.enabled = config.GUARDAR_LINHAS_ORIGINAIS
        self.extra_docs = _EXTRA_DOCS[tipo]
        # acesso direto aos buffers colunares do sink (caminho mais quente da importação)
        self.sink = sinks.sinks[self.table]
        self._bind()

    def _bind(self) -> None:
        b = self.sink.buf
        self._a_file, self._a_line, self._a_reg, self._a_estab, self._a_doc, self._a_txt = (x.append for x in b)

    def add(self, line_no: int, raw: str, p: list[str]) -> None:
        if not self.enabled:
            return
        reg = p[0]
        bloco = reg[:1]
        if bloco != self.bloco:
            self.bloco = bloco
            self.doc_line = None
            if self.tipo == "CONTRIB":
                self.estab = self.matriz
        if reg == "0000":
            if self.tipo == "ICMS_IPI":
                self.estab = (p[6] if len(p) > 6 else "") or (p[7] if len(p) > 7 else "")
            else:
                self.matriz = p[8] if len(p) > 8 else ""
            self.estab = self.estab if self.tipo == "ICMS_IPI" else self.matriz
        elif self.tipo == "CONTRIB" and (reg == "0140" or reg in _EC_ESTAB_REGS):
            self.estab = (p[3] if reg == "0140" else p[1]) if len(p) > (3 if reg == "0140" else 1) else self.matriz
            self.doc_line = None
        if bloco not in ("0", "9"):
            if reg.endswith("001") or reg.endswith("990"):
                self.doc_line = None
            elif reg.endswith("00") or reg in self.extra_docs:
                self.doc_line = line_no
        self._a_file(self.file_id)
        self._a_line(line_no)
        self._a_reg(reg)
        self._a_estab(self.estab or None)
        self._a_doc(self.doc_line if bloco not in ("0", "9") else None)
        self._a_txt(raw.rstrip("\r\n"))
        sink = self.sink
        sink.n += 1
        if sink.n >= sink.batch_rows:
            sink.flush()
            self._bind()   # flush recria os buffers


def parse_raw(path: str | Path, file_id: int, tipo: str, out_dir: Path) -> dict[str, int]:
    """Lê apenas as linhas originais (usado para indexar arquivos importados antes desta funcionalidade)."""
    table = TABLE[tipo]
    sinks = SinkSet(file_id, out_dir, [table])
    tr = RawLineTracker(tipo, sinks, file_id)
    tr.enabled = True
    n = 0
    try:
        with open(path, "r", encoding=config.FILE_ENCODING, errors="replace", newline="") as f:
            for line in f:
                n += 1
                p = split_line(line)
                if not p:
                    continue
                tr.add(n, line, p)
                if p[0] == "9999":
                    break
        counts = sinks.close()
    except Exception:
        sinks.abort()
        raise
    counts["_linhas"] = n
    return counts
