"""Gerador de arquivos SPED sintéticos (leiaute oficial) para testes e demonstração.

Cenário: Matriz A (SP) e Filial B (RJ), competências 2024-01 e 2024-02.
"""
from __future__ import annotations

from pathlib import Path

CNPJ_A = "11111111000191"
CNPJ_B = "11111111000272"
F_X = "22222222000100"   # fornecedor de mercadorias
F_Y = "33333333000100"   # fornecedor de insumos
F_T = "44444444000100"   # transportadora
F_E = "55555555000100"   # distribuidora de energia


def money(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def line(*fields) -> str:
    return "|" + "|".join("" if f is None else str(f) for f in fields) + "|\r\n"


def chave(n: int, cnpj_emit: str, mod: str = "55", comp: str = "2024-01") -> str:
    return ("35" + comp[2:4] + comp[5:7] + cnpj_emit + mod + "001" + f"{n:09d}" + "1" + f"{n:08d}" + "0")[:44].ljust(44, "0")


def _dates(comp: str) -> tuple[str, str]:
    y, m = comp.split("-")
    last = {"01": 31, "02": 29, "03": 31}[m]
    return f"01{m}{y}", f"{last}{m}{y}"


def sped_fiscal(cnpj: str, uf: str, comp: str, cod_fin: str = "0", extra_valor: float = 0.0) -> str:
    di, df = _dates(comp)
    m = comp[5:7]
    out = [line("0000", "017", cod_fin, di, df, f"EMPRESA TESTE {cnpj[-6:]}", cnpj, "", uf, "123456789",
                "3550308" if uf == "SP" else "3304557", "", "", "A", "1"),
           line("0001", "0"),
           line("0150", "FX", "FORNECEDOR X LTDA", "1058", F_X, "", "111", "3550308", "", "RUA A", "1", "", "C"),
           line("0175", f"15{m}2024", "03", "FORNECEDOR X ANTIGO"),
           line("0150", "FY", "FORNECEDOR Y SA", "1058", F_Y, "", "222", "3106200", "", "RUA B", "2", "", "C"),
           line("0150", "FT", "TRANSPORTADORA T", "1058", F_T, "", "333", "4106902", "", "RUA C", "3", "", "C"),
           line("0150", "FE", "ENERGIA E", "1058", F_E, "", "444", "3550308", "", "RUA D", "4", "", "C"),
           line("0190", "UN", "UNIDADE"),
           line("0190", "KG", "QUILO"),
           line("0200", "P1", "CERVEJA LATA", "7890000000011", "", "UN", "00", "22030000", "", "22", "", "18,00", ""),
           line("0205", "CERVEJA ANTIGA", "01012023", "31122023", "OLD1"),
           line("0200", "P2", "MALTE", "", "", "KG", "01", "11071010", "", "11", "", "", ""),
           line("0200", "P3", "MATERIAL ESCRITORIO", "", "", "UN", "07", "48201000", "", "48", "", "", ""),
           line("0400", "N1", "COMPRA"),
           line("0500", "01012020", "01", "A", "5", "1.1.01", "ESTOQUE"),
           line("0990", "0"),
           line("C001", "0")]
    n0 = 1000 if cnpj == CNPJ_A else 2000
    # NF1: fornecedor X, 2 itens + frete 10,00 no cabeçalho (rateado ao C190), FCP em um C190
    k1 = chave(n0 + 1, F_X, comp=comp)
    v1, v2 = 1000.00 + extra_valor, 500.00
    out += [line("C100", "0", "1", "FX", "55", "00", "1", n0 + 1, k1, f"05{m}2024", f"06{m}2024",
                 money(v1 + v2 + 10 + 90), "0", "0,00", "0,00", money(v1 + v2), "0", "10,00", "0,00", "0,00",
                 money(v1 + v2), money(v1 * 0.18 + v2 * 0.12), "0,00", "0,00", "90,00", "", "", "", ""),
            line("C170", "1", "P1", "", "100,00000", "UN", money(v1), "0,00", "0", "000", "1102", "N1",
                 money(v1), "18,00", money(v1 * 0.18), "0,00", "0,00", "0,00", "0", "00", "999", money(v1),
                 "9,00", "90,00", "", "", "", "", "", "", "", "", "", "", "", "", "1.1.01", ""),
            line("C170", "2", "P2", "", "50,00000", "KG", money(v2), "0,00", "0", "000", "1101", "N1",
                 money(v2), "12,00", money(v2 * 0.12), "0,00", "0,00", "0,00", "0", "49", "999", "0,00",
                 "0,00", "0,00", "", "", "", "", "", "", "", "", "", "", "", "", "1.1.01", ""),
            line("C190", "000", "1102", "18,00", money(v1 + 90 + 10 * v1 / (v1 + v2)), money(v1), money(v1 * 0.18),
                 "0,00", "0,00", "0,00", "90,00", ""),
            line("C191", "20,00", "0,00", "0,00"),
            line("C190", "000", "1101", "12,00", money(v2 + 10 * v2 / (v1 + v2)), money(v2), money(v2 * 0.12),
                 "0,00", "0,00", "0,00", "0,00", "")]
    # NF2: emissão própria na entrada (IND_EMIT=0) sem C170 — itens virão do C170 da EFD-Contribuições
    k2 = chave(n0 + 2, cnpj, comp=comp)
    out += [line("C100", "0", "0", "FY", "55", "00", "1", n0 + 2, k2, f"10{m}2024", f"10{m}2024", "300,00", "0",
                 "0,00", "0,00", "300,00", "9", "0,00", "0,00", "0,00", "300,00", "36,00", "0,00", "0,00", "0,00",
                 "", "", "", ""),
            line("C190", "000", "1101", "12,00", "300,00", "300,00", "36,00", "0,00", "0,00", "0,00", "0,00", "")]
    # NF3: uso e consumo, sem crédito na EFD-Contribuições
    k3 = chave(n0 + 3, F_Y, comp=comp)
    out += [line("C100", "0", "1", "FY", "55", "00", "1", n0 + 3, k3, f"12{m}2024", f"12{m}2024", "80,00", "0",
                 "0,00", "0,00", "80,00", "9", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00",
                 "", "", "", ""),
            line("C170", "1", "P3", "", "10,00000", "UN", "80,00", "0,00", "0", "090", "1556", "N1", "0,00",
                 "0,00", "0,00", "0,00", "0,00", "0,00", "0", "49", "999", "0,00", "0,00", "0,00", "", "", "", "",
                 "", "", "", "", "", "", "", "", "", ""),
            line("C190", "090", "1556", "0,00", "80,00", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00", "")]
    # NF4 cancelada (excluída) e NF5 saída (ignorada)
    out += [line("C100", "0", "1", "FY", "55", "02", "1", n0 + 4, chave(n0 + 4, F_Y, comp=comp), "", "", "", "", "", "",
                 "", "", "", "", "", "", "", "", "", "", "", "", "", ""),
            line("C100", "1", "0", "FY", "55", "00", "1", n0 + 5, chave(n0 + 5, cnpj, comp=comp), f"15{m}2024", f"15{m}2024",
                 "999,00", "0", "0,00", "0,00", "999,00", "0", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00",
                 "0,00", "", "", "", ""),
            line("C170", "1", "P1", "", "1,00000", "UN", "999,00", "0,00", "0", "000", "5102", "", "0,00", "0,00",
                 "0,00", "0,00", "0,00", "0,00", "0", "50", "", "0,00", "0,00", "0,00", "", "", "", "", "", "", "",
                 "", "", "", "", "", "", ""),
            line("C190", "000", "5102", "0,00", "999,00", "0,00", "0,00", "0,00", "0,00", "0,00", "0,00", "")]
    # Energia elétrica (C500/C590)
    out += [line("C500", "0", "1", "FE", "06", "00", "1", "", "", "9001", f"20{m}2024", f"21{m}2024", "250,00",
                 "0,00", "250,00", "0,00", "0,00", "0,00", "250,00", "45,00", "0,00", "0,00", "", "", "", "1", ""),
            line("C590", "000", "1252", "18,00", "250,00", "250,00", "45,00", "0,00", "0,00", "0,00", "")]
    out += [line("C990", "0"), line("D001", "0")]
    # Frete CT-e (D100/D190)
    kd = chave(n0 + 7, F_T, "57", comp=comp)
    out += [line("D100", "0", "1", "FT", "57", "00", "1", "", n0 + 7, kd, f"07{m}2024", f"08{m}2024", "0", "",
                 "120,00", "0,00", "1", "120,00", "120,00", "14,40", "0,00", "", "", "4106902", "3550308"),
            line("D190", "000", "1353", "12,00", "120,00", "120,00", "14,40", "0,00", ""),
            line("D990", "0"), line("9001", "0"), line("9990", "0"), line("9999", "0")]
    return "".join(out)


def efd_contrib(comp: str, tipo_escrit: str = "0", extra_pis: float = 0.0) -> str:
    di, df = _dates(comp)
    m = comp[5:7]
    out = [line("0000", "006", tipo_escrit, "", "", di, df, "EMPRESA TESTE MATRIZ", CNPJ_A, "SP", "3550308", "",
                "00", "0"),
           line("0001", "0"),
           line("0110", "1", "1", "1", ""),
           line("0140", "001", "EMPRESA TESTE MATRIZ", CNPJ_A, "SP", "123", "3550308", "", ""),
           line("0150", "FX", "FORNECEDOR X LTDA", "1058", F_X, "", "", "3550308", "", "", "", "", ""),
           line("0150", "FY", "FORNECEDOR Y SA", "1058", F_Y, "", "", "3106200", "", "", "", "", ""),
           line("0150", "FT", "TRANSPORTADORA T", "1058", F_T, "", "", "4106902", "", "", "", "", ""),
           line("0150", "FE", "ENERGIA E", "1058", F_E, "", "", "3550308", "", "", "", "", ""),
           line("0150", "FS", "ESCRITORIO SERVICOS", "1058", "66666666000100", "", "", "3550308", "", "", "", "", ""),
           line("0200", "P1", "CERVEJA LATA", "", "", "UN", "00", "22030000", "", "22", "", ""),
           line("0200", "P2", "MALTE", "", "", "KG", "01", "11071010", "", "11", "", ""),
           line("0200", "S1", "SERVICO MANUTENCAO", "", "", "UN", "09", "", "", "", "1401", ""),
           line("0140", "002", "EMPRESA TESTE FILIAL RJ", CNPJ_B, "RJ", "456", "3304557", "", ""),
           line("0150", "FX", "FORNECEDOR X LTDA", "1058", F_X, "", "", "3550308", "", "", "", "", ""),
           line("0200", "P1", "CERVEJA LATA", "", "", "UN", "00", "22030000", "", "22", "", ""),
           line("0990", "0"),
           line("A001", "0"),
           line("A010", CNPJ_A),
           line("A100", "0", "1", "FS", "00", "1", "", "77", "", f"03{m}2024", f"03{m}2024", "1000,00", "1", "0,00",
                "1000,00", "16,50", "1000,00", "76,00", "0,00", "0,00", "50,00"),
           line("A170", "1", "S1", "", "1000,00", "0,00", "03", "0", "50", "1000,00", "1,6500", "16,50", "50",
                "1000,00", "7,6000", "76,00", "3.1.01", ""),
           line("A990", "0"),
           line("C001", "0"),
           line("C010", CNPJ_A, "2")]
    v1 = 1000.00
    n0 = 1000
    pis1 = round(v1 * 0.0165, 2) + extra_pis
    out += [line("C100", "0", "1", "FX", "55", "00", "1", n0 + 1, chave(n0 + 1, F_X, comp=comp), f"05{m}2024", f"06{m}2024",
                 "1600,00", "0", "0,00", "0,00", "1500,00", "0", "10,00", "0,00", "0,00", "1500,00", "240,00", "0,00",
                 "0,00", "90,00", money(pis1 + 8.25), money(76 + 38), "", ""),
            line("C170", "1", "P1", "", "100,00000", "UN", "1000,00", "0,00", "0", "000", "1102", "", "1000,00",
                 "18,00", "180,00", "0,00", "0,00", "0,00", "0", "00", "", "1000,00", "9,00", "90,00", "50",
                 "1000,00", "1,6500", "", "", money(pis1), "50", "1000,00", "7,6000", "", "", "76,00", "1.1.01"),
            line("C170", "2", "P2", "", "50,00000", "KG", "500,00", "0,00", "0", "000", "1101", "", "500,00",
                 "12,00", "60,00", "0,00", "0,00", "0,00", "0", "49", "", "0,00", "0,00", "0,00", "50", "500,00",
                 "1,6500", "", "", "8,25", "50", "500,00", "7,6000", "", "", "38,00", "1.1.01")]
    # NF de emissão própria (sem C170 no SPED Fiscal)
    out += [line("C100", "0", "0", "FY", "55", "00", "1", n0 + 2, chave(n0 + 2, CNPJ_A, comp=comp), f"10{m}2024",
                 f"10{m}2024", "300,00", "0", "0,00", "0,00", "300,00", "9", "0,00", "0,00", "0,00", "300,00", "36,00",
                 "0,00", "0,00", "0,00", "4,95", "22,80", "", ""),
            line("C170", "1", "P2", "", "30,00000", "KG", "300,00", "0,00", "0", "000", "1101", "", "300,00",
                 "12,00", "36,00", "0,00", "0,00", "0,00", "0", "49", "", "0,00", "0,00", "0,00", "50", "300,00",
                 "1,6500", "", "", "4,95", "50", "300,00", "7,6000", "", "", "22,80", "1.1.01")]
    # Energia elétrica (C500/C501/C505)
    out += [line("C500", "FE", "06", "00", "1", "", "9001", f"20{m}2024", f"21{m}2024", "250,00", "45,00", "",
                 "4,13", "19,00", ""),
            line("C501", "50", "250,00", "04", "250,00", "1,6500", "4,13", "3.1.02"),
            line("C505", "50", "250,00", "04", "250,00", "7,6000", "19,00", "3.1.02")]
    # Filial B: escrituração consolidada (C190 + C191/C195)
    out += [line("C010", CNPJ_B, "1"),
            line("C190", "55", di, df, "P1", "22030000", "", "1590,00"),
            line("C191", F_X, "50", "1102", "1590,00", "0,00", "1500,00", "1,6500", "", "", "24,75", "1.1.01"),
            line("C195", F_X, "50", "1102", "1590,00", "0,00", "1500,00", "7,6000", "", "", "114,00", "1.1.01"),
            line("C990", "0"),
            line("D001", "0"),
            line("D010", CNPJ_A),
            line("D100", "0", "1", "FT", "57", "00", "1", "", "1007", chave(1007, F_T, "57", comp=comp), f"07{m}2024",
                 f"08{m}2024", "0", "", "120,00", "0,00", "1", "120,00", "120,00", "14,40", "0,00", "", "3.1.03"),
            line("D101", "0", "120,00", "50", "03", "120,00", "1,6500", "1,98", "3.1.03"),
            line("D105", "0", "120,00", "50", "03", "120,00", "7,6000", "9,12", "3.1.03"),
            line("D990", "0"),
            line("F001", "0"),
            line("F010", CNPJ_A),
            line("F100", "0", "FS", "", f"28{m}2024", "2000,00", "50", "2000,00", "1,6500", "33,00", "50",
                 "2000,00", "7,6000", "152,00", "06", "0", "3.1.04", "", "ALUGUEL PREDIO"),
            line("F120", "09", "04", "0", "1", "500,00", "0,00", "50", "500,00", "1,6500", "8,25", "50", "500,00",
                 "7,6000", "38,00", "1.2.01", "", "DEPRECIACAO MAQUINAS"),
            line("F990", "0")]
    out += bloco_m(comp)
    out += [line("9001", "0"), line("9990", "0"), line("9999", "0")]
    return "".join(out)


# Bases de crédito dos documentos acima (CST 50, alíquota básica), por natureza (Tabela 4.3.7):
#   01 revenda: C170 CFOP 1102 (1.000) + C191 CFOP 1102 (1.500); 02 insumo: C170 CFOP 1101 (500 + 300);
#   03 serviço: A170 (1.000) + D101 (120); 04 energia: C501 (250); 06 F100 (2.000); 09 F120 (500)
BASES_CREDITO = {"01": 2500.0, "02": 800.0, "03": 1120.0, "04": 250.0, "06": 2000.0, "09": 500.0}
RECEITA_BRUTA = 20000.0


def bloco_m(comp: str) -> list[str]:
    """Apuração (Bloco M) e controle de créditos (1100/1500) coerentes com os documentos de efd_contrib().
    Em 2024-02: ajuste de acréscimo de crédito (M110/M510) e uso de crédito de período anterior (1100/1500)."""
    fev = comp == "2024-02"
    base = sum(BASES_CREDITO.values())
    out = [line("M001", "0")]
    for trib, aliq, cod_rec, aj, ant in (("PIS", 1.65, "691201", 10.0, 50.0), ("COFINS", 7.6, "585601", 40.0, 200.0)):
        cred = round(base * aliq / 100, 2)
        aj = aj if fev else 0.0
        ant = ant if fev else 0.0
        disp = round(cred + aj, 2)
        cont = round(RECEITA_BRUTA * aliq / 100, 2)
        dev = round(cont - disp - ant, 2)
        r_cred, r_det, r_aj, r_cons, r_rec, r_det_cont, r_nt, r_nt_det = (
            ("M100", "M105", "M110", "M200", "M205", "M210", "M400", "M410") if trib == "PIS"
            else ("M500", "M505", "M510", "M600", "M605", "M610", "M800", "M810"))
        out.append(line(r_cred, "101", "0", money(base), f"{aliq:.4f}".replace(".", ","), "", "", money(cred),
                        money(aj), "0,00", "0,00", money(disp), "0", money(disp), "0,00"))
        for nat, b in BASES_CREDITO.items():
            out.append(line(r_det, nat, "50", money(b), "", money(b), money(b), "", "", ""))
        if aj:
            out.append(line(r_aj, "1", money(aj), "05", "123", "AJUSTE DE TESTE", f"01{comp[5:7]}{comp[:4]}"))
        out.append(line(r_cons, money(cont), money(disp), money(ant), money(dev), "0,00", "0,00", money(dev),
                        "0,00", "0,00", "0,00", "0,00", money(dev)))
        out.append(line(r_rec, "08", cod_rec, money(dev)))
        out.append(line(r_det_cont, "01", money(RECEITA_BRUTA), money(RECEITA_BRUTA), "0,00", "0,00",
                        money(RECEITA_BRUTA), f"{aliq:.4f}".replace(".", ","), "", "", money(cont), "0,00", "0,00",
                        "0,00", "0,00", money(cont)))
        out.append(line(r_nt, "06", "1000,00", "3.1.10", ""))
        out.append(line(r_nt_det, "999", "1000,00", "3.1.10", ""))
    out.append(line("M990", "0"))
    out.append(line("1001", "0" if fev else "1"))
    if fev:
        for reg, apu, usado_ant, usado in (("1100", 500.0, 100.0, 50.0), ("1500", 2000.0, 400.0, 200.0)):
            disp = apu - usado_ant
            out.append(line(reg, "122023", "01", "", "101", money(apu), "0,00", money(apu), money(usado_ant),
                            "0,00", "0,00", money(disp), money(usado), "0,00", "0,00", "0,00", "0,00",
                            money(disp - usado)))
    out.append(line("1990", "0"))
    return out


def write_scenario(dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for comp in ("2024-01", "2024-02"):
        for cnpj, uf in ((CNPJ_A, "SP"), (CNPJ_B, "RJ")):
            p = dest / f"SPED_FISCAL_{cnpj}_{comp}.txt"
            p.write_bytes(sped_fiscal(cnpj, uf, comp).encode("latin-1"))
            paths.append(p)
        p = dest / "contrib" / f"EFD_CONTRIB_{CNPJ_A}_{comp}.txt"
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(efd_contrib(comp).encode("latin-1"))
        paths.append(p)
    return paths


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/exemplo_sped")
    for p in write_scenario(out):
        print(p)
