# zfm-efd — visão técnica

Aplicação local (Python + Streamlit + DuckDB) para quantificar o benefício da ZFM a partir das
EFD ICMS/IPI e EFD Contribuições e simular o regime pós-Reforma. Especificação: SPEC_ZFM_EFD.md
(v1.3, fornecida pelo usuário; não versionada aqui). Manual do usuário: `MANUAL.md`. Decisões: `DECISOES.md`.

## Situação

| Fase | Entrega | Situação |
| --- | --- | --- |
| 0 | `iniciar.bat`, `diagnostico.bat`, `testar.bat`, ambiente `.venv` | pronta; falta validar no Windows do usuário |
| 1 | Parser das duas EFDs + DuckDB + tela de carga + Q1/Q2 | pronta |
| 2–7 | Visões, conciliações, parâmetros, benefício atual, simulação, exportação | a fazer |

## Estrutura

```
iniciar.bat / diagnostico.bat / testar.bat   duplo clique (Windows)
ferramentas/        scripts dos .bat (só biblioteca padrão)
app.py, pages/      telas Streamlit (st.navigation)
zfm/layouts/        dicionários de campos por registro, com versões
zfm/parsers/base.py leitura em streaming → arquivos temporários → DuckDB (read_csv)
zfm/db.py           esquema: arquivos, arquivo_contagens, avisos_carga, raw_<icms|contrib>_<reg>
zfm/empresas.py     cadastro automático de empresas/estabelecimentos
zfm/qualidade.py    Q1 (completude) e Q2 (bloco 9)
tests/              pytest; tests/fixtures/gerador.py gera EFDs sintéticas
data/               (fora do git) banco zfm.duckdb, logs, arquivos temporários
```

## Tabelas brutas

Uma por registro (`raw_icms_c100`, `raw_contrib_m210`...). Colunas: `arquivo_id`, `linha_num`,
`pai_linha` (linha do registro pai no mesmo arquivo), `cnpj_estab`, `layout_versao` + os campos do
Guia Prático com tipo derivado do nome (`VL_*` → `DECIMAL(18,2)`, `ALIQ*` → `DECIMAL(18,4)`,
`DT_*` → `DATE`...). Só arquivos com `arquivos.ativo = TRUE` entram nas análises.

## Desenvolvimento

```bash
python -m venv .venv && .venv/bin/pip install --only-binary=:all: -r requirements.txt
.venv/bin/python -m pytest -q                 # todos os testes
.venv/bin/python -m pytest -q -m "not lento"  # sem o teste de 1 milhão de linhas
.venv/bin/python -m tests.fixtures.gerador data/exemplo_sintetico   # EFDs sintéticas
```

Regras: nenhum dado real no repositório; nenhum pacote fora do `requirements.txt`
(`tests/test_dependencias.py`); nenhuma chamada de rede.
