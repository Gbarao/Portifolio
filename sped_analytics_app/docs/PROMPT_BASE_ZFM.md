# Prompt-base — versão customizada para a ZFM

Como usar: abra uma sessão nova do Claude Code com o repositório (ou o zip descompactado) disponível, anexe também o arquivo
`docs/ESPECIFICACAO_COMPLETA.md`, e cole o texto abaixo. Preencha os campos `[PREENCHER]` antes de enviar; o que não for
preenchido o assistente deve perguntar, não presumir.

---

## Texto do prompt

Você vai criar uma **versão customizada para a ZFM (Zona Franca de Manaus)** de um sistema que já existe e funciona.

### 1. Ponto de partida (não reescrever do zero)
- Código-base: pasta `sped_analytics_app/` deste repositório (versão 2.3.1). Leia `docs/ESPECIFICACAO_COMPLETA.md` inteiro antes de qualquer alteração; ele descreve arquitetura, regras de consolidação, telas, API, testes, desempenho e limites conhecidos.
- Trate o sistema atual como a base e **reaproveite**: importação em streaming para Parquet + DuckDB, motor de consolidação em SQL, tabelas agregadas, relatório dinâmico, busca por fornecedor, Bloco M, telas "como estão", auditoria, exportação para Excel, interface React ajustável à tela, instaladores.
- Crie a versão ZFM em uma **branch/pasta própria** (`[PREENCHER: nome]`), sem quebrar a versão atual. Os 138 testes atuais devem continuar passando, exceto os que forem substituídos por equivalentes mais específicos (diga quais e por quê).

### 2. Princípios que não podem ser perdidos
1. 100% local, sem enviar dados para fora; interface só em `127.0.0.1`.
2. **Nenhum valor contado duas vezes e nenhum crédito perdido.** Qualquer regra nova de consolidação precisa de teste que prove o fechamento (total na base = total bruto do arquivo de origem).
3. Desempenho: relatórios respondem por tabelas agregadas; consultas pesadas em duas fases; medir antes e depois com volume grande (`tests/perf_gen.py`) e registrar os números.
4. O que o usuário vê "como está nos arquivos" (telas SPED Fiscal / EFD-Contribuições) nunca é alterado por regra de negócio.
5. Alterou a lógica ou o esquema da fato → incrementar `FATO_VERSION`; alterou `frontend/src` → rodar `npm run build` e conferir no navegador com Playwright (sem erros no console, captura de tela).
6. Verificar antes de afirmar: se faltar informação (regra fiscal, leiaute, código), **dizer "informação insuficiente"** e perguntar; não inventar CFOP, CST, benefício, alíquota ou prazo.

### 3. Contexto da ZFM neste projeto
[PREENCHER — o que a empresa precisa. Exemplos de pontos a definir, apagar os que não se aplicam:]
- Perfil da empresa: `[indústria / comércio / outro]`; regime; filiais dentro e fora da ZFM: `[ ]`.
- Quais obrigações entram: SPED Fiscal, EFD-Contribuições, outras (`[PREENCHER]`). Há arquivos da SUFRAMA ou de outros órgãos a importar? `[PREENCHER]`
- Operações a cobrir: **só entradas** (como hoje) ou também **saídas/remessas/retornos/devoluções**? `[PREENCHER]`
- Benefícios e tratamentos específicos que a análise precisa evidenciar (isenções, suspensões, alíquota zero, créditos, ajustes de apuração): `[PREENCHER com a lista e a base legal que você usa]`.
- CFOPs, CSTs, códigos de ajuste (C197/E111) e naturezas de crédito relevantes: `[PREENCHER]` — o assistente não deve presumir esta lista.
- Relatórios/saídas que o time fiscal usa hoje e que a ferramenta deve reproduzir: `[PREENCHER, com exemplos/planilhas]`.
- Volume esperado (arquivos, empresas, anos): `[PREENCHER]`.

### 4. Fatos do sistema atual que provavelmente tocam a ZFM (conferir no código antes de usar)
- O sistema consolida **apenas entradas** (IND_OPER = 0). Saídas só existem nas telas "como estão".
- Devoluções de compra não são abatidas; C197 (ajustes por documento) é carregado mas não entra em valor algum; E111/E116 só aparecem na tela "como está".
- O campo **SUFRAMA** consta nos leiautes (0000/0150 do SPED Fiscal; 0000/0140/0150 da EFD-Contribuições) e está disponível nas telas "como estão", mas **não é carregado na tabela fato nem usado em análises**.
- A natureza da base de crédito é derivada do CFOP por uma tabela padrão (`ref_cfop_nat_bc_cred`) que precisa de revisão para a realidade da empresa.
- Os testes usam dados sintéticos; leiautes reais fora do padrão ainda não foram observados.

### 5. O que entregar (nesta ordem)
1. **Levantamento e plano:** liste, a partir da seção 3, cada mudança necessária, indicando se é (a) configuração, (b) nova coluna/regra na consolidação, (c) novo campo lido dos TXT, (d) nova tela/relatório, (e) nova verificação de auditoria. Aponte riscos e perguntas em aberto. **Pare e espere minha confirmação** antes de implementar.
2. **Implementação em etapas pequenas**, cada uma com: testes novos (dados sintéticos no leiaute oficial, inclusive casos em que os arquivos não são espelhos), suíte completa verde, medição de desempenho quando mexer em consulta, atualização de `README.md`, `LEIA-ME.txt` e `docs/ESPECIFICACAO_COMPLETA.md`.
3. **Pacote final:** zip pronto (mesmo padrão do atual), testado em pasta limpa (`instalar` + testes + abrir a interface + exportar um Excel), e um resumo do que mudou, do que ficou de fora e do que precisa de validação por especialista fiscal.

### 6. Regras de trabalho
- Resposta objetiva, sem rodeios; relate falhas e itens não concluídos como estão.
- Não faça commit nem PR sem eu pedir; trabalhe na branch indicada em `[PREENCHER]`.
- Dados de usuário (`data/`) nunca entram no git nem em exemplos.
- Dúvida que muda o resultado fiscal: pergunte. Dúvida de implementação: escolha o padrão do sistema atual e registre a decisão.

---

## Checklist para o usuário antes de enviar
- [ ] Preenchi a seção 3 (mesmo que parcialmente).
- [ ] Anexei `docs/ESPECIFICACAO_COMPLETA.md` e deixei o repositório/zip acessível.
- [ ] Tenho 2 ou 3 arquivos SPED reais **anonimizados** (ou os meus relatórios atuais) para validar as regras novas.
- [ ] Defini quem valida o resultado fiscal (o assistente implementa e testa; a validação da regra é de especialista).
