# Visualização de dados — Passo 6

Decisões de gráfico do sistema, com a razão de cada uma. A cor **não foi
escolhida a olho**: cada paleta passou pelo validador antes de entrar no
código.

## Separação entre cor de marca e cor de dado

Verde é identidade visual — navegação, botões, marca. **Azul é dado.** Manter
as duas separadas evita que a interface compita com o gráfico e que o leitor
confunda um botão com uma série.

## Paleta validada

| Papel | Claro (fundo `#ffffff`) | Escuro (fundo `#2b2b33`) |
|---|---|---|
| Escada de preços (rampa ordinal) | `#86b6ef → #5598e7 → #2a78d6 → #1c5cab → #104281` | `#256abf → #3987e5 → #6da7ec → #9ec5f4 → #cde2fb` |
| Série única (barras nominais) | `#2a78d6` | `#3987e5` |
| Neutro (mercado, totais) | `#898781` (3,59:1) | `#898781` (3,91:1) |

**Resultados do validador:**

- Rampa ordinal, modo claro: L monotônica, ΔL ≥ 0,06 entre passos, ponta clara
  a 2,11:1, dispersão de matiz 3° — todos os testes aprovados.
- Rampa ordinal, modo escuro: aprovada **depois de corrigida**. A primeira
  tentativa (`#184f95` na ponta) reprovou com 1,73:1 contra o fundo escuro
  deste tema, que é mais claro que o fundo de referência. A rampa foi deslocada
  para os passos 500→100.
- Neutro: 3,59:1 e 3,91:1 — acima do piso de 3:1 para marcas.

## Duas decisões que o validador mudou

**1. As camadas de preço eram cinco matizes diferentes; viraram uma rampa de um
matiz só.** As camadas formam uma escala **ordenada** (caixa < contribuição <
operacional < sustentável < alvo). Cinco matizes seriam um arco-íris que
esconde justamente a ordem que é o significado. Com a rampa ordinal, mais
escuro é mais alto na escada — a ordem se lê na própria cor.

**2. Verde/vermelho para variação foi descartado.** A intuição financeira pede
verde para aumento e vermelho para redução. O validador reprovou: sob
deuteranopia o par `#0ca30c ↔ #d03b3b` mede ΔE 4,1 — abaixo do piso 6. Um
leitor com daltonismo veria duas barras da mesma cor. O par azul↔vermelho
(`#2a78d6 ↔ #d03b3b`) passa com ΔE 23,8.

## Uma decisão de forma que a tela mudou

A composição do preço começou como **cascata (waterfall)** e virou **barra
empilhada**. A cascata existe para mostrar variação entre dois pontos; o preço
não varia — ele **é** a soma das suas partes. Renderizada, a cascata mostrava
incrementos minúsculos flutuando ao lado de barras de total, difíceis de
comparar. A barra empilhada responde a mesma pergunta ("de onde vem cada
centavo") com as mesmas cores da escada de preços: a mesma camada tem sempre a
mesma cor nos dois gráficos.

## Especificações de marca

- Barra com no máximo 24px de espessura, ponta arredondada em 4px **apenas no
  lado do dado**, quadrada na linha de base
- 2px de superfície separando segmentos vizinhos — nunca um contorno
- Grade em fio de cabelo, sólida (nunca tracejada), um passo fora da superfície
- Rótulo que não cabe dentro da marca vai para fora dela; nada é cortado
- Texto nunca veste a cor da série: a identidade vem da marca colorida ao lado

## Acessibilidade

- **Todo gráfico tem gêmeo em tabela** — botão "Ver tabela" no cabeçalho de cada um
- Cor nunca é o único canal: cada barra tem rótulo de nome e valor
- Alvo de foco/hover cobre a faixa inteira da barra, não só os pixels pintados
- Cada marca é focável por teclado e anuncia nome e valor via `aria-label`
- Modo escuro é uma paleta **escolhida e validada** contra o fundo escuro, não
  uma inversão automática

## Formas usadas e por quê

| Pergunta do leitor | Forma | Cor |
|---|---|---|
| Onde minha proposta cai na escada? | Barras horizontais ordenadas + linha de referência | rampa ordinal |
| De onde vem cada centavo do preço? | Barra empilhada (parte-todo) | rampa ordinal |
| Qual atividade custa mais ociosa? | Barras horizontais ordenadas por valor | série única |
| Quanto de capacidade sobra? | Medidor por atividade | status (bom/atenção/crítico) |
| Qual o custo por tonelada? | Figura-herói | — |
| Um único material tem qual margem? | **Indicador**, não gráfico de uma barra só | — |

A última linha é regra, não exceção: quando a lista tem um item só, o
componente troca a barra por um indicador. Uma barra sozinha não compara nada.
