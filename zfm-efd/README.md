# zfm-efd — visão técnica

Aplicação local (Python + Streamlit + DuckDB) para quantificar o benefício da ZFM a partir das
EFD ICMS/IPI e EFD Contribuições e simular o regime pós-Reforma. Especificação: SPEC_ZFM_EFD.md
(v1.3, fornecida pelo usuário; não versionada aqui). Manual do usuário: `MANUAL.md`. Decisões: `DECISOES.md`.

## Situação

| Fase | Entrega | Situação |
| --- | --- | --- |
| 0 | `iniciar.bat`, `diagnostico.bat`, `testar.bat`, ambiente `.venv` | pronta; validada pelo usuário |
| 1 | Parser das duas EFDs + DuckDB + tela de carga + Q1/Q2 | pronta; validada com EFDs reais |
| 2 | Visões normalizadas + telas Saídas, Entradas, Apurações | pronta |
| 3 | Conciliações Q3–Q11 | pronta |
| 4 | Parâmetros (CSV) + preenchimento a partir das EFDs | pronta |
| 5 | Benefício atual | pronta |
| 6 | Simulação, teses, teste de absorção | pronta |
| 7 | Exportação Excel | pronta |

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
zfm/params.py       tabelas de parâmetros (CSV em data/params; modelos em params/)
zfm/cfop.py         classificação automática de CFOP
zfm/visoes.py       visões normalizadas (v_docs, v_saidas_item, v_saidas_dest, v_entradas_item, v_apur_*)
zfm/conciliacoes.py Q3–Q11
zfm/beneficio_atual.py  benefício As Is (7.5)
zfm/simulacao.py    simulação pós-reforma e teste de absorção (7.6)
zfm/exportacao.py   Excel
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
