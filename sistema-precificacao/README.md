# Sistema de custeio e precificação para reciclagem

Implementação do documento *Modelo de precificação para operações de
reciclagem* (v1.1): custeio híbrido por lote + ABC + absorção gerencial +
margem de contribuição, com motor tributário parametrizável por regime e
escada de cinco preços.

## Estado atual

| Passo | Entrega | Situação |
|---|---|---|
| 1 | Arquitetura, stack e sequência | concluído |
| 2 | Modelo de dados, migrações e seeds | **concluído** |
| 3 | Motor de domínio + motor tributário + casos de aceite | **concluído** |
| 4 | API FastAPI | **concluído** |
| 5 | Frontend Next.js — Cadastros e Operações | **concluído** |
| 6 | Cotação, simulação e painel gerencial | **concluído** |

### Sistema completo

Os seis passos estão concluídos. A especificação que originou o sistema está em
[docs/especificacao.md](docs/especificacao.md).

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2
- **Banco:** PostgreSQL em produção, SQLite em desenvolvimento e testes
- **Frontend:** Next.js + TypeScript, Tailwind CSS,
  Radix UI, Recharts

## Arquitetura

```
LEIA-ME.txt         instruções em texto puro, dentro do pacote
INICIAR-*           instalador e inicializador: um clique, os dois papéis
instalador/         instalar.py (só biblioteca padrão) e montar-pacote.sh

frontend/           Next.js 15, Tailwind 4, Radix UI
├── app/            rotas dos módulos
├── components/     primitivos de UI e componentes de domínio
├── lib/            cliente da API, tipos e formatação pt-BR
└── out/            interface compilada e versionada, servida pelo backend

backend/app/
├── db/          base declarativa, tipos monetários e mixins de vigência
├── models/      39 tabelas: cadastro, operação, fiscal, comercial, governança
├── seeds/       dados de demonstração dos três regimes tributários
├── dominio/     massa, aquisição, ABC, conjuntos, capital, camadas, preços, memória
├── tributario/  resolução de regras por vigência, aplicação e regimes
├── aplicacao/   cotação versionada e demonstração executável
├── servicos/    ligação entre persistência e motor (parâmetros, lote, cotação)
└── api/         FastAPI: routers, schemas e mapeamento de erros
```

Princípios que o schema já sustenta:

1. **Nada de ponto flutuante em dinheiro.** Toda coluna monetária é
   `NUMERIC(18,6)` — há teste que falha se alguém introduzir `Float`.
2. **Nada é sobrescrito.** Parâmetros e regras são versionados por vigência;
   correção de evento entra como lançamento de ajuste com referência ao
   original; `auditoria` é append-only.
3. **Custo fixo rateia pela capacidade prática.** `atividade_taxa` guarda pool
   e capacidade separados; a ociosidade vai para `fechamento_mensal`, nunca
   para dentro da taxa.
4. **Crédito fiscal não presumido.** `requer_confirmacao_condicao` impede que
   crédito condicionado (ex.: Lei 15.394/2026) reduza custo antes da
   confirmação.
5. **Preço sempre com rótulo.** `cotacao_preco` tem uma linha por camada da
   escada, cada uma com sua visão de custo.

E o que o motor acrescenta:

6. **Toda fórmula é reproduzível.** Cada cálculo registra passo, fórmula,
   entradas, fonte e vigência; o preço pode ser refeito à mão a partir da
   exportação da cotação.
7. **Regra vencida bloqueia.** Uma única regra fora de vigência na data da
   operação impede a cotação definitiva — não existe cotação parcialmente
   definitiva.
8. **A mudança de faixa do Simples é calculada.** O sistema mostra a alíquota
   marginal real da venda, não a da faixa atual.

## Como usar

O sistema é **um programa só**. O servidor Python entrega a API e as telas no
mesmo endereço — não há dois processos para gerenciar nem Node.js no uso
diário.

### Para quem vai usar

Peça o arquivo `sistema-precificacao-reciclagem.zip` (ou gere-o com
`./instalador/montar-pacote.sh`), descompacte em qualquer pasta e:

1. Instale o **Python 3.11+** (no Windows, marque *Add Python to PATH*).
2. Clique duas vezes no arquivo do seu sistema:

   | Sistema | Arquivo |
   |---|---|
   | Windows | `INICIAR-Windows.bat` |
   | macOS | `INICIAR-Mac.command` |
   | Linux | `INICIAR-Linux.sh` |

Na primeira vez o instalador cria o ambiente, instala as bibliotecas, prepara o
banco e pergunta se deve carregar dados de exemplo. Nas seguintes, ele apenas
abre o sistema. O navegador abre sozinho em `http://localhost:8000`.

O passo a passo completo, escrito para quem não programa, está no
[manual em PDF](docs/manual-instalacao-e-primeiros-passos.pdf).

### Para desenvolver

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seeds.demo
.venv/bin/python -m pytest -q              # 87 testes
.venv/bin/uvicorn app.api.main:app --reload
```

As telas compiladas ficam versionadas em `frontend/out/` — é isso que permite
instalar sem Node.js. Para alterá-las:

```bash
cd frontend
npm install
cp .env.example .env.local     # aponta para localhost:8000/api
npm run dev                    # desenvolvimento em http://localhost:3000
npm run build                  # regenera frontend/out/, que vai versionado
```

## Documentação

- [Dicionário de dados](docs/dicionario-de-dados.md) — correspondência com a
  seção 10 da especificação, convenções de unidade e semântica das flags
  fiscais.
- [Motor de cálculo](docs/motor-de-calculo.md) — fórmulas implementadas,
  camadas de custo, resolução de regras fiscais e composição de `r` por
  regime.
- [API](docs/api.md) — endpoints, mapeamento de erros de domínio para HTTP e
  exemplos de chamada.
- [Frontend](docs/frontend.md) — estrutura das telas, decisões de interface e
  convenções de formatação.
- [Visualização de dados](docs/visualizacao.md) — paleta validada, formas de
  gráfico escolhidas e o que o validador de cor mudou no projeto.
- [Especificação](docs/especificacao.md) — o documento de requisitos original
  (v1.1), fonte de todas as regras implementadas.
- **[Manual de instalação e primeiros passos](docs/manual-instalacao-e-primeiros-passos.pdf)**
  (PDF) — como colocar o sistema no ar, ajustar a matriz tributária e começar
  a usar. Gerado por `docs/manual/gerar_manual.py`.

## Aviso

Os dados de demonstração são **exemplos**, não parâmetros da empresa. Todas as
regras tributárias das seeds nascem com status `PROVISORIA` e exigem validação
do responsável fiscal antes de apoiarem qualquer cotação definitiva.
