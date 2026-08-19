# Frontend — Passo 5

Next.js 15 (App Router) + TypeScript + Tailwind CSS 4 + Radix UI, consumindo a
API do Passo 4.

```bash
cd frontend
npm install
cp .env.example .env.local     # NEXT_PUBLIC_API_URL
npm run dev                    # http://localhost:3000
```

O backend precisa estar no ar em `http://localhost:8000`. Se não estiver, as
telas mostram um aviso com o comando para subi-lo — não uma tela quebrada.

## Estrutura

```
frontend/
├── app/                   rotas (App Router)
│   ├── layout.tsx         casca: navegação lateral + topo
│   ├── page.tsx           painel de módulos
│   ├── cadastros/         materiais, parceiros, unidades e parâmetros
│   ├── operacoes/         lotes e resultado do lote
│   └── tributario/        matriz de regras e simulador do Simples
├── components/
│   ├── ui/                primitivos: cartão, botão, tabela, campo, distintivo
│   ├── layout/            navegação, cabeçalho de página, tema
│   └── dominio/           badges de status, alertas, memória de cálculo
└── lib/                   cliente da API, tipos e formatação pt-BR
```

## Decisões de interface

**Cor nunca aparece sozinha.** Todo status tem ícone e texto além da cor —
`StatusDadoBadge`, `StatusFiscalBadge` e `CamadaBadge` sempre trazem o rótulo
escrito. Daltonismo e impressão em preto e branco continuam legíveis.

**Decimais chegam como string e são formatados no cliente.** A API envia
precisão cheia de propósito; `lib/formato.ts` decide as casas de apresentação:
4 para preço unitário (R$/kg), 2 para valores, tonelada com zeros à direita
removidos (`12 t`, não `12,000 t`).

**Bloqueio de negócio é explicado, não escondido.** `ErroDeCarregamento`
distingue três casos: API fora do ar (mostra o comando para subir), bloqueio de
regra de negócio 409/422 (mostra a causa e explica que é a especificação
funcionando) e falha técnica.

**A memória de cálculo é componente de primeira classe.** Cada passo abre
mostrando fórmula, entradas nomeadas, fonte, vigência da regra e status do
dado. Há exportação em JSON — é o que sustenta o caso de aceitação 11.

## Telas entregues

| Rota | Conteúdo |
|---|---|
| `/` | Painel dos cinco módulos e as três regras que o sistema não relaxa |
| `/cadastros/materiais` | Rendimento-padrão, perdas, NCM e status do dado |
| `/cadastros/parceiros` | Regime fiscal, condição de contribuinte, prazos, inadimplência |
| `/cadastros/unidades` | Parâmetros vigentes por unidade, com data de vigência |
| `/operacoes/lotes` | Lista de lotes por status |
| `/operacoes/lotes/[id]` | Balanço de massa, composição do custo e memória completa |
| `/tributario/regras` | Matriz com efeito econômico de cada regra e status |
| `/tributario/simples` | Simulador de mudança de faixa da RBT12 |

Cotações e Painel gerencial aparecem na navegação marcados como Passo 6.

## Tema

Claro e escuro via tokens em `app/globals.css`. O padrão segue
`prefers-color-scheme`; o alternador no topo grava a escolha em
`localStorage` e aplica `data-tema` na raiz.
