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

**D-023 — Método As Is × To Be (substitui o resultado principal das D-016/D-017).** O resultado
do estudo passou a ser a **diferença de carga** por empresa, ano e tributo:
`Diferença = carga To Be − carga As Is` (positivo = aumento de carga/perda; negativo = ganho).
- *As Is*: lido da apuração, sem recálculo (D-025/D-026), anualizado (soma do período ÷ meses com
  arquivo × 12).
- *To Be*: CBS e IBS calculados sobre a base de operações; ICMS = As Is × fator do ano; IPI próprio =
  As Is × `fator_ipi_proprio` (padrão 0); PIS/COFINS = 0 a partir de 2027; contribuição do art. 457.
- O benefício "regime geral − ZFM" (D-016/D-017) continua como tela **informativa** (tela 9).

**D-024 — Duas métricas.** A carga própria de IPI da empresa da ZFM é zero antes e depois; o efeito
do IPI é concorrencial. A **perda de vantagem competitiva** = IPI que o concorrente de fora pagaria
sobre os produtos incentivados (receita × TIPI) − o que continua pagando no To Be (só produtos com
IPI protegido e TIPI ≥ limite). Mostrada separada da diferença de carga própria.

**D-025 — Carga de ICMS As Is.** Guia Prático: soma do E116 = ICMS a recolher + débitos especiais do
E110. Premissa `carga_icms_as_is` (padrão `e110_mais_excesso_e116`): carga = ICMS a recolher +
débitos especiais + o que o E116 informar além disso (ex.: fundos pagos à parte). Alternativas:
`e110_mais_fundos` e `somente_e110`. A checagem Q12 mostra onde o E116 excede o E110. O crédito
estímulo aproveitado é informativo (já reduz o ICMS a recolher).

**D-026 — PIS/COFINS As Is.** M200/M600 `VL_TOT_CONT_REC`. A EFD Contribuições é da empresa inteira
(pode incluir estabelecimentos fora do AM): por padrão o valor é rateado pela receita dos
estabelecimentos do AM no mês (premissa `rateio_pis_cofins_am`; `nenhum` = valor inteiro). O mesmo
rateio vale para o filtro por estabelecimento.

**D-027 — Base de operações única (v_base_operacoes).** Uma linha por item ou consolidação; uma
fonte por visão: saídas por produto da EFD Contribuições (C170 ou C181/C185, destino pelo C190+0150
da Fiscal); entradas da EFD ICMS/IPI (C170; C190 se o documento não tem C170); serviços (A170/F100).
Cancelados, denegados e inutilizados ficam fora (COD_SIT 02–05).

**D-028 — Devoluções.** Devolução de venda (entradas 1201/2201/1203/1410...) abate a saída de origem;
devolução de compra (saídas 5201/6201/5553/5556...) abate a entrada de origem. A operação de origem
de cada CFOP fica em Parâmetros > CFOPs (coluna `devolucao_de`). Premissa `abater_devolucoes`.

**D-029 — Transferências entre estabelecimentos.** Identificadas pelo CFOP (x151, x152...) e mostradas
à parte (tela 4). Por padrão fora da base de CBS/IBS (premissa `transferencias_na_base_cbs_ibs`;
conferir na LC 214/2025).

**D-030 — Reconciliação R5 e ajuste de reconciliação.** A carga é recalculada trocando os débitos e
créditos da apuração pelos da base de operações (ajustes do E111, deduções, saldo anterior e ajustes
do bloco M — inclusive os de acréscimo de 2026, LC 224/2025 — continuam os da apuração). Se não
fechar, a diferença `apuração − base` aparece como **ajuste de reconciliação** na tela 8 e na ponte,
separada do efeito da reforma. Tolerância: R$ por estabelecimento/mês (ICMS/IPI) e % (PIS/COFINS, R3).

**D-031 — Conciliações revisadas.** Q3 cobre também o C170 da Contribuições; Q7 (R4) compara
documento a documento só as saídas (entradas sem crédito podem não constar da Contribuições);
Q8 (R3) compara receitas da base × bloco M com tolerância de 0,5%; novas Q12 (E116 × E110) e Q13
(C180 × C181/C185).

**D-032 — C181 × C185 sem dupla contagem.** Na escrituração consolidada, a receita vem do C181 (PIS);
o C185 (COFINS) é casado pela mesma linha (CFOP e valor). C185 sem par entra só com a COFINS. Só
quando o C180 não tem nenhum C181 a receita vem do C185.

**D-033 — Leitura.** (1) Valor que não é número/data válido (ex.: "100.000,00", data 32/01) gera aviso
"conversão" com exemplo e linha, em vez de virar vazio calado. (2) CNPJ alfanumérico (a partir de
jul/2026) e chave da NF-e são tratados como texto. (3) Leiaute 020 (2026) da EFD ICMS/IPI: sem campos
novos no C170 nas fontes consultadas; o leiaute 021 (2027) muda tipos de campo (CNPJ e chave para
alfanumérico), já compatível. Se aparecer aviso de "número de campos", o registro mudou de leiaute.

**D-034 — 2027–2028.** CBS = referência − `reducao_cbs_2027_2028` (0,1 p.p.) e IBS de teste =
`aliq_ibs_teste` (0,1%), sem créditos presumidos de entrada (fator 0) e sem o art. 450 de IBS antes
de `ano_inicio_cp450_ibs` (2029). Substitui o "IBS = 0" da D-015.

**D-035 — Teses.** Teses com status "ativa" já estão na apuração: não ajustam o As Is e seguem no To Be
dentro do ICMS × fator. Teses "em discussão"/"simulação apenas" (com o filtro "Com teses") reduzem a
carga As Is e a To Be (ICMS × fator; IPI × fator do IPI próprio; PIS/COFINS perdem efeito em 2027).

**D-036 — Nível de apuração e ordem de dedução (agora lidos pelo motor).** `nivel_apuracao_cbs_ibs` =
`raiz` (padrão) ou `estabelecimento`. `ordem_deducao_ibs` = CP de entrada antes do art. 450 (padrão)
ou art. 450 antes.

**D-037 — Filtros.** Barra lateral: empresas, período (meses de 2026; a anualização usa os meses do
filtro), estabelecimentos (abre a empresa por CNPJ), com/sem teses. Telas com filtros próprios
(CFOP, produto, NCM, UF, origem, natureza, tributo, cenário, ano, visão saídas/entradas).

**D-038 — E116 com COD_OR 000.** É o ICMS próprio a recolher, não um ajuste: classificado como
"outros". Código sem regra fica `nao_classificado` e gera alerta (Q11) até ser classificado.

**D-039 — Cenários C1–C5 (classificação).** Cada operação da base recebe um cenário na visão
`v_cenarios`. Entradas: importação (CFOP 3xxx) → C1a (estabelecimento indústria incentivada), C1b
(habilitado, compra para revenda presencial — premissa `revenda_presencial`), C1c (demais habilitados);
compra de outro Estado → C2a (indústria incentivada), C2b (habilitado do regime regular), C2c (habilitado
do Simples); compra de fornecedor da ZFM → C3a (intermediário de indústria incentivada para indústria
incentivada — premissa `c3a_intermediario`) ou C3b (demais). Saídas: C4a (fora da ZFM, contribuinte),
C4b (fora da ZFM, consumidor final/não contribuinte), C4c (dentro da ZFM, bem final), C4d (dentro da ZFM,
intermediário para indústria incentivada), EXP (exportação, fora do escopo). À parte: TR (transferências),
REM (remessas/retornos), SRV (serviços tomados). O que não se encaixa vira NC_S/NC_E ("não classificado"),
com o motivo, e entra na simulação pela regra geral. Devoluções recebem o cenário da operação de origem
(abatem); cancelados ficam fora.

**D-040 — Tipo ZFM e regime (tabela `param_empresas_zfm`).** Uma linha por CNPJ (estabelecimentos do grupo
e participantes do AM). Preenchimento automático: estabelecimento do grupo que vende produção própria =
`industria_incentivada`; com SUFRAMA = `habilitado`; demais = `nao_habilitado`. Participante do AM em
município da ZFM com SUFRAMA no 0150 = `habilitado`. Regime inicial = `regular`. O usuário confirma e
marca "revisado"; enquanto não revisar, há alerta.

**D-041 — Regras To Be por cenário (tabela `param_regras_cenario`).** Frações da alíquota do ano para débito,
tributo devido na entrada, crédito do fornecedor e créditos presumidos (art. 450; 447/449/444).
Valores iniciais: C1a suspensão sem crédito (art. 443); C1b CBS e IBS integrais com crédito presumido de
IBS de 50% (art. 444); C1c integrais; C2a zero com CP 447; C2b IBS de 70% na entrada + CP 447 (arts. 445–447);
C2c IBS de 70% sem CP; C3a zero com CP 449; C3b IBS pela regra geral com crédito do fornecedor (art. 451);
C4a/C4b débito integral com CP do art. 450 de CBS e IBS; C4c CBS zero e IBS com CP do art. 450; C4d zero.
Crédito na entrada (`entrada_creditavel` = `regime`): só o regime regular credita. Todos os valores são
editáveis; os pontos a validar estão em P-016.

**D-042 — As Is por cenário.** Tributo escriturado na própria operação: débito nas saídas (+), crédito nas
entradas (−); PIS/COFINS só creditam com CST 50–66. Crédito estímulo e fundos do ICMS (apuração) são
distribuídos entre as vendas incentivadas (C4) pela proporção do ICMS debitado. A diferença entre a carga
total da apuração e a soma dos cenários (ajustes, saldos credores, teses) aparece na linha
"Não atribuído", para que a soma por cenário seja igual ao total da empresa.

**D-043 — To Be por cenário.** CBS/IBS por cenário com as regras da D-041 e as alíquotas do ano; o crédito
presumido do art. 450 de IBS (calculado sobre o saldo devedor pelo motor mensal) é distribuído entre os
cenários de venda pela base incentivada; ICMS = As Is × fator do ano; IPI próprio = As Is ×
`fator_ipi_proprio` (0 = extinto). A linha "Não atribuído" fecha com o motor mensal (absorção dos créditos
presumidos, safras que expiram, teses). Consolidado = soma das empresas, sem compensação entre elas.

**D-044 — IPI por produto (C5).** Premissa `ipi_protegido_regra` = `tipi` (padrão): TIPI de 31/12/2023 ≥
`limite_tipi_ipi` (6,5%) → IPI mantido para o concorrente; abaixo disso e produzido na ZFM em 2024 → IPI
zero para todos (vantagem perdida; o comprador também perde o crédito de IPI). Com `tabela`, vale a marcação
"ipi_protegido" de cada produto. TIC: regra própria (art. 454, § 2º), sinalizado para análise manual.
Duas métricas separadas: carga própria de IPI (zero antes e depois) e vantagem competitiva (receita
incentivada anualizada × TIPI). Alerta quando o crédito estímulo atual do produto é maior que o percentual
do art. 450 (candidato a perda no IBS).

**D-045 — Conferências do As Is (tabela `param_conferencia_cenario`).** Regras CST/alíquota esperadas por
cenário (ex.: PIS 0,65%/1,3% e COFINS 3%/6% nas vendas para fora da ZFM; IPI com CST 52 nas vendas
incentivadas; entradas C1/C2 sem IPI destacado). Divergência gera alerta com arquivo e linha; devoluções não
são conferidas (usam CST de entrada).

**D-046 — Ano-base automático.** Premissa `ano_base` = `auto`: usa o ano mais recente com EFD carregada
(ou o ano informado, se houver arquivo dele). Evita telas vazias quando as EFDs não são de 2026.

**D-047 — Importação em segundo plano.** A leitura roda numa linha de execução própria do programa,
independente da tela: trocar de tela, recarregar ou fechar a aba do navegador não interrompe; só para ao
fechar a janela preta ou em "Cancelar". Cada arquivo é gravado numa transação (cancelado = nada daquele
arquivo fica no banco). Arquivo repetido é reconhecido em segundos por uma assinatura rápida (tamanho +
primeiro e último 1 MB) antes do SHA-256. Ao final, as análises são preparadas e os cadastros novos entram
nos parâmetros, sem apagar o que foi editado.

**D-048 — Desempenho com arquivos de 1 GB+.** Leitura em partes (memória baixa) e gravação via CSV
temporário lido pelo DuckDB. As visões pesadas são materializadas em tabelas e só são refeitas quando os
dados ou os parâmetros mudam (versão gravada em `_meta`). Os cálculos ficam em cache por versão dos dados +
filtro: trocar de tela não recalcula. As telas agregam no banco e mostram até alguns milhares de linhas;
o CSV traz o restante.

**D-049 — Interface.** Navegação por seções (Visão geral, Dados, Operações, Análise, Relatórios), painel com
roteiro e pendências, cartões, abas e tabelas com números no formato do navegador. Estilo e ícones são
locais (nenhum recurso da internet; conferido no navegador: zero requisições externas). A tabela
`param_regras_entradas` foi substituída por `param_regras_cenario` (fica no arquivo, sem uso).

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
- **P-009** — ~~Método da carga total (D-016)~~ → substituído pelo método As Is × To Be (D-023).
- **P-010** — Alíquota TIPI (31/12/2023) de cada produto incentivado.
- **P-011** — Regra de centralização da apuração de CBS/IBS por raiz do CNPJ (LC 214/2025).
- **P-012** — Composição da base de CBS/IBS na transição (LC 214/2025, art. 12).
- **P-013** — Tratamento das transferências entre estabelecimentos na CBS/IBS.
- **P-014** — Lista dos produtos com IPI mantido (art. 454, § 3º).
- **P-015** — Onde as empresas registram as contribuições a FTI/UEA/FMPES (E111, E116 ou fora da EFD).
- **P-016** — Validar as regras por cenário (D-041), em especial: crédito presumido de 50% do art. 444 (C1b),
  IBS de 70% na entrada para habilitados (C2b/C2c), crédito de IBS do fornecedor em C3b e CBS zero em C4c.
- **P-017** — Comprovação de ingresso (internamento) nas compras C2: hoje só alerta; a simulação da perda
  do benefício está desligada (`simular_risco_ingresso_c2` = nao).
- **P-018** — Produtos TIC (art. 454, § 2º): tratamento a definir caso a caso.
- **P-019** — Tipo ZFM (indústria incentivada/habilitado) e regime dos participantes: confirmar na aba
  Empresas ZFM; a classificação automática usa SUFRAMA e município do 0150.
