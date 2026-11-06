"""Leitura em streaming dos arquivos SPED e carga em lotes no DuckDB.

Regras do formato (SPEC 4.1):
- linhas delimitadas por '|', primeiro campo = REG;
- encoding normalmente ISO-8859-1; detectado, nunca presumido UTF-8;
- decimais com virgula e datas DDMMAAAA (conversao feita no banco, exata);
- hierarquia por ordem: o filho pertence ao ultimo pai lido;
- tudo que vier depois do 9999 (assinatura digital) e ignorado.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterator

import duckdb

from .. import db
from ..config import logger, pasta_dados
from ..layouts import efd_contrib, efd_icms_ipi
from ..layouts.comum import Registro

AMOSTRA_ENCODING = 4 * 1024 * 1024


class ErroEFD(Exception):
    """Erro com mensagem pronta para o usuario (sem termos tecnicos)."""


# ---------------------------------------------------------------------------
# Encoding e linhas
# ---------------------------------------------------------------------------
def detectar_encoding(caminho: Path) -> str:
    """UTF-8 apenas se a amostra decodifica em UTF-8 e tem caracteres nao-ASCII.
    Caso contrario, ISO-8859-1 (que para texto ASCII e identico)."""
    with open(caminho, "rb") as f:
        amostra = f.read(AMOSTRA_ENCODING)
    if amostra.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        texto = amostra.decode("utf-8")
    except UnicodeDecodeError as e:
        # a amostra pode ter cortado um caractere multibyte no final
        if e.start >= len(amostra) - 3:
            try:
                texto = amostra[: e.start].decode("utf-8")
            except UnicodeDecodeError:
                return "latin-1"
        else:
            return "latin-1"
    return "utf-8" if any(ord(ch) > 127 for ch in texto) else "latin-1"


def separar_campos(linha: str) -> list[str] | None:
    """'|C100|0|1|...|' -> ['C100','0','1',...]. Retorna None para linha vazia."""
    linha = linha.rstrip("\r\n")
    if not linha.strip():
        return None
    s = linha.strip()
    if not s.startswith("|"):
        raise ValueError("linha nao comeca com |")
    if s.endswith("|"):
        s = s[1:-1]
    else:
        s = s[1:]
    return s.split("|")


def _data(txt: str) -> date | None:
    try:
        return datetime.strptime(txt.strip(), "%d%m%Y").date()
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Identificacao do arquivo pelo registro 0000
# ---------------------------------------------------------------------------
@dataclass
class Identificacao:
    tipo: str
    cod_ver: str
    cod_fin: str
    retificador: bool
    dt_ini: date
    dt_fin: date
    nome: str
    cnpj: str
    ie: str | None
    uf: str
    cod_mun: str | None
    suframa: str | None


def _mapear(registro: Registro, valores: list[str], cod_ver: str | None = None) -> dict[str, str]:
    versao, _ = registro.escolher_versao(len(valores), cod_ver)
    return dict(zip(versao.campos, valores))


def identificar(campos_0000: list[str]) -> Identificacao:
    """Detecta o tipo (ICMS/IPI ou Contribuicoes) pela posicao do DT_INI.

    ICMS/IPI: |0000|COD_VER|COD_FIN|DT_INI|...   (DT_INI na 4a posicao)
    Contribuicoes: |0000|COD_VER|TIPO_ESCRIT|IND_SIT_ESP|NUM_REC_ANTERIOR|DT_INI|...
    """
    if not campos_0000 or campos_0000[0] != "0000":
        raise ErroEFD("a primeira linha não começa com |0000|.")
    if len(campos_0000) > 3 and _data(campos_0000[3]):
        d = _mapear(efd_icms_ipi.REGISTROS["0000"], campos_0000)
        return Identificacao(
            tipo=efd_icms_ipi.TIPO, cod_ver=d.get("COD_VER", ""), cod_fin=d.get("COD_FIN", ""),
            retificador=d.get("COD_FIN", "0").strip() == "1",
            dt_ini=_data(d["DT_INI"]), dt_fin=_data(d.get("DT_FIN", "")),
            nome=d.get("NOME", ""), cnpj=d.get("CNPJ", ""), ie=d.get("IE") or None,
            uf=d.get("UF", ""), cod_mun=d.get("COD_MUN") or None, suframa=d.get("SUFRAMA") or None)
    if len(campos_0000) > 5 and _data(campos_0000[5]):
        d = _mapear(efd_contrib.REGISTROS["0000"], campos_0000)
        return Identificacao(
            tipo=efd_contrib.TIPO, cod_ver=d.get("COD_VER", ""), cod_fin=d.get("TIPO_ESCRIT", ""),
            retificador=d.get("TIPO_ESCRIT", "0").strip() == "1",
            dt_ini=_data(d["DT_INI"]), dt_fin=_data(d.get("DT_FIN", "")),
            nome=d.get("NOME", ""), cnpj=d.get("CNPJ", ""), ie=None,
            uf=d.get("UF", ""), cod_mun=d.get("COD_MUN") or None, suframa=d.get("SUFRAMA") or None)
    raise ErroEFD("o registro |0000| não tem o formato da EFD ICMS/IPI nem da EFD Contribuições "
                  "(não foi encontrada a data inicial do período).")


def ler_primeira_linha(caminho: Path, encoding: str) -> list[str]:
    with open(caminho, "rb") as f:
        bruto = f.readline()
    try:
        texto = bruto.decode(encoding)
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    try:
        campos = separar_campos(texto.lstrip("﻿"))
    except ValueError:
        campos = None
    if not campos or campos[0] != "0000":
        raise ErroEFD(f"O arquivo {caminho.name} não parece ser uma EFD: a primeira linha não "
                      "começa com |0000|. Verifique se é o arquivo .txt original.")
    return campos


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
@dataclass
class ResultadoCarga:
    arquivo_id: int | None
    nome_arquivo: str
    tipo: str | None
    situacao: str          # carregado | duplicado | erro
    mensagem: str
    ativo: bool = False
    qtd_linhas: int = 0
    avisos: list[str] = field(default_factory=list)


ProgressoFn = Callable[[float, str], None]


def _linhas_arquivo(caminho: Path, encoding: str, hasher, contador_bytes: list[int]
                    ) -> Iterator[tuple[int, str]]:
    """Le em streaming. O hash cobre o arquivo inteiro (inclusive apos o 9999)."""
    enc_linha = "utf-8" if encoding.startswith("utf-8") else encoding
    with open(caminho, "rb") as f:
        n = 0
        for bruto in f:
            hasher.update(bruto)
            contador_bytes[0] += len(bruto)
            n += 1
            try:
                texto = bruto.decode(enc_linha)
            except UnicodeDecodeError:
                texto = bruto.decode("latin-1")
            if n == 1:
                texto = texto.lstrip("﻿")
            yield n, texto


def carregar_arquivo(con: duckdb.DuckDBPyConnection, caminho: str | Path,
                     progresso: ProgressoFn | None = None) -> ResultadoCarga:
    caminho = Path(caminho)
    log = logger()
    try:
        return _carregar(con, caminho, progresso)
    except ErroEFD as e:
        log.warning("Arquivo %s recusado: %s", caminho, e)
        return ResultadoCarga(None, caminho.name, None, "erro", str(e))
    except Exception as e:  # noqa: BLE001 - detalhe vai para o log, nunca para a tela
        log.exception("Falha inesperada ao carregar %s", caminho)
        return ResultadoCarga(None, caminho.name, None, "erro",
                              f"Não foi possível ler o arquivo {caminho.name}. O detalhe técnico "
                              f"foi gravado em data/logs/zfm.log ({type(e).__name__}).")


def _carregar(con: duckdb.DuckDBPyConnection, caminho: Path,
              progresso: ProgressoFn | None) -> ResultadoCarga:
    if not caminho.is_file():
        raise ErroEFD(f"O arquivo {caminho} não foi encontrado.")
    tamanho = os.path.getsize(caminho)
    if tamanho == 0:
        raise ErroEFD(f"O arquivo {caminho.name} está vazio.")
    encoding = detectar_encoding(caminho)
    ident = identificar(ler_primeira_linha(caminho, encoding))
    if ident.dt_ini is None:
        raise ErroEFD(f"O arquivo {caminho.name} tem data inicial inválida no registro 0000.")
    registros = db.LAYOUTS[ident.tipo]

    hasher = hashlib.sha256()
    lidos_bytes = [0]
    contagem: Counter[str] = Counter()
    qtd_9900: dict[str, int] = {}
    qtd_lin_9999: int | None = None
    avisos: Counter[tuple[str, str, str]] = Counter()
    exemplo_aviso: dict[tuple[str, str, str], int] = {}
    ultimo_por_reg: dict[str, int] = {}
    cnpj_estab_atual: str = ident.cnpj or ""
    eh_contrib = ident.tipo == efd_contrib.TIPO
    encerrado = False
    total_linhas = 0
    # Arquivos temporarios por (registro, versao de layout): o DuckDB le direto
    pasta_tmp = Path(tempfile.mkdtemp(prefix="carga_", dir=pasta_dados()))
    saidas: dict[tuple[str, str], object] = {}
    versao_campos: dict[tuple[str, str], tuple[str, ...]] = {}
    cache_versao: dict[tuple[str, int], tuple] = {}

    def avisar(reg_: str, tipo_aviso: str, msg: str, linha: int) -> None:
        k = (reg_, tipo_aviso, msg)
        avisos[k] += 1
        exemplo_aviso.setdefault(k, linha)

    con.execute("BEGIN TRANSACTION")
    try:
        arquivo_id = con.execute("SELECT nextval('seq_arquivo')").fetchall()[0][0]
        ultimo_progresso = 0.0
        for linha_num, texto in _linhas_arquivo(caminho, encoding, hasher, lidos_bytes):
            if encerrado:
                continue  # assinatura digital ou lixo apos o 9999: so entra no hash
            s_ = texto.strip()
            if not s_:
                continue
            if s_[0] != "|":
                avisar("?", "linha_invalida", "Linha que não começa com |", linha_num)
                continue
            corpo = s_[1:-1] if s_.endswith("|") and len(s_) > 1 else s_[1:]
            p_ = corpo.find("|")
            reg_ = (corpo if p_ < 0 else corpo[:p_]).strip().upper()
            total_linhas = linha_num
            contagem[reg_] += 1
            ultimo_por_reg[reg_] = linha_num
            if reg_ == "9999":
                encerrado = True

            r = registros.get(reg_)
            if r is None:
                continue
            n_campos = corpo.count("|") + 1
            ck = (reg_, n_campos)
            sel = cache_versao.get(ck)
            if sel is None:
                sel = cache_versao[ck] = r.escolher_versao(n_campos, ident.cod_ver)
            versao, exato = sel
            precisa_campos = (not exato) or r.campo_cnpj_estab or reg_ in ("9900", "9999")
            if precisa_campos:
                valores = corpo.split("|")
                if not exato:
                    avisar(reg_, "numero_campos",
                           f"Linha com {n_campos - 1} campos; o leiaute conhecido tem "
                           f"{versao.n - 1}. Campos lidos por posição.", linha_num)
                    if len(valores) < versao.n:
                        valores = valores + [""] * (versao.n - len(valores))
                    else:
                        valores = valores[: versao.n]
                    corpo = "|".join(valores)
                d = dict(zip(versao.campos, valores))
                if r.campo_cnpj_estab:
                    cnpj_estab_atual = (d.get(r.campo_cnpj_estab) or cnpj_estab_atual).strip()
                if reg_ == "9900":
                    try:
                        qtd_9900[d["REG_BLC"].strip().upper()] = int(d["QTD_REG_BLC"])
                    except (KeyError, ValueError):
                        avisar(reg_, "valor_invalido", "QTD_REG_BLC inválido", linha_num)
                elif reg_ == "9999":
                    try:
                        qtd_lin_9999 = int(d["QTD_LIN"])
                    except (KeyError, ValueError):
                        pass
            if not r.carregar:
                continue
            if r.pai:
                pai_linha = ultimo_por_reg.get(r.pai)
                if pai_linha is None:
                    avisar(reg_, "sem_pai", f"Registro {reg_} sem registro pai {r.pai}", linha_num)
                    pai_txt = ""
                else:
                    pai_txt = str(pai_linha)
            else:
                pai_txt = ""
            # Blocos M, 1 e 9 da Contribuicoes sao da empresa (matriz)
            cnpj_linha = ident.cnpj if eh_contrib and reg_[0] in "M19" else cnpj_estab_atual
            chave = (reg_, versao.rotulo)
            f_ = saidas.get(chave)
            if f_ is None:
                versao_campos[chave] = versao.campos
                f_ = saidas[chave] = open(pasta_tmp / f"{reg_}_{versao.rotulo}.csv", "w",
                                          encoding="utf-8", newline="\n", buffering=1 << 20)
            f_.write(f"{arquivo_id}|{linha_num}|{pai_txt}|{cnpj_linha}|{versao.rotulo}|{corpo}\n")

            if progresso and linha_num % 20_000 == 0:
                frac = lidos_bytes[0] / tamanho
                if frac - ultimo_progresso >= 0.01:
                    ultimo_progresso = frac
                    progresso(min(frac, 0.95) * 0.8,
                              f"{caminho.name}: {linha_num:,} linhas lidas".replace(",", "."))

        for f_ in saidas.values():
            f_.close()
        if progresso:
            progresso(0.85, f"{caminho.name}: gravando no banco local")
        for chave, campos_ in versao_campos.items():
            db.inserir_csv(con, ident.tipo, chave[0], campos_,
                           pasta_tmp / f"{chave[0]}_{chave[1]}.csv")

        if not encerrado:
            avisar("9999", "sem_9999", "Arquivo sem registro 9999 (pode estar incompleto)", total_linhas)

        hash_hex = hasher.hexdigest()
        dup = con.execute(
            "SELECT arquivo_id, nome_arquivo FROM arquivos WHERE hash_sha256 = ?", [hash_hex]
        ).fetchall()
        dup = dup[0] if dup else None
        if dup:
            con.execute("ROLLBACK")
            return ResultadoCarga(dup[0], caminho.name, ident.tipo, "duplicado",
                                  f"Já carregado anteriormente (como {dup[1]}). Nada foi alterado.",
                                  ativo=True)

        # Contagens (para a checagem Q2)
        regs = set(contagem) | set(qtd_9900)
        con.executemany(
            "INSERT INTO arquivo_contagens VALUES (?, ?, ?, ?)",
            [[arquivo_id, r_, contagem.get(r_, 0), qtd_9900.get(r_)] for r_ in sorted(regs)])
        if avisos:
            con.executemany(
                "INSERT INTO avisos_carga VALUES (?, ?, ?, ?, ?, ?)",
                [[arquivo_id, k[0], k[1], k[2], n, exemplo_aviso[k]] for k, n in avisos.items()])

        raiz = (ident.cnpj or "")[:8]
        con.execute(
            """INSERT INTO arquivos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
               current_localtimestamp(), TRUE, NULL, ?, ?, ?)""",
            [arquivo_id, ident.tipo, ident.cnpj, raiz, ident.ie, ident.uf, ident.nome,
             ident.dt_ini, ident.dt_fin, ident.cod_ver, ident.cod_fin, ident.retificador,
             hash_hex, caminho.name, str(caminho), encoding, total_linhas, tamanho, qtd_lin_9999])
        ativo, msg_ret = _resolver_versoes(con, arquivo_id, ident)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        for f_ in saidas.values():
            if not f_.closed:
                f_.close()
        shutil.rmtree(pasta_tmp, ignore_errors=True)

    if progresso:
        progresso(1.0, f"{caminho.name}: concluido")
    lista_avisos = [f"{k[0]}: {k[2]} ({n} ocorrência(s))" for k, n in avisos.items()]
    tipo_txt = "EFD ICMS/IPI" if ident.tipo == efd_icms_ipi.TIPO else "EFD Contribuições"
    msg = (f"{tipo_txt} de {ident.dt_ini:%m/%Y}, CNPJ {ident.cnpj}"
           f"{' (retificadora)' if ident.retificador else ''}: {total_linhas:,} linhas lidas."
           ).replace(",", ".")
    if msg_ret:
        msg += " " + msg_ret
    logger().info("Carregado %s como arquivo_id=%s (%s)", caminho, arquivo_id, msg)
    return ResultadoCarga(arquivo_id, caminho.name, ident.tipo, "carregado", msg, ativo,
                          total_linhas, lista_avisos)


def _resolver_versoes(con: duckdb.DuckDBPyConnection, novo_id: int,
                      ident: Identificacao) -> tuple[bool, str]:
    """Mantem ativa so a versao mais recente do mesmo CNPJ/IE/periodo (DECISOES D-004).

    Retificadora prevalece sobre original. Entre arquivos do mesmo tipo
    (duas retificadoras), prevalece o carregado por ultimo.
    """
    chave_sql = "tipo = ? AND cnpj = ? AND dt_ini = ? AND dt_fin = ? AND coalesce(ie,'') = ?"
    params = [ident.tipo, ident.cnpj, ident.dt_ini, ident.dt_fin, ident.ie or ""]
    outros = con.execute(
        f"SELECT arquivo_id, retificador, nome_arquivo FROM arquivos "
        f"WHERE {chave_sql} AND ativo AND arquivo_id <> ?", params + [novo_id]).fetchall()
    if not outros:
        return True, ""
    if not ident.retificador and any(o[1] for o in outros):
        con.execute("UPDATE arquivos SET ativo = FALSE, substituido_por = ? WHERE arquivo_id = ?",
                    [outros[0][0], novo_id])
        return False, (f"ATENÇÃO: já existe retificadora carregada para este período "
                       f"({outros[0][2]}); este arquivo original ficou inativo.")
    ids = [o[0] for o in outros]
    con.execute(
        f"UPDATE arquivos SET ativo = FALSE, substituido_por = ? "
        f"WHERE arquivo_id IN ({', '.join('?' * len(ids))})", [novo_id] + ids)
    nomes = ", ".join(o[2] for o in outros)
    return True, f"ATENÇÃO: substitui a versão anterior do mesmo período ({nomes}), que ficou inativa."


def listar_txt(pasta: str | Path) -> list[Path]:
    p = Path(str(pasta).strip().strip('"'))
    if not p.exists():
        raise ErroEFD(f"A pasta {p} não foi encontrada. Confira o caminho copiado do Windows Explorer.")
    if p.is_file():
        return [p]
    arquivos = sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() == ".txt")
    if not arquivos:
        raise ErroEFD(f"Nenhum arquivo .txt foi encontrado na pasta {p}.")
    return arquivos
