# DECISOES.md — dúvidas e decisões de regra de negócio e de implementação

Formato: **D-nnn** (decisão tomada, pode ser revista) · **P-nnn** (pergunta pendente ao usuário).

---

## Decisões

**D-001 — Estrutura do código (Fase 1).** A leitura das duas EFDs é feita por um único leitor
(`zfm/parsers/base.py`); o que difere entre EFD ICMS/IPI e EFD Contribuições fica nos
dicionários de layout (`zfm/layouts/`). Os scripts chamados pelos `.bat` ficam em `ferramentas/`
e usam só a biblioteca padrão (rodam antes de os pacotes existirem).

**D-002 — Versões dos pacotes.** `pandas 3.x` e `streamlit ≥ 1.66` exigem Python 3.11+. Como a
SPEC admite Python 3.10, foi fixado um conjunto único, conferido com o `pip` (pacotes prontos para
Windows 64 bits em Python 3.10, 3.11, 3.12, 3.13 e 3.14): `duckdb 1.5.6`, `streamlit 1.65.0`,
`plotly 7.1.0`, `pandas 2.3.3`, `openpyxl 3.1.5`, `pytest 9.2.0`. Dependências indiretas (numpy,
pyarrow etc.) não são fixadas. A instalação usa `--only-binary=:all:` (nunca compila).

**D-003 — Layouts SPED e versões.** Os campos dos registros seguem o Guia Prático, mas **não foram
conferidos contra o Guia da versão 2026**. Cada registro tem uma ou mais versões; a versão de cada
linha é escolhida pelo `COD_VER` (quando mapeado) e pelo número de campos. Se o número de campos não
bater com nenhuma versão conhecida, a linha é lida por posição e aparece um aviso na tela
"Perímetro e qualidade". Pontos a conferir no Guia Prático vigente:
- EFD ICMS/IPI: `C170.VL_ABAT_NT` (último campo), `0200.CEST`, `E113.CHV_DOCe`, `E116.MES_REF`;
  eventuais campos novos de 2026.
- EFD Contribuições: `M210`/`M610` com 16 campos (versão com ajustes de base) × 13 campos;
  nome do campo `VL_CRED_DIF` em `M100`/`M500`.
- Os limites de `COD_VER` de cada versão ficaram em branco (escolha só pelo número de campos).

**D-004 — Retificadora.** Mesma chave = tipo + CNPJ + IE + período (`DT_INI`/`DT_FIN`).
Retificadora (`COD_FIN = 1` na ICMS/IPI; `TIPO_ESCRIT = 1` na Contribuições) prevalece sobre a
original, em qualquer ordem de carga. Entre duas do mesmo tipo, prevalece a carregada por último.
A versão substituída fica no banco como "Substituído" e não entra em nenhum cálculo.

**D-005 — Arquivo repetido.** Arquivo com o mesmo conteúdo (hash SHA-256) de um já carregado é
ignorado, sem alterar nada.

**D-006 — Tipo do arquivo.** Detectado pela posição da data inicial no registro 0000
(4º campo na ICMS/IPI; 6º na Contribuições).

**D-007 — Estabelecimento de cada linha da EFD Contribuições.** Registros dos blocos A, C e F
recebem o CNPJ do último `A010`/`C010`/`F010`; registros do bloco 0 após um `0140` recebem o CNPJ
desse `0140`; blocos M, 1 e 9 recebem o CNPJ da matriz (registro 0000).

**D-008 — Conversão de números e datas.** Feita no banco local (DuckDB): vírgula → ponto e
conversão para `DECIMAL` exato (valores: 2 casas; alíquotas: 4; quantidades: 6). Valor que não é
número vira vazio (nulo). Uma checagem de valores inválidos pode ser acrescentada na Fase 3.

**D-009 — Q1 (completude).** Considera os estabelecimentos com UF = AM (do 0000 da ICMS/IPI ou do
0140 da Contribuições). EFD ICMS/IPI: por CNPJ completo; EFD Contribuições: pela raiz do CNPJ
(entregue pela matriz). Período: janeiro/2026 até o último mês com arquivo carregado (ajustável).

**D-010 — Pasta de EFDs.** O programa lê todos os `.txt` da pasta informada **e das subpastas**.

**D-011 — Carga.** A carga é feita com barra de progresso, mas a tela fica ocupada até terminar
(não roda em segundo plano). Medição: 1 milhão de linhas em ~10 s, com memória estável (~20 MB).

**D-012 — Execução local.** Teste automático confirma que as telas não fazem nenhuma requisição
fora de `127.0.0.1`. O teste com a rede desligada no Windows (SPEC 2.1) depende do usuário.

**D-013 — Escrituração da EFD Contribuições (as duas formas).** O programa usa o que estiver no
arquivo de cada estabelecimento:
- *detalhada* (C100/C170): produto, CFOP, PIS/COFINS e destinatário exato pelo `COD_PART` (0150);
- *consolidada* (C180 + C181/C185): produto, CFOP e PIS/COFINS; o C181 (PIS) e o C185 (COFINS) são
  casados por C180, CFOP e valor. O destino (ZFM, interna, interestadual, exportação, grupo) é
  rateado pela proporção do C190 + 0150 da EFD ICMS/IPI do mesmo estabelecimento, mês e CFOP
  (premissa `rateio_produto_uf`). A tela avisa quando houve rateio.

**D-014 — Códigos de ajuste do ICMS (E111/E116), sem lista prévia.** Classificação automática a
partir do próprio arquivo, nesta ordem: (1) texto da descrição (`DESCR_COMPL_AJ` / `TXT_COMPL`):
"FTI", "UEA", "FMPES", "ESTÍMULO", "PRESUMIDO"; (2) códigos citados em Resoluções GSEFAZ
(`AM040001`, `AM040014` = crédito estímulo — conferir na versão vigente); (3) estrutura do código
(Tabela 5.1.1): 4º caractere = 4 (dedução do ICMS próprio) no AM → crédito estímulo; = 2 (outro
crédito) → outros_beneficios; (4) demais → outros. Cada linha mostra a regra usada e tem a coluna
"revisado". Tudo é editável em Parâmetros > Códigos de ajuste.

**D-015 — Alíquotas de CBS/IBS (pesquisa de 06/11/2026; editáveis em Parâmetros > Alíquotas por cenário).**
- *base*: CBS 11,3% (cálculo do TCU para a alíquota de referência de 2027, aprovado em 28/10/2026;
  o Senado tem até 15/12/2026 para fixá-la) e IBS 18,7% (premissa usada pela Resolução CGIBS
  14/2026 para projetar arrecadação — não é a alíquota que será cobrada);
- *baixo*: teto conjunto de 26,5% da LC 214/2025 (CBS 8,8% + IBS 17,7%, divisão usada pelo CGIBS);
- *alto*: base + 1 p.p. no IBS (sensibilidade, sem fonte oficial);
- *adverso*: base sem créditos presumidos do art. 450 e sem IPI protegido.
- 2027–2028: CBS = referência − 0,1 p.p.; IBS-teste de 0,1% (compensável com a CBS) tratado como
  neutro (IBS = 0). 2029–2032: IBS = referência × (1 − fator_icms) (aproximação). Contribuição do
  art. 457: 0 (preencher para sensibilidade).

**D-016 — Carga no regime geral (DIVERGE da fórmula literal da SPEC 7.6).** A SPEC define
`carga_geral = débitos sem exceções − créditos das entradas como se tributadas`. Com essa fórmula,
toda compra com alíquota zero (art. 445) vira "perda", embora o fornecedor também não cobre o
tributo. O programa usa a **carga total** (tributo pago + tributo embutido nas compras):
`benefício CBS = (débito sem exceções ZFM − débito com exceções) + crédito presumido usado`;
idem para o IBS (com os créditos presumidos de entrada e do art. 450). Créditos "normais" acima do
débito são tratados como ressarcíveis. **Confirmar com o usuário.**

**D-017 — Benefício atual.** Exportações (CFOP 7xxx) ficam fora (imunes com ou sem ZFM). Saídas
incentivadas = produto marcado como incentivado + CFOP de venda de produção própria +
estabelecimento do AM. IPI sem CST por item (C181) é tratado como isento (premissa
`ipi_sem_cst_assume_isento`). Crédito estímulo e fundos são alocados aos produtos pela receita
incentivada do estabelecimento no mês (o débito de ICMS por produto não existe sem C170 de saída).

**D-018 — Produtos.** Preenchimento automático: incentivado = item vendido com CFOP de produção
própria (x101, x103, x105...); `tipo_bem` = intermediario se `TIPO_ITEM` = 06, senão final.
A alíquota TIPI não existe na EFD: **precisa ser preenchida** (sem ela, IPI = 0 e CP de CBS = 2%).

**D-019 — Simulação.** Anualização: meses observados de 2026 + média mensal nos demais (soma =
média × 12). Apuração mês a mês de 2027 a 2033, por empresa, com saldo de créditos presumidos por
safra (consumo do mais antigo primeiro) e expiração em `prazo_cp_anos`. Saídas a PJ na ZFM:
CBS/IBS zero (arts. 448/451). Tratamento das entradas por origem em Parâmetros > Tratamento das
entradas (padrão: nacional fora da ZFM = alíquota zero + base do CP 447; ZFM = alíquota zero +
base do CP 449; importação = suspensão).

**D-020 — Entradas na EFD Contribuições.** As entradas usam a EFD ICMS/IPI (C170; C190 quando o
documento não tem C170). A EFD Contribuições (C191/C195) não é usada como alternativa nesta versão.

**D-021 — Visão só de saídas × só de entradas (pedido do usuário).** Telas 4 e 5 = operações de
saída e de entrada. Nas telas 7 e 8 há o seletor "Visão do benefício":
- *Benefício atual*: todo o benefício calculado vem das vendas (IPI, PIS, COFINS, ICMS). A visão
  "Só entradas" mostra, como informação, as compras com isenção, suspensão ou alíquota zero por
  tributo e CST (PIS/COFINS não cobrados estimados pela alíquota do regime geral). Não soma no total.
- *Simulação*: benefício pós-reforma = parte das saídas (CBS/IBS zero nas vendas à ZFM, créditos
  presumidos do art. 450, ICMS residual, IPI protegido, art. 457) + parte das entradas (créditos
  presumidos de IBS dos arts. 447/449 efetivamente usados). Saídas + entradas = total.

**D-022 — Nenhum percentual fixo no código.** Os percentuais do art. 450 (55%, 75%, 90,25%, 100%;
6% e 2%), o limite de TIPI de 6,5%, os créditos presumidos dos arts. 447 (7,5% / 13,5%) e 449 (7,5%)
e a redução da CBS em 2027–2028 (0,1 p.p.) passaram para Parâmetros > Premissas. A aba
"Premissas e alíquotas" lista todas as premissas adotadas (valor, onde alterar, fonte) e permite
digitar a alíquota de referência de CBS/IBS por cenário (recalcula 2027–2033).

---

## Perguntas pendentes

- **P-001** — ~~Códigos de crédito estímulo e fundos~~ → resolvido por classificação automática
  (D-014); revisar a aba Códigos de ajuste.
- **P-002** — ~~Escrituração detalhada ou consolidada~~ → as duas tratadas (D-013).
- **P-003** — ~~Estudo da A&M~~ → ignorado por decisão do usuário; produtos preenchidos a partir
  das EFDs (D-018).
- **P-004** — Lista das teses e forma de quantificar cada uma (tabela Teses, vazia).
- **P-005** — ~~Alíquotas de CBS/IBS~~ → valores pesquisados como ponto de partida (D-015).
- **P-006** — Ordem de dedução dos créditos presumidos de IBS e fator de transição dos arts. 447/449
  (valores iniciais da SPEC mantidos).
- **P-007** — Inclusão futura do XML das NF-e de saída.
- **P-008** — Códigos IBGE de Presidente Figueiredo (1303536) e Rio Preto da Eva (1303569): conferir.
- **P-009** — Confirmar o método da carga total (D-016).
- **P-010** — Alíquota TIPI (31/12/2023) de cada produto incentivado.
