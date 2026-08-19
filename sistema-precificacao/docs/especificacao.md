# Modelo de precificação para operações de reciclagem

**Versão:** 1.1 (Atualizada com especificações por Regime Tributário)  
**Data de referência:** 19 de agosto de 2026  
**Finalidade:** especificação financeira, operacional, tributária e de governança para orientar a criação futura de um agente, sistema ou programa de precificação.  
**Escopo:** compra, coleta, recebimento, triagem, beneficiamento, armazenagem e venda de papelão, papel, plástico e outros materiais recicláveis, com frete próprio ou terceirizado.

> Este documento define a arquitetura do modelo. Ele não fixa alíquotas, enquadramentos fiscais ou critérios contábeis específicos da empresa. Regras tributárias devem ser parametrizadas, versionadas por vigência e validadas pelo contador ou assessor tributário, considerando regime da empresa, NCM, UF, município, CFOP, CST/CSOSN, fornecedor, cliente e natureza de cada operação.

---

## 1. Prompt mestre aprimorado

O texto abaixo pode ser copiado e entregue a outra IA para orientar a futura construção do agente ou programa.

```text
Atue como arquiteto de sistemas financeiros, controller industrial, especialista em custos, logística e precificação, com experiência no setor brasileiro de reciclagem e conhecimento de governança corporativa e tributação brasileira.

Sua missão é projetar, antes de escrever código, um sistema auditável de custeio e precificação para uma empresa que compra, coleta, recebe, separa, prensa, enfarda, armazena, transporta e vende materiais recicláveis, incluindo papel, papelão, plásticos e outros resíduos ou aparas.

O sistema deverá calcular o resultado por lote, material, produto de saída, fornecedor, cliente, rota, veículo, unidade e período. Use uma arquitetura híbrida formada por: custeio por lote; custeio baseado em atividades (ABC) para operações e logística; custeio por absorção gerencial para sustentabilidade no longo prazo; e margem de contribuição para decisões comerciais de curto prazo.

Não presuma valores, alíquotas ou tratamentos fiscais ausentes. Quando faltar um dado, solicite-o, use um parâmetro explicitamente identificado ou marque o cálculo como provisório. Nunca trate tributo destacado como custo sem avaliar sua recuperabilidade. Nunca trate crédito fiscal potencial como redução de custo antes de confirmar o direito, a documentação, o aproveitamento e o prazo de realização.

Modele, no mínimo:

1. Quantidade bruta, tara, quantidade líquida recebida, umidade, contaminação, impurezas, rejeitos, perdas normais e anormais, rendimento, quantidade vendável e coprodutos/subprodutos.
2. Preço de compra, descontos e bonificações, tributos não recuperáveis, créditos fiscais recuperáveis, frete de entrada, pedágio, seguro, descarga, pesagem, inspeção, destinação de rejeitos e demais custos de aquisição.
3. Mão de obra CLT com custo integral por empregado, função, atividade e centro de custo, incluindo salário, encargos patronais aplicáveis, benefícios, férias, adicional de férias, 13º salário, FGTS, adicionais, horas extras, afastamentos e provisões.
4. Frota própria por veículo e rota, incluindo combustível, motorista, ajudante, manutenção, pneus, lubrificantes, pedágios, seguro, licenciamento, rastreamento, depreciação ou arrendamento, custo de capital, quilômetros vazios, horas paradas e capacidade utilizada. Compare sempre com frete terceirizado.
5. Máquinas e equipamentos por hora-máquina, incluindo energia, operador, manutenção, peças, consumíveis, depreciação, seguro, disponibilidade, eficiência e capacidade prática.
6. Prédio e instalações, incluindo aluguel ou custo de ocupação, depreciação quando aplicável, IPTU, seguro, vigilância, limpeza, energia, água, manutenção, licenças e despesas ambientais.
7. Despesas administrativas, comerciais e de governança separadas dos custos de produção, mas consideradas no preço sustentável de longo prazo.
8. Capital de giro, prazo de estoque, prazo de recebimento, prazo de pagamento, inadimplência, volatilidade de preço, risco de qualidade, concentração de clientes e fornecedores e custo de oportunidade do capital.
9. Tributos por operação, com regras versionadas por data e parametrizadas por regime tributário, NCM, tipo de material, CFOP, CST/CSOSN, origem e destino, UF, município, perfil do fornecedor e cliente, recuperabilidade de créditos, diferimento, suspensão, isenção, redução de base, substituição tributária e obrigações da transição para CBS/IBS.
10. Preços mínimos distintos: preço de caixa/emergencial, preço mínimo de contribuição, preço operacional, preço sustentável e preço-alvo. Nenhum preço abaixo do sustentável deve ser apresentado como rentável sem alerta e justificativa.

Utilize capacidade normal ou prática para alocar custos fixos de produção. Evidencie separadamente o custo de ociosidade e não o transfira automaticamente para os produtos. Use direcionadores causais para o ABC, como toneladas recebidas, toneladas processadas, horas de triagem, horas-máquina, número de fardos, quilômetros, horas de veículo, área ocupada multiplicada pelo tempo e número de documentos.

Para processos que gerem vários materiais de saída, aproprie custos diretamente quando houver medição confiável. Para custos conjuntos não separáveis, aplique critério racional e consistente, preferencialmente valor realizável líquido relativo. Trate a receita de subproduto imaterial como redução do custo conjunto somente quando a política contábil e gerencial aprovada assim determinar.

O sistema deve produzir memória de cálculo completa, permitir simulações e explicar: dados de entrada; fonte; vigência; fórmula; direcionador; regra fiscal; premissas; alertas; responsável pela aprovação; versão; e reconciliação com contabilidade, folha, estoque, documentos fiscais e telemetria.

Antes do código, entregue:

- modelo conceitual e fluxo de cálculo;
- dicionário de dados;
- fórmulas e regras de negócio;
- matriz tributária parametrizável;
- política de rateio e tratamento de ociosidade;
- relatórios e indicadores;
- perfis de acesso e trilha de auditoria;
- casos de teste e critérios de aceitação;
- plano de implantação por etapas;
- lista de decisões e dados ainda pendentes.

Não confunda preço com valor contábil do estoque. Mantenha três visões reconciliáveis: custo contábil, custo gerencial completo e custo relevante para decisão. Toda recomendação comercial deve mostrar impacto em margem de contribuição, resultado operacional, caixa, capital de giro e sensibilidade a preço de compra, rendimento, frete, tributos e preço de venda.

Adote moeda, unidade de medida e arredondamento configuráveis. Internamente, normalize peso em quilogramas, distância em quilômetros, tempo em horas e valores em reais, preservando a unidade original do documento. Bloqueie cálculos com denominador zero, massa inconsistente, regra fiscal vencida ou dado obrigatório ausente.

Use como especificação funcional o restante do documento “Modelo de precificação para operações de reciclagem”. Não escreva o código antes de confirmar a arquitetura, os dados disponíveis, as regras tributárias validadas e os critérios de aceite com os responsáveis da empresa.
```

---

## 2. Decisão metodológica

O método recomendado é híbrido porque nenhuma técnica isolada responde bem a todas as decisões da empresa.

| Camada | Método | Uso gerencial |
|---|---|---|
| Material e estoque | Custo por lote, com custo médio ponderado ou identificação específica conforme a natureza do estoque | Saber quanto custou cada entrada e cada saldo |
| Operação | Custeio baseado em atividades (ABC) | Atribuir triagem, prensagem, movimentação, armazenagem e controle aos materiais que consomem essas atividades |
| Produção | Absorção gerencial com capacidade normal/prática | Formar preço sustentável e evidenciar ociosidade |
| Comercial | Margem de contribuição | Avaliar pedidos, clientes, rotas e decisões de curto prazo |
| Capital e risco | Custo econômico incremental | Incorporar prazo, inadimplência, volatilidade, qualidade e capital de giro |
| Fiscal | Motor de regras por operação e vigência | Distinguir débito, crédito, diferimento, suspensão, isenção e tributo não recuperável |

O sistema deve manter três visões simultâneas e reconciliáveis:

1. **Custo contábil:** segue a política contábil aprovada e serve para valorização do estoque e apuração contábil.
2. **Custo gerencial completo:** inclui custos e despesas necessários à sustentabilidade da operação, custo de capital e riscos aprovados.
3. **Custo relevante para decisão:** considera apenas valores que mudam em razão da decisão analisada, sem apagar a existência dos custos fixos.

Misturar essas três visões produz dois erros recorrentes: recusar negócios que contribuiriam para o resultado no curto prazo ou aceitar preços que parecem lucrativos, mas não sustentam a estrutura no longo prazo.

---

## 3. Objeto de custo e dimensões de análise

A unidade básica de rastreamento deve ser o **lote de entrada**. Cada lote precisa ter uma origem, material declarado, pesagem, condição, preço e documentação. Depois do processamento, o lote pode gerar um ou vários lotes de saída.

O cálculo deverá ser consultável pelas seguintes dimensões:

| Dimensão | Exemplos |
|---|---|
| Empresa e unidade | Matriz, filial, galpão |
| Lote e documento | Lote de compra, NF-e, romaneio, ticket de balança |
| Material de entrada | Papelão misto, PET, PEAD, filme plástico |
| Produto de saída | Papelão enfardado, PET separado por cor, plástico moído |
| Qualidade | Umidade, contaminação, grau, cor, densidade, compactação |
| Fornecedor | Cooperativa, empresa, pessoa física, ponto de coleta |
| Cliente | Indústria, aparista, reciclador, exportador |
| Operação | Compra, coleta, triagem, prensagem, armazenagem, entrega |
| Rota e frete | Origem, destino, veículo, transportador, viagem |
| Recursos | Empregado, equipe, máquina, caminhão, área física |
| Tempo | Data, turno, semana, mês e vigência fiscal |
| Contrato | Tabela, indexador, faixa de qualidade, prazo, reajuste |

A unidade comercial poderá ser R$/kg, R$/t, R$/fardo, R$/viagem ou R$/serviço. O motor interno deve converter tudo para unidades-padrão e guardar a unidade original para auditoria.

---

## 4. Fluxo operacional que deve gerar custos

O fluxo de referência é:

**cotação de compra → coleta ou recebimento → pesagem e inspeção → aceite e classificação → descarga → triagem → beneficiamento → geração de produto, subproduto e rejeito → armazenagem → cotação de venda → carregamento → entrega → faturamento → recebimento → encerramento econômico do lote.**

Cada evento deve registrar data, quantidade, qualidade, recurso utilizado, centro de custo, responsável e vínculo com o lote. Correções devem ser feitas por lançamento de ajuste, sem apagar o histórico original.

### 4.1 Direcionadores recomendados

| Atividade | Direcionador principal | Alternativas ou controles |
|---|---|---|
| Pesagem e recebimento | número de recebimentos | minutos por recebimento |
| Inspeção e classificação | minutos de inspeção | número de amostras |
| Descarga | hora-equipe ou tonelada descarregada | tipo de veículo |
| Triagem manual | hora de mão de obra | tonelada bruta processada |
| Prensagem | hora-máquina | tonelada ou número de fardos |
| Moagem/lavagem | hora-máquina | kg processado e consumo de energia/água |
| Movimentação interna | hora de empilhadeira | número de movimentos |
| Armazenagem | tonelada-dia ou m²-dia | volume-dia quando densidade for relevante |
| Controle de qualidade | número de análises | minutos de laboratório |
| Expedição | carregamento ou hora-equipe | tonelada expedida |
| Frota própria | km, hora de veículo e viagem | tonelada-km, com ocupação e retorno vazio |
| Frete terceirizado | valor contratado por viagem | rateio por peso, volume ou lote |
| Compras e fiscal | pedido/documento | número de itens ou tempo efetivo |

O direcionador deve ter relação causal com o consumo do recurso. Rateio apenas por faturamento deve ser exceção documentada, não padrão.

---

## 5. Cadastro mínimo

### 5.1 Empresa e parâmetros gerais

Devem ser cadastrados CNPJ, unidades, regime tributário, período de apuração, moeda, calendário, política de estoque, método de arredondamento, taxa mínima de atratividade, meta de retorno, horizonte de validade das cotações, capacidade prática por recurso e responsáveis pelas aprovações.

### 5.2 Materiais e produtos

Cada item deve conter código interno, descrição, família, NCM validada, unidade, densidade quando relevante, especificação de qualidade, faixas de umidade e contaminação, rendimento-padrão, perdas normais, processo necessário, embalagem, forma de armazenagem, vida útil comercial e possíveis produtos de saída.

### 5.3 Parceiros

O cadastro de fornecedor e cliente deve contemplar natureza jurídica, CNPJ/CPF, inscrição estadual, UF e município, regime e características fiscais relevantes, condição de pagamento, limite de crédito, comportamento de qualidade, pontualidade, documentação, regras comerciais, endereços logísticos e restrições de acesso.

### 5.4 Recursos

Empregados, equipes, veículos, máquinas, imóveis e áreas devem possuir centro de custo, disponibilidade, capacidade prática, vida útil, valor residual, critério de depreciação gerencial, custos fixos e variáveis, agenda de manutenção e medidores operacionais.

---

## 6. Estrutura dos custos

### 6.1 Compra do material

O custo de aquisição do lote deverá começar pelo valor efetivamente negociado, ajustado pela quantidade aceita, qualidade e condições comerciais. Deve contemplar:

- valor da mercadoria;
- diferenças de pesagem e classificação;
- descontos, abatimentos e bonificações;
- tributos não recuperáveis;
- frete de entrada, pedágio, seguro e gerenciamento de risco;
- coleta, carregamento, descarga e movimentação inicial;
- pesagem, inspeção e análise;
- embalagem ou recipiente não retornável;
- comissão de compra;
- custo esperado de rejeito diretamente atribuível;
- custos documentais diretamente atribuíveis;
- créditos fiscais confirmados e realizáveis, apresentados separadamente.

Crédito fiscal não confirmado não reduz o custo. Crédito confirmado, mas com realização lenta ou saldo acumulado estrutural, deve ter seu valor econômico ajustado pelo prazo e risco de aproveitamento.

### 6.2 Mão de obra CLT

O custo mensal integral de cada empregado deve ser calculado por componentes, sem aplicar um “multiplicador universal”. A ficha deverá conter salário, encargos patronais aplicáveis à empresa, FGTS, benefícios, adicionais, horas extras, provisões de férias e adicional constitucional, 13º salário, exames, uniformes, EPIs, treinamentos, afastamentos, indenizações esperadas e outros itens efetivamente suportados.

Fórmula conceitual:

```text
Custo mensal integral do empregado
= remuneração e adicionais
+ encargos patronais aplicáveis
+ benefícios
+ provisões trabalhistas mensais
+ custos diretamente relacionados ao posto
```

O valor da hora produtiva não deve usar todas as horas pagas como se fossem produtivas:

```text
Custo por hora produtiva
= custo mensal integral
÷ horas produtivas práticas do mês
```

As horas produtivas práticas excluem férias, feriados, treinamentos, reuniões, pausas previstas, afastamentos, manutenção organizacional e ociosidade normal, conforme política aprovada. Ociosidade anormal permanece evidenciada no resultado do período.

### 6.3 Frota própria

Cada veículo deve possuir custo fixo mensal e custo variável por quilômetro/hora. O cálculo por viagem deverá considerar distância total, inclusive retorno vazio, duração, pedágio, ocupação e restrições.

```text
Custo fixo mensal do veículo
= depreciação ou arrendamento
+ seguro + licenciamento + rastreamento
+ parcela fixa de pessoal
+ estrutura dedicada
+ custo de capital aprovado

Custo variável por km
= combustível por km
+ pneus por km
+ manutenção variável por km
+ lubrificantes e consumíveis por km

Custo da viagem
= custo variável por km × km totais
+ custo por hora × horas totais
+ pedágios + estadias + despesas específicas
+ parcela do custo fixo pela capacidade prática
```

O custo por tonelada entregue é o custo da viagem dividido pela carga útil efetivamente transportada. Devem existir indicadores de ocupação, km vazio, espera, consumo, disponibilidade e comparação “frota própria versus terceiro”.

### 6.4 Máquinas e equipamentos

O custo da hora-máquina será composto por depreciação gerencial, custo de capital, manutenção preventiva e corretiva, peças, seguro, energia, água, consumíveis e operador quando não apropriado separadamente.

```text
Custo fixo por hora-máquina
= custos fixos mensais do equipamento
÷ horas práticas disponíveis

Custo do uso
= horas efetivas × custo fixo por hora
+ consumo real de energia, água e insumos
+ manutenção variável atribuível
```

Capacidade prática corresponde à capacidade teórica menos paradas normais de setup, manutenção preventiva, limpeza, troca de turno e restrições recorrentes justificadas.

### 6.5 Imóveis e instalações

Aluguel, depreciação, IPTU, condomínio, vigilância, seguro, limpeza, manutenção predial e utilidades devem ser apropriados por área, uso e tempo. Armazenagem deve preferir tonelada-dia, m³-dia ou m²-dia, pois materiais de baixa densidade podem consumir muito espaço mesmo com pouco peso.

### 6.6 Rejeitos, perdas e qualidade

O sistema deve diferenciar:

- desconto de compra por material não aceito;
- rejeito recebido e destinado;
- perda normal do processo;
- perda anormal por falha operacional;
- variação de umidade;
- diferença de balança;
- furto, avaria ou deterioração;
- reclassificação para produto de menor valor.

Perdas normais compõem o rendimento esperado e elevam o custo da quantidade vendável. Perdas anormais devem ser lançadas separadamente como desvio e não incorporadas silenciosamente ao custo-padrão.

### 6.7 Despesas administrativas e comerciais

Devem incluir diretoria, financeiro, contabilidade, jurídico, tecnologia, recursos humanos, vendas, marketing, cobrança, auditoria, licenças, associações e demais estruturas não produtivas. Essas despesas não devem contaminar o custo contábil do estoque quando não atendam aos critérios contábeis, mas precisam constar no preço sustentável.

### 6.8 Capital de giro e risco

O modelo deve reconhecer que pagar o fornecedor antes de receber do cliente consome capital.

```text
Dias do ciclo financeiro
= dias médios de estoque
+ dias médios de recebimento
- dias médios de pagamento
```

Para um lote específico:

```text
Custo financeiro do lote
= capital líquido comprometido
× [(1 + taxa diária) ^ dias comprometidos - 1]
```

Provisões de risco devem ser baseadas em histórico e segmentadas: inadimplência por cliente, devolução, reclassificação de qualidade, variação de preço entre compra e venda, passivo ambiental, acidentes, multas contratuais e concentração. Não se deve somar um percentual genérico de “imprevistos” sem base histórica.

---

## 7. Fórmulas centrais e o Impacto dos Regimes Tributários

### 7.1 Balanço de massa

Definições:

```text
Q_bruta = peso de entrada menos tara
Q_aceita = Q_bruta - quantidade recusada ou descontada fisicamente
Q_vendavel = soma das quantidades dos produtos de saída aprovados
Q_rejeito = quantidade destinada sem venda
Q_perda = Q_aceita - Q_vendavel - demais saídas mensuradas

Rendimento = Q_vendavel ÷ Q_aceita
Taxa de rejeito = Q_rejeito ÷ Q_aceita
```

A equação de massa deve fechar dentro de uma tolerância configurável. Diferença acima da tolerância bloqueia o encerramento do lote ou exige aprovação e justificativa.

### 7.2 Custo líquido de aquisição

```text
C_aquisicao_lote
= preço de compra bruto
- descontos e abatimentos
+ tributos não recuperáveis
+ frete e seguro de entrada
+ coleta, carga, descarga, inspeção e manuseio atribuíveis
+ destinação esperada de rejeito atribuível
- créditos fiscais confirmados, realizáveis e apropriáveis ao lote
```

O valor por quilograma aceito é `C_aquisicao_lote ÷ Q_aceita`. O valor por quilograma vendável será maior quando houver perda ou rejeito.

### 7.3 Custo de transformação

```text
C_transformacao_lote
= Σ (quantidade do direcionador da atividade × taxa da atividade)
+ custos diretos exclusivos do lote
```

A taxa da atividade deve ser calculada pela capacidade prática:

```text
Taxa da atividade
= custo do conjunto de recursos da atividade
÷ capacidade prática do direcionador
```

A diferença entre capacidade prática e utilização real será custo de ociosidade do período, não aumento automático da taxa.

### 7.4 Produtos conjuntos e subprodutos

Quando uma triagem gerar vários produtos e o custo não puder ser medido diretamente, recomenda-se o valor realizável líquido relativo:

```text
VRL_i = quantidade_i × (preço estimado de venda_i - gastos específicos posteriores_i)

Fator_i = VRL_i ÷ soma dos VRLs de todos os produtos

Custo conjunto atribuído_i = custo conjunto × Fator_i
```

O método deve ser aplicado de forma consistente. Se um subproduto for imaterial, sua receita líquida poderá reduzir o custo do produto principal, desde que essa política seja formalmente aprovada.

### 7.5 Custo gerencial completo

```text
C_total_lote
= C_aquisicao_lote
+ C_transformacao_lote
+ logística de saída suportada pelo vendedor
+ parcela produtiva dos custos fixos pela capacidade prática
+ despesas administrativas e comerciais alocadas para a visão gerencial
+ custo de capital de giro
+ provisões de risco aprovadas
+ custo ambiental e de destinação atribuível
- receitas líquidas de subprodutos tratadas como crédito de custo
```

```text
Custo completo unitário = C_total_lote ÷ Q_vendavel
```

### 7.6 Formação do preço por margem-alvo

Definições por unidade de venda:
- `C`: custo unitário incluído na camada de preço escolhida. O valor de `C` muda drasticamente conforme o regime tributário, pois o direito a créditos fiscais na compra altera o custo líquido.
- `r`: soma das deduções proporcionais incidentes sobre o preço bruto, tais como tributos não recuperáveis sobre a venda, comissão percentual e desconto contratual esperado. O comportamento de `r` depende integralmente do enquadramento fiscal.
- `m`: margem-alvo, medida como percentual da receita líquida após as deduções `r`.
- `P`: preço bruto de venda.

```text
Receita líquida unitária = P × (1 - r)

P = C ÷ [(1 - r) × (1 - m)]
```

Essa fórmula não deve receber alíquotas somadas sem análise da base de cálculo. Tributo “por dentro”, base reduzida, pauta, valor fixo, diferimento, crédito presumido, substituição tributária e regras cumulativas exigem cálculo específico no motor fiscal.

### 7.7 Tratamento do `r` e do IRPJ/CSLL por Regime Tributário

O sistema não deve simplesmente somar IRPJ e CSLL aos tributos sobre a venda sem uma regra validada. O cálculo da variável `r` e da margem obedece às seguintes lógicas:

**A) Empresa no Lucro Real:**
*   **Custo (`C`):** É reduzido pelos créditos não cumulativos de PIS, COFINS e ICMS nas compras (quando aplicável).
*   **Deduções (`r`):** Inclui o PIS e COFINS sobre o faturamento (geralmente 9,25% no total) e o ICMS de saída.
*   **IRPJ/CSLL:** NÃO compõem a variável `r`. Eles incidem apenas sobre o lucro fiscal apurado no fim do período. A margem-alvo (`m`) deve ser tratada como margem *antes* do IRPJ/CSLL.

**B) Empresa no Lucro Presumido:**
*   **Custo (`C`):** Geralmente maior do que no Lucro Real, pois não há crédito de PIS/COFINS nas aquisições (regime cumulativo). Créditos de ICMS dependem da operação.
*   **Deduções (`r`):** Inclui PIS e COFINS (geralmente 3,65% no total), ICMS de saída, E TAMBÉM a presunção do IRPJ e da CSLL. Como o IRPJ/CSLL tornam-se percentuais fixos e lineares sobre a receita bruta (ex: 8% de presunção para venda de mercadorias), eles atuam na prática como deduções diretas do preço, devendo integrar a variável `r`.

**C) Empresa no Simples Nacional:**
*   **Custo (`C`):** Não há apropriação de qualquer crédito tributário (ICMS, IPI, PIS, COFINS) na compra de insumos ou mercadorias. O valor bruto da nota fiscal de compra (somado a fretes e seguros) é o custo líquido.
*   **Deduções (`r`):** É representada pela alíquota efetiva do Documento de Arrecadação do Simples Nacional (DAS), que engloba todos os tributos. 
*   **Atenção Crítica:** O sistema deve prever o risco de *mudança de faixa*. Se uma venda volumosa fizer a Receita Bruta Acumulada nos últimos 12 meses (RBT12) mudar de faixa, a alíquota efetiva do DAS aumentará não apenas para aquela venda, mas para todo o faturamento daquele mês.

---

## 8. Escada de preços

O sistema deve produzir mais de um preço, sempre com rótulo e finalidade.

| Preço | Conteúdo | Uso |
|---|---|---|
| Preço de caixa/emergencial | desembolsos incrementais inevitáveis e deduções da venda | decisão excepcional, com validade curta e aprovação superior |
| Preço mínimo de contribuição | custos variáveis e margem de contribuição mínima | ocupação de capacidade ociosa no curto prazo |
| Preço operacional | aquisição, transformação e logística atribuíveis | avaliação da eficiência operacional |
| Preço sustentável | custo gerencial completo, capital e riscos | piso normal de negociação |
| Preço-alvo | preço sustentável acrescido da margem estratégica | proposta comercial padrão |
| Preço de mercado comparável | referência externa ajustada por qualidade, prazo, frete e risco | teste de competitividade, não substitui o custo |

Qualquer proposta abaixo do preço sustentável deve mostrar: valor da concessão, motivo, prazo, capacidade ociosa utilizada, contribuição gerada, risco de virar precedente, responsável e data de expiração.

---

## 9. Arquitetura tributária

### 9.1 Princípio
O módulo tributário deve ser uma matriz de regras, não um percentual único. Toda regra precisa conter fonte, responsável pela validação, início e fim de vigência, hipótese de aplicação e resultado do cálculo.

### 9.2 Chaves mínimas da regra

| Grupo | Campos mínimos |
|---|---|
| Empresa | CNPJ, estabelecimento, regime tributário, atividade |
| Mercadoria/serviço | código interno, NCM/NBS quando aplicável, descrição fiscal |
| Operação | compra, venda, industrialização, serviço, bonificação, devolução, transferência |
| Documento | modelo, CFOP, CST/CSOSN e finalidade |
| Geografia | UF e município de origem e destino |
| Partes | PF/PJ, contribuinte ou não, regime do fornecedor e do cliente |
| Regra | tributo, base, alíquota, redução, valor fixo, cálculo por dentro/fora |
| Tratamento | débito, crédito, isenção, suspensão, diferimento, ST, retenção |
| Recuperabilidade | elegível, vedada, proporcional, condicionada e prazo estimado |
| Vigência | data inicial, data final, fundamento, versão e aprovador |

### 9.3 Tributos e temas que devem ser avaliados
O cadastro deve permitir ICMS, IPI quando aplicável, PIS/Pasep, Cofins, ISS para serviços, contribuições e retenções incidentes em transportes ou contratações, IRPJ, CSLL, Simples Nacional, CBS, IBS e Imposto Seletivo quando pertinente. Deve também comportar DIFAL, substituição tributária, diferimento, benefícios estaduais, crédito presumido, estorno de crédito e obrigações de transporte.

O tratamento do ICMS sobre sucatas, resíduos e aparas pode variar por Estado e tipo de operação. Portanto, UF, NCM, CFOP, condição do remetente/destinatário e legislação estadual devem ser campos obrigatórios antes de concluir a cotação.

### 9.4 Especificidades do Setor por Regime Tributário

O motor de regras precisa obrigatoriamente diferenciar as empresas da seguinte forma:

1.  **Lucro Real e a Lei nº 15.394/2026:**
    A Lei nº 15.394, de 22 de abril de 2026, autoriza créditos de PIS/Pasep e Cofins nas aquisições de desperdícios, resíduos ou aparas por pessoa jurídica no lucro real que os utilize como matéria-prima ou material secundário. Também prevê isenção na venda dos itens abrangidos para pessoa jurídica no lucro real. Essa lógica precisa ser transformada em regra condicional, e não aplicada indistintamente.
2.  **Lucro Presumido e o Custo Cumulativo:**
    Empresas de reciclagem neste regime sofrem o impacto da cumulatividade. O sistema deve calcular o custo sabendo que os tributos embutidos na compra não se transformam em direito creditório. A competitividade do preço dependerá de uma alta eficiência operacional, visto que o peso tributário na cadeia é absorvido integralmente como custo.
3.  **Simples Nacional, RBT12 e Diferimento:**
    O sistema deve calcular o valor do DAS baseado no Anexo correspondente (Anexo II para indústria/beneficiamento ou Anexo I para comércio). Um fator crítico é o diferimento ou isenção de ICMS sobre sucatas previsto em legislações estaduais. O motor fiscal deve permitir a parametrização para segregar a parcela do ICMS de dentro do DAS caso a operação goze de isenção ou diferimento estadual específico, evitando a bitributação ou o pagamento indevido no recolhimento unificado.

### 9.5 Transição para CBS e IBS
O sistema precisa selecionar a regra pela data da operação. As orientações oficiais para 2026 determinam destaque individualizado de CBS e IBS em documentos fiscais eletrônicos a partir de 1º de janeiro de 2026 e tratam 2026 como ano de teste, com dispensa de recolhimento nas condições informadas pela Receita. Isso exige separar no banco de dados: valor destacado, valor devido, valor recolhido, crédito apropriável e efeito de caixa. A legislação estrutural deve ser mantida vinculada à Lei Complementar nº 214/2025 e às normas posteriores vigentes.

### 9.6 Saídas obrigatórias do motor fiscal

Para cada simulação ou venda, o sistema deverá exibir:

```text
tributo ou contribuição
base de cálculo
alíquota nominal e efetiva
valor destacado
valor devido
crédito de entrada relacionado
valor efetivamente recuperável
efeito líquido no resultado
efeito e data provável no caixa
fundamento e vigência da regra
status: validada, provisória, vencida ou bloqueada
```

---

## 10. Modelo de dados conceitual

| Entidade | Conteúdo essencial |
|---|---|
| `empresa_parametro` | unidade, regime, metas, moeda, arredondamento, capacidade e vigência |
| `material` | descrição, família, NCM, unidade, qualidade, rendimento e processo |
| `parceiro` | dados cadastrais, fiscais, financeiros, logísticos e de risco |
| `contrato_tabela` | preço, indexador, qualidade, prazo, frete, tolerâncias e validade |
| `lote_compra` | fornecedor, documento, material, peso, qualidade, preço e tributos |
| `evento_balanca` | peso bruto, tara, líquido, balança, operador, data e evidência |
| `evento_qualidade` | amostra, umidade, impureza, classificação, desconto e responsável |
| `evento_processo` | atividade, lote, recurso, início, fim, quantidade e consumo |
| `lote_saida` | vínculo de origem, produto, peso, qualidade e rendimento |
| `rejeito_perda` | tipo, quantidade, normal/anormal, destino, custo e causa |
| `empregado_custo` | componentes do custo, função, centro, horas e vigência |
| `veiculo_custo` | custos fixos/variáveis, capacidade, km, horas e vigência |
| `maquina_custo` | custos, capacidade prática, consumo, horas e disponibilidade |
| `centro_custo` | natureza, responsável, orçamento e regra de apropriação |
| `atividade_taxa` | pool de custos, direcionador, capacidade prática, taxa e vigência |
| `regra_tributaria` | chaves de aplicação, fórmula, recuperabilidade, fonte e vigência |
| `cotacao_venda` | cliente, produto, quantidade, preço, camadas de custo e validade |
| `pedido_venda` | cotação aprovada, condições, reserva, entrega e faturamento |
| `evento_frete` | rota, veículo/terceiro, km, horas, carga, pedágio e custo |
| `fechamento_mensal` | reconciliações, desvios, ociosidade, ajustes e aprovações |
| `auditoria` | usuário, data, ação, valor anterior, valor novo e justificativa |

Todos os registros financeiros e fiscais devem guardar data de competência, data de caixa e versão da regra usada.

---

## 11. Regras de negócio essenciais

1. Nenhum lote pode ser encerrado sem fechamento do balanço de massa ou aprovação de exceção.
2. Nenhuma cotação pode ser classificada como definitiva com regra fiscal vencida, provisória ou ausente.
3. Crédito tributário só reduz custo quando elegível, documentado, apropriável e com expectativa razoável de realização.
4. Peso de compra, peso recebido, peso aceito e peso vendido são campos diferentes e não podem ser substituídos entre si.
5. Custos fixos produtivos são alocados pela capacidade normal/prática; ociosidade é mostrada separadamente.
6. Perda anormal não integra o custo-padrão sem aprovação formal.
7. Frete próprio deve considerar retorno vazio, tempo de espera e ocupação; frete terceirizado deve conter todos os adicionais.
8. Custo e preço devem informar unidade, moeda, data-base e validade.
9. A cotação deve congelar as premissas usadas. Alteração posterior gera nova versão.
10. O preço recomendado deve indicar a margem na visão de contribuição, operacional e completa.
11. Operação abaixo do preço sustentável exige alçada, motivo, prazo e impacto financeiro explícito.
12. O sistema deve impedir dupla contagem, principalmente de mão de obra, depreciação, frete, tributos e despesas administrativas.
13. Receita de venda e crédito de custo de subproduto não podem ser reconhecidos simultaneamente para o mesmo valor.
14. Valores estimados devem ser substituídos pelos realizados no fechamento, preservando a variação entre padrão e real.
15. Toda fórmula deve ser reproduzível com a memória de cálculo armazenada.

---

## 12. Relatórios e indicadores

### 12.1 Relatório de cotação

Deve mostrar cliente, material, qualidade, quantidade, rota, prazo, custo por camada, tributos, créditos, preço mínimo, preço-alvo, preço proposto, margem, capital de giro, validade, sensibilidade e aprovações.

### 12.2 Resultado por lote

Deve reconciliar compra, balanço de massa, custos das atividades, produtos de saída, receita, margem, perdas, rejeitos, fretes, tributos, prazo e desvio contra padrão.

### 12.3 Painel gerencial

Indicadores mínimos:

- margem de contribuição em R$ e % por tonelada, material, fornecedor, cliente e rota;
- resultado operacional e completo;
- preço médio de compra e venda;
- rendimento, rejeito, perda normal e anormal;
- custo de triagem, prensagem e armazenagem por tonelada;
- custo da frota por km, hora, viagem e tonelada entregue;
- ocupação, km vazio, consumo e tempo de espera;
- hora produtiva, hora ociosa e custo de ociosidade;
- giro, idade e valor realizável líquido do estoque;
- dias do ciclo financeiro e capital empregado;
- inadimplência e concentração;
- créditos tributários gerados, utilizados, glosados e acumulados;
- acurácia do custo-padrão e da margem cotada versus realizada;
- ponte de margem explicando preço, volume, mix, rendimento, compra, frete, tributo e eficiência.

---

## 13. Governança

### 13.1 Papéis

| Responsável | Atribuição |
|---|---|
| Operações | apontamento de peso, qualidade, tempo, consumo, perdas e capacidade |
| Logística | rotas, telemetria, frete, ocupação, espera e custo da frota |
| Compras | condições, fornecedor, qualidade contratada e preço de entrada |
| Comercial | cliente, preço, prazo, frete, mercado e justificativa de exceção |
| Financeiro/Controladoria | plano de contas, taxas, rateios, capital, fechamento e reconciliação |
| Contábil/Fiscal | enquadramento, regras tributárias, recuperabilidade e vigências |
| Diretoria/Comitê de preços | metas, alçadas, exceções, capacidade e riscos estratégicos |
| Tecnologia/Dados | integrações, segurança, disponibilidade e trilha de auditoria |

### 13.2 Alçadas sugeridas

As alçadas não devem depender apenas de desconto nominal. Devem considerar margem, risco, prazo e exposição. Uma política possível é:

- preço igual ou superior ao alvo: fluxo comercial normal;
- entre alvo e sustentável: aprovação do gestor comercial;
- entre sustentável e contribuição: aprovação conjunta de controladoria e diretoria, com prazo definido;
- abaixo da contribuição ou com caixa incremental negativo: bloqueio, salvo decisão estratégica formal da diretoria com valor máximo de perda.

Os limites percentuais e valores devem ser definidos pela empresa.

### 13.3 Fechamento e atualização

Mensalmente, a controladoria deve reconciliar volumes, estoque, compras, vendas, folha, imobilizado, manutenção, combustível, fretes, documentos fiscais, tributos e contabilidade. Taxas ABC e custos-padrão devem ser revisados quando os desvios excederem tolerância ou ocorrer alteração material de preço, processo, legislação ou capacidade.

---

## 14. Simulações obrigatórias

Toda cotação relevante deve permitir cenários alterando, isolada e conjuntamente:

- preço de compra;
- rendimento, umidade e contaminação;
- preço de venda;
- carga útil e km vazio;
- diesel, pedágio e frete terceiro;
- horas de triagem e máquina;
- volume e capacidade utilizada;
- prazo de estoque, pagamento e recebimento;
- inadimplência;
- regra ou aproveitamento tributário;
- destino e custo do rejeito;
- mix dos produtos de saída.

O resultado deve apresentar cenário-base, otimista, estressado e ponto de equilíbrio. Também deve calcular o preço máximo de compra para um preço de venda conhecido e o preço mínimo de venda para um custo de compra conhecido.

```text
Preço máximo de compra
= receita líquida esperada
- todos os demais custos e despesas da camada escolhida
- lucro-alvo

Preço máximo unitário de compra
= preço máximo total de compra
÷ quantidade aceita esperada
```

Esse cálculo é especialmente útil quando o preço de venda é determinado pelo mercado e a principal decisão está na compra do material.

---

## 15. Requisitos do futuro agente ou sistema

O agente deverá conversar em linguagem gerencial, mas nunca ocultar a matemática. Para cada resposta deverá informar dados usados, dados faltantes, premissas, fórmula, resultado, sensibilidade, riscos e versão fiscal.

Funcionalidades mínimas:

1. importação de documentos e dados de balança, ERP, folha, telemetria e planilhas;
2. validação de unidade, duplicidade, peso, data e vínculo do lote;
3. classificação assistida de custos, sempre sujeita a confirmação;
4. cálculo de custo padrão, realizado e variação;
5. simulação de compra, venda, rota e processamento;
6. comparação de frete próprio e terceirizado;
7. recomendação de preço e preço máximo de compra;
8. alerta de margem, capacidade, qualidade, prazo e regra fiscal;
9. explicação completa e exportável da memória de cálculo;
10. versionamento, aprovação, segregação de funções e auditoria.

O agente não poderá:

- inventar alíquota, NCM, capacidade, rendimento ou custo faltante;
- substituir validação fiscal, contábil ou trabalhista;
- apagar ou sobrescrever eventos históricos;
- recomendar preço sem identificar a camada de custo;
- tratar operação abaixo do preço sustentável como lucro normal;
- usar média global quando houver dado causal disponível;
- revelar dados salariais ou comerciais a usuários sem permissão.

---

## 16. Controles de qualidade dos dados

Cada campo deve ter fonte, proprietário, frequência de atualização e grau de confiabilidade. Sugere-se o seguinte status:

| Status | Significado |
|---|---|
| Confirmado | originado de documento, integração ou medição validada |
| Estimado | premissa aprovada com data de revisão |
| Provisório | aguarda documento ou validação |
| Vencido | perdeu vigência e não pode apoiar cotação definitiva |
| Inconsistente | conflito entre fontes ou fora da tolerância |

Uma cotação deverá apresentar um índice de completude dos dados, mas esse índice não substitui bloqueios específicos. Uma regra fiscal vencida, por exemplo, bloqueia o preço definitivo mesmo que todos os demais campos estejam preenchidos.

---

## 17. Casos de teste e critérios de aceitação

O futuro sistema só estará apto à implantação quando cumprir, no mínimo, os seguintes testes:

1. Um lote com 10% de perda deve transferir o custo para 90% da quantidade vendável, sem perder o registro da perda.
2. Um lote com dois produtos de saída deve repartir o custo conjunto pelo método aprovado e fechar 100% do custo.
3. Um crédito fiscal vedado não pode reduzir o custo; um crédito condicionado deve gerar alerta.
4. Uma regra fiscal fora da vigência deve impedir cotação definitiva.
5. Uma queda de volume abaixo da capacidade prática deve gerar ociosidade separada, sem inflar automaticamente a taxa-padrão.
6. Uma viagem com retorno vazio deve incluir todos os quilômetros.
7. Uma cotação com prazo maior deve refletir capital de giro adicional.
8. O mesmo custo não pode aparecer simultaneamente na taxa de atividade e como lançamento direto.
9. A soma dos resultados por lote deve reconciliar com o resultado mensal dentro da tolerância aprovada.
10. Alteração de premissa deve gerar nova versão e preserve a memória anterior.
11. O usuário deve conseguir reproduzir o preço a partir dos dados e fórmulas exportados.

---

## 18. Plano de implantação sem desenvolvimento de código

### Etapa 1 — Diagnóstico e desenho
Mapear fluxo real, materiais, documentos, centros de custo, rotas, recursos, regime tributário, política contábil, sistemas existentes e responsáveis. Definir objetos de custo, unidade-padrão e alçadas.

### Etapa 2 — Cadastro e qualidade de dados
Limpar cadastros de materiais, parceiros, NCMs, veículos, máquinas, empregados, centros e contas. Criar o dicionário e nomear proprietário para cada dado.

### Etapa 3 — Custeio piloto
Escolher de dois a quatro materiais representativos, uma rota própria, uma rota terceirizada e um mês fechado. Calcular lotes do início ao fim e reconciliar com contabilidade e caixa.

### Etapa 4 — Política de preços
Aprovar camadas de preço, margem-alvo, taxa de capital, riscos, capacidade prática, rateios, validade de cotações e alçadas.

### Etapa 5 — Matriz tributária
Contador ou assessor tributário valida as combinações materiais/operações/UF/clientes, com fundamento e vigência. Somente regras validadas entram em produção.

### Etapa 6 — Especificação técnica
Converter este documento em requisitos, telas, integrações, permissões, testes e critérios de aceite. Nessa etapa será decidido se o primeiro produto será planilha controlada, aplicação web, módulo de ERP ou agente conectado às bases.

### Etapa 7 — Operação assistida
Executar cálculo paralelo ao método atual, comparar preço previsto e margem realizada, ajustar direcionadores e só então tornar o novo processo obrigatório.

---

## 19. Informações que a empresa deverá levantar

Para transformar as bases em um modelo calibrado, serão necessários, idealmente para os últimos 12 meses:

- razão contábil e plano de contas por centro de custo;
- notas e romaneios de compra e venda;
- tickets de balança e registros de qualidade;
- movimentação de estoque e inventários;
- folha e componentes do custo por empregado;
- cadastro e histórico de máquinas, manutenção e consumo;
- cadastro da frota, abastecimentos, pneus, manutenção, telemetria e pedágios;
- fretes terceirizados, tabelas e adicionais;
- despesas do prédio e áreas ocupadas;
- produção, horas, paradas, perdas, rejeitos e destinação;
- prazos de fornecedores e clientes, inadimplência e devoluções;
- apurações fiscais, créditos acumulados e matriz fiscal validada;
- contratos, tabelas comerciais, indexadores e histórico de preços;
- capacidade teórica, normal, prática e utilizada por recurso.

Se os dados históricos forem incompletos, o piloto poderá começar com medições por amostragem e parâmetros provisórios aprovados, sempre com data de revisão.

---

## 20. Premissas que ainda precisam de decisão empresarial

Antes da implementação, a diretoria deverá decidir:

- materiais e unidades que entrarão primeiro no piloto;
- tratamento de lotes misturados e rastreabilidade entre entrada e saída;
- método contábil de estoque e método gerencial complementar;
- critérios para produtos conjuntos e subprodutos;
- capacidade prática por equipe, veículo, máquina e área;
- taxa de capital e metodologia de risco;
- meta de margem por família, cliente e tipo de operação;
- política de preço abaixo do sustentável;
- tolerâncias de peso, rendimento e fechamento;
- periodicidade de atualização de taxas e padrões;
- nível de integração com ERP, balança, telemetria, folha e fiscal;
- responsáveis e alçadas;
- regime de acesso a salários, custos, contratos e regras fiscais.

---

## 21. Referencial contábil e fiscal

O desenho contábil parte do CPC 16 (R1) — Estoques, que inclui no custo de estoque os custos de aquisição, transformação e outros necessários para trazer os estoques à condição e localização atuais; exclui tributos recuperáveis do custo de aquisição; orienta a alocação de custos fixos com base na capacidade normal; e prevê critério racional e consistente para produtos conjuntos. A política contábil definitiva deve ser aprovada pelo responsável técnico da empresa.

As referências fiscais centrais desta versão são:

- Lei nº 15.394/2026, sobre regras de PIS/Pasep e Cofins relacionadas a determinados resíduos e aparas;
- Lei Complementar nº 214/2025, regulamentação estrutural de IBS, CBS e Imposto Seletivo;
- Orientações da Reforma Tributária para 2026 — Receita Federal, sobre documentos, destaque e tratamento do ano de teste.

Este referencial deve ser revisado sempre que houver mudança legislativa, normativa, jurisprudencial ou de entendimento aplicável à empresa.

---

## 22. Resultado esperado

Ao final da implantação, a empresa deverá conseguir responder, com memória de cálculo:

1. Quanto custa comprar, coletar, separar, beneficiar, armazenar e entregar cada tonelada de cada material?
2. Qual fornecedor entrega melhor resultado após qualidade, frete, rejeito, prazo e tributos?
3. Qual cliente e rota geram maior contribuição e maior retorno sobre o capital empregado?
4. Qual é o preço máximo de compra e o preço mínimo de venda para cada cenário?
5. Quanto da diferença entre margem cotada e realizada veio de preço, rendimento, frete, tributo, prazo, mix ou eficiência?
6. Quanto custa a ociosidade e quais pedidos podem utilizá-la sem comprometer o preço de longo prazo?
7. Quais créditos tributários são efetivamente realizáveis e em quanto tempo?
8. Quais exceções comerciais estão destruindo valor e quem as aprovou?
