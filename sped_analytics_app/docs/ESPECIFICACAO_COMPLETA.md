# Consolidação Fiscal SPED — regras, cruzamento, layout e arquitetura do programa (v2.3.1)

Documento único de referência para recriar ou customizar o sistema: regras de negócio, racional do cruzamento SPED Fiscal × EFD-Contribuições, telas e layout, arquitetura, API, testes e limites. Descreve o que **existe no código**, não o que foi planejado.
Onde algo não foi implementado ou não foi verificado, está dito.

- Repositório: `gbarao/portifolio`, pasta `sped_analytics_app/`, branch `claude/wonderful-rubin-5qi5sj`.
- Linguagens e tamanho: Python (backend, ~5.900 linhas) + SQL (consolidação, 640 linhas) + TypeScript/React (interface, ~4.500 linhas) + testes (~1.500 linhas).
- Execução: 100% local, sem internet depois da instalação. A interface escuta apenas `127.0.0.1`.

---

## 1. Objetivo e premissas

Consolidar, em uma única base consultável, as **entradas** do **SPED Fiscal (EFD ICMS/IPI)** e da **EFD-Contribuições (PIS/Cofins)**:

1. o SPED Fiscal é a base mestre (valor contábil, quantidade, ICMS, ST, FCP, IPI);
2. a EFD-Contribuições entrega PIS e Cofins (CST, base, alíquota, valor), atribuídos às linhas do SPED Fiscal;
3. **nenhum valor pode ser contado duas vezes e nenhum crédito pode desaparecer**;
4. análise multidimensional (Unidade → Fornecedor → CFOP → Item → NF), filtros salvos, análises congeladas, auditoria, exportação para Excel;
5. além da consolidação, três visões **sem cruzamento**: conteúdo dos TXT como está (por registro), Bloco M da EFD-Contribuições e busca por fornecedor.

Escopo fiscal atual: **somente entradas/aquisições** (IND_OPER = 0). Saídas ficam guardadas apenas nas telas "como estão".

---

## 2. Arquitetura

```
TXT (SPED Fiscal / EFD-Contribuições, latin-1)
   │  detector (registro 0000 + SHA-256)
   ▼
parsers em streaming (multiprocessing "spawn") ──► Parquet ZSTD (staging, parquet_store/)
   ▼
DuckDB embarcado  data/sped_master.duckdb
   ├─ tabelas brutas  sf_* / ec_*            (o que foi lido, por arquivo)
   ├─ sf_linhas / ec_linhas                  (TODAS as linhas originais de cada TXT)
   ├─ queries_join.sql  ──► fato_entradas_consolidadas (+ agg_filial/fornecedor/produto/item)
   └─ sys_* (arquivos, log, filtros, snapshots, sessão)
   ▼
FastAPI (app/api/server.py) ──► interface React/TypeScript/Tailwind (app/web, já compilada)
   ▼
janela nativa (pywebview) ou navegador local;  exportações .xlsx (xlsxwriter), .csv, .parquet
```

Pilha e versões fixadas (`requirements.txt`): duckdb 2.0.0, pyarrow 26.0.1, polars 2.1.0, xlsxwriter 3.2.9, fastapi 0.162.5, starlette 1.10.0, uvicorn 0.54.0, python-multipart 0.0.32; opcionais: pywebview ≥ 5.0, pytest ≥ 8, httpx. Python 3.11+ (testado em 3.13).
Interface: React 18.3.1, TypeScript 5.6.3, Vite 5.4.11, Tailwind 3.4.15, Radix UI (dialog, dropdown, popover, tooltip), `@tanstack/react-virtual`, sonner (avisos), lucide-react (ícones), fonte Inter. Node só é necessário para **alterar** a interface (`npm run build` gera `app/web`).

### Estrutura de pastas

```
app/main.py                 ponto de entrada (--browser, --importar DIR, --reconsolidar, --demo)
app/config.py               diretórios, paralelismo, constantes de regra de negócio (parametrizáveis)
app/parser/                 detector, sped_fiscal, efd_contrib, normalizer, layouts, catalog, raw_lines
app/database/               engine, schema.sql, queries_join.sql, aggregates, analytics, filter_builder, audit,
                            snapshots, raw_view, bloco_m, tabelas_efd, fornecedor
app/exporter/excel_writer.py
app/api/server.py           todos os endpoints
app/web/                    interface compilada (index.html + assets)
frontend/src/               código-fonte da interface
tests/                      138 testes + gerador de dados sintéticos
instalar.bat/.sh, iniciar.bat/.sh, iniciar_demonstracao.bat, abrir_no_navegador.bat, LEIA-ME.txt, README.md
```

Diretório de dados: `data/` (ou `SPED_DATA_DIR`): `sped_master.duckdb`, `parquet_store/`, `snapshots/`, `backups/`, `exports/`, `uploads/`, `user_presets.json`, `last_session.json`. A pasta `data/` é ignorada pelo git (dados do usuário).

Variáveis de ambiente: `SPED_DATA_DIR`, `SPED_PARSER_WORKERS` (padrão CPU−1), `SPED_BATCH_ROWS` (200.000), `SPED_DUCKDB_THREADS`, `SPED_DUCKDB_MEMORY` (60%), `SPED_UI_PORT` (8765), `SPED_UI_MAX_ROWS` (5.000), `SPED_LINHAS_ORIGINAIS` (1; 0 desliga a guarda das linhas originais).

---

## 3. Importação

1. **Descoberta:** varre pasta e subpastas por `.txt`.
2. **Identificação (paralela):** lê o registro 0000 → tipo (SPED Fiscal × EFD-Contribuições), CNPJ, competência, finalidade (original/retificadora), e calcula SHA-256.
3. **Decisão (`_plan_imports`):**
   - hash já conhecido → "DUPLICADO" (mensagem diferente se a versão foi substituída);
   - repetido no lote → "DUPLICADO";
   - por (tipo, CNPJ, competência) vence **retificadora > original**, depois o arquivo mais recente em disco; o que perde fica "IGNORADO";
   - original que chega depois de retificadora já importada → ignorado;
   - retificadora substitui o arquivo ativo anterior (`ativo = FALSE`, `substituido_por`).
   - **Exceção (v2.3.1):** hash já importado cujo arquivo **não tem linhas originais** guardadas → resultado "INDEXADO" (guarda as linhas, não duplica nada).
4. **Parsing em streaming**, um processo por arquivo (`spawn`; scripts que usam multiprocessing precisam do guard `if __name__ == "__main__"`), gravando Parquet ZSTD em lotes de 200 mil linhas.
5. **Carga transacional no DuckDB**, um arquivo por transação; depois `rebuild_fato` para as competências afetadas.
6. **Linhas originais:** cada linha do TXT vai também para `sf_linhas`/`ec_linhas` (ver §7).

Gestão de arquivos: matriz de cobertura filial × mês, remoção de arquivo ou de competência (reconsolida), backup/restauração em .zip, log de importação, reconsolidação completa. `FATO_VERSION` ("3") em `aggregates.py`: ao mudar a lógica/esquema da fato, a base é recriada e reconsolidada sozinha na próxima abertura (usa os dados já importados).

### Registros lidos

**SPED Fiscal** (só IND_OPER = 0): documentos C100, C500, D100, D500, D700 (`sf_doc`); itens C170 (`sf_c170`); analíticos C190, C590, D190, D590, D730 (`sf_anal`); C191 (FCP, `sf_c191`); C197 (`sf_c197` — **carregado, mas não entra em nenhum valor**); cadastros 0150, 0175, 0190, 0200, 0205, 0400, 0500.

**EFD-Contribuições**: documentos C100, A100, C500, D100, D500 (IND_OPER = 0; no C500 o campo é forçado a 0) em `ec_doc`; itens C170 e A170 (`ec_item`); tributos dos C501/C505, D101/D105, D501/D505 (`ec_doc_trib`); consolidação C190 + C191/C195 (`ec_c190`, `ec_c191_195`); F100 (IND_OPER = 0), F120, F130 (`ec_f`); cadastros 0140, 0150, 0200, 0205, 0500. A **filial** de cada linha é o CNPJ do bloco de movimento (A010/C010/D010/F010) e o CNPJ do 0140 nos cadastros.

Documentos com `COD_SIT` 02, 03, 04, 05 (cancelado, cancelado extemporâneo, denegado, inutilizado) são excluídos da consolidação (`config.COD_SIT_EXCLUIDOS`).

---

## 4. Consolidação (o cruzamento) — `app/database/queries_join.sql`

Motor SQL em etapas (`-- @step nome`), executado em **uma transação** por `rebuild_fato`, com a tabela temporária `_scope` (competências a refazer). O escopo é expandido por **fecho transitivo**: se uma nota está em meses diferentes nos dois arquivos, ambos os meses são refeitos juntos. Constantes `{{...}}` vêm de `config.py`.

Etapas, em ordem: `dim_filial`, `dim_fornecedor`, `dim_item_depara`, `t_doc`, `t_ec_doc`, `t_docmatch`, `t_ec_it`, `t_item`, `t_anal_k`, `t_item_r`, `t_lin`, `n1`, `pool_n2`, `pool_n3`, `pool_doc`, `t_pc_final`, `t_lin_ec`, `fato_delete`, `fato_stage`, `fato_insert`, e a recarga incremental das agregadas.


O racional abaixo (4.1 a 4.10) é a referência das regras de cruzamento; 4.11 e 4.12 descrevem a tabela resultante.

### 4.1 Princípio

| Papel | Fonte | O que fornece |
|---|---|---|
| Base mestre | SPED Fiscal | documento, item, quantidade, valor contábil, ICMS, ICMS-ST, FCP, IPI |
| Complemento | EFD-Contribuições | CST, base, alíquota e valor de **PIS e Cofins** (e natureza da base de crédito) |

Regras que governam tudo:

1. O valor contábil, o ICMS e o IPI vêm **sempre** do SPED Fiscal. A EFD-Contribuições só entrega PIS/Cofins.
2. **Cada item da EFD-Contribuições é consumido no máximo uma vez.**
3. **Todo PIS/Cofins da EFD termina em exatamente uma linha** da tabela consolidada. O que não acha par no SPED Fiscal vira linha "somente EFD" com valor contábil zero. Nada some, nada duplica.
4. O vínculo entre documentos é **1:1**: um documento da EFD nunca alimenta dois do SPED Fiscal, nem o inverso.
5. Só se compara item a item quando há **identidade comprovada**. Na dúvida, desce para um nível mais agregado (com rateio), nunca "chuta" por posição.

Prova automatizada: o total de PIS e de Cofins na tabela consolidada é igual ao total bruto dos registros da EFD (verificação `fechamento_efd`, que deve ser zero), inclusive em cenários em que os arquivos não são espelhos (itens em ordem invertida, item só na EFD, código diferente, valor divergente, nota duplicada ou ausente, nota sem chave, notas em meses diferentes).


### 4.2 O que entra de cada arquivo

**Somente entradas/aquisições** (`IND_OPER = 0`); documentos com `COD_SIT` 02, 03, 04, 05 (cancelado, cancelado extemporâneo, denegado, inutilizado) são excluídos nos dois arquivos.

| Tipo de operação | SPED Fiscal | EFD-Contribuições |
|---|---|---|
| NF / NF-e, com item | C100 + **C170**; totalizador C190 (+ C191 FCP) | C100 + **C170** |
| NF / NF-e, consolidada | — | C190 + C191 (PIS) / C195 (Cofins) |
| Energia, água, gás | C500 + C590 (sem item) | C500 + C501 (PIS) / C505 (Cofins) |
| Frete (CT-e) | D100 + D190 | D100 + D101 / D105 |
| Telecomunicação | D500 + D590; D700 + D730 | D500 + D501 / D505 |
| Serviços tomados | não existe | A100 + A170 |
| Demais créditos | não existe | F100, F120, F130 |

Filial (unidade): SPED Fiscal = CNPJ do registro 0000 (um arquivo por estabelecimento); EFD-Contribuições = CNPJ do bloco de movimento (A010/C010/D010/F010) em que o documento está.


### 4.3 Chaves de identidade

**Fornecedor unificado.** `COD_PART` só vale dentro do arquivo: resolve-se no 0150 **do próprio arquivo** (na EFD, no mesmo estabelecimento) para o CNPJ/CPF, só dígitos. Sem CNPJ/CPF usa `EXT:<nome>`; sem 0150, `PART:<cod>`. Raiz = 8 primeiros dígitos. O nome vigente na data do documento vem do 0175 (campo 3).

**Item.** Chave de comparação é `COD_ITEM`, mas códigos antigos são unificados por `dim_item_depara` (0205 e `COD_ANT_ITEM` do 0200). A chave global do item é `NCM|código`.

**Documento.** Família (C100, C500, D100, D500; D700 conta como D500) + chave do documento eletrônico, ou, sem chave, filial + competência + CNPJ do fornecedor + modelo + série + número (zeros à esquerda ignorados).


### 4.4 Passo 1 — vincular documentos (1:1)

1. **Pela chave** (CHV_NFE / CHV_CTE / CHV_DOCe): mesma filial e família, **em qualquer competência do escopo**. Isso cobre a nota escriturada em meses diferentes nos dois arquivos. Se a mesma chave aparece duas vezes num lado, só a primeira ocorrência participa.
2. **Sem chave em um dos lados:** filial + competência + CNPJ do fornecedor + modelo + série + número. O k-ésimo documento de um lado casa com o k-ésimo do outro (ordenados de forma estável); nunca um para muitos.

Consequência: ao reconsolidar uma competência, o escopo é **fechado transitivamente** pelas chaves (as competências ligadas por uma nota são refeitas juntas). Sem isso, o 1:1 entre meses quebraria.


### 4.5 Passo 2 — montar as linhas do SPED Fiscal

#### 4.5.1 Quais linhas existem
- Itens do **C170** do SPED Fiscal.
- **Exceção — emissão própria sem C170:** se o documento vinculado não tem C170 no SPED Fiscal, os itens vêm do C170 da EFD (origem `EC_C170_VIA_CHAVE`); já nascem com o PIS/Cofins do próprio item (nível `N1_ITEM`).
- **Itens sintéticos**, um por registro analítico, quando não há item: C190 sem C170 (`_SEM_ITEM_C190_`), C590/D190/D590/D730 (`_ENERGIA_`, `_AGUA_`, `_GAS_`, `_TELECOM_`, `_FRETE_CTE_`, conforme o modelo do documento).

#### 4.5.2 Valor contábil por item (rateio contra o analítico)
O C170 não carrega frete, seguro e outras despesas do cabeçalho; o C190 sim. Para fechar:

```
base_item   = VL_ITEM − VL_DESC + VL_ICMS_ST + VL_IPI
grupo       = itens do mesmo documento com mesmo CST + CFOP + alíquota (= uma linha do C190)
diferença   = VL_OPR do C190 − Σ base_item do grupo
rateio_item = diferença × VL_ITEM / Σ VL_ITEM do grupo     (sem peso: divide por igual)
vl_contabil = base_item + rateio_item
```
O resíduo de centavos do arredondamento vai para o **maior item** do grupo, de modo que Σ `vl_contabil` do grupo = `VL_OPR` do C190 exatamente. O FCP do C191 é rateado da mesma forma.

Exemplo (dados de teste): NF com item 1 = 1.000 (IPI 90, CFOP 1102) e item 2 = 500 (CFOP 1101), frete de 10 no cabeçalho.
C190-1102 = 1.000 + 90 + 10×1.000/1.500 = 1.096,67; C190-1101 = 500 + 10×500/1.500 = 503,33.
Item 1: base 1.090 + rateio 6,67 = 1.096,67. Item 2: base 500 + rateio 3,33 = 503,33. Soma 1.600 = `VL_DOC`.


### 4.6 Passo 3 — levar PIS/Cofins para as linhas (cascata)

Do critério mais forte para o mais fraco. O que é casado em um nível sai da disputa dos seguintes.

| Nível (`nivel_cruzamento_efd`) | Quando | Critério | Como atribui |
|---|---|---|---|
| `N1_ITEM` | documento vinculado | mesmo `NUM_ITEM` + mesmo `COD_ITEM` + `VL_ITEM` igual (tolerância R$ 0,01) | o item da EFD alimenta a linha, 1 para 1 |
| `N1V_POSICAO_VALOR` | documento vinculado | mesmo `NUM_ITEM` + mesmo `VL_ITEM` + mesmo CFOP, **com código de item diferente** | idem (cobre troca de código entre os arquivos) |
| `N2_ITEM_CFOP` | documento vinculado | sobra da EFD, agrupada por `COD_ITEM` + CFOP | o conjunto vira um "pool" rateado entre as linhas do SPED Fiscal do mesmo documento com o mesmo item + CFOP, proporcional ao `VL_ITEM` |
| `N3_CONSOLIDADO_C190` | linhas de C100 que o N1 e o N2 não atenderam (com ou sem documento vinculado) | C190 + C191/C195 da EFD: filial + competência + CNPJ do fornecedor + CFOP + `COD_ITEM` | pool rateado entre as linhas de C100 ainda sem PIS/Cofins que tenham a mesma chave, proporcional ao `VL_ITEM` |
| `DOC_CHAVE` / `DOC_NUMERO` | C500, D100, D500/D700 | documento vinculado por chave ou por número | PIS/Cofins dos C501/C505, D101/D105, D501/D505 rateados entre as linhas analíticas do SPED Fiscal (C590/D190/D590/D730), proporcional ao valor contábil |

Detalhes que importam:
- **N1 exige identidade**: posição + valor + (código ou CFOP). Quem não passa **nunca** recebe o crédito de outro item só por estar na mesma posição; segue para o N2. Itens da EFD com a mesma posição repetida (`dup > 1`) não entram no N1.
- **Pool e rateio** (template `alocar`): a soma distribuída por pool é exatamente o valor do pool; resíduo de centavos no maior peso. Para CST/alíquota/natureza do pool usa-se o valor de maior base.
- No N3, só entram linhas de C100 (mercadorias) que não foram atendidas no N1 nem no N2.


### 4.7 Passo 4 — o que sobra da EFD

O que a EFD tem e o SPED Fiscal não absorveu **nunca é descartado**; vira linha própria (`t_lin_ec`):

| Nível | Origem | Tratamento |
|---|---|---|
| `EC_EXCLUSIVO` | A100/A170 (serviços tomados, CFOP `SERV`), F100 (CFOP `OUTROS`), F120/F130 (CFOP `OUTROS`) — operações que **por natureza não existem** no SPED Fiscal; ou filial/competência **sem SPED Fiscal carregado** | entra com o valor da própria EFD; nesse último caso a EFD é a única fonte |
| `EC_SEM_PAR` | há SPED Fiscal da filial no período, mas o item, o documento ou a consolidação da EFD não achou correspondência (C170 não consumido; C190/C191/C195 sem linha; C500/D100/D500 sem documento ou sem analítico — CFOP `N/D`) | entra com **valor contábil 0** (o valor pertence ao SPED Fiscal) e **todo** o PIS/Cofins, para o crédito aparecer no total |

`EC_SEM_PAR` é o sinal de divergência entre os arquivos (nota ausente no SPED Fiscal, item só na EFD, consolidação sem par). A tela de auditoria "Diagnóstico" mostra quanto casou em cada nível; é a primeira coisa a olhar ao carregar arquivos reais.


### 4.8 Colunas derivadas (depois do cruzamento)

- **Natureza da base de crédito (`nat_bc_cred`):** a informada no registro da EFD (A170, C501/C505, D101…, F100/F120/F130); no C170 e no C191/C195, que não a trazem, é **derivada do CFOP** pela tabela `ref_cfop_nat_bc_cred` (padrão: revenda 01, insumo 02, serviço insumo 03, devolução 12, ativo 11, demais 13), só quando o CST de PIS é de crédito. `nat_bc_cred_origem` registra `INFORMADO` ou `DERIVADO_CFOP`. A tabela é parametrizável e precisa de revisão por especialista.
- **Tributos recuperáveis** = ICMS + IPI (somente CST IPI `00`) + PIS (somente CST 50–56 e 60–66) + Cofins (idem).
- **Custo líquido de entrada** = valor contábil − tributos recuperáveis.
- **Status:** "Escriturado na EFD-Contribuições", "Sem crédito / não escriturado na EFD-Contribuições" (linha do SPED Fiscal sem PIS/Cofins atribuído), "Somente EFD — sem correspondência no SPED Fiscal" (`EC_SEM_PAR`), "Exclusivo EFD-Contribuições" (`EC_EXCLUSIVO`).


### 4.9 Parâmetros que controlam o cruzamento (`config.py`)

| Constante | Valor | Efeito |
|---|---|---|
| `COD_SIT_EXCLUIDOS` | 02, 03, 04, 05 | situações removidas nos dois lados |
| `TOLERANCIA_ITEM` | R$ 0,01 | diferença máxima de `VL_ITEM` para aceitar o N1 |
| `CST_PIS_COFINS_CREDITO` | 50–56, 60–66 | o que conta como crédito (recuperáveis, natureza derivada) |
| `CST_IPI_CREDITO` | 00 | IPI recuperável |
| `ITEM_SINTETICO_POR_MODELO` | por modelo | item dos documentos sem item |
| `ITEM_SINTETICO_C190` | `_SEM_ITEM_C190_` | item do C190 sem C170 |
| `TOLERANCIA_DIVERGENCIA` | R$ 0,05 | só afeta a auditoria, não o cruzamento |


### 4.10 Por que foi desenhado assim (decisões)

- **Mestre + complemento, e não "união":** unir os dois arquivos linha a linha duplicaria o valor contábil (cada arquivo traz o documento). Mantendo o SPED Fiscal como único dono do valor, a EFD só pode somar PIS/Cofins.
- **1:1 estrito entre documentos:** evita que uma chave repetida ou um número reaproveitado multiplique crédito.
- **Identidade antes de posição:** a posição do item, sozinha, não prova que é o mesmo item quando a ordem difere entre os arquivos (o PIS/Cofins iria para o item errado sem aparecer erro). Por isso a posição só vale junto com valor e (código ou CFOP) iguais.
- **Cascata com rateio em vez de falha:** quando a identidade não é provável (códigos diferentes, itens agrupados na EFD), o crédito é rateado entre candidatos legítimos do mesmo documento (ou da mesma filial/mês/fornecedor/CFOP/item) em vez de ficar sem par; o total sempre fecha.
- **"Nada some":** crédito sem par vira linha visível (`EC_SEM_PAR`/`EC_EXCLUSIVO`), com valor contábil zero para não inflar o custo. Assim o `fechamento_efd` é verificável.
- **Fecho transitivo de competências:** nota em meses diferentes nos dois arquivos exige reconsolidar os meses juntos.

### 4.11 Tabela fato `fato_entradas_consolidadas`
Uma linha por item de entrada. Colunas: competência, filial (CNPJ, nome, UF, raiz), origem, registro do documento, ids de arquivo (SF e EFD), fornecedor (CNPJ/CPF, raiz, razão social, nome na data, UF), modelo, situação, emitente, série, número, chave, datas, item (código, unificado, global, descrição, tipo, NCM, CEST, barras, unidade), CFOP, natureza, CST/alíquota de ICMS, IPI, PIS e Cofins, natureza e origem do crédito, conta contábil, quantidade e todos os valores (item, desconto, rateio C190, contábil, bases e valores de ICMS/ST/FCP/IPI/PIS/Cofins, recuperáveis, custo líquido), `nivel_cruzamento_efd`, `status_efd`, flags de item sintético e sem C190, `doc_key`.

### 4.12 Tabelas agregadas (desempenho do relatório)
`agg_filial < agg_fornecedor < agg_produto < agg_item < fato`. Cada uma é uma pré-soma (19 medidas + `n_linhas`) por competência + dimensões de baixa cardinalidade, mantida **incrementalmente por competência** ao final da consolidação. O roteador `pick_source(colunas, métricas)` escolhe a menor tabela que contém tudo o que a consulta pede; a fato linha a linha só é lida para documento, chave, contagem de documentos ou condição sobre valores de linha. A tela mostra a tabela usada ("Fonte da consulta") e o tempo.

---


## 5. Análise

`app/database/analytics.py` (dimensões, métricas, agregação em duas fases) e `filter_builder.py` (filtros).

- **Dimensões:** Unidade (filial), Fornecedor, CFOP, Item (código), Descrição do item, Competência, Ano, UF filial, Raiz CNPJ fornecedor, UF fornecedor, NCM, Tipo item, Item global (NCM|código), CST ICMS/PIS/Cofins, Natureza BC crédito, Conta contábil, Modelo do documento, Alíquota ICMS, Origem da linha, Status EFD, Nível de cruzamento.
- **Métricas:** quantidade, unidade (ou "DIVERSAS"), preço médio, valor bruto, descontos, valor contábil, BC e valor de ICMS, BC e valor de ICMS-ST, ICMS-ST + FCP, BC e valor de IPI, CST/BC/valor de PIS e de Cofins, tributos recuperáveis, custo líquido, nº de linhas, nº de documentos (mais lento; lê a fato).
- **Duas fases:** primeiro as N maiores chaves por valor, depois as métricas completas só para elas (evita agregar milhões de grupos para mostrar 5.000).
- **Filtros globais** (aplicados na hora): período (de/até ou meses), filiais, UF filial, raiz filial, fornecedores, raiz fornecedor, busca por nome de fornecedor/item/filial, CFOP (lista e prefixo), itens, NCM (lista e prefixo).
- **Regras sob demanda:** construtor E/OU com grupos aninhados, sobre qualquer coluna da fato (16 operadores: igual, diferente, maior/menor, entre, em lista, começa/termina/contém, vazio/preenchido…), com prévia do SQL e teste (linhas e valores).
- **Filtros salvos** (tabela `sys_filtros_salvos`, espelho em `user_presets.json`), por categoria; **análises congeladas** (snapshots em Parquet somente leitura, com hash SHA-256 de integridade, verificação, exportação e restauração do contexto); **estado da sessão** salvo automaticamente (`sys_sessao`, versão de estado 3).

### Relatório dinâmico (`report()`)
Linhas × coluna opcional (pivô, até 60 valores) × valores. Ordenação por valor ou dimensão (maior→menor / menor→maior, A→Z / Z→A), limite (50 a 20.000), filtro por **texto** (códigos e descrições das dimensões), **filtros por valor** sobre cada linha do relatório (>, ≥, <, ≤, =, ≠, zero, não zero). Totais **sempre calculados na base** (nunca somando a tela); com filtro por valor, apenas sobre os grupos que passam. Subtotais por grupo no cliente. Comprovado em teste: para 60 combinações de dimensões a soma das linhas exibidas = total da base = total devolvido, sem chave repetida, e PIS do relatório = PIS bruto da EFD.

### Auditoria (`audit.py`)
`fechamento_efd` (deve ser zero), `efd_sem_par`, `valor_documento` (C100 SF × EFD), `valor_item`, `credito_icms_sem_pis`, `credito_pis_sem_icms`, `cst_divergente_filiais`, `ec_sem_sf`, `item_sem_c190`, `qualidade_cruzamento` (informativo: quanto casou em cada nível). Tolerância configurável (padrão R$ 0,05).

---

## 6. Telas (menu lateral)

Resumo funcional; o layout de cada tela está em §11.3.

| Tela | Conteúdo |
|---|---|
| **Análise** | filtros globais; indicadores (valor contábil, ICMS, ICMS-ST+FCP, IPI, PIS, Cofins, recuperáveis, custo líquido, nº de documentos/linhas); evolução mensal; visões Árvore (Unidade▸Fornecedor▸CFOP▸Item carregada nível a nível), Tabela e Mês a mês; hierarquia reordenável; escolha de colunas; clique em qualquer linha abre as notas fiscais (com chave de 44 dígitos); exportação de resumo, itens (xlsx/csv/parquet) e notas; congelar análise |
| **Relatório dinâmico** | montagem arrastando campos para Linhas/Colunas/Valores; ordenação, texto, filtros por valor, subtotais, 6 modelos prontos + modelos do usuário; clique abre as notas; Excel com linha Total e aba de parâmetros |
| **Busca por fornecedor** | CNPJ, CPF, raiz ou nome; cadastro (todas as versões do 0150 e os 0175); entradas consolidadas por mês/filial/CFOP/status/CST PIS/natureza; notas; itens; **linhas dos TXT ligadas ao fornecedor (entradas e saídas)**; Excel completo (uma aba por registro) |
| **Bloco M (PIS/Cofins)** | apuração como informada no arquivo (ver §8) |
| **SPED Fiscal** / **EFD-Contribuições** | conteúdo dos arquivos como está, por registro (ver §7) |
| **Arquivos** | importação (pasta ou arrastar), progresso, cobertura filial × mês, lista com remoção, backup/restauração, reconsolidação, log |
| **Regras e filtros** | construtor de regras, modelos, biblioteca de filtros, visualizador de snapshots |
| **Auditoria** | verificações agrupadas, contagens automáticas, exportação |

---

## 7. Consulta direta dos arquivos (sem cruzamento) — `raw_view.py`, `raw_lines.py`

- `sf_linhas`/`ec_linhas`: `(file_id, line_no, reg, cnpj_estab, doc_line, linha)` — o texto original completo de cada linha, mais `linhas_contagem` (registros por arquivo/unidade).
- `doc_line` liga cada linha ao registro "pai" mais recente do mesmo bloco (terminados em `00`, mais C190/C180/C380/C395/C490/D350 etc.), reiniciando a cada troca de estabelecimento (A010/C010/D010/F010) e de bloco. Serve para mostrar contexto (número, série, chave, datas, participante) ao lado de filhos (C170 → C100).
- Unidade: SPED Fiscal = CNPJ do 0000; EFD-Contribuições = CNPJ do 0140/A010/C010/D010/F010/I010/P010; blocos M, 1 etc. usam o CNPJ da matriz.
- Consulta em **duas fases** com `split_part`/`string_split`: primeiro localiza as chaves (arquivo, linha) que atendem aos filtros; depois monta as colunas só da página pedida. Valores (`VL_`, `ALIQ_`, `QTD`) viram número e `DT_` vira data; "Linha original" mantém o texto exato.
- Filtros: período, unidade, arquivo, Entradas/Saídas (IND_OPER do registro ou do pai), texto em qualquer campo, condições por campo (igual, diferente, contém, começa com, lista, maior/menor, vazio, preenchido) e, desde a v2.3, **participante** (busca por fornecedor).
- Modo **Arquivo**: o TXT inteiro na ordem original, com filtro por registro e texto.
- Nomes de campos: `catalog.py` (catálogo de blocos/registros/descrições/leiautes) + `layouts.py`. Registro fora do catálogo aparece como `CAMPO_02, CAMPO_03…`; leiautes alternativos por quantidade de campos (`LAYOUT_VARIANTS`, hoje M210/M610 anteriores a 2019).
- Arquivos importados antes da v2.1 não têm linhas originais: banner de indexação (§11.4).

---

## 8. Bloco M (`bloco_m.py`, `tabelas_efd.py`)

Fonte: `ec_linhas`; valores **como informados**, sem recalcular nem cruzar com o SPED Fiscal.

- Registros: M100/M500 (crédito), M105/M505 (base por natureza e CST), M110/M510 e M115/M515 (ajustes de crédito), M200/M600 (consolidação), M205/M605 (débitos por código de receita), M210/M610 (contribuição por código, leiautes antes/depois de 2019), M215/M615, M220/M620 e M225/M625 (ajustes de base e de contribuição), M400/M800 e M410/M810 (receitas não tributadas), 1100/1500 (controle de créditos de períodos anteriores).
- Abas: Apuração (demonstrativo M200/M600), Créditos (mestre-detalhe M100→M105), Contribuição, Ajustes, Receitas não tributadas, Saldos de créditos, **Conferência com documentos**, **Verificações**.
- **Verificações aritméticas** (tolerância R$ 0,01): crédito descontado do M200 = soma dos M100; crédito de períodos anteriores = soma dos 1100; contribuição devida = apurada − créditos; a recolher = devida − retenções − deduções; total = não cumulativa + cumulativa; soma dos M205 = total a recolher; no M100: disponível = apurado + acréscimos − reduções − diferido, saldo = disponível − descontado, ajustes = soma dos M110; no M210: período = apurada + acréscimos − reduções − diferida + diferida anterior; no 1100: saldos disponível e final.
- **Conferência com documentos:** base do M105/M505 (CST 50–56 e 60–66) × soma dos documentos da mesma escrituração (C170, A170, C191/C195, C501/C505, D101/D105, D501/D505, F100, F120, F130; documentos cancelados excluídos), por competência, natureza e CST. Natureza do C170 e do C191/C195 derivada do CFOP. Para CST de rateio (53–56, 63–66) a base total, repetida por tipo de crédito, é contada uma vez. **Não entram:** C395/C396, F150, F200–F211, 1101/1501.
- Descrições de códigos (`tabelas_efd.py`): só as conferidas — CST (Tabela 4.3.3), natureza da base (4.3.7), tipo de crédito (4.3.6), código de contribuição e de receita mais usuais. Fora disso, só o código.
- Aviso de leiaute quando a linha tem quantidade de campos diferente da esperada.

---

## 9. Busca por fornecedor (`fornecedor.py`)

- Sugestões por CNPJ/CPF (só dígitos), raiz (8 dígitos, oferece "todos os estabelecimentos") ou nome; ordenadas por valor de entradas.
- **Perfil:** cadastro (0150 de todos os arquivos, versões distintas com primeira/última competência, códigos `COD_PART` usados), alterações 0175, totais e quebras do consolidado (mês, filial, CFOP, item, status, CST PIS, natureza), notas e itens.
- **Linhas nos arquivos** (`participant_lines_sql`): documentos com `COD_PART` (C100, C500, D100, D500, D700, H010, A100, F100) cujo código, **dentro do próprio arquivo** (na EFD, dentro do mesmo estabelecimento), aponta para o CNPJ/CPF no 0150; os registros filhos desses documentos; C191/C195 da EFD (CNPJ no próprio registro); o 0150 e o 0175. Retorna entradas **e saídas**; resumo por registro com contagem de entradas/saídas.
- Limite conhecido: registros que não estão no catálogo (por exemplo C113, E113) não são ligados ao participante.

---

## 10. API (FastAPI, `app/api/server.py`)

Grupos: `/api/meta`, `/api/state`, `/api/options`; análise (`/api/aggregate`, `/totals`, `/count-docs`, `/pivot`, `/documents`, `/lines`); relatório (`/api/report`, `/api/export/report`); exportações (`/api/export/summary|lines|documents|audit|blocom|fornecedor`, `/api/download/{nome}`); regras e filtros (`/api/rules/*`, `/api/filters`); snapshots (`/api/snapshots*`); auditoria (`/api/audit/*`); central de arquivos (`/api/hub/*`: stats, coverage, files, log, import, upload, rebuild, remove-files, remove-competencias, backup, restore); tarefas em segundo plano (`/api/jobs*`, com progresso); arquivos como estão (`/api/raw/{tipo}/overview|registers|query|lines|export`, `/api/raw/pending`, `/api/raw/index`); Bloco M (`/api/blocom/*`); fornecedor (`/api/fornecedor/*`); seletor de pasta nativo; servidor dos arquivos estáticos.
Endpoints síncronos rodam no pool de threads; cada consulta usa cursor próprio do DuckDB; escrita sob `write_lock`. Erros de regra (`FilterError`, `RawQueryError`, `ReportError`, `FornecedorError`) viram HTTP 400 com mensagem em português.

---

## 11. Interface — layout, componentes e comportamento

### 11.1 Identidade visual
- **Tema** claro, escuro ou "seguir o sistema" (classe `dark` no `<html>`, escolha em `localStorage`). Cores definidas como variáveis CSS (RGB) e expostas ao Tailwind (`bg`, `panel`, `sunken`, `line`, `fg`, `muted`, `accent`, `ok`, `warn`, `bad`, `info`):

| Token | Claro | Escuro |
|---|---|---|
| `--bg` (fundo da página) | 246 247 249 | 11 13 18 |
| `--panel` (cartões, barras) | 255 255 255 | 18 21 28 |
| `--sunken` (áreas rebaixadas, cabeçalho de tabela) | 241 243 246 | 24 28 36 |
| `--line` (bordas) | 226 230 236 | 39 45 56 |
| `--fg` (texto) | 17 24 39 | 229 233 240 |
| `--muted` (texto secundário) | 100 112 132 | 141 151 170 |
| `--accent` (índigo) | 79 70 229 | 129 140 248 |
| `--ok` / `--warn` / `--bad` / `--info` | 22 163 74 / 202 138 4 / 220 38 38 / 37 99 235 | 74 222 128 / 250 204 21 / 248 113 113 / 96 165 250 |

- **Tipografia:** Inter (variável), 13,5 px no corpo, 13 px nos controles, 11–12,5 px em rótulos e textos de apoio; números com algarismos tabulares (classe `num`, `font-feature-settings: tnum`). Rótulos de seção em caixa alta, 11 px, espaçados, cor `muted`.
- **Forma:** cartões `rounded-xl` com borda e sombra leve (`shadow-card`), controles `rounded-lg` com 34 px de altura (botão pequeno 28 px), popovers com `shadow-pop` e animação curta de entrada, barras de rolagem finas, seleção de texto em índigo translúcido.
- **Estados:** esqueleto com brilho (`skeleton`) enquanto carrega, barra de carregamento fina no topo das grades, avisos (sonner) no canto inferior direito (sucesso, alerta, erro, com ação "Abrir pasta"), estados vazios com ícone + título + explicação, foco visível em índigo.
- **Ícones:** lucide-react, 14–18 px.
- **Cores com significado fixo:** verde = crédito/OK/sem duplicidade; vermelho = a recolher/divergência; âmbar = aviso (arquivos pendentes, truncamento, leiaute); índigo = seleção/ação principal; chips de montagem do relatório: índigo (linhas), azul (colunas), verde (valores).

### 11.2 Estrutura geral da janela
```
┌ barra lateral 236 px ┬ cabeçalho (título + subtítulo da tela)  48/56 px ───────────────┐
│ logo + nome          ├────────────────────────────────────────────────────────────────┤
│ Análise              │                                                                │
│ Relatório dinâmico   │              área da tela (preenche a altura)                  │
│ Busca por fornecedor │                                                                │
│ APURAÇÃO             │   barra de filtros / ações  (quebra em várias linhas se preciso)│
│  Bloco M (PIS/Cofins)│   cartões, indicadores                                         │
│ ARQUIVOS COMO ESTÃO  │   GRADE PRINCIPAL (ocupa o espaço restante, com rolagem própria)│
│  SPED Fiscal         │   painel inferior opcional (notas, detalhes) com divisor       │
│  EFD-Contribuições   │                                                                │
│ GESTÃO               │                                                                │
│  Arquivos            │                                                                │
│  Regras e filtros    │                                                                │
│  Auditoria           │                                                                │
│ FILTROS SALVOS (1 clique)                                                             │
│ ─ Tema · Recolher menu · Tamanho (Ctrl +/−) · "100% local · vX" ──────────────────────┘
```
- Barra lateral recolhível a 60 px (só ícones, com dicas); começa recolhida em janelas com menos de 1280 px de largura quando o usuário ainda não escolheu. A lista de navegação tem rolagem própria em telas baixas.
- Telas de grade (Análise, Relatório, Busca, Bloco M, SPED, EFD, Auditoria) usam `overflow-hidden` e distribuem a altura entre seus blocos; telas de formulário/gestão (Arquivos, Regras) rolam.
- Espaçamento: em telas com altura ≥ 821 px (variante `tall:`) o preenchimento é 20 px e o espaço entre blocos 12 px; abaixo disso, 12 px e 8 px; cabeçalho de 56 px vs 48 px; itens do menu de 36 px vs 32 px.

### 11.3 Layout de cada tela

**Análise**
1. Linha de filtros globais: botões **Período, Filial, Fornecedor, CFOP, Item, UF, Mais** (cada um abre um popover com busca instantânea e lista com valor contábil; "Mais" = razão social, raiz de CNPJ, descrição, prefixos de CFOP e NCM). À direita: "Recolher indicadores", tela cheia e a etiqueta da tabela consultada (`agg_*`/itens) com o tempo em ms. Abaixo, chip da regra ativa (se houver).
2. **Indicadores:** grade de 8 cartões (Valor contábil com nº de documentos/linhas, ICMS, ICMS-ST + FCP, IPI, PIS, COFINS, Tributos recuperáveis com % do valor contábil, Custo líquido) + cartão **Evolução mensal** (barras do valor contábil com a parcela recuperável em verde, últimos 24 meses, dica ao passar o mouse) em telas largas. Recolhido, vira uma linha de resumo.
3. **Barra de visualização:** alternância **Árvore / Tabela / Mês a mês**; editor da hierarquia (reordenar e escolher níveis); escolha de **Colunas** (contador); "Recolher tudo"; **Exportar** (resumo, itens em xlsx/csv/parquet); **Congelar análise**.
4. **Grade** (restante da altura, mínimo 220 px) com linha **Total** fixa no rodapé. Árvore: seta ▸ ou duplo clique abre o nível seguinte (Unidade ▸ Fornecedor ▸ CFOP ▸ Item), cada nível carregado só ao abrir.
5. **Painel de notas fiscais** abaixo da grade ao clicar numa linha: divisor arrastável (altura guardada), botões "Notas" e "Itens" (Excel), contador de documentos; sem seleção, mostra uma dica.

**Relatório dinâmico**
1. Filtros globais iguais aos da Análise.
2. Corpo em duas colunas: **painel "Campos"** (264 px, arrastável/recolhível) e a área principal.
3. Painel Campos: busca; lista de **Dimensões** (alça de arrastar, nome, etiqueta "linha"/"coluna" quando em uso) e de **Valores**; clique adiciona.
4. Área principal, de cima para baixo: cartão **Montagem** com três zonas tracejadas lado a lado (**Linhas** 1,4 fr, **Colunas** 0,8 fr, **Valores** 1,4 fr), onde os campos viram "chips" numerados, reordenáveis e removíveis (arrastar e soltar nativo); pode recolher para uma linha de resumo.
5. Barra de controles: **Ordenar por** (valores ou dimensões) + **Maior→menor / Menor→maior** (ou Z→A / A→Z para dimensões) + **Mostrar** (50 a 20.000) + campo de **texto** + **Filtros por valor** (popover, contador) + chave **Subtotais** + (à direita) **Modelos** (6 prontos + "Meus modelos" + salvar montagem atual) + **Excel**.
6. Chips dos filtros por valor ativos; linha de status (nº de linhas, aviso de truncamento, selo verde "Consolidado SPED Fiscal + EFD-Contribuições, sem duplicidade" com explicação, tabela usada e ms, botão de tela cheia).
7. Grade com colunas de dimensão fixas à esquerda (largura 110–250 px conforme a dimensão), valores à direita, coluna por competência quando há pivô (`valor · métrica` + `TOTAL`), linhas de subtotal em negrito com ícone Σ, Total fixo; painel de notas com divisor abaixo.
Modelos prontos: Unidade›Fornecedor›CFOP›Descrição do item (valores e tributos); Fornecedor›Descrição (quantidade e preço médio); CFOP mês a mês; Unidade mês a mês (ICMS, PIS, COFINS); Unidade›CST PIS (bases e créditos); Fornecedor por status na EFD.

**Busca por fornecedor**
1. Barra: **caixa de busca** (CNPJ, CPF, raiz ou nome) com lista suspensa navegável por teclado — cada sugestão mostra nome, CNPJ·UF e "R$ … em entradas"; opção "todos os N estabelecimentos da raiz"; opção "procurar este CNPJ nos arquivos" quando não consta no cadastro — + período (de/até) + **Excel completo**.
2. Sem seleção: estado vazio explicativo e chips de **Recentes** (até 8).
3. Com seleção: cartão-cabeçalho (nome, CNPJ, UF, IE, endereço, etiqueta "N versões de cadastro", tempo) + 8 indicadores recolhíveis (valor contábil e nº de documentos, ICMS, ICMS-ST+FCP, IPI, PIS, Cofins, recuperáveis, linhas nos TXT).
4. Abas (segmentado): **Visão geral** (entradas por competência com mini-gráfico e tabela, por unidade, por CFOP, situação na EFD, CST PIS, natureza do crédito), **Notas fiscais**, **Itens** (grade com item fixo e tela cheia), **Nos arquivos (n)** (lista lateral de registros agrupados por SPED Fiscal / EFD-Contribuições, com contagem de entradas e saídas; ao lado, grade do registro com **Todas/Entradas/Saídas**, Excel e tela cheia), **Cadastro** (versões do 0150, alterações 0175, todos os 0150).

**Bloco M (PIS/Cofins)**
1. Barra: filtro **Empresa**, período, chave **PIS/Pasep | Cofins**, tempo, "Recolher indicadores", **Excel**. Abaixo, avisos: arquivos pendentes de indexação (âmbar, com ações), arquivos sem Bloco M, leiaute diferente do esperado.
2. **Indicadores** (6): apurado (com não cumulativo/cumulativo), créditos apurados (ajustes e disponível), créditos descontados (período/anteriores), retenções e deduções, **a recolher** (vermelho), saldo de créditos.
3. Abas (8) + selo "verificações sem divergência" (verde) ou "N divergências" (vermelho): **Apuração** (gráfico de 3 barras por mês — contribuição, crédito apurado, a recolher — e demonstrativo com uma coluna por competência + Total, subtotais em negrito, código do campo ao lado de cada linha), **Créditos** e **Ajustes** e **Receitas não tributadas** (mestre acima, detalhe abaixo, divisor arrastável; clicar no mestre filtra o detalhe), **Contribuição**, **Saldos de créditos**, **Conferência com documentos** (caixa explicativa, resumo por competência, detalhe por natureza/CST com chave "Só diferenças"; diferenças em vermelho, zero em verde), **Verificações** (caixa explicativa, grade com selo OK/Divergente e chave "Só divergências").

**SPED Fiscal / EFD-Contribuições (arquivos como estão)**
1. Filtros: **Período, Unidade, Arquivo**, segmentado **Todas/Entradas/Saídas**, texto em qualquer campo, "Limpar filtros". Banner de indexação quando há arquivos antigos.
2. **Painel de registros** (300 px, arrastável/recolhível): alternância **Por registro / Arquivo**, busca, registros agrupados por bloco (título do bloco, código em fonte monoespaçada, descrição, contagem).
3. Cartão principal: cabeçalho com código do registro, descrição, nº de linhas, tempo e "contexto do documento-pai"; **Condições** (popover 560 px com campo, operador, valor), **Exportar** (Excel/CSV), tela cheia; chips das condições; grade densa (linha de 32 px) com colunas de contexto (competência, unidade, linha, dados do pai), campos oficiais do registro, participante/item (0150/0200), arquivo e **Linha original**. Modo Arquivo: seletor do arquivo, filtro de registros, grade com o texto de cada linha.

**Arquivos** (gestão): indicadores da base; cartão de importação (pasta ou arquivo, "Procurar…" na janela nativa, nº de processos, **Importar**, área de arrastar/soltar com barra de envio); progresso e resultado por arquivo (IMPORTADO, SUBSTITUIDO, INDEXADO, DUPLICADO, IGNORADO, ERRO); matriz de **cobertura filial × mês**; lista de arquivos com remoção (por arquivo ou por competência); backup e restauração; log; reconsolidação.

**Regras e filtros:** construtor de regras E/OU com grupos aninhados (campo, operador conforme o tipo, valor), prévia do SQL, teste (linhas e valores), modelos prontos, biblioteca de filtros salvos por categoria (aplicar, excluir), visualizador de análises congeladas (verificar integridade, exportar, restaurar contexto). Em telas largas: construtor à esquerda e biblioteca à direita (420 px).

**Auditoria:** linha com o escopo (usa o período/filiais da Análise), tolerância em R$, **Executar verificações**, **Exportar todas**; grade de 3 colunas com os grupos de verificações (ícone de estado, texto, contagem em vermelho quando há ocorrência; a de diagnóstico é informativa); cartão de detalhe com a grade da verificação escolhida, Excel e tela cheia.

### 11.4 Componentes (`frontend/src/components`)
- `ui.tsx`: Button (outline, primary, secondary, ghost, danger; tamanhos sm/md/ícone), Input (com ícone), Select, Checkbox, Switch, Segmented, Card, CardHeader, Badge (tons neutro, accent, ok, warn, bad, info), Kpi, Popover, Dialog, Menu/MenuItem, Tip (dica), Confirm, Field, Empty, Progress, Spinner.
- `DataGrid.tsx`: grade **virtualizada** (renderiza só as linhas visíveis; 16 linhas de reserva), colunas redimensionáveis (arrastar a borda), colunas fixas à esquerda, largura automática das numéricas pelo maior valor formatado, ordenação por clique no cabeçalho, árvore expansível, seleção de linha, caixas de marcação, linha **Total** fixa, linhas de subtotal, rolagem infinita (`onEndReached`), CNPJ formatado, números `pt-BR` (valor com 2 casas, quantidade até 3, preço até 4).
- `FilterBar.tsx`: botões de filtro com lista pesquisável (`MultiList`), editor de hierarquia, seletor de colunas.
- `layout.tsx`: `SidePanel` (largura arrastável, duplo clique restaura, recolhe para uma aba vertical), `useDragHeight` (divisor de altura de painel inferior), `useMaximize`/`MaxButton`/`MaxBackdrop` (tela cheia de uma tabela, Esc sai), `CollapseToggle`/`useCollapsed` (recolher indicadores e montagem; começam recolhidos com altura < 820 px), `useLocal` (preferência por computador em `localStorage`, chaves `ui:*`).
- `MiniTable.tsx` (tabela compacta com ordenação e total), `IndexBanner.tsx` (indexação de arquivos antigos, com "Indicar a pasta dos arquivos").
- Utilitários: `lib/format.ts` (moeda, número, CNPJ/CPF, data, competência), `lib/api.ts` (cliente HTTP, upload com progresso, acompanhamento de tarefas), `lib/exporting.ts` (gerar exportação, avisar e baixar), `lib/store.tsx` (estado único), `lib/types.ts`.

### 11.5 Ajuste à tela (v2.3)
Janela nativa abre maximizada (mínimo 960×600) e aceita zoom do navegador (Ctrl +, Ctrl −, Ctrl 0, Ctrl + roda) e seleção/cópia de texto; painéis laterais com largura arrastável e recolhíveis; painéis inferiores com altura arrastável; tela cheia nas tabelas; indicadores e montagem recolhíveis; espaçamentos menores em telas baixas. Sem pywebview, o programa abre no navegador em `127.0.0.1`.

### 11.6 Estado e desempenho no cliente
Estado único salvo automaticamente na API (600 ms após a última mudança) e restaurado ao abrir; normalizado ao carregar (descarta dimensões/métricas que não existem mais, migra estado de versões anteriores); consultas com debounce e cancelamento por geração; árvore busca só o nível aberto; contagem de documentos chega depois, sem travar a tela; grades virtualizadas; exportações geradas no servidor com aviso e abertura da pasta.

---

## 12. Testes (138) e desempenho

| Arquivo | Qtde | Cobre |
|---|---|---|
| `test_pipeline.py` | 18 | detecção, duplicidade, retificadora, fechamento C170 = C190, rateio de frete, N1/N3/DOC, Exceção 2, 0175, filtros, auditoria, cobertura, exportação, snapshot, backup, remoção |
| `test_cruzamento.py` | 22 | arquivos que **não** são espelhos: itens em ordem invertida, item só na EFD, código diferente, valor divergente, nota duplicada ou ausente, nota sem chave, CT-e sem D190, notas em meses diferentes; em todos, PIS/Cofins da EFD = totalizador; agregadas = fato |
| `test_api.py` | 10 | todos os endpoints usados pela interface |
| `test_raw.py` | 10 | linhas guardadas idênticas ao TXT, saídas e canceladas presentes, contexto do pai, unidade na EFD, filtros, paginação, exportação, indexação |
| `test_report.py` | 64 | 60 combinações de dimensões sem duplicidade, ordenação, limite, texto, filtros por valor, exportação |
| `test_blocom_fornecedor.py` | 12 | Bloco M (coerente e com divergências, leiaute antigo, sem Bloco M), busca por fornecedor |
| `test_reindex.py` | 2 | arquivos antigos movidos e renomeados: indexação pela pasta e reimportação |

Dados de teste: `tests/sample_data.py` gera SPED Fiscal e EFD-Contribuições sintéticos no leiaute oficial (2 filiais, 2 competências, NF com 2 itens e frete, emissão própria sem C170, uso e consumo, nota cancelada, saída, energia, CT-e, serviço A100/A170, F100/F120, C190/C191/C195, Bloco M e 1100/1500 coerentes). `tests/perf_gen.py` gera volume grande.

Desempenho medido (ambiente de desenvolvimento, 4 vCPUs; detalhes e tabelas no README):
- importação de 5 arquivos / 3,6 milhões de linhas / 520 MB: ~36–53 s (conforme a medida), banco +169 MB para guardar as linhas originais;
- com fato de 28,8 milhões de linhas: consultas por filial/fornecedor/item entre 3 e 34 ms; visão plana de 4 níveis (5 mil maiores) 0,86 s;
- relatório dinâmico (fato de 1,2 milhão): 13 ms a 0,43 s;
- busca por fornecedor: sugestões 5 ms, perfil 44 ms, linhas nos arquivos 0,32 s, grade de um registro 0,6–0,7 s; Bloco M 0,13 s.

---

## 13. Limites conhecidos (verificados no código)

1. **Só entradas** são consolidadas. Devoluções de compra (saídas, CFOP 5.2xx/6.2xx) não são abatidas.
2. O C190 da EFD-Contribuições também abrange devoluções (Guia Prático); hoje todo C191/C195 é tratado como crédito de entrada. Se vier CFOP de saída, aparece como "Somente EFD". Não verificado em arquivos reais.
3. **C197** (ajustes/benefícios por documento) e **E111/E116** são lidos/guardados, mas não entram em nenhum valor consolidado.
4. O campo **SUFRAMA** existe nos leiautes (0000 e 0150 do SPED Fiscal; 0000, 0140 e 0150 da EFD-Contribuições) e fica disponível nas telas "como estão", mas **não é carregado na fato nem usado em análise**.
5. Conferência do Bloco M não cobre C395/C396, F150, F200–F211, 1101/1501.
6. Descrições de códigos do Bloco M limitadas às tabelas conferidas.
7. Os testes usam arquivos sintéticos. Em arquivos reais (a base do usuário tem centenas de arquivos) o comportamento de leiautes fora do padrão não foi observado, exceto o que a tela de aviso de leiaute detecta.
8. A natureza da base de crédito por CFOP (`ref_cfop_nat_bc_cred`) é uma derivação padrão; precisa de revisão por especialista.

---

## 14. Pontos de extensão (onde mexer para customizar)

| Necessidade | Onde |
|---|---|
| Regras (situações excluídas, CST de crédito, itens sintéticos, tolerâncias) | `app/config.py` |
| Nova coluna ou regra na consolidação | `queries_join.sql` (etapa correspondente) + `schema.sql` (fato) + `aggregates.py` (`_BASE/_FORN/_ITEM`, `MEASURES`) + **incrementar `FATO_VERSION`** |
| Ler campos novos dos TXT (ex.: SUFRAMA, C197 detalhado) | `parser/layouts.py`, `sped_fiscal.py`/`efd_contrib.py`, `normalizer.py` (`SCHEMAS`) |
| Nova dimensão/métrica de análise | `analytics.py` (`DIMENSIONS`, `METRICS`), `filter_builder.py` (`FIELDS`) |
| Novos registros nas telas "como estão" | `parser/catalog.py` (descrição e leiaute) |
| Nova verificação de auditoria | `audit.py` (`CHECKS`) |
| Nova tela | `frontend/src/pages/`, `App.tsx` (`PAGES`), `lib/types.ts`/`store.tsx` (estado), endpoint em `server.py` |
| Dados de teste | `tests/sample_data.py` |
| Tabelas de códigos | `database/tabelas_efd.py`, `ref_cfop_nat_bc_cred` |

Cuidados já aprendidos: scripts com multiprocessing `spawn` exigem o guard `if __name__ == "__main__"`; na API do DuckDB 2.0, relação não tem `fetchone()` (usar `.limit(1).fetchall()`) e `.pl()` deve ser chamado a partir de `cursor.sql(...)`; `export_query_excel` recebe `info=` por nome; recompilar a interface (`npm run build`) após qualquer mudança em `frontend/src`.

---

## 15. Empacotamento e entrega

- Zip `ConsolidacaoFiscalSPED.zip` com os arquivos versionados no git, `.sh` com permissão de execução, prefixo `ConsolidacaoFiscalSPED/`.
- Windows: `instalar.bat` (cria `.venv`, instala dependências; só aqui precisa de internet), `iniciar.bat`, `iniciar_demonstracao.bat` (gera arquivos de exemplo e importa), `abrir_no_navegador.bat`. macOS/Linux: `instalar.sh`, `iniciar.sh [--demo] [--browser]`.
- Atualização: extrair por cima da pasta antiga **sem apagar `data/`**, rodar `instalar.bat`; a base é refeita sozinha quando `FATO_VERSION` muda.
- Arquivos importados antes da v2.1 (sem linhas originais): "Indexar agora" (caminho original) ou "Indicar a pasta dos arquivos" (reconhece cada TXT pelo hash, mesmo renomeado ou movido); reimportar os mesmos TXT também guarda as linhas.

## 16. Histórico (commits na branch)

`fd423e3` sistema base → `fbaf8c3` instaladores → `ed6dab4` correção do cruzamento e relatório rápido → `d61c249` interface React (substitui NiceGUI) → `d224fba` telas SPED Fiscal / EFD-Contribuições → `2f6502c` relatório dinâmico (v2.2.0) → `822e00b` Bloco M, busca por fornecedor, interface ajustável (v2.3.0) → `f3f8e90` indexação a partir da pasta atual (v2.3.1).
