# Consulta em lote — Optantes do Simples Nacional

Ferramenta de linha de comando para verificar, em lote, se CNPJs são optantes
pelo Simples Nacional / SIMEI.

Fonte online: `https://www8.receita.fazenda.gov.br/simplesnacional/aplicacoes.aspx?id=21`
(tela "Consulta Optantes", sem captcha no layout analisado).

---

## Antes de rodar: leia isto

Três decisões de projeto determinam a eficiência da solução.

**1. Uma consulta por empresa, não por estabelecimento.**
A própria tela de resultado informa: *"A opção pelo Simples Nacional e/ou SIMEI
abrange todos os estabelecimentos da empresa"*. Logo, filiais com a mesma raiz
(8 primeiros dígitos) não precisam de consulta própria — herdam o resultado.
Em bases corporativas isso costuma cortar de 20% a 60% das requisições.
Ativado por padrão (`--sem-agrupar` desliga).

**2. Validação de CNPJ antes da rede.**
Dígitos verificadores são conferidos localmente. CNPJ malformado sai com
status `CNPJ_INVALIDO` sem gastar requisição.

**3. Para milhares de CNPJs, o caminho mais rápido não é o site.**
A Receita Federal publica mensalmente, nos Dados Abertos do CNPJ, o arquivo
`Simples` com a opção pelo Simples/SIMEI de **todas** as empresas do país.
Baixar esse arquivo uma vez e cruzar localmente resolve 50 mil CNPJs em
segundos, sem nenhuma requisição ao site (subcomando `offline`).

Regra prática:

| Situação | Modo |
|---|---|
| Base grande, tolera defasagem de até 1 mês | `offline` (Dados Abertos) |
| Poucas centenas, precisa da posição de hoje | `consultar` (site) |
| Base grande + posição de hoje | `offline` para varrer, `consultar` só nos casos relevantes |

---

## Instalação

```bash
pip install -r requirements.txt          # httpx, beautifulsoup4, lxml
pip install openpyxl                     # opcional: entrada/saída .xlsx
```

## Uso

### 1. Diagnóstico (execute isto primeiro)

Mostra o formulário que a ferramenta detectou na página e, opcionalmente,
executa uma consulta real:

```bash
python -m consulta_simples diagnostico --cnpj 56228356000131
```

Saída esperada: a URL de `action`, o `name` do campo de CNPJ, os campos ocultos
(`__VIEWSTATE` e afins) e o resultado interpretado. Se isso funcionar, o lote
funciona.

### 2. Consulta em lote (site da Receita)

```bash
python -m consulta_simples consultar exemplos/base_clientes.csv \
    --saida resultado.xlsx \
    --concorrencia 4
```

Entrada aceita `.csv`, `.txt` (um por linha) ou `.xlsx`. A coluna de CNPJ é
detectada automaticamente (procura uma coluna com "cnpj" no nome; se não
houver, escolhe a coluna cujo conteúdo mais parece CNPJ). Use `--coluna` para
fixar.

Opções relevantes:

| Flag | Efeito |
|---|---|
| `-c, --concorrencia` | requisições simultâneas (padrão 4) |
| `--intervalo` | jitter aleatório entre requisições, em segundos |
| `--db` | caminho do cache SQLite (padrão `cache/consultas.sqlite`) |
| `--limite N` | processa só os N primeiros — use para um teste piloto |
| `--campo-cnpj` | força o `name` do input, caso a detecção falhe |
| `--sem-agrupar` | consulta cada estabelecimento individualmente |
| `--matriz` | consulta o CNPJ da matriz calculado a partir da raiz |
| `--modo browser` | usa Playwright (lento; só se o modo HTTP falhar) |

### 3. Cruzamento offline (Dados Abertos da RFB)

```bash
python -m consulta_simples offline exemplos/base_clientes.csv Simples.zip \
    --saida resultado_offline.csv
```

`Simples.zip` é o arquivo publicado pela Receita Federal no portal de Dados
Abertos do CNPJ. O leitor **detecta as colunas pelo conteúdo** (raiz de 8
dígitos, colunas `S`/`N`, datas `AAAAMMDD`) em vez de assumir uma ordem fixa;
se o layout mudar, a execução falha com mensagem explícita em vez de produzir
resultado errado em silêncio.

---

## Saída

Uma linha por CNPJ de entrada:

```
cnpj;cnpj_formatado;raiz;chave_consultada;status;optante_simples;situacao_simples;
optante_simei;situacao_simei;nome_empresarial;data_consulta;mensagem
```

`chave_consultada` mostra qual CNPJ foi efetivamente enviado ao site — para
filiais, é o CNPJ da mesma raiz que foi consultado.

Valores de `status`:

| Status | Significado | Reexecutar resolve? |
|---|---|---|
| `OK` | resultado extraído | — |
| `CNPJ_INVALIDO` | DV ou tamanho inválidos | não, corrija a base |
| `ERRO_REDE` | timeout, 5xx, 429 após as retentativas | sim |
| `ERRO_FORMULARIO` | página sem o formulário esperado | não, rode `diagnostico` |
| `SEM_RESULTADO` | resposta sem os rótulos de situação (ver `mensagem`) | talvez |

## Reexecução e retomada

Todo resultado vai para um cache SQLite indexado por CNPJ. Reexecutar o mesmo
comando:

- **não** repete as consultas já com status `OK`;
- **repete** as que ficaram em erro.

Ou seja, um lote de 50 mil CNPJs interrompido na metade continua de onde parou.
Para forçar uma reconsulta completa, apague o arquivo do `--db`.

## Arquitetura

```
consulta_simples/
  cnpj.py           validação de DV, raiz, matriz, formatação
  scraper.py        cliente HTTP: descobre o formulário e faz o POST
  browser.py        fallback com Playwright
  parser.py         HTML do resultado -> dados estruturados
  storage.py        cache SQLite (idempotência e retomada)
  runner.py         deduplicação, concorrência, montagem da saída
  io_tabular.py     leitura/escrita CSV, TXT, XLSX
  dados_abertos.py  cruzamento offline com o arquivo Simples da RFB
  cli.py            linha de comando
```

O ponto central do `scraper.py`: **nada do formulário é fixado em código**. A
ferramenta baixa a página, localiza o `<form>`, coleta todos os campos ocultos
(a página é ASP.NET WebForms, que exige `__VIEWSTATE` no POST), identifica o
campo de CNPJ e só então envia. Se a Receita renomear um campo, a detecção
acompanha. Por padrão o formulário é recarregado a cada consulta, porque o
`__VIEWSTATE` do WebForms costuma ser de uso único.

## Testes

```bash
python -m pytest
```

22 testes, todos offline. `tests/servidor_falso.py` sobe um servidor HTTP local
que imita o comportamento do WebForms (exige `__VIEWSTATE` no POST), o que
permite exercitar o fluxo completo — GET do formulário, POST, parse, cache,
saída — sem tocar no site da Receita.

## Limitações e pontos a confirmar

Registrados explicitamente, para não serem confundidos com fatos verificados:

1. **O site não pôde ser acessado durante o desenvolvimento** (a política de
   rede do ambiente bloqueou `www8.receita.fazenda.gov.br`). Os nomes dos
   campos do formulário **não foram verificados ao vivo** — daí a detecção
   automática e o subcomando `diagnostico`, que é o primeiro passo obrigatório
   no seu ambiente.
2. O parser foi construído sobre os rótulos visíveis na tela de resultado
   ("Situação no Simples Nacional:", "Situação no SIMEI:", "Nome Empresarial:",
   "CNPJ:", "Data da consulta:"). Textos de erro do site (CNPJ inexistente,
   indisponibilidade) **não são conhecidos**: caem em `SEM_RESULTADO`, com um
   trecho da página gravado em `mensagem` para inspeção.
3. Não há limite de requisições publicado para essa consulta. O padrão de
   concorrência 4 é conservador por escolha, não por medida. Comece com
   `--limite 50`, observe, e ajuste.
4. A validação aceita CNPJ alfanumérico (valor do caractere = `ord(c) - 48`).
   Se a sua base ainda for só numérica, isso é indiferente; se já houver CNPJ
   alfanumérico, confirme o comportamento com `--limite` antes do lote inteiro.
   `--sem-validacao` desliga a checagem.
5. O modo `offline` reflete a data de extração do arquivo da RFB, não a posição
   de hoje. Para prova documental, use o modo online.
