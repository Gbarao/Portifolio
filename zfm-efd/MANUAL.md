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

## 4. Importar as EFDs (Dados > Importação das EFDs)

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

## 5. O mapa do programa (9 telas)

| Menu | Tela | Para que serve |
|---|---|---|
| Visão geral | **Painel** | Situação dos dados, o que falta fazer e o resultado consolidado |
| Dados | **Importação das EFDs** | Ler os .txt e conferir se cada empresa tem as duas EFDs em todos os meses |
| Dados | **Qualidade e conferências** | Arquivos completos? As duas EFDs batem entre si e com a apuração? |
| Dados | **Cadastros** | Confirmar o que o programa não tira sozinho das EFDs |
| Análise | **Operações** | Abas Saídas, Entradas e Base completa (tudo o que foi lido, já normalizado) |
| Análise | **Cenários ZFM** | Em que cenário cada operação caiu, o resultado por cenário, IPI por produto, pendências e como é calculado |
| Análise | **Resultado As Is × To Be** | Diferença por ano, empresa e tributo; carga atual da apuração; benefício atual (informativo) |
| Análise | **Simulador individual** | Calcular uma operação isolada, com memória de cálculo e efeito no preço |
| Relatórios | **Exportação para Excel** | Tudo num arquivo Excel |

Ordem de uso: Importação → Qualidade → Cadastros → Cenários → Resultado → Exportação.

## 6. Conferir os arquivos (Dados > Qualidade e conferências)

No topo, cartões com o resultado de cada grupo. As abas:
- **Completude e integridade:** uma linha por estabelecimento do AM e uma coluna por mês (verde = as duas EFDs
  existem) e a integridade do bloco 9.
- **Fiscal × Contribuições:** quantas notas estão nas duas EFDs, só numa, sem contrapartida etc.; o diagnóstico do
  crédito de PIS/COFINS por nível; o fechamento (deve ficar verde) e a cobertura.
- **Conferências:** lista única, em 4 grupos (arquivos; dentro de cada EFD; documentos × apuração; EFD ICMS/IPI ×
  EFD Contribuições). Escolha uma checagem com divergência para ver as linhas, com arquivo e linha do .txt.
- **Reconciliação R5:** a base de operações explica a apuração? O que não fecha vira "ajuste de reconciliação".
- **Avisos de leitura.**

## 7. Cadastros (Dados > Cadastros)

Tudo vem pré-preenchido das EFDs ao fim de cada importação. Você só confirma ou corrige. No topo há a lista do
que falta. Cada tabela mostra só as colunas essenciais (botão **Mostrar todas as colunas** para o resto).
Edite na tabela e clique em **Salvar** (ou baixe o CSV, edite no Excel e importe).

1. **Empresas ZFM** — estabelecimentos do grupo: confirme o **Tipo ZFM** (indústria incentivada, habilitado, não
   habilitado) e o **Regime** e marque **Revisado**. O número SUFRAMA da EFD é só indício. Para ver clientes e
   fornecedores do AM, ligue "Mostrar também os participantes".
2. **Produtos** — mostra só os incentivados (desligue o filtro para ver todos). Confira **Incentivado**, **Tipo de bem**
   (final, capital, intermediário, informática: define o percentual do art. 450) e a **alíquota do IPI**.
   **A alíquota do IPI é lida da própria EFD** (C170, campo ALIQ_IPI): primeiro das saídas do produto na EFD
   Contribuições, depois na EFD ICMS/IPI, depois de qualquer nota do produto e, por último, de outro produto com o
   mesmo NCM. A coluna **Origem da alíquota de IPI** mostra de onde veio. Saída isenta da ZFM costuma vir com
   alíquota zero, que não informa a TIPI: nesse caso a coluna avisa e você informa a TIPI. Marque **Revisado** para
   que a EFD não altere mais o valor. Botão **Reler as alíquotas de IPI da EFD** refaz a leitura.
3. **Alíquotas CBS/IBS** — premissas de simulação por cenário (base, baixo, alto, adverso). Digite a alíquota cheia
   e clique em **Aplicar aos anos 2027–2033**.
4. **Comprovações (opcional)** — projetos SUFRAMA, internamento (ingresso na ZFM) e serviços prestados na ZFM. Sem
   elas, as operações incentivadas ficam "potencialmente elegíveis": o incentivo é calculado como estimativa e o
   valor em risco aparece em Cenários ZFM > Pendências.
5. **Avançado** — regras legais (percentuais e vigências da LC 214/2025), tratamento de cada cenário, conferências,
   CFOPs, códigos de ajuste do ICMS, empresas do grupo, municípios da ZFM, regime geral, teses e premissas. Já vêm
   preenchidos; só altere para mudar uma regra de cálculo.
6. **Premissas adotadas** — lista legível de tudo o que foi assumido (vai para o Excel).

## 8. Telas de análise

**Barra lateral (vale para todas as telas):** empresas (uma, várias ou o consolidado), meses, estabelecimentos e
*Com teses*. Os selos abaixo do título mostram o filtro em uso.

- **Operações:** abas Saídas, Entradas e Base completa, com filtros e download em CSV.
- **Cenários ZFM:**
  - *Resumo*: matriz cenário × empresa (valor ou nº de documentos);
  - *Resultado por cenário*: As Is, To Be e diferença por cenário, tributo e ano; ponte e ranking;
  - *IPI por produto (C6)*: carga própria de IPI (zero) × vantagem competitiva (IPI do concorrente), com a alíquota
    lida da EFD;
  - *Pendências*: status de elegibilidade (Elegível, Potencialmente elegível, Informação insuficiente, Não elegível),
    o que falta comprovar, o valor em risco, os alertas e as operações não classificadas;
  - *Como é calculado*: para cada cenário, como é identificado, o que é lido das EFDs, o cálculo e os cruzamentos.
- **Resultado As Is × To Be:**
  - *Diferença To Be × As Is*: cenário de alíquotas, ano e tributos; cartões, diferença por tributo, ponte,
    evolução 2027–2033, art. 450 por faixa e absorção dos créditos presumidos, vantagem do IPI;
  - *Carga As Is (apuração)*: ICMS, IPI, PIS e COFINS lidos da apuração, anualizados;
  - *Benefício ZFM atual (informativo)*: quanto a ZFM reduz hoje (não entra na diferença).
- **Simulador individual:** escolha o cenário, o ano e as alíquotas e marque os requisitos; mostra o status, os
  valores, a memória de cálculo e o efeito no preço.

## 9. Exportar para o Excel (Relatórios > Exportação para Excel)

Clique em **Gerar Excel** e depois em **Baixar Excel**. Uma aba por visão, mais **Premissas** e **Parâmetros
(tabelas)**. Os filtros da barra lateral valem para todas as abas.

## 10. Quando der erro

- **Erro na janela preta do `iniciar.bat`:** selecione o texto da janela, copie e envie ao
  Claude Code. A instalação também grava um arquivo em `data\logs\instalacao_*.log`.
- **Erro na tela do programa:** a mensagem indica o arquivo `data\logs\zfm.log`
  (dentro da pasta do programa). Envie esse arquivo ao Claude Code.
- **Nunca envie EFDs reais na conversa.** Só a mensagem de erro e o arquivo de log.
- **Testes automáticos:** duplo clique em `testar.bat` mostra quantos testes passaram e falharam.

## 11. Perguntas frequentes

- **Os dados saem do meu computador?** Não. O programa só aceita conexões do próprio
  computador (`127.0.0.1`) e não usa internet depois da instalação das bibliotecas.
- **Onde ficam os dados?** Na pasta `data` dentro da pasta do programa (banco `zfm.duckdb` e logs).
- **Posso abrir duas janelas do programa?** Não ao mesmo tempo: feche a janela preta antiga antes.
- **Por que o benefício de IPI está zerado?** Falta a alíquota TIPI dos produtos em
  Cadastros > Produtos.
- **Mudei um parâmetro e nada mudou.** Clique em *Salvar* na aba; as telas usam o valor salvo.
- **Uma tela aparece vazia.** Abra o Painel: o quadro de diagnóstico mostra o motivo (sem estabelecimento no
  AM, falta EFD Contribuições, empresa desmarcada etc.).
- **Posso usar o programa durante a importação?** Sim. As telas mostram os dados anteriores com um aviso e
  são atualizadas ao final.
- **O antivírus/TI perguntou sobre o Python acessando a rede:** é o servidor local do programa
  (endereço `127.0.0.1`, só dentro do computador).
