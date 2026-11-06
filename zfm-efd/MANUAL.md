# Manual do usuário — Programa ZFM × Reforma Tributária

> Versão da Fase 1. As partes marcadas como *(em construção)* chegam nas próximas fases.

## 1. O que o programa faz

O programa lê as EFD ICMS/IPI e EFD Contribuições de 2026 das empresas do grupo no Amazonas,
confere se os arquivos estão completos e íntegros, calcula o benefício atual da Zona Franca de
Manaus (IPI, PIS/COFINS e ICMS) e simula esse benefício depois da Reforma Tributária (CBS, IBS e
IPI residual). Tudo roda **só no seu computador**: nenhum dado é enviado para a internet.

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
  Verde *OK* = as duas EFDs existem. Vermelho = falta arquivo (a célula diz qual).
  A EFD Contribuições é procurada pela empresa (raiz do CNPJ), porque é entregue pela matriz.
- **Q2 – Integridade:** compara a quantidade de registros lidos com a informada no próprio arquivo
  (registros 9900 e 9999). Divergência indica arquivo incompleto ou alterado.
- **Avisos de leitura:** linhas com formato diferente do esperado (o arquivo foi carregado,
  mas convém conferir).

**Seletor de empresas (barra lateral):** marcado *Todas as empresas (consolidado)* por padrão.
Desmarque para escolher uma ou várias empresas. Vale para todas as telas.

## 6. Parâmetros, resultados e Excel *(em construção)*

Tabelas de parâmetros, telas de Saídas, Entradas, Apurações, Benefício atual, Simulação e
Exportação para o Excel entram nas Fases 2 a 7.

## 7. Quando der erro

- **Erro na janela preta do `iniciar.bat`:** selecione o texto da janela, copie e envie ao
  Claude Code. A instalação também grava um arquivo em `data\logs\instalacao_*.log`.
- **Erro na tela do programa:** a mensagem indica o arquivo `data\logs\zfm.log`
  (dentro da pasta do programa). Envie esse arquivo ao Claude Code.
- **Nunca envie EFDs reais na conversa.** Só a mensagem de erro e o arquivo de log.
- **Testes automáticos:** duplo clique em `testar.bat` mostra quantos testes passaram e falharam.

## 8. Perguntas frequentes

- **Os dados saem do meu computador?** Não. O programa só aceita conexões do próprio
  computador (`127.0.0.1`) e não usa internet depois da instalação das bibliotecas.
- **Onde ficam os dados?** Na pasta `data` dentro da pasta do programa (banco `zfm.duckdb` e logs).
- **Posso abrir duas janelas do programa?** Não ao mesmo tempo: feche a janela preta antiga antes.
- **O antivírus/TI perguntou sobre o Python acessando a rede:** é o servidor local do programa
  (endereço `127.0.0.1`, só dentro do computador).
