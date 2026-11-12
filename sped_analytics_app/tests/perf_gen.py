"""Gera arquivos SPED volumosos (para teste de desempenho): python -m tests.perf_gen DESTINO N_DOCS N_FILIAIS"""
import random
import sys
from pathlib import Path

from tests.sample_data import line, money

ITENS = [(f"I{i:05d}", f"ITEM {i}", random.choice(["00", "01", "02", "07"]), f"{22030000 + i % 500:08d}")
         for i in range(2000)]
FORN = [f"{70000000 + i:08d}0001{i % 90 + 10:02d}" for i in range(500)]


def chave(f: int, n: int, comp: str) -> str:
    return f"35{comp[2:4]}{comp[5:7]}{FORN[n % 500]}55001{n:09d}1{f:04d}{n % 10000:04d}0"[:44]


def gen(dest: Path, ndocs: int, nfil: int, comp: str = "2024-03") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    m = comp[5:7]
    rnd = random.Random(42)
    matriz = "99999999000191"
    ec_lines = [line("0000", "006", "0", "", "", f"01{m}2024", f"31{m}2024", "EMPRESA PERF", matriz, "SP", "3550308",
                     "", "00", "0"), line("0001", "0")]
    ec_blocks = []
    for f in range(nfil):
        cnpj = f"99999999{f + 1:04d}{f % 90 + 10:02d}"
        ec_lines.append(line("0140", f"{f}", f"FILIAL {f}", cnpj, "SP", "", "3550308", "", ""))
        ec_lines += [line("0150", f"F{i}", f"FORNECEDOR {i}", "1058", c, "", "", "3550308", "", "", "", "", "")
                     for i, c in enumerate(FORN)]
        ec_lines += [line("0200", c, d, "", "", "UN", t, n, "", "", "", "") for c, d, t, n in ITENS]
        with open(dest / f"SF_{cnpj}_{comp}.txt", "w", encoding="latin-1", newline="") as sf:
            sf.write(line("0000", "017", "0", f"01{m}2024", f"31{m}2024", f"FILIAL {f}", cnpj, "", "SP", "1",
                          "3550308", "", "", "A", "1"))
            for i, c in enumerate(FORN):
                sf.write(line("0150", f"F{i}", f"FORNECEDOR {i}", "1058", c, "", "", "3550308", "", "", "", "", ""))
            for c, d, t, n in ITENS:
                sf.write(line("0200", c, d, "", "", "UN", t, n, "", "", "", "18,00", ""))
            ec_doc = [line("C010", cnpj, "2")]
            for n in range(ndocs):
                k = chave(f, n, comp)
                items = [(ITENS[rnd.randrange(2000)], rnd.randint(1, 50), round(rnd.uniform(1, 300), 2))
                         for _ in range(3)]
                tot = sum(q * p for _, q, p in items)
                sf.write(line("C100", "0", "1", f"F{n % 500}", "55", "00", "1", n, k, f"05{m}2024", f"06{m}2024",
                              money(tot + 10), "0", "0,00", "0,00", money(tot), "0", "10,00", "0,00", "0,00",
                              money(tot), money(tot * 0.18), "0,00", "0,00", "0,00", "", "", "", ""))
                ec_doc.append(line("C100", "0", "1", f"F{n % 500}", "55", "00", "1", n, k, f"05{m}2024",
                                   f"06{m}2024", money(tot + 10), "0", "0,00", "0,00", money(tot), "0", "10,00", "0,00",
                                   "0,00", money(tot), money(tot * 0.18), "0,00", "0,00", "0,00", "", "", "", ""))
                for j, ((c, d, t, nc), q, p) in enumerate(items, 1):
                    v = q * p
                    sf.write(line("C170", j, c, "", f"{q},00000", "UN", money(v), "0,00", "0", "000", "1102", "",
                                  money(v), "18,00", money(v * 0.18), "0,00", "0,00", "0,00", "0", "49", "", "0,00",
                                  "0,00", "0,00", "", "", "", "", "", "", "", "", "", "", "", "", "", ""))
                    ec_doc.append(line("C170", j, c, "", f"{q},00000", "UN", money(v), "0,00", "0", "000", "1102", "",
                                       money(v), "18,00", money(v * 0.18), "0,00", "0,00", "0,00", "0", "49", "",
                                       "0,00", "0,00", "0,00", "50", money(v), "1,6500", "", "", money(v * 0.0165),
                                       "50", money(v), "7,6000", "", "", money(v * 0.076), ""))
                sf.write(line("C190", "000", "1102", "18,00", money(tot + 10), money(tot), money(tot * 0.18), "0,00",
                              "0,00", "0,00", "0,00", ""))
            sf.write(line("9999", "0"))
            ec_blocks += ec_doc
    with open(dest / f"EC_{matriz}_{comp}.txt", "w", encoding="latin-1", newline="") as ec:
        ec.writelines(ec_lines)
        ec.write(line("C001", "0"))
        ec.writelines(ec_blocks)
        ec.write(line("9999", "0"))


if __name__ == "__main__":
    gen(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
