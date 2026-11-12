"""Tipagem, higienização e gravação colunar em Parquet (streaming, em lotes).

Os parsers entregam linhas como listas de strings cruas do TXT. Este módulo acumula as linhas em buffers
colunares e, a cada lote, converte os tipos de forma vetorizada (PyArrow compute) e grava em Parquet/ZSTD.
Nada é mantido em memória além do lote corrente — permite processar arquivos de vários GB.
"""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from app import config

# Tipos lógicos: s=texto, n=numérico (DECIMAL 18,6), d=data DDMMAAAA, i=inteiro
NUM_TYPE = pa.decimal128(18, 6)
_ARROW = {"s": pa.string(), "n": NUM_TYPE, "d": pa.date32(), "i": pa.int64()}


def _cols(spec: str) -> list[tuple[str, str]]:
    """'file_id:i cod_part nome vl_doc:n' -> [(file_id,i),(cod_part,s),...]"""
    out = []
    for tok in spec.split():
        name, _, typ = tok.partition(":")
        out.append((name, typ or "s"))
    return out


# --------------------------------------------------------------------------------------
# Esquemas das tabelas brutas (staging). Prefixo sf_ = SPED Fiscal; ec_ = EFD-Contribuições.
# --------------------------------------------------------------------------------------
SCHEMAS: dict[str, list[tuple[str, str]]] = {
    # ---------------- SPED Fiscal ----------------
    "sf_part": _cols("file_id:i cod_part nome cod_pais cnpj cpf ie cod_mun"),
    "sf_part_hist": _cols("file_id:i cod_part dt_alt:d nr_campo cont_ant"),
    "sf_unid": _cols("file_id:i unid descr"),
    "sf_item_cad": _cols("file_id:i cod_item descr_item cod_barra cod_ant_item unid_inv tipo_item cod_ncm "
                         "ex_ipi cod_gen cod_lst aliq_icms:n cest"),
    "sf_item_hist": _cols("file_id:i cod_item descr_ant_item dt_ini:d dt_fim:d cod_ant_item"),
    "sf_nat": _cols("file_id:i cod_nat descr_nat"),
    "sf_conta": _cols("file_id:i dt_alt:d cod_nat_cc ind_cta nivel cod_cta nome_cta"),
    "sf_doc": _cols("file_id:i doc_id:i reg ind_oper ind_emit cod_part cod_mod cod_sit ser num_doc chave "
                    "dt_doc:d dt_e_s:d vl_doc:n vl_desc:n vl_merc:n vl_frt:n vl_seg:n vl_out_da:n "
                    "vl_bc_icms:n vl_icms:n vl_bc_icms_st:n vl_icms_st:n vl_ipi:n vl_pis:n vl_cofins:n"),
    "sf_c170": _cols("file_id:i doc_id:i num_item:i cod_item descr_compl qtd:n unid vl_item:n vl_desc:n "
                     "ind_mov cst_icms cfop cod_nat vl_bc_icms:n aliq_icms:n vl_icms:n vl_bc_icms_st:n "
                     "aliq_st:n vl_icms_st:n ind_apur cst_ipi cod_enq vl_bc_ipi:n aliq_ipi:n vl_ipi:n "
                     "cst_pis vl_bc_pis:n aliq_pis:n vl_pis:n cst_cofins vl_bc_cofins:n aliq_cofins:n "
                     "vl_cofins:n cod_cta vl_abat_nt:n"),
    "sf_anal": _cols("file_id:i doc_id:i anal_id:i reg cst_icms cfop aliq_icms:n vl_opr:n vl_bc_icms:n "
                     "vl_icms:n vl_bc_icms_st:n vl_icms_st:n vl_red_bc:n vl_ipi:n"),
    "sf_c191": _cols("file_id:i doc_id:i anal_id:i vl_fcp_op:n vl_fcp_st:n vl_fcp_ret:n"),
    "sf_c197": _cols("file_id:i doc_id:i cod_aj descr_compl_aj cod_item vl_bc_icms:n aliq_icms:n "
                     "vl_icms:n vl_outros:n"),
    # ---------------- EFD-Contribuições ----------------
    "ec_estab": _cols("file_id:i cod_est nome cnpj uf ie cod_mun"),
    "ec_bloco_estab": _cols("file_id:i reg cnpj ind_escri"),
    "ec_part": _cols("file_id:i cnpj_filial cod_part nome cod_pais cnpj cpf ie cod_mun"),
    "ec_item_cad": _cols("file_id:i cnpj_filial cod_item descr_item cod_barra cod_ant_item unid_inv tipo_item "
                         "cod_ncm ex_ipi cod_gen cod_lst aliq_icms:n"),
    "ec_item_hist": _cols("file_id:i cnpj_filial cod_item descr_ant_item dt_ini:d dt_fim:d cod_ant_item"),
    "ec_conta": _cols("file_id:i dt_alt:d cod_nat_cc ind_cta nivel cod_cta nome_cta"),
    "ec_doc": _cols("file_id:i doc_id:i cnpj_filial reg ind_oper ind_emit cod_part cod_mod cod_sit ser "
                    "num_doc chave dt_doc:d dt_e_s:d vl_doc:n vl_desc:n vl_merc:n vl_icms:n vl_ipi:n "
                    "vl_pis:n vl_cofins:n"),
    "ec_item": _cols("file_id:i doc_id:i cnpj_filial reg num_item:i cod_item descr_compl qtd:n unid "
                     "vl_item:n vl_desc:n cst_icms cfop aliq_icms:n vl_bc_icms:n vl_icms:n vl_icms_st:n "
                     "vl_ipi:n nat_bc_cred cst_pis vl_bc_pis:n aliq_pis:n vl_pis:n cst_cofins "
                     "vl_bc_cofins:n aliq_cofins:n vl_cofins:n cod_cta"),
    "ec_doc_trib": _cols("file_id:i doc_id:i reg tributo cst vl_item:n nat_bc_cred vl_bc:n aliq:n vl:n cod_cta"),
    "ec_c190": _cols("file_id:i c190_id:i cnpj_filial cod_mod dt_ref_ini:d dt_ref_fin:d cod_item cod_ncm "
                     "vl_tot_item:n"),
    "ec_c191_195": _cols("file_id:i c190_id:i reg tributo cnpj_cpf_part cst cfop vl_item:n vl_desc:n vl_bc:n "
                         "aliq:n vl:n cod_cta"),
    "ec_f": _cols("file_id:i cnpj_filial reg ind_oper cod_part cod_item dt_oper:d vl_oper:n nat_bc_cred "
                  "ind_orig_cred cst_pis vl_bc_pis:n aliq_pis:n vl_pis:n cst_cofins vl_bc_cofins:n "
                  "aliq_cofins:n vl_cofins:n cod_cta descr"),
}


def arrow_schema(table: str) -> pa.Schema:
    return pa.schema([(c, _ARROW[t]) for c, t in SCHEMAS[table]])


def _to_array(values: list, typ: str) -> pa.Array:
    if typ == "i":
        return pa.array([int(v) if v not in ("", None) and str(v).strip().lstrip("-").isdigit() else None
                         for v in values], pa.int64())
    arr = pa.array(values, pa.string())
    arr = pc.utf8_trim_whitespace(arr)
    arr = pc.if_else(pc.equal(arr, ""), pa.scalar(None, pa.string()), arr)
    if typ == "s":
        return arr
    if typ == "n":
        txt = pc.replace_substring(arr, ",", ".")
        try:
            return txt.cast(NUM_TYPE)
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
            # valor fora do padrão (ex.: mais de 6 casas) -> converte item a item, arredondando
            from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
            out = []
            for v in txt.to_pylist():
                if v is None:
                    out.append(None)
                    continue
                try:
                    out.append(Decimal(v).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
                except InvalidOperation:
                    out.append(None)
            return pa.array(out, NUM_TYPE)
    if typ == "d":
        valid = pc.and_kleene(pc.equal(pc.utf8_length(arr), 8), pc.utf8_is_digit(arr))
        arr = pc.if_else(valid, arr, pa.scalar(None, pa.string()))
        try:
            return pc.strptime(arr, format="%d%m%Y", unit="s", error_is_null=True).cast(pa.date32())
        except pa.ArrowInvalid:
            return pa.nulls(len(arr), pa.date32())
    raise ValueError(typ)


class TableSink:
    """Buffer colunar com flush periódico em Parquet (um arquivo por tabela por arquivo SPED)."""

    def __init__(self, table: str, path: Path, batch_rows: int = config.PARSER_BATCH_ROWS):
        self.table = table
        self.cols = SCHEMAS[table]
        self.ncols = len(self.cols)
        self.path = path
        self.batch_rows = batch_rows
        self.buf: list[list] = [[] for _ in self.cols]
        self.n = 0
        self.total = 0
        self.writer: pq.ParquetWriter | None = None
        self.schema = arrow_schema(table)

    def add(self, row: list) -> None:
        for col, v in zip(self.buf, row):
            col.append(v)
        self.n += 1
        if self.n >= self.batch_rows:
            self.flush()

    def flush(self) -> None:
        if not self.n:
            return
        arrays = [_to_array(vals, typ) for vals, (_, typ) in zip(self.buf, self.cols)]
        tbl = pa.Table.from_arrays(arrays, schema=self.schema)
        if self.writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.writer = pq.ParquetWriter(self.path, self.schema, compression=config.PARQUET_COMPRESSION,
                                           compression_level=config.PARQUET_COMPRESSION_LEVEL)
        self.writer.write_table(tbl)
        self.total += self.n
        self.buf = [[] for _ in self.cols]
        self.n = 0

    def close(self) -> int:
        self.flush()
        if self.writer is not None:
            self.writer.close()
        return self.total


class SinkSet:
    """Conjunto de sinks de um arquivo SPED."""

    def __init__(self, file_id: int, out_dir: Path, tables: list[str]):
        self.file_id = file_id
        self.sinks = {t: TableSink(t, out_dir / t / f"{file_id}.parquet") for t in tables}

    def add(self, table: str, row: list) -> None:
        self.sinks[table].add(row)

    def close(self) -> dict[str, int]:
        return {t: s.close() for t, s in self.sinks.items()}

    def abort(self) -> None:
        for s in self.sinks.values():
            try:
                if s.writer is not None:
                    s.writer.close()
            finally:
                s.path.unlink(missing_ok=True)


def pick(parts: list[str], idx: list[int]) -> list[str]:
    """Seleciona campos pelas posições do leiaute; campos ausentes (versões antigas) viram ''."""
    n = len(parts)
    return [parts[i] if i < n else "" for i in idx]


def split_line(line: str) -> list[str]:
    s = line.rstrip("\r\n")
    if not s.startswith("|"):
        return []
    parts = s.split("|")
    return parts[1:-1] if s.endswith("|") else parts[1:]
