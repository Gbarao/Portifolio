# Cobertura dos seis macrocenários da ZFM (LC 214/2025, arts. 440–455)

Situação em 23/11/2026. Percentuais e vigências: Parâmetros > Regras legais (`param_regras_legais`).
Alíquotas gerais de CBS/IBS/IPI: premissas de simulação, nunca fixas no código.

Legenda: **Sim** = implementado e testado; **Parcial** = implementado com limitação descrita; **Não** = fora desta versão.

| Cenário | Regra | Classificação nas EFDs | Requisitos testados | Cálculo (motor anual) | Simulador individual | Teste de aceitação |
|---|---|---|---|---|---|---|
| 1 – Importação, indústria incentivada | art. 443 | Sim (C1a) | área, habilitação, projeto, NCM, art. 441, uso pessoal, finalidade | Sim (suspensão: sem CBS/IBS) | Sim (suspensão, conversão em 48 meses, saída antes com acréscimos) | 1, 2 |
| 1 – Importação, revenda presencial | art. 444 | Sim (C1b) | habilitação, revenda presencial (premissa), ingresso, art. 441 | Sim (CP 50% a partir de 2027) | Sim (nominal, CP, recolhimento, crédito ordinário, recuperação) | 3 |
| 2 – Compra de outra UF | arts. 445–447 | Sim (C2a, C2b, C2c) | habilitação, origem nacional (CST, inferência sinalizada), ingresso, art. 441, uso pessoal | Sim (IBS de entrada 446 e CP 447 a partir de 2029) | Sim (inclui encomenda pelo valor agregado e estorno) | 4, 5, 12 |
| 3 – ZFM → ZFM, intermediário | arts. 448–449 | Sim (C3a) | fornecedor e adquirente validados, projeto, consumo produtivo, art. 441 | Sim (CP 449 a partir de 2029; sem 450) | Sim | 6 |
| 4 – Venda de produto industrializado | art. 450 | Sim (C4a–C4d) | habilitação, produto no projeto, NCM, tipo de bem, art. 441, operação tributada, trava do 448 | Sim (IBS por faixa sobre o saldo devedor; CBS 6%/2% por item) | Sim | 7, 8, 11, 14 |
| 5 – Venda dentro da ZFM / serviço | art. 451 | Sim (C5M, C5S; C3b do lado do adquirente) | área, origem nacional, art. 441, local físico do serviço | Sim (CBS zero, IBS normal) | Sim | 9 |
| 6 – IPI | arts. 454–455 | Sim (C6, por produto) | TIPI 31/12/2023, industrializado em 2024 ou projeto CAS 2022–2025, TIC, art. 441, similar nacional | Sim (vantagem competitiva e IPI futuro) | Sim (455 pendente de regulamentação) | 10 |
| Transversal – duplicidade entre EFDs | — | Sim (vínculo 1:1, uma fonte por sentido) | — | — | — | 13 |

## Limitações conhecidas

- **Bloco K** (produção e consumo) não é lido: o consumo produtivo do art. 449 é informado no cadastro do produto;
  sem ele, fica "depende de comprovação produtiva".
- **Importação**: a EFD não traz todos os componentes da base (II, despesas aduaneiras, AFRMM). O cadastro de
  Importações complementa; sem ele, o cálculo usa o valor da EFD e deve ser lido como estimativa.
- **C120, 0300/0305, G110/G125, 0005, C197** não são lidos nesta versão.
- **Acréscimos legais**: taxa de juros e multa são premissas; vazias = acréscimos não calculados (sinalizados).
- **LC 227/2026**: as regras atribuídas a ela (trava 448 × 450, § 6º do art. 450) estão marcadas "conferir".
- **Vigência** dos arts. 443, 445, 448 e 451: marcada "a conferir no art. 544".
- **Data da operação**: os requisitos com data (validade da habilitação, vigência do projeto) usam o mês do arquivo.
- **Campos da NF-e da reforma** (gCredPres, cClassTrib, CST de IBS/CBS) ainda não são lidos.
