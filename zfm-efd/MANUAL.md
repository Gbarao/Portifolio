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

## 4. Carregar as EFDs

1. Copie as EFDs (`.txt` originais) para uma pasta, por exemplo `Documentos\EFDs 2026`.
   Podem estar em subpastas.
2. No programa, abra **1. Carga de arquivos** (menu à esquerda).
3. No Windows Explorer, abra a pasta das EFDs, clique na **barra de endereço** (no alto da
   janela) e aperte **Ctrl+C**.
4. No programa, clique no campo **Pasta das EFDs** e aperte **Ctrl+V**.
5. Clique em **Carregar arquivos**. Aguarde a barra de progresso chegar ao fim.
6. A tabela mostra cada arquivo como *Carregado*, *Já existia* ou *Não carregado* (com o motivo).

Observações:
- O programa reconhece sozinho se o arquivo é EFD ICMS/IPI ou EFD Contribuições.
- Se carregar uma **retificadora**, ela substitui a original do mesmo CNPJ/IE/período
  (a original aparece como *Substituído*).
- Carregar o mesmo arquivo de novo não duplica nada.
- Para recomeçar do zero: *Apagar todos os dados carregados*, no fim da tela (os `.txt` não são apagados).

## 5. Conferir os arquivos (tela 2. Perímetro e qualidade)

- **Q1 – Completude:** uma linha por estabelecimento do Amazonas e uma coluna por mês.
  Verde *OK* = as duas EFDs existem. Vermelho = falta arquivo.
- **Q2 – Integridade:** quantidade de registros lidos × informada no próprio arquivo (9900/9999).
- **Conciliações:** cada linha abre a lista do que não fecha.
  - R1 (Q5) documentos × E110; R2 (Q6) documentos × E520; R3 (Q8) receitas × bloco M (tolerância de
    0,5%); R4 (Q7) mesmo documento nas duas EFDs; **R5** carga recalculada pela base de operações ×
    carga da apuração. O R5 é a porta de entrada da simulação: se não fechar, a diferença aparece na
    tela 8 como "ajuste de reconciliação", separada do efeito da reforma.
  - Q3, Q4, Q9 a Q13: itens × documento, alíquotas de PIS/COFINS, CST de IPI, códigos de ajuste sem
    classificação, E116 × E110 e C180 × C181/C185.
- **Avisos de leitura:** linhas com formato diferente do esperado ou valores que não são número/data
  válidos (o aviso mostra o exemplo e a linha do arquivo).

## 6. Preencher os parâmetros (tela 3. Parâmetros e premissas)

1. Depois de carregar as EFDs, clique em **Preencher a partir das EFDs**. O programa acrescenta
   empresas, produtos (registro 0200), CFOPs e códigos de ajuste do ICMS (E111/E116) encontrados nos
   arquivos. O que você já editou não é apagado.
2. Revise cada aba e clique em **Salvar** na própria aba. Alternativa: **Baixar CSV**, editar no
   Excel, salvar como CSV e usar **Importar CSV**.
3. Avisos amarelos no topo mostram o que falta (por exemplo, produtos sem alíquota TIPI).

**Aba "Premissas e alíquotas" (a primeira):**
- *1. Alíquotas de referência*: digite a CBS e o IBS de referência (%) de cada cenário e clique em
  **Aplicar aos anos 2027–2033**. O programa calcula os anos de transição sozinho. Para criar um
  cenário novo, acrescente uma linha.
- *2. Todas as premissas adotadas*: lista, em linguagem simples, cada premissa usada nos cálculos,
  o valor adotado, onde alterar e a fonte. É a mesma lista da aba "Premissas adotadas" do Excel.

Abas e exemplo de linha preenchida:

| Aba | O que preencher | Exemplo |
| --- | --- | --- |
| Empresas | Nome curto e se entra na análise | `12345678; ALFA ELETRONICOS LTDA; Alfa; sim` |
| Produtos | Incentivado, tipo de bem, **alíquota TIPI de 31/12/2023 (%)**, IPI protegido, nível de crédito estímulo (%) | `12345678; TV50; 85287200; Televisor; sim; final; 15; ; sim; não; não; 55; não` |
| Alíquotas por cenário | CBS e IBS do ano (%), fator do ICMS, crédito presumido do art. 450 | `base; 2033; 11,3; 18,7; 0; 1; sim; ; 0` |
| Códigos de ajuste | Classe de cada código E111/E116 (crédito estímulo, fundo FTI/UEA/FMPES, outros) | `AM040014; E111; credito_estimulo; ...; sim` |
| Tratamento das entradas | Como cada origem de compra é tratada após a reforma | `nacional_fora_zfm; aliquota_zero; aliquota_zero; sim; não` |
| Regime geral | PIS 1,65% e COFINS 7,6% (contrafactual fora da ZFM) | `PIS; 1,65` |
| CFOPs | Categoria e se é receita | `6101; venda_producao; sim` |
| Municípios da ZFM | Código IBGE | `1302603; Manaus` |
| Teses | Efeito de cada tese (R$/mês ou %) e vigência | `T1; Exclusão X; todas; ICMS; valor_fixo_mensal; 10000; 2026-01; 2032-12; ativa` |
| Premissas | Bases de cálculo, rateios, prazo do crédito presumido | `prazo_cp_anos; 5` |

**Códigos de ajuste:** como os códigos não eram conhecidos, o programa classifica sozinho pela
descrição na EFD (ex.: texto com "ESTÍMULO", "FTI", "UEA", "FMPES") e pelo tipo do código
(dedução do ICMS no AM = crédito estímulo). A coluna *regra_automatica* mostra o motivo. Confira e
marque *revisado*.

**Alíquotas de CBS e IBS:** os valores iniciais vêm de pesquisa de 06/11/2026 (coluna *fonte*):
CBS 11,3% (TCU) e IBS 18,7% (premissa do Comitê Gestor) no cenário base. Edite quando o Senado
fixar as alíquotas.

## 7. Filtros e telas de resultado

**Barra lateral (vale para todas as telas):** empresas (uma, várias ou o consolidado), **período**
(meses de 2026 — a anualização usa os meses escolhidos), **estabelecimentos** (abre a empresa por
CNPJ completo; vazio = todos) e **Com teses**. Nas telas há filtros próprios (CFOP, produto, NCM, UF,
origem, natureza, tributo, cenário, ano, visão).

- **4. Base de operações:** a base usada na simulação, uma linha por item. Devoluções aparecem com
  valor negativo (abatem a operação de origem). Transferências entre estabelecimentos aparecem à parte.
  Botão para baixar em CSV.
- **5. Saídas / 6. Entradas:** só as saídas ou só as entradas, com filtros.
- **7. Carga As Is (apuração):** ICMS, IPI, PIS e COFINS **lidos da apuração**, sem recálculo; carga
  anualizada; composição saídas × entradas; crédito estímulo e fundos (informativo); saldos credores no
  fim do período; resultado do R5.
- **8. To Be e diferença:**
  - escolha **cenário**, **ano**, **tributos** e a **visão** (Completa, Só saídas, Só entradas);
  - cartões: carga As Is, carga To Be e diferença (vermelho = perda);
  - **diferença por tributo** (uma coluna por empresa e o total);
  - **ponte**: carga As Is → ajuste de reconciliação → efeito CBS (substitui PIS/COFINS) → efeito IBS →
    ICMS residual → IPI → contribuição do art. 457 → carga To Be;
  - **ranking** das empresas, da maior perda ao maior ganho;
  - **duas métricas**: diferença de carga própria × perda de vantagem competitiva do IPI (IPI que o
    concorrente de fora pagava e deixa de pagar), também por produto;
  - **teste de absorção**: crédito presumido gerado, usado e expirado; carga teórica × realizável;
    alerta de saldo credor estrutural.
- **9. Benefício ZFM (informativo):** quanto a ZFM reduz hoje de IPI, PIS, COFINS e ICMS (regime
  geral − ZFM). Não entra na diferença.

## 8. Exportar para o Excel (tela 10)

Clique em **Gerar Excel** e depois em **Baixar Excel**. O arquivo usa os filtros da barra lateral e
traz: diferença por tributo e por empresa, ponte, composição saídas × entradas, vantagem competitiva do
IPI, absorção, carga As Is, R5, base de operações (resumo), benefício informativo, divergências das
conciliações, **Premissas adotadas** (lista legível) e **Parâmetros (tabelas)**.

**Depois de atualizar o programa:** abra 3. Parâmetros, clique em **Preencher a partir das EFDs**
(acrescenta as colunas novas, como a operação de origem das devoluções) e, na aba "Premissas e
alíquotas", clique em **Aplicar aos anos 2027–2033** (aplica o IBS de teste de 0,1% em 2027–2028).
Não é preciso carregar as EFDs de novo.

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
- **O antivírus/TI perguntou sobre o Python acessando a rede:** é o servidor local do programa
  (endereço `127.0.0.1`, só dentro do computador).
