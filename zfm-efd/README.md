# zfm-efd — visão técnica

Aplicação local (Python + Streamlit + DuckDB) para quantificar o benefício da ZFM a partir das
EFD ICMS/IPI e EFD Contribuições e simular o regime pós-Reforma. Especificação: SPEC_ZFM_EFD.md
(v1.3, fornecida pelo usuário; não versionada aqui). Manual do usuário: `MANUAL.md`. Decisões: `DECISOES.md`.

## Situação

Fluxo implementado (As Is × To Be, 9 etapas): ingestão → perímetro → base de operações única →
carga As Is lida da apuração → reconciliação R1–R5 → parâmetros → motor To Be 2027–2033 mês a mês
por empresa → diferença To Be − As Is (positivo = perda) → cenários, ponte, ranking e Excel.
Benefício "regime geral − ZFM" mantido como informativo. Análise por cenário ZFM (C1–C5): matriz
cenário × empresa, As Is escriturado × To Be por cenário/tributo/ano, IPI por produto, alertas e não
classificados. Importação em segundo plano; visões materializadas por versão dos dados.

## Estrutura

```
iniciar.bat / diagnostico.bat / testar.bat   duplo clique (Windows)
ferramentas/        scripts dos .bat (só biblioteca padrão)
app.py, telas/      telas Streamlit (st.navigation)
zfm/layouts/        dicionários de campos por registro, com versões
zfm/parsers/base.py leitura em streaming → arquivos temporários → DuckDB (read_csv)
zfm/importacao.py   importação em segundo plano (thread), progresso e cancelamento
zfm/db.py           esquema: arquivos, arquivo_contagens, avisos_carga, raw_<icms|contrib>_<reg>
zfm/empresas.py     cadastro automático de empresas/estabelecimentos
zfm/qualidade.py    Q1 (completude) e Q2 (bloco 9)
zfm/params.py       tabelas de parâmetros (CSV em data/params; modelos em params/)
zfm/cfop.py         classificação automática de CFOP
zfm/visoes.py       visões (v_docs, v_saidas_item, v_entradas_item, v_base_operacoes, v_cenarios, v_apur_*);
                    preparar() materializa as pesadas e só refaz quando dados/parâmetros mudam (_meta)
zfm/filtros.py      filtro global (empresas, estabelecimentos, período) aplicado no SQL
zfm/as_is.py        carga As Is lida da apuração, anualização, R5, saldos credores
zfm/conciliacoes.py Q3–Q13 (R1 = Q5, R2 = Q6, R3 = Q8, R4 = Q7)
zfm/simulacao.py    motor To Be, diferença, ponte, composição saídas × entradas, absorção
zfm/cenarios.py     cenários C1–C5: matriz, As Is × To Be por cenário, IPI por produto, conferências, alertas
zfm/beneficio_atual.py  benefício ZFM (informativo)
zfm/ui.py           componentes das telas (estilo local, cartões, tabelas, cache por versão dos dados)
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
