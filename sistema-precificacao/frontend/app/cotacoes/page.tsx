"use client";

/**
 * Cotacao e simulacao.
 *
 * A tela de trabalho do comercial: muda premissa, ve o preco mudar. Nada e
 * persistido enquanto o usuario nao decide salvar -- e o motor de calculo do
 * backend que responde, nunca uma conta refeita no navegador.
 */

import * as React from "react";

import {
  Alerta,
  Indicador,
  StatusFiscalBadge,
} from "@/components/dominio/indicadores";
import {
  BarraComposicao,
  EscadaPrecos,
  FiguraHeroi,
  type DegrauEscada,
  type ParteComposicao,
} from "@/components/dominio/graficos";
import { MemoriaCalculo } from "@/components/dominio/memoria-calculo";
import { CabecalhoPagina } from "@/components/layout/pagina";
import {
  Botao,
  Campo,
  Cartao,
  CartaoCabecalho,
  CartaoCorpo,
  Distintivo,
  Entrada,
  LinhaTabela,
  Selecao,
  Tabela,
  Td,
  Th,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import { moeda, percentual, precoUnitario } from "@/lib/formato";
import type { CamadaPreco, CotacaoCalculada, PrecoMaximoCompra } from "@/lib/tipos";

const CAMADAS_ESCADA: CamadaPreco[] = [
  "CAIXA",
  "CONTRIBUICAO",
  "OPERACIONAL",
  "SUSTENTAVEL",
  "ALVO",
];

interface Formulario {
  regime: string;
  quantidade_kg: string;
  aquisicao: string;
  transformacao: string;
  estrutura: string;
  despesas: string;
  margem_alvo: string;
  margem_contribuicao: string;
  preco_proposto: string;
  preco_mercado: string;
  rendimento: string;
}

const INICIAL: Formulario = {
  regime: "LUCRO_REAL",
  quantidade_kg: "10000",
  aquisicao: "5000",
  transformacao: "800",
  estrutura: "1200",
  despesas: "900",
  margem_alvo: "0.12",
  margem_contribuicao: "0.05",
  preco_proposto: "0.80",
  preco_mercado: "0.95",
  rendimento: "0.90",
};

/** Monta o corpo da simulacao a partir do formulario, com um fator opcional. */
function corpoSimulacao(f: Formulario, fatorCusto = 1, margemAlvo?: string) {
  const escalar = (valor: string) => String(Number(valor) * fatorCusto);
  return {
    contexto: {
      data_operacao: new Date().toISOString().slice(0, 10),
      tipo_operacao: "VENDA",
      regime_tributario: f.regime,
      uf_origem: "SP",
      uf_destino: "SP",
    },
    quantidade_kg: f.quantidade_kg,
    margem_alvo: margemAlvo ?? f.margem_alvo,
    margem_contribuicao_minima: f.margem_contribuicao,
    preco_mercado: f.preco_mercado || null,
    componentes_custo: [
      { nome: "Aquisição", valor: escalar(f.aquisicao), camada_minima: "CAIXA" },
      {
        nome: "Transformação",
        valor: escalar(f.transformacao),
        camada_minima: "CONTRIBUICAO",
      },
      {
        nome: "Estrutura produtiva",
        valor: escalar(f.estrutura),
        camada_minima: "OPERACIONAL",
        e_desembolso: false,
      },
      {
        nome: "Despesas administrativas",
        valor: escalar(f.despesas),
        camada_minima: "SUSTENTAVEL",
        visoes: ["GERENCIAL_COMPLETO"],
      },
    ],
    preco_proposto: f.preco_proposto || null,
  };
}

interface Cenario {
  nome: string;
  descricao: string;
  precoAlvo: number;
  margem: number;
  base?: boolean;
}

export default function PaginaCotacoes() {
  const [formulario, setFormulario] = React.useState<Formulario>(INICIAL);
  const [resultado, setResultado] = React.useState<CotacaoCalculada | null>(null);
  const [cenarios, setCenarios] = React.useState<Cenario[]>([]);
  const [precoMaximo, setPrecoMaximo] = React.useState<PrecoMaximoCompra | null>(null);
  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(false);

  const campo = (nome: keyof Formulario) => ({
    value: formulario[nome],
    onChange: (
      evento: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => setFormulario((f) => ({ ...f, [nome]: evento.target.value })),
  });

  async function calcular(evento?: React.FormEvent) {
    evento?.preventDefault();
    setCarregando(true);
    setErro(null);

    try {
      // Os cenarios da secao 14 sao calculados pelo motor, um por chamada:
      // recalcular no navegador produziria numeros que ninguem pode auditar.
      const [base, otimista, estressado, equilibrio] = await Promise.all([
        api.post<CotacaoCalculada>("/cotacoes/simular", corpoSimulacao(formulario)),
        api.post<CotacaoCalculada>("/cotacoes/simular", corpoSimulacao(formulario, 0.9)),
        api.post<CotacaoCalculada>("/cotacoes/simular", corpoSimulacao(formulario, 1.15)),
        api.post<CotacaoCalculada>(
          "/cotacoes/simular",
          corpoSimulacao(formulario, 1, "0"),
        ),
      ]);

      setResultado(base);

      const alvoDe = (c: CotacaoCalculada) =>
        Number(c.precos.find((p) => p.camada === "ALVO")?.preco_unitario ?? 0);
      const margemDe = (c: CotacaoCalculada) =>
        Number(c.precos.find((p) => p.camada === "ALVO")?.margem_percentual ?? 0);

      setCenarios([
        {
          nome: "Base",
          descricao: "Premissas informadas",
          precoAlvo: alvoDe(base),
          margem: margemDe(base),
          base: true,
        },
        {
          nome: "Otimista",
          descricao: "Custos 10% menores",
          precoAlvo: alvoDe(otimista),
          margem: margemDe(otimista),
        },
        {
          nome: "Estressado",
          descricao: "Custos 15% maiores",
          precoAlvo: alvoDe(estressado),
          margem: margemDe(estressado),
        },
        {
          nome: "Equilíbrio",
          descricao: "Margem-alvo zerada",
          precoAlvo: alvoDe(equilibrio),
          margem: margemDe(equilibrio),
        },
      ]);

      const demaisCustos =
        Number(formulario.transformacao) +
        Number(formulario.estrutura) +
        Number(formulario.despesas);

      setPrecoMaximo(
        await api.post<PrecoMaximoCompra>("/simulacoes/preco-maximo-compra", {
          preco_venda_unitario: formulario.preco_mercado || formulario.preco_proposto,
          quantidade_vendavel: String(
            Number(formulario.quantidade_kg) * Number(formulario.rendimento),
          ),
          quantidade_aceita_esperada: formulario.quantidade_kg,
          demais_custos: String(demaisCustos),
          margem_alvo: formulario.margem_alvo,
          contexto: corpoSimulacao(formulario).contexto,
        }),
      );
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
      setResultado(null);
    } finally {
      setCarregando(false);
    }
  }

  React.useEffect(() => {
    void calcular();
    // Calcula uma vez ao abrir, com as premissas iniciais.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const degraus: DegrauEscada[] = React.useMemo(() => {
    if (!resultado) return [];
    return CAMADAS_ESCADA.map((camada) => {
      const degrau = resultado.precos.find((p) => p.camada === camada);
      return {
        camada,
        preco: degrau?.preco_unitario ?? "0",
        custo: degrau?.custo_unitario ?? "0",
        margem: degrau?.margem_percentual ?? "0",
        finalidade: degrau?.finalidade ?? "",
      };
    });
  }, [resultado]);

  /**
   * Partes do preco-alvo, na mesma rampa da escada: cada camada acrescenta
   * um pedaco, e o ultimo pedaco e o que a margem e as deducoes somam.
   */
  const partesPreco: ParteComposicao[] = React.useMemo(() => {
    if (!resultado) return [];
    const custo = (camada: string) => Number(resultado.custo_por_camada[camada] ?? 0);
    const alvo = Number(
      resultado.precos.find((p) => p.camada === "ALVO")?.preco_unitario ?? 0,
    );
    const sustentavel = custo("SUSTENTAVEL");

    return [
      {
        rotulo: "Aquisição",
        valor: custo("CAIXA"),
        cor: "var(--camada-caixa)",
      },
      {
        rotulo: "Transformação",
        valor: custo("CONTRIBUICAO") - custo("CAIXA"),
        cor: "var(--camada-contribuicao)",
      },
      {
        rotulo: "Estrutura produtiva",
        valor: custo("OPERACIONAL") - custo("CONTRIBUICAO"),
        cor: "var(--camada-operacional)",
      },
      {
        rotulo: "Despesas e capital",
        valor: sustentavel - custo("OPERACIONAL"),
        cor: "var(--camada-sustentavel)",
      },
      {
        rotulo: "Margem-alvo e deduções",
        valor: alvo - sustentavel,
        cor: "var(--camada-alvo)",
      },
    ];
  }, [resultado]);

  const avaliacao = resultado?.avaliacao_proposta ?? null;
  const precoAlvo = degraus.find((d) => d.camada === "ALVO")?.preco;

  return (
    <>
      <CabecalhoPagina
        titulo="Cotação e simulação"
        descricao="A escada de preços, a alçada necessária para a proposta e os cenários obrigatórios — tudo calculado pelo motor, com memória exportável."
        acoes={
          <Botao onClick={() => calcular()} disabled={carregando}>
            {carregando ? "Calculando…" : "Recalcular"}
          </Botao>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[20rem_1fr]">
        {/* ---------------------------------------------------- premissas */}
        <Cartao className="h-fit xl:sticky xl:top-20">
          <CartaoCabecalho
            titulo="Premissas"
            descricao="Alterar qualquer campo e recalcular gera uma nova versão."
          />
          <CartaoCorpo>
            <form onSubmit={calcular} className="space-y-4">
              <Campo rotulo="Regime tributário">
                <Selecao {...campo("regime")}>
                  <option value="LUCRO_REAL">Lucro Real</option>
                  <option value="LUCRO_PRESUMIDO">Lucro Presumido</option>
                  <option value="SIMPLES_NACIONAL">Simples Nacional</option>
                </Selecao>
              </Campo>

              <Campo rotulo="Quantidade (kg)">
                <Entrada inputMode="decimal" {...campo("quantidade_kg")} />
              </Campo>

              <fieldset className="space-y-3 rounded-lg border border-borda p-3">
                <legend className="px-1 text-xs font-medium tracking-wide text-texto-tenue uppercase">
                  Custos do lote (R$)
                </legend>
                <Campo rotulo="Aquisição" dica="Entra já no preço de caixa">
                  <Entrada inputMode="decimal" {...campo("aquisicao")} />
                </Campo>
                <Campo rotulo="Transformação" dica="ABC: triagem, prensagem">
                  <Entrada inputMode="decimal" {...campo("transformacao")} />
                </Campo>
                <Campo rotulo="Estrutura produtiva" dica="Não é desembolso">
                  <Entrada inputMode="decimal" {...campo("estrutura")} />
                </Campo>
                <Campo
                  rotulo="Despesas administrativas"
                  dica="Fora do custo contábil do estoque"
                >
                  <Entrada inputMode="decimal" {...campo("despesas")} />
                </Campo>
              </fieldset>

              <Campo rotulo="Margem-alvo" dica="Fração: 0,12 = 12%">
                <Entrada inputMode="decimal" {...campo("margem_alvo")} />
              </Campo>
              <Campo rotulo="Contribuição mínima">
                <Entrada inputMode="decimal" {...campo("margem_contribuicao")} />
              </Campo>
              <Campo rotulo="Preço proposto (R$/kg)" dica="Para avaliar a alçada">
                <Entrada inputMode="decimal" {...campo("preco_proposto")} />
              </Campo>
              <Campo rotulo="Preço de mercado (R$/kg)">
                <Entrada inputMode="decimal" {...campo("preco_mercado")} />
              </Campo>
              <Campo
                rotulo="Rendimento esperado"
                dica="Usado no preço máximo de compra"
              >
                <Entrada inputMode="decimal" {...campo("rendimento")} />
              </Campo>

              <Botao type="submit" disabled={carregando} className="w-full">
                {carregando ? "Calculando…" : "Simular"}
              </Botao>
            </form>
          </CartaoCorpo>
        </Cartao>

        {/* ---------------------------------------------------- resultados */}
        <div className="min-w-0 space-y-6">
          {erro ? (
            <Alerta severidade="critico" titulo="Não foi possível calcular">
              {erro}
            </Alerta>
          ) : null}

          {resultado ? (
            <>
              <Cartao>
                <CartaoCorpo className="flex flex-wrap items-end justify-between gap-6">
                  <FiguraHeroi
                    rotulo="Preço-alvo recomendado"
                    valor={precoUnitario(precoAlvo ?? "0")}
                    detalhe={`por quilograma · deduções de ${percentual(resultado.deducoes_r)} sobre o preço bruto`}
                  />
                  <div className="flex flex-col items-end gap-2">
                    <StatusFiscalBadge status={resultado.status_fiscal} />
                    <Distintivo
                      tom={resultado.permite_cotacao_definitiva ? "ok" : "atencao"}
                    >
                      {resultado.permite_cotacao_definitiva
                        ? "Pode ser definitiva"
                        : "Apenas estimativa"}
                    </Distintivo>
                  </div>
                </CartaoCorpo>
              </Cartao>

              {!resultado.permite_cotacao_definitiva ? (
                <Alerta
                  severidade="atencao"
                  titulo="Esta cotação não pode ser classificada como definitiva"
                >
                  {resultado.alertas[0] ??
                    "A matriz tributária tem regras provisórias ou vencidas."}
                </Alerta>
              ) : null}

              <EscadaPrecos
                degraus={degraus}
                precoProposto={formulario.preco_proposto || null}
              />

              {avaliacao ? (
                <Cartao>
                  <CartaoCabecalho
                    titulo="Avaliação da proposta"
                    descricao="A alçada considera margem, risco e prazo — não o desconto nominal."
                    acao={
                      <Distintivo tom={avaliacao.bloqueado ? "critico" : "atencao"}>
                        {avaliacao.bloqueado ? "Bloqueada" : "Requer aprovação"}
                      </Distintivo>
                    }
                  />
                  <CartaoCorpo className="space-y-4">
                    <p className="text-sm">{avaliacao.mensagem}</p>
                    <div className="grid gap-6 sm:grid-cols-3">
                      <Indicador
                        rotulo="Preço proposto"
                        valor={precoUnitario(avaliacao.preco_proposto)}
                      />
                      <Indicador
                        rotulo="Valor da concessão"
                        valor={moeda(avaliacao.valor_concessao)}
                        detalhe="diferença para o preço-alvo, no volume cotado"
                      />
                      <Indicador
                        rotulo="Alçada necessária"
                        valor={
                          <span className="text-base">
                            {avaliacao.alcada_necessaria}
                          </span>
                        }
                      />
                    </div>
                  </CartaoCorpo>
                </Cartao>
              ) : null}

              <BarraComposicao
                titulo="Composição do preço-alvo"
                descricao="De onde vem cada centavo. As cores são as mesmas da escada — a mesma camada tem sempre a mesma cor."
                partes={partesPreco}
                total={Number(precoAlvo ?? 0)}
              />

              <Cartao>
                <CartaoCabecalho
                  titulo="Cenários"
                  descricao="Base, otimista, estressado e ponto de equilíbrio — cada um calculado pelo motor, não extrapolado na tela."
                />
                <CartaoCorpo className="px-0 pb-0">
                  <Tabela>
                    <thead>
                      <tr>
                        <Th>Cenário</Th>
                        <Th>Premissa</Th>
                        <Th numerica>Preço-alvo</Th>
                        <Th numerica>Margem</Th>
                        <Th numerica>Δ vs base</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {cenarios.map((cenario) => {
                        const base = cenarios.find((c) => c.base)?.precoAlvo ?? 0;
                        const delta = cenario.precoAlvo - base;
                        return (
                          <LinhaTabela
                            key={cenario.nome}
                            className={cenario.base ? "bg-fundo-sutil" : undefined}
                          >
                            <Td className="font-medium">{cenario.nome}</Td>
                            <Td className="text-texto-suave">{cenario.descricao}</Td>
                            <Td numerica>{precoUnitario(cenario.precoAlvo)}</Td>
                            <Td numerica>{percentual(cenario.margem)}</Td>
                            <Td numerica>
                              {cenario.base
                                ? "—"
                                : `${delta >= 0 ? "+" : "−"} ${precoUnitario(Math.abs(delta))}`}
                            </Td>
                          </LinhaTabela>
                        );
                      })}
                    </tbody>
                  </Tabela>
                </CartaoCorpo>
              </Cartao>

              {precoMaximo ? (
                <Cartao>
                  <CartaoCabecalho
                    titulo="Preço máximo de compra"
                    descricao="Quando o preço de venda é ditado pelo mercado, a decisão real está na compra."
                  />
                  <CartaoCorpo>
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                      <Indicador
                        rotulo="Máximo por kg aceito"
                        valor={precoUnitario(precoMaximo.preco_maximo_unitario)}
                        destaque
                      />
                      <Indicador
                        rotulo="Receita líquida esperada"
                        valor={moeda(precoMaximo.receita_liquida_total)}
                      />
                      <Indicador
                        rotulo="Demais custos"
                        valor={moeda(precoMaximo.demais_custos)}
                      />
                      <Indicador
                        rotulo="Lucro-alvo"
                        valor={moeda(precoMaximo.lucro_alvo)}
                      />
                    </div>
                    <p className="mt-4 text-xs text-texto-tenue">
                      O divisor é a quantidade <strong>aceita</strong>, não a
                      vendável: paga-se pelo que entra e vende-se o que sobra.
                    </p>
                  </CartaoCorpo>
                </Cartao>
              ) : null}

              <MemoriaCalculo memoria={resultado.memoria} />
            </>
          ) : null}
        </div>
      </div>
    </>
  );
}
