# Consolidação Fiscal SPED — especificação completa do que foi construído (v2.3.1)

Documento de referência para recriar ou customizar o sistema. Descreve o que **existe no código**, não o que foi planejado.
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

### 4.1 Dimensões
- **Filial:** SPED Fiscal = CNPJ do 0000 (um arquivo por estabelecimento); EFD-Contribuições = CNPJ do 0140/bloco de movimento. Nome/UF pelo registro mais recente.
- **Fornecedor unificado:** `COD_PART` → 0150 **do próprio arquivo** → CNPJ/CPF (só dígitos); sem CNPJ/CPF usa `EXT:<nome>`; sem 0150, `PART:<cod>`. Raiz = 8 primeiros dígitos. Nome na data do documento via 0175 (campo 3 = nome; vale o conteúdo anterior se a alteração é posterior à data do documento).
- **Item:** 0200 de cada arquivo (tipo, NCM, CEST, código de barras); `dim_item_depara` a partir do 0205 e de `COD_ANT_ITEM` unifica códigos antigos/novos; `chave_item_global` = `NCM|código`.

### 4.2 Vínculo de documentos (estritamente 1:1) — `t_docmatch`
1. Pela **chave** do documento eletrônico (CHV_NFE/CHV_CTE/CHV_DOCe) na mesma filial e família (C100, C500, D100, D500/D700→D500), em qualquer competência do escopo. Se há duplicidade de chave, só o primeiro de cada lado participa.
2. Quando falta chave em um dos lados: filial + competência + CNPJ do fornecedor + modelo + série + número (zeros à esquerda ignorados); o k-ésimo documento de um lado casa com o k-ésimo do outro. **Nunca um para muitos.**

### 4.3 Linhas do SPED Fiscal — `t_item`, `t_anal_k`, `t_item_r`, `t_lin`
- Itens candidatos: C170 do SPED Fiscal; **Exceção 2** (nota de emissão própria sem C170 no SPED Fiscal): itens do C170 da EFD-Contribuições do documento vinculado (origem `EC_C170_VIA_CHAVE`, já com seu PIS/Cofins).
- Base do item = `VL_ITEM − VL_DESC + ICMS-ST + IPI`.
- **Rateio contra o C190:** agrupa itens e C190 por CST + CFOP + alíquota; a diferença entre `VL_OPR` do C190 e a soma das bases é distribuída proporcionalmente ao `VL_ITEM` (frete, seguro, outras despesas), com o resíduo de centavos no maior item — a soma por grupo fecha exatamente com o C190. FCP (C191) é rateado do mesmo modo. `vl_contabil = base + rateio`.
- Itens **sintéticos**: C190 sem item (`_SEM_ITEM_C190_`), energia/água/gás/telecom/frete — um por registro analítico (C590, D190, D590, D730) com item `_ENERGIA_`, `_AGUA_`, `_GAS_`, `_TELECOM_`, `_FRETE_CTE_` conforme o modelo (`config.ITEM_SINTETICO_POR_MODELO`).

### 4.4 Cascata de PIS/Cofins (`nivel_cruzamento_efd`)
Cada item da EFD-Contribuições é consumido **no máximo uma vez** (identificador `eid`).

| Nível | Critério |
|---|---|
| `N1_ITEM` | mesmo documento vinculado + mesmo `NUM_ITEM` + mesmo `COD_ITEM` + `VL_ITEM` igual (tolerância R$ 0,01). Inclui os itens da Exceção 2. |
| `N1V_POSICAO_VALOR` | mesma posição + mesmo `VL_ITEM` + mesmo CFOP, com código de item diferente entre os arquivos |
| `N2_ITEM_CFOP` | itens da EFD ainda não consumidos, por documento + `COD_ITEM` + CFOP, formam um "pool" rateado entre as linhas do SPED Fiscal da mesma chave (proporcional ao `VL_ITEM`) |
| `N3_CONSOLIDADO_C190` | C190 + C191/C195 da EFD: filial + competência + CNPJ do fornecedor + CFOP + `COD_ITEM`, rateado pelo `VL_ITEM` |
| `DOC_CHAVE` / `DOC_NUMERO` | C501/C505 (energia, água, gás), D101/D105 (frete), D501/D505 (telecom) do documento vinculado, rateados entre as linhas analíticas do SPED Fiscal (C590/D190/D590/D730) |
| `EC_EXCLUSIVO` | só existe na EFD por natureza (A100/A170 serviços, F100, F120, F130) ou a filial/competência não tem SPED Fiscal carregado |
| `EC_SEM_PAR` | há SPED Fiscal da filial no período, mas o item/documento/consolidação da EFD não achou correspondência: entra com **valor contábil 0** e todo o PIS/Cofins |

O rateio genérico (template `alocar`) distribui um pool sobre as linhas candidatas com a mesma chave, proporcional ao peso, com o resíduo de centavos no maior peso: a soma por pool é exatamente o valor do pool. Quem não passa no N1 nunca recebe crédito de outro item por posição.

Garantia (provada em teste): o PIS/Cofins somado na fato é igual ao PIS/Cofins bruto da EFD (`fechamento_efd` na auditoria deve ser 0); linhas "só EFD" mantêm o crédito sem inflar o valor contábil.

### 4.5 Colunas derivadas na carga (`fato_insert`)
- `nat_bc_cred` (Tabela 4.3.7): a informada no registro; senão derivada do CFOP pela tabela `ref_cfop_nat_bc_cred` (padrão: revenda `01`, insumo `02`, serviço insumo `03`, devolução `12`, ativo `11`, demais `13`), apenas quando o CST de PIS é de crédito; `nat_bc_cred_origem` = `INFORMADO` ou `DERIVADO_CFOP`. A tabela é editável/parametrizável.
- `vl_trib_recuperaveis` = ICMS + IPI (somente CST IPI `00`) + PIS (somente CST 50–56 e 60–66) + Cofins (idem).
- `vl_custo_liquido` = `vl_contabil − vl_trib_recuperaveis`.
- `status_efd`: "Escriturado na EFD-Contribuições", "Sem Crédito / Não Escriturado na EFD-Contribuições", "Somente EFD — sem correspondência no SPED Fiscal" (EC_SEM_PAR), "Exclusivo EFD-Contribuições" (EC_EXCLUSIVO).
- `doc_key` (inteiro) para contagem distinta rápida de documentos; ordenação física da carga por competência/filial/fornecedor/item (permite ao DuckDB pular blocos).
- Serviços tomados (A170) usam CFOP `SERV`; C500/D100/D500 sem par usam `N/D`; F100/F120/F130 usam `OUTROS`.

### 4.6 Tabela fato `fato_entradas_consolidadas`
Uma linha por item de entrada. Colunas: competência, filial (CNPJ, nome, UF, raiz), origem, registro do documento, ids de arquivo (SF e EFD), fornecedor (CNPJ/CPF, raiz, razão social, nome na data, UF), modelo, situação, emitente, série, número, chave, datas, item (código, unificado, global, descrição, tipo, NCM, CEST, barras, unidade), CFOP, natureza, CST/alíquota de ICMS, IPI, PIS e Cofins, natureza e origem do crédito, conta contábil, quantidade e todos os valores (item, desconto, rateio C190, contábil, bases e valores de ICMS/ST/FCP/IPI/PIS/Cofins, recuperáveis, custo líquido), `nivel_cruzamento_efd`, `status_efd`, flags de item sintético e sem C190, `doc_key`.

### 4.7 Tabelas agregadas (desempenho do relatório)
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
- Arquivos importados antes da v2.1 não têm linhas originais: banner de indexação (§11).

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

## 11. Interface — layout e padrões

### Identidade visual
Tema claro/escuro/sistema (variáveis CSS `--bg --panel --sunken --line --fg --muted --accent --ok --warn --bad --info`, expostas como cores Tailwind), fonte Inter, cantos arredondados (`rounded-xl` em cartões), sombras suaves, tipografia compacta (13 px nos controles, números tabulares na classe `num`), ícones lucide, avisos com sonner no canto inferior direito.

### Estrutura
- Barra lateral (236 px, recolhível a 60 px; começa recolhida abaixo de 1280 px de largura, se o usuário ainda não escolheu) com Análise, Relatório dinâmico e Busca por fornecedor (sem título de seção), e as seções Apuração (Bloco M), Arquivos como estão (SPED Fiscal, EFD-Contribuições), Gestão (Arquivos, Regras e filtros, Auditoria), filtros salvos com 1 clique, tema, aviso de tamanho (Ctrl +/−), versão.
- Cabeçalho com título e subtítulo da tela; conteúdo em `overflow-hidden` (grades) ou `overflow-auto` (telas longas).

### Componentes-chave (`frontend/src/components`)
- `ui.tsx`: Button, Input, Select, Checkbox, Switch, Segmented, Card, Badge, Kpi, Popover, Dialog, Menu, Tip, Confirm, Field, Empty, Progress.
- `DataGrid.tsx`: grade **virtualizada** (só as linhas visíveis), colunas redimensionáveis, coluna fixa, largura automática pelas colunas numéricas, ordenação, árvore expansível, seleção, linha de totais fixa, linhas de subtotal, rolagem infinita (`onEndReached`).
- `FilterBar.tsx`: botões de filtro com busca instantânea (período, filial, fornecedor, CFOP, item, UF, "Mais"), editor de hierarquia, seletor de colunas.
- `layout.tsx`: `SidePanel` (largura arrastável e recolhível, duplo clique restaura), `useDragHeight` (divisor de altura), `useMaximize`/`MaxButton` (tela cheia por tabela, Esc sai), `CollapseToggle`/`useCollapsed` (indicadores e montagem recolhíveis; começam recolhidos em telas com menos de 820 px de altura). Preferências guardadas em `localStorage` (`ui:*`), por computador.
- `MiniTable.tsx` (tabelas pequenas com ordenação e total), `IndexBanner.tsx` (indexação de arquivos antigos).
- Variante Tailwind `tall:` = altura ≥ 821 px; abaixo disso, espaçamentos menores.

### Janela nativa (`app/main.py`)
pywebview: abre maximizada, 960×600 mínimo, zoom do navegador (Ctrl +, Ctrl −, Ctrl 0, Ctrl + roda), seleção de texto. Sem pywebview, abre no navegador em `127.0.0.1`.

### Estado e desempenho no cliente
Estado único (`store.tsx`) salvo automaticamente na API em 600 ms; normalizado ao carregar (descarta dimensões/métricas que não existem mais); consultas com debounce; árvore busca só o nível aberto; contagem de documentos chega depois, sem travar a tela.

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
