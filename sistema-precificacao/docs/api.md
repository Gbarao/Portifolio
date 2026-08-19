# API — Passo 4

FastAPI sobre o motor do Passo 3. Documentação interativa em `/docs`
(Swagger) e `/redoc`; esquema OpenAPI em `/openapi.json`.

```bash
cd backend
.venv/bin/uvicorn app.api.main:app --reload
```

## Princípios da API

1. **Bloqueio de negócio não é erro de servidor.** Balanço de massa aberto,
   regra fiscal vencida e dupla contagem retornam 409 ou 422 com corpo
   explicativo — nunca 500.
2. **Nenhum preço sem rótulo.** A escada devolve os cinco degraus, cada um com
   sua finalidade; quem escolhe qual apresentar é o cliente da API.
3. **Memória em toda saída relevante.** Respostas de custo e preço carregam os
   passos, fórmulas e fontes que os produziram.
4. **Decimais viajam como texto**, em precisão cheia. O arredondamento é de
   apresentação e fica com o cliente — arredondar no servidor quebraria a
   reprodutibilidade da memória.

## Mapeamento de erros

| Exceção de domínio | HTTP | Quando |
|---|---|---|
| `MassaInconsistenteError` | 409 | Balanço fora da tolerância no encerramento |
| `RegraFiscalIndisponivelError` | 409 | Sem regra vigente para a operação |
| `DuplaContagemError` | 409 | Custo em pool de atividade e lançamento direto |
| `DenominadorZeroError` | 422 | Quantidade ou capacidade zerada |
| `ParametroInvalidoError` | 422 | `r ≥ 100%`, RBT12 fora das faixas, VRL não positivo |
| `DadoObrigatorioAusenteError` | 422 | Lote sem balança, atividade sem taxa vigente |
| `RecursoNaoEncontrado` | 404 | Registro inexistente |

Corpo padrão de erro:

```json
{ "erro": "MassaInconsistenteError", "mensagem": "...", "bloqueante": true }
```

## Endpoints

### Cadastros
| Método | Rota | Observação |
|---|---|---|
| GET | `/unidades` | Paginado |
| GET | `/unidades/{id}/parametros?em=AAAA-MM-DD` | Parâmetros **vigentes na data**, não os mais recentes |
| GET/POST | `/materiais` | Filtros por família e tipo |
| GET | `/materiais/{id}` | |
| GET/POST | `/parceiros` | Filtro por papel |
| GET | `/parceiros/{id}` | |

### Operações
| Método | Rota | Observação |
|---|---|---|
| GET/POST | `/lotes` | |
| GET | `/lotes/{id}` | |
| POST | `/lotes/{id}/eventos-balanca` | Peso líquido é derivado, nunca informado solto |
| POST | `/lotes/{id}/eventos-qualidade` | Define a quantidade aceita |
| POST | `/lotes/{id}/saidas` | |
| POST | `/lotes/{id}/perdas` | Perda anormal marcada como fora do custo-padrão |
| GET | `/lotes/{id}/balanco?bloquear=true` | Sem bloquear, devolve a divergência para a tela mostrar |
| GET | `/lotes/{id}/resultado` | Custo por camada + memória |
| POST | `/lotes/{id}/encerrar` | 409 se a massa não fecha; libera com `justificativa` e `aprovado_por` |

### Motor tributário
| Método | Rota | Observação |
|---|---|---|
| GET | `/tributario/regras` | Filtros por regime, tributo, operação e vigência |
| POST | `/tributario/regras` | **Sempre nasce `PROVISORIA`** — não há caminho para criar validada |
| POST | `/tributario/regras/{id}/validar` | Registra quem validou e quando |
| POST | `/tributario/deducoes` | Calcula `r` com detalhamento por tributo |
| POST | `/tributario/simples/aliquota-efetiva` | Com opção de segregar o ICMS |
| POST | `/tributario/simples/mudanca-faixa` | O alerta crítico da seção 7.7-C |

### Cotações e simulações
| Método | Rota | Observação |
|---|---|---|
| POST | `/cotacoes/simular` | Calcula sem persistir — a tela de trabalho do comercial |
| POST | `/cotacoes` | Persiste versão, preços por camada e memória |
| GET | `/cotacoes/{id}` | Recalcula a partir das **premissas congeladas** |
| POST | `/cotacoes/{id}/versoes` | Nova versão; a anterior permanece intacta |
| POST | `/simulacoes/preco-maximo-compra` | `r` vem do motor fiscal se o contexto for informado |

## Exemplo: simulação de cotação

```bash
curl -X POST localhost:8000/cotacoes/simular -H 'Content-Type: application/json' -d '{
  "contexto": {"data_operacao":"2026-03-10","tipo_operacao":"VENDA",
               "regime_tributario":"LUCRO_REAL","uf_origem":"SP","uf_destino":"SP"},
  "quantidade_kg":"10000","margem_alvo":"0.12","margem_contribuicao_minima":"0.05",
  "preco_proposto":"0.72",
  "componentes_custo":[
    {"nome":"Aquisicao","valor":"5000","camada_minima":"CAIXA"},
    {"nome":"Transformacao","valor":"800","camada_minima":"CONTRIBUICAO"},
    {"nome":"Estrutura","valor":"1200","camada_minima":"OPERACIONAL","e_desembolso":false},
    {"nome":"Administrativas","valor":"900","camada_minima":"SUSTENTAVEL",
     "visoes":["GERENCIAL_COMPLETO"]}
  ]}'
```

Resposta (resumida):

```
status fiscal: PROVISORIA | permite cotação definitiva: false
r = 0,0925

camada                custo     preço   margem
CAIXA                0,5000    0,5510     0,0%
CONTRIBUICAO         0,5800    0,6728     5,0%
OPERACIONAL          0,7000    0,7713     0,0%
SUSTENTAVEL          0,7900    0,8705     0,0%
ALVO                 0,7900    0,9892    12,0%

proposta R$ 0,72  →  ENTRE_SUSTENTAVEL_E_CONTRIBUICAO
alçada: Controladoria e diretoria, com prazo definido
concessão: R$ 2.692,31
21 passos na memória de cálculo
```

O `permite_cotacao_definitiva: false` está correto: as regras das seeds são
provisórias. Depois de `POST /tributario/regras/{id}/validar` em cada uma, o
mesmo cálculo passa a autorizar cotação definitiva.
