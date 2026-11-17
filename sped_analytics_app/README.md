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
| `SPED_UI_MAX_ROWS` | linhas enviadas à grade (padrão 5.000, as maiores por valor; a linha TOTAL considera todas) |

## Arquitetura

| Camada | Implementação |
|---|---|
| Detecção | `parser/detector.py`: identifica o tipo pelo registro 0000 (posição de `DT_INI`), finalidade (original/retificadora), CNPJ, competência e SHA-256 |
| Parsing | `parser/sped_fiscal.py` e `parser/efd_contrib.py`: leitura linha a linha com máquina de estados, em processos paralelos (`spawn`). Lê só as entradas (`IND_OPER=0`) e para no registro 9999 |
| Normalização | `parser/normalizer.py`: buffers colunares, conversão vetorizada com PyArrow (`DECIMAL(18,6)` exato e datas) e Parquet ZSTD em lotes de 200 mil linhas |
| Banco | `database/engine.py`: DuckDB em arquivo único (`data/sped_master.duckdb`), carga transacional por arquivo, deduplicação e retificadoras |
| Consolidação | `database/queries_join.sql`: SQL em etapas (`-- @step`) com um template genérico de rateio (`-- @template alocar`) |
| Filtros | `database/filter_builder.py`: regras JSON convertidas em SQL parametrizado, com whitelist de colunas e operadores |
| Agregadas | `database/aggregates.py`: quatro tabelas pré-somadas (`agg_filial`, `agg_fornecedor`, `agg_produto`, `agg_item`) e o roteador que escolhe a menor capaz de responder cada consulta |
| Análise | `database/analytics.py` (agregação multinível, mês a mês, drill-down) e `database/audit.py` (divergências e fechamento) |
| API local | `api/server.py`: FastAPI em 127.0.0.1; serve a interface e expõe o motor (consultas, importação em segundo plano, exportações) |
| Interface | React + TypeScript + Tailwind (`frontend/`), compilada em `app/web` e distribuída pronta (não exige Node no seu computador). Grade virtualizada com árvore expansível sob demanda, tema claro/escuro, fonte Inter embutida |
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
6. **Cruzamento de PIS/COFINS** (coluna `nivel_cruzamento_efd`). Primeiro os documentos são vinculados, sempre
   1:1: pela chave do documento eletrônico (em qualquer competência) ou, sem chave em um dos lados, por filial +
   competência + CNPJ do fornecedor + modelo + série + número. Depois, dentro do documento vinculado:
   - `N1_ITEM`: mesma posição (`NUM_ITEM`) **e** mesmo `COD_ITEM` **e** mesmo `VL_ITEM` (tolerância de R$ 0,01).
   - `N1V_POSICAO_VALOR`: mesma posição, mesmo valor e mesmo CFOP, com código de item diferente entre os arquivos.
   - `N2_ITEM_CFOP`: `COD_ITEM` + CFOP. Os itens da EFD ainda não usados formam um saldo por chave, rateado entre
     as linhas do SPED Fiscal da mesma chave. É o caminho de quem tem numeração de itens diferente nos dois arquivos.
   - `N3_CONSOLIDADO_C190`: filial + competência + CNPJ fornecedor + CFOP + `COD_ITEM` (C190 com C191/C195).
   - `DOC_CHAVE` / `DOC_NUMERO`: C500, D100, D500 e D700 contra C501/C505, D101/D105 e D501/D505.
   - `EC_EXCLUSIVO`: A100/A170 (CFOP `SERV`), F100 (CFOP `OUTROS`), F120/F130 (crédito sobre ativo; valor contábil 0
     para não duplicar a NF de aquisição do bem) e documentos de filial/competência sem SPED Fiscal carregado.
   - `EC_SEM_PAR`: há SPED Fiscal da filial no período, mas o item, documento ou consolidação da EFD não encontrou
     correspondência. Entra como linha "Somente EFD", com valor contábil zero e todo o PIS/COFINS.

   Garantias, cobertas por testes automatizados:
   - **Nada some**: todo PIS/COFINS da EFD termina em exatamente uma linha do totalizador. A auditoria
     "Fechamento" compara os registros brutos da EFD com o totalizador, por competência e filial.
   - **Nada duplica**: um documento ou item da EFD nunca alimenta duas linhas do SPED Fiscal (por exemplo, quando a
     mesma chave aparece duas vezes no SPED Fiscal, só a primeira recebe o crédito).
   - **Nada vai para o item errado**: a posição do item sozinha não basta para casar.
   - **Coerência entre períodos**: quando a mesma nota está em meses diferentes nos dois arquivos, os dois meses
     são reconsolidados juntos, inclusive ao substituir ou remover um arquivo.
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
| `fato_entradas_consolidadas` | tabela fato com todas as chaves, valores e tributos, gravada em ordem de filial/fornecedor/item |
| `agg_filial`, `agg_fornecedor`, `agg_produto`, `agg_item` | resumos pré-somados da fato, atualizados por competência a cada consolidação |
| `sys_meta` | versão da fato; ao abrir uma base de versão anterior, a fato é recriada e reconsolidada sozinha a partir dos dados brutos |
| `sys_filtros_salvos` + `data/user_presets.json` | biblioteca de filtros (espelho em JSON) |
| `sys_snapshots_analises` + `data/snapshots/*.parquet` | análises congeladas, somente leitura, com hash de integridade |
| `sys_sessao` | último estado da tela (filtros, hierarquia, aba, tema), restaurado ao reabrir |
| `data/parquet_store/` | cache colunar bruto de cada arquivo importado |
| `sf_linhas`, `ec_linhas`, `linhas_contagem` | todas as linhas originais dos TXT (com unidade e documento-pai) e a contagem por registro, para as telas SPED Fiscal / EFD-Contribuições. Ocupam cerca de 1/3 do tamanho dos TXT; podem ser desligadas com `SPED_LINHAS_ORIGINAIS=0` |

Regras de proteção na importação:
- Um arquivo com hash idêntico é bloqueado como **DUPLICADO**.
- Uma retificadora do mesmo tipo, CNPJ e competência **substitui** os dados anteriores e reconsolida o período.
- Uma original recebida depois de uma retificadora ativa é **ignorada**.
- Em um mesmo lote, prevalece a retificadora e, entre arquivos de mesma finalidade, o mais recente no disco.

## Telas

A interface é aberta em uma janela própria (com `pywebview`) ou no navegador, sempre em `127.0.0.1`. Menu lateral
recolhível com acesso rápido aos filtros salvos, tema claro/escuro/sistema e estado salvo automaticamente (filtros,
hierarquia, colunas e tela são restaurados ao reabrir).

1. **Análise**:
   - filtros globais em botões com busca instantânea (período, filial, fornecedor, CFOP, item, UF e "Mais":
     razão social, raiz de CNPJ, descrição, prefixos de CFOP e NCM), aplicados na hora;
   - indicadores (valor contábil, ICMS, ST + FCP, IPI, PIS, COFINS, recuperáveis, custo líquido, documentos) e
     gráfico de evolução mensal;
   - três visões: **Árvore** (Empresa ▸ Fornecedor ▸ CFOP ▸ Item na mesma tabela, cada nível carregado só ao
     abrir), **Tabela** (todas as dimensões juntas) e **Mês a mês** (árvore com uma coluna por competência);
   - hierarquia reordenável, escolha de colunas, ordenação por qualquer coluna, colunas redimensionáveis;
   - clique em qualquer linha abre o painel de **notas fiscais** (com chave de 44 dígitos), redimensionável;
   - exportação do resumo, dos itens detalhados (Excel, CSV, Parquet) e das notas; congelamento de snapshots.
2. **Relatório dinâmico**: monte o relatório livremente, sempre sobre o **consolidado SPED Fiscal +
   EFD-Contribuições** (a mesma base da Análise, em que cada valor é contado uma única vez):
   - arraste os campos para **Linhas** (ex.: Unidade, Fornecedor, CFOP, Descrição do item), **Colunas**
     (opcional, ex.: Competência — uma coluna por mês, com total) e **Valores** (Valor contábil, ICMS, ICMS-ST +
     FCP, IPI, PIS, COFINS, recuperáveis, custo líquido, quantidades…); incluir, retirar ou reordenar um campo
     recalcula o relatório na hora;
   - ordenação por qualquer valor (**maior → menor** ou **menor → maior**) ou por dimensão (A→Z / Z→A), também
     clicando no cabeçalho;
   - filtro por **texto** (busca em códigos e descrições das dimensões das linhas), **filtros por valor** sobre
     cada linha do relatório (ex.: PIS > 0, ICMS igual a zero), quantidade de linhas exibidas e os mesmos filtros
     globais da Análise;
   - **subtotais** por grupo, modelos prontos e modelos salvos pelo usuário;
   - clique em uma linha para ver as notas fiscais que a compõem;
   - exportação para Excel com linha de total e aba de parâmetros.
   O total é sempre calculado na base (não somando as linhas da tela); com filtro por valor ativo, sobre as linhas
   que passam no filtro.
3. **SPED Fiscal** e **EFD-Contribuições** (seção "Arquivos como estão"): o conteúdo dos arquivos exatamente como
   importado, **sem nenhum cruzamento** — inclusive saídas, notas canceladas, apuração (E110, M100, M200…),
   inventário e qualquer outro registro:
   - lista de registros presentes, agrupada por bloco, com descrição e quantidade de linhas;
   - grade do registro escolhido com os nomes oficiais dos campos; valores (VL_, ALIQ_, QTD) como números e datas
     (DT_) como datas; coluna "Linha original" com o texto exato do TXT;
   - registros filhos mostram o contexto do documento-pai do próprio arquivo (ex.: C170 → número, série, chave,
     datas e participante do C100), e registros com COD_PART/COD_ITEM mostram o nome do participante (0150) e a
     descrição/NCM do item (0200) do mesmo arquivo;
   - filtros: período, unidade (CNPJ do estabelecimento — na EFD-Contribuições, o do 0140/A010/C010/D010/F010),
     arquivo, Entradas/Saídas (IND_OPER do registro ou do documento-pai), texto em qualquer campo e condições por
     campo (igual, contém, começa com, lista, maior/menor, vazio);
   - modo **Arquivo**: o TXT inteiro na ordem original, com filtro por registro e texto;
   - exportação de tudo o que estiver filtrado para Excel (com aba de parâmetros) ou CSV.
4. **Arquivos**: importação por pasta ou arrastando arquivos, com barra de progresso e resultado por arquivo;
   matriz de cobertura filial × mês; lista de arquivos com remoção; remoção por competência; backup e restauração;
   reconsolidação; log.
5. **Regras e filtros**: construtor de regras E/OU com grupos aninhados, prévia do SQL, teste (linhas e valores),
   modelos prontos, biblioteca de filtros salvos por categoria e visualizador de snapshots (com verificação de
   integridade, exportação e restauração do contexto).
6. **Auditoria**: verificações agrupadas, contadas automaticamente e exportáveis em uma pasta de trabalho:
   - **fechamento**: PIS/COFINS dos registros brutos da EFD × totalizador (deve ser sempre zero);
   - créditos somente na EFD (linhas `EC_SEM_PAR`);
   - diferença de valor do documento entre SF e EFD;
   - itens na mesma posição com código, CFOP ou valor diferente;
   - crédito de ICMS/IPI sem crédito de PIS/COFINS, e o inverso;
   - CST divergente entre filiais para o mesmo item e CFOP;
   - NF presente na EFD e ausente no SF;
   - item sem C190;
   - **diagnóstico** (informativo): distribuição das linhas e do PIS por nível de cruzamento, por filial e mês.
     É a primeira tela a olhar ao carregar arquivos reais: mostra quanto casou item a item, quanto precisou de
     rateio e quanto ficou sem par.

## Testes e desempenho

```bash
pip install -r requirements-opcional.txt
python -m pytest -q tests
```

São 124 testes sobre arquivos sintéticos no leiaute oficial (`tests/sample_data.py`):
- `tests/test_pipeline.py` (18): detecção, duplicidade, retificadora, fechamento C170 = C190, rateio de frete,
  N1/N3/DOC, Exceção 2, 0175, filtros, auditoria, cobertura, exportação, snapshot, backup e remoção.
- `tests/test_cruzamento.py` (22): cenários em que os dois arquivos **não** são espelhos. Numeração de itens
  invertida, item só na EFD, código de item diferente, valor divergente, nota duplicada no SPED Fiscal, nota
  ausente no SPED Fiscal, nota sem chave, CT-e sem D190, nota em meses diferentes e todos combinados. Em todos,
  o total de PIS e COFINS da EFD é igual ao do totalizador. Inclui a prova de que as tabelas agregadas devolvem
  exatamente o mesmo resultado da fato linha a linha.
- `tests/test_api.py` (10): todos os endpoints usados pela interface — importação por pasta e por envio de
  arquivos, árvore nível a nível, totais, mês a mês, notas, filtros salvos, snapshots, migração do estado salvo
  pela versão anterior, exportações e downloads, auditoria, backup, remoção e reconsolidação.

- `tests/test_raw.py` (10): telas SPED Fiscal / EFD-Contribuições — todas as linhas guardadas idênticas ao TXT,
  saídas e canceladas presentes, contexto do documento-pai, unidade por estabelecimento na EFD, filtros e
  condições, registro fora do catálogo, modo arquivo e paginação, exportação e indexação de arquivos antigos.
- `tests/test_report.py` (64): relatório dinâmico — para 60 combinações de dimensões, a soma das linhas exibidas é
  igual ao total da base e ao total devolvido, sem chave repetida (nenhum valor duplicado); PIS do relatório igual
  ao PIS bruto da EFD; colunas por competência somam a coluna total; ordenação, limite, texto, filtros por valor,
  API e exportação.

### Alterar a interface (opcional, para desenvolvedores)

A pasta `app/web` já contém a interface compilada. Só é preciso Node.js para modificá-la:

```bash
cd frontend
npm install
npm run build      # gera app/web
```

### Como o relatório fica rápido

- Cada consulta é respondida pela **menor tabela agregada** que contém as colunas pedidas. A tela mostra qual foi
  usada ("Fonte da consulta").
- A fato linha a linha só é lida quando a pergunta exige o documento (drill-down até a nota, contagem de
  documentos) ou uma condição sobre valores de linha (por exemplo `VL_ICMS > 0`).
- Visões com muitas linhas são resolvidas em duas fases: primeiro as N maiores chaves, depois as métricas
  completas só para elas.
- A fato é gravada em ordem de filial/fornecedor/item, o que permite ao DuckDB pular blocos nos filtros.
- Na tela, a árvore busca só o nível aberto; grade, indicadores e gráfico são consultados em paralelo; a
  contagem de documentos chega depois, sem segurar a tela; as linhas são desenhadas de forma virtualizada (só as
  visíveis), então milhares de linhas rolam sem travar.

### Medições (ambiente de desenvolvimento, 4 vCPUs)

Importação, com `python -m tests.perf_gen DEST 100000 4` (5 arquivos, 3,6 milhões de linhas, 520 MB):

| Medida | Resultado |
|---|---|
| Importação + consolidação | 36 s |
| Tabela fato | 1,2 milhão de linhas |
| Reconsolidação do mês | 12,6 s |
| Auditoria de fechamento | 78 ms |

Relatório, com a fato ampliada artificialmente para **28,8 milhões de linhas** (24 meses). É um cenário
desfavorável: os itens são sorteados, então quase não há repetição de fornecedor + item e a `agg_item` fica com
24,9 milhões de linhas.

| Consulta | Tabela usada | Tempo |
|---|---|---|
| Por filial / indicadores do topo | `agg_filial` | 14 ms / 3 ms |
| Fornecedores de uma filial | `agg_fornecedor` | 21 ms |
| CFOPs de filial + fornecedor | `agg_fornecedor` | 14 ms |
| Itens de filial + fornecedor + CFOP | `agg_item` | 30 ms |
| Por item ou por NCM, sem filtro | `agg_produto` | 34 ms / 22 ms |
| Mês a mês por fornecedor / por item | `agg_fornecedor` / `agg_produto` | 16 ms / 25 ms |
| Listas dos 5 filtros globais | agregadas | 16 ms |
| Visão plana de 4 níveis (5 mil maiores linhas) | `agg_item` | 0,86 s |
| Regra por linha (`VL_ICMS > 0`), por filial, sem período | fato | 0,6 s |
| Regra por linha, 1 filial + 3 meses | fato | 49 ms |
| Contagem de documentos distintos | fato | 0,15 s |
| Drill-down até as notas | fato | 17–38 ms |

Na interface (navegador, mesma base de 28,8 milhões de linhas, tempo até o conteúdo aparecer na tela):

| Ação | Tempo |
|---|---|
| Abrir o programa até a árvore preenchida | 0,22 s |
| Abrir uma filial (500 fornecedores) | 0,10 s |
| Abrir um fornecedor (CFOPs) / um CFOP (itens) | 0,08 s / 0,12 s |
| Clicar em uma linha até as notas fiscais aparecerem | 0,14 s |
| Buscar na lista de fornecedores do filtro | 0,08 s |
| Marcar um fornecedor e recalcular a árvore | 0,27 s |
| Trocar para Mês a mês | 0,07 s |
| Trocar para Tabela com 4 dimensões (5 mil maiores linhas) | 1,4 s |

Relatório dinâmico (fato com 1,2 milhão de linhas, 8 valores, consulta já aquecida):

| Relatório | Tabela usada | Tempo |
|---|---|---|
| Unidade | `agg_filial` | 13 ms |
| Unidade + Fornecedor (2 mil linhas) | `agg_fornecedor` | 21 ms |
| Unidade + Fornecedor + CFOP + Descrição (1 milhão de grupos, 5 mil maiores) | `agg_item` | 0,21 s |
| idem, ordenado A→Z por fornecedor | `agg_item` | 0,17 s |
| idem + filtro por texto | `agg_item` | 0,43 s |
| idem + filtro por valor (PIS > 0) | `agg_item` | 0,34 s |
| Fornecedor × Competência (colunas por mês) | `agg_fornecedor` | 22 ms |

Telas SPED Fiscal / EFD-Contribuições (base de 3,6 milhões de linhas originais):

| Medida | Resultado |
|---|---|
| Custo na importação | +13% de tempo (46,6 s → 52,9 s) e +169 MB no banco (520 MB de TXT) |
| C100 do SPED Fiscal (400 mil linhas): 1ª página + total | 0,11 s |
| C170 (1,2 milhão de linhas): 1ª página + total / página 100 | 0,32 s / 0,36 s |
| C170 com unidade + CFOP + VL_ITEM > 10.000 | 0,56 s |
| C170 da EFD só entradas (pelo IND_OPER do C100 pai) | 0,60 s |
| Na tela: abrir SPED Fiscal / trocar para C170 / filtrar unidade | 0,36 s / 0,91 s / 0,71 s |

## Premissas e limites conhecidos

- **Linhas por nível.** Cada nível da árvore traz até 5.000 linhas na raiz e 2.000 por item aberto (os maiores
  por valor); a linha Total sempre considera todas. Acima disso, refine os filtros ou exporte.
- **Derivação de `NAT_BC_CRED`.** A tabela CFOP → `NAT_BC_CRED` (`ref_cfop_nat_bc_cred`) é uma derivação
  parametrizável e não um mapeamento oficial. Ela só é aplicada quando o registro de origem não informa a natureza
  (C170 da EFD-Contribuições), e a coluna `nat_bc_cred_origem` indica `INFORMADO` ou `DERIVADO_CFOP`.
- **Leiautes a conferir.** Os leiautes dos registros D700/D730 (NFCom) e as posições acrescidas em versões recentes
  do C500 devem ser conferidos com o Guia Prático vigente. Campos ausentes em versões antigas são lidos como vazios.
- **Vínculo entre competências.** O vínculo pela chave do documento eletrônico aceita competências diferentes entre
  SF e EFD. O vínculo por número/série só ocorre dentro da mesma competência.
- **Validação com arquivos reais.** Toda a lógica foi testada com arquivos sintéticos. Ao carregar os primeiros
  arquivos reais, confira a auditoria "Diagnóstico" (níveis de cruzamento) e "Fechamento".
- **Fechamento com o Bloco M.** A conferência do totalizador com a apuração oficial (M100/M105, M500/M505) não
  está implementada.
- **Contagem de documentos.** É a única métrica que sempre lê a fato linha a linha; por isso saiu das colunas
  padrão da grade (continua no indicador do topo, calculada à parte).
- **Nomes de campos nas telas SPED Fiscal / EFD-Contribuições.** Registros fora do catálogo (ou campos acrescidos
  em versões mais novas do leiaute) aparecem como CAMPO_02, CAMPO_03…; o conteúdo é sempre o do arquivo. Os nomes
  dos campos dos Blocos E e M devem ser conferidos com o Guia Prático vigente.
- **Arquivos importados antes da versão 2.1.** Não têm as linhas originais guardadas. As telas oferecem
  "Indexar agora", que lê de novo o TXT no caminho de origem (só se ele ainda existir e tiver o mesmo hash);
  caso contrário, é preciso reimportar o arquivo.
- **De-para de itens.** O de-para do 0205 é de um nível (código anterior → código atual).
- **Upload pela interface.** O envio por arrastar copia os arquivos para `data/uploads`. Para volumes de vários GB,
  prefira informar a pasta.
