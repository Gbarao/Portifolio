# Manual do usuário — Programa ZFM × Reforma Tributária

> Versão: análise As Is (apuração atual) × To Be (2027–2033).

## 1. O que o programa faz

O programa lê as EFD ICMS/IPI e EFD Contribuições de 2026 das empresas do grupo no Amazonas e
compara a **carga atual** (As Is, lida da apuração) com a **carga simulada após a Reforma**
(To Be, 2027 a 2033: CBS, IBS, ICMS residual, IPI e contribuição estadual do art. 457).
O resultado principal é a **diferença To Be − As Is** por empresa, ano e tributo:
**positivo = aumento de carga (perda); negativo = redução (ganho)**.
Tudo roda **só no seu computador**: nenhum dado é enviado para a internet.

## 2. Primeiro uso (uma vez só)

1. **Verifique se o Python existe.** Abra o menu Iniciar, digite `cmd` e abra o *Prompt de Comando*.
   Digite o texto abaixo e aperte Enter:

   ```
   py --version
   ```

   Deve aparecer algo como `Python 3.12.4`. Se der erro, tente `python --version`.
   Feche a janela preta.
2. **Se não houver Python (ou for menor que 3.10):** não instale por conta própria. Envie à TI:

   > Preciso do Python 3.10 ou superior (64 bits) instalado no meu computador, com o `pip` e o
   > módulo `venv` incluídos (instalação padrão do python.org). Uso: ferramenta interna de análise
   > fiscal que roda só no meu computador.
3. **Coloque a pasta do programa** num lugar seu, por exemplo `Documentos\zfm-efd`.
   (Se recebeu um `.zip`: clique com o botão direito → *Extrair tudo...* → escolha `Documentos`.)
4. **Dê duplo clique em `diagnostico.bat`.** Uma janela preta mostra uma lista com `[OK]` ou
   `[FALHA]`. No final deve aparecer **"RESULTADO: Tudo certo"**. Se aparecer `[FALHA]`, a própria
   linha diz o que fazer.
5. **Se aparecer falha de rede, proxy ou certificado** (mensagens com `SSL`,
   `CERTIFICATE_VERIFY_FAILED` ou `ProxyError`): envie à TI:

   > Preciso instalar bibliotecas Python com o `pip` numa pasta do meu usuário (sem
   > administrador). Peço a liberação do acesso HTTPS a `pypi.org` e `files.pythonhosted.org`,
   > ou o endereço do proxy corporativo para configurar o `pip`. A verificação de certificado
   > deve continuar ligada.
6. **Dê duplo clique em `iniciar.bat`.** Na primeira vez ele baixa as bibliotecas (alguns minutos;
   é a única vez que o programa usa a internet). Depois o navegador abre sozinho na página do
   programa.

## 3. Abrir e fechar

- **Abrir:** duplo clique em `iniciar.bat`. A janela preta fica aberta e o navegador mostra o programa.
  Se o navegador não abrir, copie o endereço que aparece na janela preta (ex.: `http://127.0.0.1:8501`).
  Esse endereço só funciona no seu computador.
- **Fechar:** feche a janela preta. (Fechar só o navegador não encerra o programa.)

## 4. Importar as EFDs (menu Dados > Importação das EFDs)

1. Copie as EFDs (`.txt` originais) para uma pasta, por exemplo `Documentos\EFDs 2026`.
   Podem estar em subpastas. Arquivos de 1 GB ou mais são aceitos.
2. No Windows Explorer, abra a pasta, clique na **barra de endereço** (no alto da janela) e aperte **Ctrl+C**.
3. No programa, clique no campo **Pasta das EFDs** e aperte **Ctrl+V**.
4. Clique em **Verificar pasta**. Aparecem cartões com a quantidade de arquivos, o tamanho total e o maior
   arquivo.
5. Clique em **Iniciar importação**. Aparece a barra de progresso (com tempo decorrido e estimativa) e uma
   tabela com a situação de cada arquivo: *Na fila*, *Lendo*, *Carregado*, *Já existia* ou *Não carregado*
   (com o motivo).

**A importação roda em segundo plano.** Você pode ir para outras telas: o progresso continua aparecendo na
barra lateral. Fechar a aba do navegador também não interrompe. Ela só para se você **fechar a janela
preta** ou clicar em **Cancelar importação** (o arquivo que estava sendo lido é descartado; os já
concluídos ficam). Enquanto a importação roda, as telas mostram os dados importados antes, com um aviso
azul; ao final, tudo é atualizado sozinho e os cadastros novos entram em Parâmetros.

**Validação das duas EFDs.** Ao clicar em **Verificar pasta**, o programa lê só o cabeçalho de cada arquivo e
mostra, antes de importar, se cada empresa tem a **EFD ICMS/IPI** de cada estabelecimento do AM e a **EFD
Contribuições** da empresa em todos os meses (somando o que já está no banco). Aparece:
- uma tabela por empresa (estabelecimentos, meses e quantas escriturações faltam);
- uma grade estabelecimento × mês: verde "ICMS/IPI ✓ · Contrib. ✓"; vermelho quando falta alguma (✗);
- a lista do que falta, com o que importar (ex.: "Importar a EFD Contribuições da empresa (matriz)").

A mesma validação aparece depois da importação (seção *Validação das escriturações no banco*), no Painel e em
Qualidade > Fiscal × Contribuições. Os estabelecimentos considerados são os que têm EFD ICMS/IPI e os listados
no registro 0140 da EFD Contribuições com inscrição estadual.

Observações:
- Tempo de referência: alguns minutos por GB. Arquivo já importado é reconhecido em segundos e pulado.
- O programa reconhece sozinho se o arquivo é EFD ICMS/IPI ou EFD Contribuições.
- Uma **retificadora** substitui a original do mesmo CNPJ/IE/período (a original aparece como *Substituído*).
- Para recomeçar do zero: *Apagar todos os dados carregados*, no fim da tela (os `.txt` e os parâmetros não
  são apagados).

## 5. Conferir os arquivos (menu Dados > Qualidade e reconciliação)

No topo, quatro cartões resumem a situação (OK ou quantidade de divergências). As abas:
- **Completude e integridade:** uma linha por estabelecimento do Amazonas e uma coluna por mês. Verde *OK* =
  as duas EFDs existem; vermelho = falta arquivo. Abaixo, Q2: registros lidos × informados (9900/9999).
- **Conciliações:** lista das checagens com a situação. Escolha uma na caixa *Ver divergências de* para ver
  as linhas que não fecham. R1 (Q5) documentos × E110; R2 (Q6) documentos × E520; R3 (Q8) receitas × bloco M
  (0,5%); R4 (Q7) mesmo documento nas duas EFDs; Q3, Q4, Q9 a Q13.
- **Fiscal × Contribuições:** mesma mecânica do sistema de consolidação SPED Fiscal × EFD Contribuições:
  - *Vínculo dos documentos:* cada nota é ligada à da outra EFD uma única vez — pela chave da NF-e (mesmo que
    esteja em meses diferentes) ou, sem chave, por estabelecimento, mês, fornecedor, modelo, série e número. A
    tabela mostra quantas notas estão nas duas EFDs (coluna *Vínculo*: CHAVE ou NUMERO), só numa, sem
    contrapartida, na Contribuições consolidada ou repetidas.
  - *Diagnóstico do cruzamento de PIS/COFINS:* o PIS/COFINS das entradas vem sempre da EFD Contribuições, ligado
    ao item do SPED Fiscal por nível — N1 (mesmo item, posição e valor), N1V (mesma posição e valor, código
    diferente), N2 (mesmo código e CFOP na nota), N3 (escrituração consolidada: mês, fornecedor, CFOP e código),
    "só na EFD" e "sem crédito". Olhe primeiro esta tabela com os arquivos reais: muito "sem par" indica códigos
    de item ou CFOPs diferentes entre as duas EFDs.
  - *Fechamento:* mensagem verde quando todo o PIS/COFINS das entradas da EFD Contribuições está na base uma vez
    só (Q18).
  - *Cobertura:* a grade das EFDs por estabelecimento e mês.
  Divergências detalhadas em Conciliações: Q7 (nota só numa EFD ou valor/data/fornecedor diferentes), Q15 (item
  na mesma posição com código/CFOP/valor diferente; CFOP só de um lado), Q16 (repetidas), Q14 (item sem C190),
  Q17 (escrituração faltando), Q18 (fechamento), Q19 (crédito só na EFD), Q20 (crédito de ICMS/IPI sem PIS/COFINS
  e o inverso), Q21 (CST diferente entre estabelecimentos).
- **Reconciliação R5:** carga recalculada pela base de operações × carga da apuração. Se não fechar, a
  diferença aparece como "ajuste de reconciliação", separada do efeito da reforma.
- **Avisos de leitura:** linhas com formato diferente do esperado (com exemplo e linha do arquivo).

## 6. Revisar os parâmetros (menu Dados > Parâmetros e premissas)

O preenchimento a partir das EFDs é automático ao fim de cada importação (o botão **Preencher a partir das
EFDs** repete o processo). O que você editou não é apagado. O quadro **Pendências de revisão** lista o que
falta. Para editar: clique na célula, digite, e clique em **Salvar** na própria aba. Alternativa: **Baixar
CSV**, editar no Excel e usar **Importar CSV editado no Excel**. Tabelas grandes têm o campo **Buscar**.

Ordem recomendada:

1. **Empresas ZFM** — uma linha por CNPJ (estabelecimentos do grupo e participantes do Amazonas). Confira a
   coluna *tipo* (`industria_incentivada`, `habilitado`, `nao_habilitado`) e *regime* (`regular`, `simples`)
   e marque *revisado*. É o que define os cenários C1 a C4.
   Exemplo: `11111111000191; 11111111; ALFA; grupo; AM; 1302603; 200001; industria_incentivada; regular; ...; sim`
2. **Produtos** — preencha a **alíquota TIPI de 31/12/2023 (%)**, *produzido_zfm_2024*, *eh_tic* e o *nível de
   crédito estímulo (%)*. Abaixo da tabela aparecem os percentuais do art. 450 calculados.
   Exemplo: `11111111; TV50; 85287200; Televisor; sim; final; 15; ; sim; não; não; 55; não`
3. **Regras por cenário** — tratamento simulado de cada cenário (frações da alíquota: 1 = integral, 0 = zero,
   0,7 = 70%) e créditos presumidos. Valores iniciais com a base legal na própria linha.
4. **Conferências** — CST/alíquota esperados por cenário (geram alertas de divergência).
5. **Cadastros complementares** (nada é presumido; campo vazio = não comprovado):
   - **Empresas ZFM**: além de tipo e regime, *status_habilitacao* (ativa/suspensa/cancelada), *validade_ini* e
     *validade_fim* (AAAA-MM-DD) e *evidencia*. Só a linha marcada *revisado* conta como habilitação comprovada.
   - **Produtos**: *origem* (nacional/importada), *excluido_art441* (sim/nao) e *motivo_exclusao* (ex.: bebida
     alcoólica), *uso_consumo_pessoal*, *similar_nacional*, *projeto_cas_2022_2025*, *art455_alternativa*,
     *aliq_ipi_futura*, *consumo_produtivo_comprovado* (art. 449) e *classificacao_aprovada*.
   - **Projetos SUFRAMA**: uma linha por produto aprovado (CNPJ, projeto, data CAS, vigência, cod_item ou NCM, PPB,
     status). Exemplo: `11111111000191; PRJ-001; 2023-05-10; 2023-06-01; ; TV50; ; sim; ; aprovado; `
   - **Internamento**: chave da NF-e e status (confirmado/pendente/negado). Exemplo:
     `13260155...; 2026-01-20; confirmado; PROT-123; sim; 11111111000191; vistoria`
   - **Importações**: DI/DUIMP, valor aduaneiro, II, IPI, despesas, destinação e controle das quantidades (art. 443).
   - **Serviços na ZFM**: documento do A100, município e *local_fisico_zfm* (sim/nao) com a evidência.
   - **Regras legais**: percentuais, vigências e status das regras da LC 214/2025. Ao mudar um percentual ou a data
     de início, os cálculos acompanham. Regra "pendente_regulamentacao" não é aplicada.
6. **Alíquotas por ano**, **Códigos de ajuste**, **CFOPs**, **Empresas do grupo**, **Municípios ZFM**,
   **Regime geral**, **Teses** e **Premissas** — como antes.

**Aba "Resumo e alíquotas" (a primeira):** digite a CBS e o IBS de referência (%) de cada cenário e clique em
**Aplicar aos anos 2027–2033**; abaixo, a lista de **todas as premissas adotadas** (valor, onde alterar e
fonte) — a mesma da aba "Premissas" do Excel.

**Códigos de ajuste:** classificação automática pela descrição (ex.: "ESTÍMULO", "FTI", "UEA", "FMPES"); a
coluna *regra_automatica* mostra o motivo. Confira e marque *revisado*.

**Alíquotas de CBS e IBS:** valores iniciais de pesquisa de 06/11/2026 (coluna *fonte*): CBS 11,3% (TCU) e
IBS 18,7% (premissa do Comitê Gestor) no cenário base.

## 7. Telas de análise

**Barra lateral (vale para todas as telas):** empresas (uma, várias ou o consolidado), **meses** do ano-base
(a anualização usa os meses escolhidos), **estabelecimentos** e **Com teses**. Os selos abaixo do título de
cada tela mostram o filtro em uso.

- **Painel (Visão geral):** números da base, roteiro com o que está concluído/pendente, resultado consolidado
  (As Is, To Be 2033, diferença), gráfico da diferença 2027–2033, diferença por empresa e alertas principais.
  Se alguma tela aparecer vazia, o painel explica o motivo (ex.: nenhum estabelecimento no AM).
- **Base de operações, Saídas, Entradas (Operações):** cartões, abas e **Filtros** (clique para abrir).
  As tabelas mostram as maiores linhas; o CSV traz todas.
- **Simulador individual (Análise):** escolha o cenário (arts. 443, 444, 445–447, 448/449, 450 IBS, 450 CBS, 451,
  454, 455), o ano e as alíquotas; marque cada requisito como *Atendido*, *Não atendido* ou *Não comprovado*. Aparecem
  o status, a tabela de valores, a **memória de cálculo** (fatos, requisitos, fórmula, fundamento e grau de confiança)
  e o efeito no preço (preço líquido constante, bruto constante ou repasse parcial).
- **Cenários ZFM (C1–C6) (Análise):** a aba **Elegibilidade** mostra o valor por status (Elegível, Potencialmente
  elegível, Informação insuficiente, Não elegível), o que falta comprovar em cada cenário e o **valor em risco**
  (simulação com as operações não confirmadas pela regra geral × com o incentivo).
  - *Matriz*: cenário × empresa, em valor ou nº de documentos; coluna *intragrupo* sinaliza operações com
    empresas do grupo;
  - *As Is × To Be*: escolha cenário de alíquotas, ano e tributos; tabela por cenário (As Is, To Be,
    diferença), por cenário × tributo, por cenário × empresa e evolução 2027–2033. A linha **"Não atribuído"**
    reúne ajustes da apuração, saldos credores, absorção dos créditos presumidos e teses: com ela, a soma dos
    cenários é igual à diferença total da empresa;
  - *Ponte e ranking*: gráfico As Is → cenários → To Be (vermelho = paga mais; verde = paga menos) e
    rankings de cenários e empresas;
  - *IPI por produto (C6)*: carga própria de IPI (zero) × vantagem competitiva (IPI do concorrente) hoje e no
    To Be, por situação da TIPI; chave para simular sem IPI protegido;
  - *Alertas*: não classificados, divergências de CST/alíquota (com arquivo e linha), comprovação de ingresso,
    produtos candidatos a perda no IBS, produtos sem TIPI, TIC, tipo ZFM não revisado e R5;
  - *Não classificados*: operações sem cenário, com o motivo e onde corrigir.
- **Metodologia e cruzamentos (Análise):**
  - *Cenários*: tabela com todos os cenários; escolha um para ver **como é identificado**, **quais registros e
    campos são capturados**, o **As Is** (o que é lido), o **To Be** (com os parâmetros em uso — muda quando
    você edita Parâmetros > Regras por cenário), as conferências, os cruzamentos que validam e a base legal;
  - *Registros capturados*: as linhas que caíram no cenário, com registro, arquivo e linha do .txt e os campos
    usados na classificação (CFOP, participante, UF, tipo ZFM, produto);
  - *Cruzamentos*: cada cruzamento (lado A × lado B, chave de ligação, tolerância, o que indica) com a situação
    atual;
  - *De onde vem cada dado*: EFD, registros e campos de cada informação usada nos cálculos.
- **Carga As Is:** ICMS, IPI, PIS e COFINS lidos da apuração (sem recálculo), anualizados; composição;
  crédito estímulo e fundos; saldos credores; R5.
- **To Be e diferença:** cenário, ano, tributos e visão (Completa, Só saídas, Só entradas); diferença por
  tributo, ranking, ponte por tributo, evolução, comparação de cenários de alíquotas, teste de absorção e
  vantagem do IPI.
- **Benefício ZFM (informativo):** quanto a ZFM reduz hoje (regime geral − ZFM); não entra na diferença.

## 8. Exportar para o Excel (menu Relatórios)

Clique em **Gerar Excel** e depois em **Baixar Excel**. Uma aba por visão: Metodologia (cenários, cruzamentos e fontes dos dados), Pareamento Fiscal x Contrib, Cobertura das EFDs, Matriz cenários, Cenários As Is x
To Be, IPI por produto (C6), Alertas, Não classificados, Diferença por tributo e por empresa, Ponte, Saídas x
entradas, Vantagem competitiva IPI, Absorção, Carga As Is, R5, Benefício (informativo), divergências das
conciliações, **Premissas** (lista legível) e **Parâmetros (tabelas)**. Os filtros da barra lateral valem para
todas as abas.

## 9. Quando der erro

- **Erro na janela preta do `iniciar.bat`:** selecione o texto da janela, copie e envie ao
  Claude Code. A instalação também grava um arquivo em `data\logs\instalacao_*.log`.
- **Erro na tela do programa:** a mensagem indica o arquivo `data\logs\zfm.log`
  (dentro da pasta do programa). Envie esse arquivo ao Claude Code.
- **Nunca envie EFDs reais na conversa.** Só a mensagem de erro e o arquivo de log.
- **Testes automáticos:** duplo clique em `testar.bat` mostra quantos testes passaram e falharam.

## 10. Perguntas frequentes

- **Os dados saem do meu computador?** Não. O programa só aceita conexões do próprio
  computador (`127.0.0.1`) e não usa internet depois da instalação das bibliotecas.
- **Onde ficam os dados?** Na pasta `data` dentro da pasta do programa (banco `zfm.duckdb` e logs).
- **Posso abrir duas janelas do programa?** Não ao mesmo tempo: feche a janela preta antiga antes.
- **Por que o benefício de IPI está zerado?** Falta a alíquota TIPI dos produtos em
  Parâmetros > Produtos.
- **Mudei um parâmetro e nada mudou.** Clique em *Salvar* na aba; as telas usam o valor salvo.
- **Uma tela aparece vazia.** Abra o Painel: o quadro de diagnóstico mostra o motivo (sem estabelecimento no
  AM, falta EFD Contribuições, empresa desmarcada etc.).
- **Posso usar o programa durante a importação?** Sim. As telas mostram os dados anteriores com um aviso e
  são atualizadas ao final.
- **O antivírus/TI perguntou sobre o Python acessando a rede:** é o servidor local do programa
  (endereço `127.0.0.1`, só dentro do computador).
