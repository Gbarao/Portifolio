# Consolidador EFD — EFD Fiscal (ICMS/IPI) × EFD-Contribuições

Aplicação local em Python que carrega os `.txt` da **EFD ICMS/IPI** e da
**EFD-Contribuições**, cruza as duas escriturações e mostra, em uma tabela com
filtros, os valores de **entradas** consolidados por empresa, fornecedor, CFOP
e item (ou por qualquer outra combinação de níveis), com acesso ao documento.

O relatório é o que está nas EFDs: a ferramenta não aplica regra de crédito e
não simula tributo. Cada coluna leva o nome do campo e o registro de origem,
por exemplo `VL_ICMS (Reg. C170/C190/C590/D190/D590 · EFD Fiscal)`.

![Visão consolidada](docs/visao_consolidada.png)

## Como usar

```bash
pip install -r requirements.txt
python iniciar.py            # no Windows também serve o duplo clique em iniciar.bat
```

A aplicação abre no navegador, em `localhost`. Tudo roda neste computador: os
arquivos são lidos do disco e a base fica na pasta `base/`. Nenhum dado sai da
máquina.

1. **Carregar EFDs**: selecione os arquivos (ou uma pasta). O tipo de cada um
   é reconhecido pelo registro 0000. A tela mostra o que será feito com cada
   arquivo antes de carregar.
2. **Visão consolidada**: escolha os níveis em "Agrupar por", as colunas de
   valor e os filtros da barra lateral. Clique em uma linha para ver os
   documentos e itens que a compõem. Exporta para Excel e CSV.
3. **Conferências**: situação de cada documento nas duas EFDs, itens
   divergentes, C190 × C170, cabeçalho × detalhes e documentos repetidos.
4. **Meus filtros e cálculos**: crie filtros com nome e campos calculados, e
   use-os na visão.
5. **Auditoria da carga**: verificações de integridade e o que foi lido de
   cada arquivo.

## O que entra

Somente entradas.

| Escrituração | Registros lidos | Como entram |
|---|---|---|
| EFD Fiscal | C100 + C170 | Uma linha por item |
| EFD Fiscal | C100 sem C170 (C190) | Uma linha por CST/CFOP/alíquota |
| EFD Fiscal | C500 + C590, D100 + D190, D500 + D590 | Uma linha por registro analítico |
| EFD Contribuições | C100 + C170, A100 + A170, F100 | Uma linha por item |
| EFD Contribuições | C500 (C501 + C505), D100 (D101 + D105), D500 (D501 + D505), C190 (C191 + C195) | Uma linha por par PIS/COFINS |

Regras de escopo:

- `IND_OPER = 0`. O C500 da EFD-Contribuições não tem esse campo e só existe
  para aquisições; no C191/C195 entram os CFOPs iniciados por 1, 2 ou 3; no
  F100 entra `IND_OPER = 0`.
- Documentos com `COD_SIT` 02, 03, 04 ou 05 (cancelados, denegados,
  inutilizados) são contados e deixados de fora.
- O `VL_ISS` do A100 é do documento; ele é distribuído entre os A170 na
  proporção do `VL_ITEM`, em centavos inteiros, e a soma dos itens é
  exatamente o valor do documento.

Registros com possíveis valores de entrada ou de crédito que esta versão não
consolida (por exemplo C395/C396, F120, F130, F150, G125 e D700) são contados
e apontados na página de auditoria quando existem no arquivo.

## Como as duas EFDs são cruzadas

- **Empresa**: raiz do CNPJ (a EFD-Contribuições é da empresa; a EFD Fiscal é
  de cada estabelecimento).
- **Fornecedor**: CNPJ/CPF do registro 0150. O `COD_PART` é um código interno
  de cada arquivo e não é usado para comparar.
- **Documento**: chave eletrônica de 44 dígitos; sem chave, o conjunto
  estabelecimento, modelo, série, número, data e participante.
- **Visão consolidada**: as linhas das duas escriturações são empilhadas e
  cada coluna de valor é somada com um filtro por fonte. Assim, valores da
  Fiscal e da Contribuições aparecem lado a lado no mesmo grupo, e o mesmo
  tributo nunca é somado das duas fontes.
- **CFOP conciliado**: os registros de energia, frete e comunicação da
  EFD-Contribuições não têm CFOP. O nível "CFOP conciliado" usa o CFOP do
  mesmo documento na EFD Fiscal, quando ele é único. O nível "CFOP" mostra só
  o que está no registro.

## Garantias contra duplicidade

1. **Arquivo**: o mesmo conteúdo não entra duas vezes, ainda que com outro
   nome, outra codificação ou outra quebra de linha.
2. **Versão**: uma escrituração por empresa/IE, tipo e período. Original e
   retificadora juntas: fica a retificadora. Dois arquivos do mesmo tipo para
   o mesmo período: os novos são bloqueados, porque o arquivo não informa qual
   é o mais recente.
3. **Carga**: cada arquivo entra em uma transação. A quantidade de linhas e a
   soma de cada coluna de valor gravadas no banco têm de ser iguais às
   calculadas na leitura; qualquer diferença desfaz a carga daquele arquivo.
4. **Documento**: o mesmo documento escriturado mais de uma vez na mesma EFD
   (por exemplo, em dois períodos) conta uma vez. As outras ocorrências ficam
   listadas em Conferências e fora dos totais.
5. **Consulta**: não há junção entre as tabelas de fatos. As junções
   auxiliares usam tabelas de chave única e a contagem de linhas é conferida a
   cada carga.

O que a ferramenta **não** decide: registros sem identificação de documento
(F100 e a consolidação C191/C195) que aparecem idênticos no mesmo arquivo. O
arquivo não permite saber se é repetição ou dois lançamentos iguais; eles são
listados em Conferências e continuam nos totais.

Os valores são guardados como decimais exatos (centavos inteiros na leitura,
`DECIMAL(18,2)` no banco). Não há soma em ponto flutuante.

## Leiautes: o que está e o que não está conferido

As posições de campo foram codificadas a partir dos leiautes da EFD ICMS/IPI e
da EFD-Contribuições, mas **não foram conferidas contra os PDFs do Guia
Prático** durante o desenvolvimento, porque o ambiente em que a ferramenta foi
escrita não tinha acesso ao portal do SPED. Em compensação, a cada carga a
ferramenta confere o que leu contra o próprio arquivo:

- contagem de linhas de cada registro × registro 9900;
- total do cabeçalho do documento × soma dos detalhes lidos;
- analítico C190 × soma dos C170;
- formato de CFOP (4 dígitos), datas e chaves eletrônicas;
- quantidade de campos de cada registro.

Se uma posição estiver errada para o seu arquivo, essas conferências deixam de
fechar e a página **Conferências** avisa. Antes de usar os números, veja se
"Cabeçalho × detalhes" fecha nos seus arquivos reais.

A tabela de CFOP não vem embutida: carregue o arquivo oficial (SPED ou CONFAZ)
em **Carregar EFDs > Tabelas de apoio**. Sem ela, o CFOP aparece só com o
código.

## Desempenho

Medido em uma máquina de 4 núcleos, com um par sintético (uma EFD Fiscal e uma
EFD-Contribuições) de 3,6 milhões de linhas e 2,4 milhões de linhas de entrada:

| Etapa | Tempo |
|---|---|
| Identificar os arquivos (tipo, empresa, período, conteúdo repetido) | 2 s |
| Carga completa (leitura dos dois arquivos em paralelo, banco e conferências) | 44 s |
| Visão por empresa, fornecedor, CFOP e item | 0,2 s |
| Visão agrupada por documento (300 mil grupos) | 0,2 s |
| Filtro por valor da linha ou por número de documento | 0,1 s |
| Detalhe de um grupo | 0,05 s |

A leitura rende de 50 a 60 mil linhas por segundo por núcleo, com um processo
por arquivo, e acontece uma vez: depois disso os filtros consultam a base
(211 MB em disco neste teste). Os tempos na sua máquina serão outros.

## Testes

```bash
python testes/test_consolidador.py          # 100 verificações de ponta a ponta
python testes/gerar_sinteticos.py pasta --docs 300000   # gera um par de volume
```

Os testes usam EFDs sintéticas com valores conhecidos e cobrem: totais por
fonte, repetição de documento entre períodos, retificadora, versões em
conflito, mesmo arquivo com outro nome ou codificação, carga desfeita por
diferença de 1 centavo no controle, pareamento, CFOP conciliado, filtros,
campos calculados e tentativas de injeção.

## Estrutura

```
app.py                 interface (Streamlit)
iniciar.py / .bat      abre a aplicação
efd/leitor.py          leitura das duas escriturações -> Parquet + totais de controle
efd/trabalhador.py     processo de leitura de um arquivo
efd/base.py            DuckDB: carga, regras de duplicidade, tabelas derivadas, verificações
efd/consulta.py        visão consolidada, filtros, campos calculados, exportação
efd/leiautes.py        colunas, rótulos de origem e registros tratados
efd/seletor.py         janela de seleção de arquivos (tkinter)
testes/                gerador de EFDs sintéticas e testes
```

> Ferramenta de apoio à análise. Não substitui a apuração oficial nem a
> avaliação de um profissional sobre o direito a crédito de cada operação.
