# Motor de cálculo — Passo 3

Documentação das fórmulas implementadas e de onde cada uma vem na
especificação. Todo o motor é composto de funções puras: nenhum módulo de
`app/dominio/` ou `app/tributario/` conhece banco de dados, o que permite
testá-los isoladamente e reproduzir qualquer cálculo fora do sistema.

## Convenções

- Percentuais são frações decimais: 9,25% é `Decimal("0.0925")`
- Nenhum arredondamento intermediário — só na apresentação
- Toda função de cálculo aceita `memoria` opcional; quando informada, registra
  passo a passo (fórmula, entradas, resultado, fonte, vigência, status)

## Fórmulas

| Cálculo | Fórmula | Módulo | Seção |
|---|---|---|---|
| Balanço de massa | `Q_aceita = (bruto − tara) − recusada` ; `rendimento = Q_vendável ÷ Q_aceita` | `dominio/massa.py` | 7.1 |
| Custo de aquisição | `preço bruto − descontos + tributos não recuperáveis + frete e afins − créditos confirmados` | `dominio/aquisicao.py` | 7.2 |
| Custo por hora produtiva | `custo mensal integral ÷ horas produtivas práticas` | `dominio/recursos.py` | 6.2 |
| Custo da viagem | `variável/km × (km carregado + km vazio) + custo/hora × horas + parcela do fixo pela capacidade prática + pedágios` | `dominio/recursos.py` | 6.3 |
| Hora-máquina | `custos fixos ÷ horas práticas + consumo variável por hora` | `dominio/recursos.py` | 6.4 |
| Taxa de atividade | `pool de custos ÷ capacidade prática` | `dominio/abc.py` | 7.3 |
| Custo de transformação | `Σ (direcionador × taxa) + custos diretos exclusivos` | `dominio/abc.py` | 7.3 |
| Ociosidade | `(capacidade prática − utilização real) × taxa fixa` | `dominio/abc.py` | 7.3 |
| Produtos conjuntos | `VRL_i = qtd × (preço − gastos posteriores)` ; `custo_i = custo conjunto × VRL_i ÷ ΣVRL` | `dominio/conjuntos.py` | 7.4 |
| Ciclo financeiro | `dias estoque + dias recebimento − dias pagamento` | `dominio/capital.py` | 6.8 |
| Custo de capital | `capital × [(1 + taxa diária)^dias − 1]` | `dominio/capital.py` | 6.8 |
| Formação de preço | `P = C ÷ [(1 − r) × (1 − m)]` | `dominio/precos.py` | 7.6 |
| Preço máximo de compra | `(receita líquida − demais custos − lucro-alvo) ÷ quantidade aceita esperada` | `dominio/precos.py` | 14 |
| Alíquota efetiva do Simples | `(RBT12 × nominal − parcela a deduzir) ÷ RBT12` | `tributario/regimes.py` | 9.4 |
| Reconciliação do período | `resultado do período − (Σ resultados por lote − itens não atribuíveis)` | `dominio/reconciliacao.py` | 13.3 |

## Camadas de custo

As camadas são cumulativas. Cada componente declara a partir de qual degrau
passa a contar, e se é desembolso — a camada de caixa ignora depreciação e
provisões, que não saem do caixa hoje.

```
CAIXA  ⊂  CONTRIBUIÇÃO  ⊂  OPERACIONAL  ⊂  SUSTENTÁVEL
                                              └─ + margem estratégica → ALVO
```

As três visões da seção 2 convivem no mesmo cálculo sem se misturar: cada
componente declara em quais delas aparece. Despesa administrativa entra na
visão gerencial e no preço sustentável, mas não no custo contábil do estoque.

## Motor tributário

**Resolução da regra** (`tributario/resolucao.py`) opera em duas dimensões:

1. *Compatibilidade* — toda chave preenchida na regra precisa bater com o
   contexto; chave nula é coringa
2. *Especificidade* — entre as compatíveis, vence a que tem mais chaves
   preenchidas

A vigência é avaliada pela **data da operação**, nunca pela data de hoje. Uma
regra cadastrada como `VALIDADA` mas fora de vigência vale `VENCIDA`, e uma
única regra vencida bloqueia a cotação definitiva inteira — não existe cotação
"parcialmente definitiva".

**Aplicação da regra** (`tributario/calculo.py`) trata as formas de base:

| Forma | Base | Efeito sobre o preço |
|---|---|---|
| `POR_FORA` | `base × (1 − redução)` | alíquota × (1 − redução) |
| `POR_DENTRO` | base cheia | alíquota |
| `BASE_REDUZIDA` com presunção | `receita × presunção` | presunção × alíquota |
| `VALOR_FIXO` | valor da regra | valor ÷ base |
| `PAUTA` | `pauta unitária × quantidade` | valor ÷ base bruta |

**Composição de `r` por regime** (`tributario/regimes.py`):

| Regime | `r` | Custo `C` |
|---|---|---|
| Lucro Real | PIS + COFINS + ICMS de saída. IRPJ/CSLL marcados `incide_sobre_lucro` ficam fora; `m` é margem pré-tributo | Reduzido por créditos elegíveis e confirmados |
| Lucro Presumido | PIS + COFINS cumulativos + ICMS + presunção IRPJ (8% × 15% = 1,2%) e CSLL (12% × 9% = 1,08%) | Sem crédito: a nota inteira é custo |
| Simples Nacional | Alíquota efetiva do DAS pela faixa de RBT12, com ICMS segregável | Sem crédito algum |

## O alerta de mudança de faixa do Simples

`simular_mudanca_faixa` responde à advertência da seção 7.7-C. Exemplo real
do sistema, com RBT12 de R$ 700.000 e uma venda de R$ 40.000:

```
faixa 3 → 4
alíquota efetiva: 8,0200% → 8,1595%
DAS adicional do mês: R$ 3.347,46
alíquota marginal real da venda: 8,3686%
```

A venda parece custar 8,02% de DAS. Custa 8,37%, porque a alíquota nova
alcança **todo o faturamento do mês**, não apenas a venda que provocou a
mudança. Sem esse cálculo, o vendedor fecha um negócio achando que a margem é
maior do que é.

## Cobertura de testes

| Arquivo | Testes | Objeto |
|---|---|---|
| `test_aceitacao.py` | 11 | Os 11 casos de aceitação da seção 17 |
| `test_regimes_tributarios.py` | 9 | Tratamento por regime, RBT12, mudança de faixa |
| `test_dominio.py` | 20 | Massa, recursos, ABC, conjuntos, camadas, escada, alçadas |
| `test_schema.py` | 15 | Integridade do modelo de dados |

## Demonstração executável

```bash
.venv/bin/python -m app.aplicacao.demonstracao
```

Roda um lote de 12.000 kg do início ao fim, mostra o custo por camada, compara
a escada de preços entre Lucro Real e Lucro Presumido, dispara o alerta de
faixa do Simples e imprime a memória de cálculo.
