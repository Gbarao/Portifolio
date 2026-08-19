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
| 5 | Frontend Next.js — Cadastros e Operações | pendente |
| 6 | Cotação, simulação e painel gerencial | pendente |

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic 2
- **Banco:** PostgreSQL em produção, SQLite em desenvolvimento e testes
- **Frontend (a partir do Passo 5):** Next.js + TypeScript, Tailwind CSS,
  Radix UI, Recharts

## Arquitetura

```
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

## Rodando localmente

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

cp .env.example .env          # ajuste DATABASE_URL se for usar PostgreSQL
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seeds.demo   # dados de demonstração
.venv/bin/python -m pytest -q        # 75 testes
.venv/bin/python -m app.aplicacao.demonstracao   # lote completo nos 3 regimes
.venv/bin/uvicorn app.api.main:app --reload      # API em http://localhost:8000/docs
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

## Aviso

Os dados de demonstração são **exemplos**, não parâmetros da empresa. Todas as
regras tributárias das seeds nascem com status `PROVISORIA` e exigem validação
do responsável fiscal antes de apoiarem qualquer cotação definitiva.
