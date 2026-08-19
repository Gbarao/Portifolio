# Dicionário de dados — Passo 2

Rastreabilidade entre o modelo conceitual da especificação (seção 10) e as
tabelas implementadas. Convenções válidas em todo o schema:

- **Unidades normalizadas:** peso em quilogramas, distância em quilômetros,
  tempo em horas, valor em BRL. A unidade original do documento é preservada
  em campo próprio (ex.: `lote_compra.unidade_negociada`).
- **Percentuais:** gravados como fração decimal — 9,25% é persistido `0.0925`.
- **Dinheiro e quantidade:** `NUMERIC(18,6)`. Nenhuma coluna usa ponto
  flutuante (há teste que garante isso).
- **Vigência:** tabelas versionadas nunca são editadas no lugar; uma alteração
  encerra a vigência atual e abre nova, para que cotações antigas continuem
  reproduzíveis.

## Correspondência com a seção 10

| Entidade da especificação | Tabela(s) | Observação |
|---|---|---|
| `empresa_parametro` | `empresa`, `unidade`, `empresa_parametro` | Regime é atributo do CNPJ, por isso vive em `empresa_parametro` versionado por unidade |
| `material` | `material`, `material_saida_esperada` | O mix esperado de saída sustenta custo-padrão e rateio conjunto |
| `parceiro` | `parceiro` | Regime e condição de contribuinte são chave fiscal, não dado cadastral |
| `contrato_tabela` | `contrato_tabela` | Versionada por vigência |
| `lote_compra` | `lote_compra` | Unidade básica de rastreamento |
| `evento_balanca` | `evento_balanca` | Correção entra por `ajuste_de_evento_id`, sem apagar o original |
| `evento_qualidade` | `evento_qualidade` | Define a quantidade aceita |
| `evento_processo` | `evento_processo` | Consumo de direcionador por atividade (ABC) |
| `lote_saida` | `lote_saida` | Guarda fator de rateio e custo conjunto atribuído |
| `rejeito_perda` | `rejeito_perda` | `integra_custo_padrao` separa perda normal de anormal |
| `empregado_custo` | `recurso`, `empregado_custo` | Somente componentes; totais são calculados pelo motor |
| `veiculo_custo` | `recurso`, `veiculo_custo` | Fixo mensal e variável por km/hora separados |
| `maquina_custo` | `recurso`, `maquina_custo` | Capacidade teórica e prática em colunas distintas |
| `centro_custo` | `centro_custo` | Natureza separa produtivo de administrativo/comercial |
| `atividade_taxa` | `atividade`, `atividade_taxa` | Taxa = pool ÷ capacidade **prática** |
| `regra_tributaria` | `regra_tributaria` | Matriz de regras; ver detalhamento abaixo |
| `cotacao_venda` | `cotacao_venda`, `cotacao_versao`, `cotacao_preco` | Premissas congeladas por versão; um registro de preço por camada |
| `pedido_venda` | `pedido_venda` | Nasce de uma versão aprovada de cotação |
| `evento_frete` | `evento_frete` | `km_vazio` é coluna separada e obrigatória |
| `fechamento_mensal` | `fechamento_mensal` | Guarda ociosidade e perda anormal explícitas |
| `auditoria` | `auditoria` | Append-only |

## Tabelas acrescentadas além da seção 10

| Tabela | Por quê |
|---|---|
| `usuario` | Perfis da seção 13.1, alçadas e restrição a dados salariais |
| `imovel_custo` | Seção 6.5 exige custo de ocupação por área e tempo |
| `despesa_estrutural` | Seção 6.7 — fora do custo contábil, dentro do preço sustentável |
| `movimento_estoque` | Giro, idade e VRL do estoque (indicadores da seção 12.3) |
| `faixa_simples_nacional` | Necessária para calcular a alíquota efetiva do DAS |
| `apuracao_rbt12` | Base do alerta de mudança de faixa (seção 7.7-C) |
| `apuracao_tributaria` | Saída obrigatória do motor fiscal (seção 9.6), gravada por operação |
| `memoria_calculo` / `memoria_passo` | Reprodutibilidade exigida pelas regras 15 e 11 da seção 11 |
| `alerta` | Feedback visual e bloqueios (seção 16) |
| `simulacao_cenario` | Cenários obrigatórios da seção 14 |

## `regra_tributaria` — as três flags que governam o efeito econômico

| Coluna | Efeito |
|---|---|
| `compoe_deducao_venda` | Entra na variável `r` da fórmula `P = C ÷ [(1-r)(1-m)]` |
| `gera_credito_compra` | Reduz o custo `C` — apenas com recuperabilidade `ELEGIVEL` e condição confirmada |
| `compoe_custo_nao_recuperavel` | Soma ao custo de aquisição |
| `incide_sobre_lucro` | Marca IRPJ/CSLL do Lucro Real: ficam fora de `r`; a margem-alvo é pré-tributo |
| `requer_confirmacao_condicao` | Regra condicional (ex.: Lei 15.394/2026): gera alerta e não abate crédito até confirmação |

Chaves nulas funcionam como coringa. A resolução escolhe a regra mais
específica **vigente na data da operação** — nunca na data de hoje.

## Como os três regimes ficam representados

| Regime | Custo `C` | Deduções `r` |
|---|---|---|
| Lucro Real | Reduzido por créditos não cumulativos; Lei 15.394/2026 aplicada por regra condicional | PIS/COFINS + ICMS de saída; IRPJ/CSLL marcados `incide_sobre_lucro` e excluídos |
| Lucro Presumido | Sem crédito na compra (`compoe_custo_nao_recuperavel`) | PIS/COFINS cumulativos + ICMS + presunção IRPJ/CSLL (`percentual_presuncao_base × aliquota`) |
| Simples Nacional | Nota integral é custo (`gera_credito_compra = false`) | Alíquota efetiva do DAS resolvida em `faixa_simples_nacional` a partir da RBT12 |

## Aviso sobre os dados de demonstração

Todas as alíquotas, faixas, capacidades e rendimentos das seeds são
**exemplos**. Entram no banco com `status_dado = ESTIMADO` e
`status = PROVISORIA`, e há teste garantindo que nenhuma regra de seed nasce
`VALIDADA`. Enquanto o responsável fiscal não validar cada regra, o sistema
deve bloquear cotação definitiva — conforme as seções 9.1, 11 e 16.
