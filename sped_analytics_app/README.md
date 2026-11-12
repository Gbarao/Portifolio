# Sistema Local de Inteligência e Consolidação Fiscal

Consolidação das **entradas** do SPED Fiscal (EFD ICMS/IPI) com a EFD-Contribuições (PIS/COFINS):
uma única grade com ICMS, ICMS-ST, FCP, IPI, PIS e COFINS por Empresa/Filial → Fornecedor → CFOP → Item →
Nota Fiscal. A execução é 100% local (DuckDB embarcado + Parquet) e nenhum dado sai da máquina.

## Instalação e execução

Requisito: Python 3.11 ou superior (testado com 3.13).

| Sistema | Instalar (uma vez) | Abrir |
|---|---|---|
| Windows | `instalar.bat` | `iniciar.bat` (ou `iniciar_demonstracao.bat` / `abrir_no_navegador.bat`) |
| macOS/Linux | `./instalar.sh` | `./iniciar.sh` |

Os instaladores criam o ambiente isolado `.venv`, instalam `requirements.txt` (versões testadas) e tentam
instalar `pywebview` (janela nativa; sem ele a interface abre no navegador em 127.0.0.1).
Guia rápido: `LEIA-ME.txt`.

Linha de comando (com o ambiente ativado ou via `.venv`):

```bash
python -m app.main                 # abre a aplicação (janela nativa se pywebview estiver instalado)
python -m app.main --browser       # abre no navegador local (http://127.0.0.1:8765)
python -m app.main --demo          # gera arquivos SPED de exemplo, importa e abre a interface
python -m app.main --importar D:\SPED\2024   # importação em lote pela linha de comando (sem interface)
python -m app.main --reconsolidar  # reconstrói a tabela fato a partir dos dados brutos
```

Variáveis de ambiente opcionais:

| Variável | Uso |
|---|---|
| `SPED_DATA_DIR` | move o cofre de dados (padrão: `./data`) |
| `SPED_PARSER_WORKERS` | número de processos de leitura (padrão: núcleos − 1) |
| `SPED_DUCKDB_MEMORY` | teto de RAM do DuckDB (padrão `60%`; acima disso o DuckDB usa disco) |
| `SPED_UI_PORT` | porta local da interface (padrão 8765) |

## Arquitetura

| Camada | Implementação |
|---|---|
| Detecção | `parser/detector.py`: identifica o tipo pelo registro 0000 (posição de `DT_INI`), finalidade (original/retificadora), CNPJ, competência e SHA-256 |
| Parsing | `parser/sped_fiscal.py` e `parser/efd_contrib.py`: leitura linha a linha com máquina de estados, em processos paralelos (`spawn`). Lê só as entradas (`IND_OPER=0`) e para no registro 9999 |
| Normalização | `parser/normalizer.py`: buffers colunares, conversão vetorizada com PyArrow (`DECIMAL(18,6)` exato e datas) e Parquet ZSTD em lotes de 200 mil linhas |
| Banco | `database/engine.py`: DuckDB em arquivo único (`data/sped_master.duckdb`), carga transacional por arquivo, deduplicação e retificadoras |
| Consolidação | `database/queries_join.sql`: SQL em etapas (`-- @step`) com um template genérico de rateio (`-- @template alocar`) |
| Filtros | `database/filter_builder.py`: regras JSON convertidas em SQL parametrizado, com whitelist de colunas e operadores |
| Análise | `database/analytics.py` (agregação multinível, mês a mês, drill-down) e `database/audit.py` (divergências) |
| Interface | NiceGUI + AG Grid Community (`ui/*.py`), com tema claro/escuro |
| Exportação | `exporter/excel_writer.py`: XLSX em streaming (divide em abas acima de 1.048.575 linhas), CSV no padrão BR (`;` e vírgula decimal) e Parquet |

## Regras de negócio implementadas

1. **LEFT JOIN mestre.** O SPED Fiscal é a base (valor contábil, quantidade, ICMS, ST, FCP e IPI). A EFD-Contribuições
   acrescenta CST, base, alíquota, valor e `NAT_BC_CRED` de PIS e COFINS. Uma entrada sem correspondência aparece com
   PIS/COFINS vazios e `status_efd = "Sem Crédito / Não Escriturado na EFD-Contribuições"`.
2. **Filiais.** No SPED Fiscal a filial é o CNPJ do 0000. Na EFD-Contribuições é o CNPJ do 0140 (cadastros) e do
   A010/C010/D010/F010 (movimento), mantido na máquina de estados do parser.
3. **Fornecedor unificado.** `COD_PART` → 0150 do próprio arquivo → CNPJ/CPF, raiz (8 dígitos), razão social e UF
   (código IBGE do município; `EX` para exterior). O 0175 (campo 03 = NOME) fornece `nome_part_na_data`, ou seja,
   o nome vigente na data do documento.
4. **Itens.** O cadastro 0200 de cada arquivo fornece `TIPO_ITEM`, NCM, CEST e código de barras. O 0205 e
   `COD_ANT_ITEM` geram `cod_item_unificado` (de-para por filial). `chave_item_global = NCM|código` permite a visão
   global.
5. **C170 × C190.** A base de cada item é `VL_ITEM − VL_DESC + ICMS-ST + IPI`. A diferença para o `VL_OPR` do C190
   (mesmo CST/CFOP/alíquota) é rateada proporcionalmente ao `VL_ITEM`, e o resíduo de centavos vai para o maior item.
   A soma por documento fecha 100% com o C190 (há teste automatizado). O FCP do C191 é rateado da mesma forma.
   - Sem C170 no SPED Fiscal (Exceção 2): os itens vêm do C170 da EFD-Contribuições, localizados pela chave da NF-e.
   - Sem itens em nenhum dos dois arquivos: é gerado o item sintético `_SEM_ITEM_C190_` com os valores do C190.
6. **Cascata de cruzamento de PIS/COFINS** (coluna `nivel_cruzamento_efd`):
   - `N1_ITEM`: CNPJ filial + CHV_NFE + NUM_ITEM.
   - `N2_ITEM_CFOP`: CNPJ filial + CHV_NFE + COD_ITEM + CFOP, com rateio do saldo não usado no N1.
   - `N3_CONSOLIDADO_C190`: CNPJ filial + competência + CNPJ fornecedor + CFOP + COD_ITEM (C190 com C191/C195).
   - `DOC_CHAVE` / `DOC_NUMERO`: C500, D100, D500 e D700 contra C501/C505, D101/D105 e D501/D505, pela chave ou, na
     falta dela, por fornecedor + número + série na mesma competência.
   - `EC_EXCLUSIVO`: A100/A170 (CFOP `SERV`), F100 (CFOP `OUTROS`), F120/F130 (crédito sobre ativo; valor contábil 0
     para não duplicar a NF de aquisição do bem). Também entram os documentos de filial/competência sem SPED Fiscal
     carregado.
7. **Itens sintéticos por modelo** (configuráveis em `config.py`): `_ENERGIA_` (06/66), `_AGUA_` (29), `_GAS_` (28),
   `_TELECOM_` (21/22/62) e `_FRETE_CTE_` (57/67 e demais modelos de transporte).
8. **Exclusões.** Documentos cancelados, denegados ou inutilizados (`COD_SIT` 02, 03, 04 e 05) e todas as saídas.

Métricas derivadas:
- `vl_trib_recuperaveis = ICMS + IPI (CST 00) + PIS + COFINS (CST 50–56 e 60–66)`
- `vl_custo_liquido = vl_contabil − vl_trib_recuperaveis`

Os CSTs considerados estão em `config.py`.

## Persistência

| Estrutura | Conteúdo |
|---|---|
| `sys_arquivos_importados` | ID, SHA-256, tipo, CNPJ, competência, finalidade, data, ativo e `substituido_por` |
| `fato_entradas_consolidadas` | tabela fato com todas as chaves, valores e tributos |
| `sys_filtros_salvos` + `data/user_presets.json` | biblioteca de filtros (espelho em JSON) |
| `sys_snapshots_analises` + `data/snapshots/*.parquet` | análises congeladas, somente leitura, com hash de integridade |
| `sys_sessao` | último estado da tela (filtros, hierarquia, aba, tema), restaurado ao reabrir |
| `data/parquet_store/` | cache colunar bruto de cada arquivo importado |

Regras de proteção na importação:
- Um arquivo com hash idêntico é bloqueado como **DUPLICADO**.
- Uma retificadora do mesmo tipo, CNPJ e competência **substitui** os dados anteriores e reconsolida o período.
- Uma original recebida depois de uma retificadora ativa é **ignorada**.
- Em um mesmo lote, prevalece a retificadora e, entre arquivos de mesma finalidade, o mais recente no disco.

## Telas

1. **Central de Arquivos**: importação por pasta (com subpastas) ou arrastando arquivos, com progresso. Também traz
   a matriz de cobertura filial × mês (SF+EFD, só SF, só EFD ou ausente), a lista de arquivos com remoção, a remoção
   por competência, o backup/restauração em `.zip`, a reconsolidação e o log.
2. **Análise Consolidada**: filtros globais (período, filial, UF, fornecedor, raiz, razão social, CFOP, item, NCM),
   hierarquia reordenável e três modos de grade:
   - drill-down: duplo clique desce um nível; as migalhas de navegação voltam;
   - visão plana: todas as dimensões juntas;
   - mês a mês: uma competência por coluna.

   A tela tem ainda indicadores, linha de totais, o painel de notas fiscais da linha clicada (com chave de 44
   dígitos), exportações e o congelamento de snapshots.
3. **Filtros & Biblioteca**: construtor de regras com E/OU e grupos aninhados, sobre qualquer coluna da fato.
   Permite testar (contagem e valor), aplicar e salvar por categoria, e oferece a biblioteca com aplicação em 1 clique
   e a lista de snapshots. O menu lateral (☰) dá acesso rápido aos mesmos itens.
4. **Auditoria**: sete verificações, exportáveis em uma pasta de trabalho:
   - diferença de valor do documento entre SF e EFD;
   - diferença de valor do item entre SF e EFD;
   - crédito de ICMS/IPI sem crédito de PIS/COFINS;
   - crédito de PIS/COFINS sem crédito de ICMS/IPI;
   - CST divergente entre filiais para o mesmo item e CFOP;
   - NF presente na EFD e ausente no SF;
   - item sem C190.

## Testes e desempenho

```bash
pip install -r requirements-opcional.txt
python -m pytest -q tests
```

São 18 testes ponta a ponta sobre arquivos sintéticos no leiaute oficial (`tests/sample_data.py`). Eles cobrem
detecção, duplicidade, retificadora, fechamento C170 = C190, rateio de frete, N1/N3/DOC, Exceção 2, 0175,
conservação total do PIS da EFD na fato, segurança do construtor de filtros, auditoria, cobertura, exportação,
snapshot, backup e remoção.

Teste de volume com `python -m tests.perf_gen DEST 100000 4`, executado no ambiente de desenvolvimento com 4 vCPUs:

| Medida | Resultado |
|---|---|
| Entrada | 5 arquivos (4 SF + 1 EFD), 3,6 milhões de linhas, 520 MB |
| Importação + consolidação | 39 s |
| Tabela fato | 1,2 milhão de linhas |
| Reconsolidação | 9,7 s |
| Agregação por filial, fornecedor ou item | 120–250 ms |
| Drill-down até as notas | 33 ms |
| Visão plana de 4 níveis (50 mil linhas) | 2,4 s |
| Cache Parquet | 95 MB |

## Premissas e limites conhecidos

- **Agrupamento da grade.** O agrupamento hierárquico é feito no servidor (drill-down, visão plana e mês a mês).
  O *row grouping* e o *pivot* nativos do AG Grid são recursos Enterprise, que exigem licença, e não são usados.
- **Derivação de `NAT_BC_CRED`.** A tabela CFOP → `NAT_BC_CRED` (`ref_cfop_nat_bc_cred`) é uma derivação
  parametrizável e não um mapeamento oficial. Ela só é aplicada quando o registro de origem não informa a natureza
  (C170 da EFD-Contribuições), e a coluna `nat_bc_cred_origem` indica `INFORMADO` ou `DERIVADO_CFOP`.
- **Leiautes a conferir.** Os leiautes dos registros D700/D730 (NFCom) e as posições acrescidas em versões recentes
  do C500 devem ser conferidos com o Guia Prático vigente. Campos ausentes em versões antigas são lidos como vazios.
- **Vínculo entre competências.** O vínculo pela chave do documento eletrônico aceita competências diferentes entre
  SF e EFD. O vínculo por número/série só ocorre dentro da mesma competência.
- **De-para de itens.** O de-para do 0205 é de um nível (código anterior → código atual).
- **Upload pela interface.** O envio por arrastar copia os arquivos para `data/uploads`. Para volumes de vários GB,
  prefira informar a pasta.
