"use client";

/**
 * Painel gerencial (secao 12.3).
 *
 * Indicador que a base nao sustenta nao aparece zerado nem estimado: aparece
 * declarado, com o motivo. Um painel incompleto e util; um painel que inventa
 * numero destroi a confianca em todos os outros.
 */

import * as React from "react";

import {
  BarrasNominais,
  FiguraHeroi,
  Medidor,
  type ItemBarra,
} from "@/components/dominio/graficos";
import { Alerta, Indicador, Rendimento } from "@/components/dominio/indicadores";
import { CabecalhoPagina } from "@/components/layout/pagina";
import {
  Botao,
  Campo,
  Cartao,
  CartaoCabecalho,
  CartaoCorpo,
  Distintivo,
  Entrada,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import { moeda, numero, percentual, peso, precoUnitario } from "@/lib/formato";
import type { Painel } from "@/lib/tipos";

export default function PaginaPainel() {
  const [periodo, setPeriodo] = React.useState({ de: "", ate: "" });
  const [painel, setPainel] = React.useState<Painel | null>(null);
  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(true);

  const carregar = React.useCallback(async (de: string, ate: string) => {
    setCarregando(true);
    setErro(null);
    try {
      const parametros = new URLSearchParams();
      if (de) parametros.set("de", de);
      if (ate) parametros.set("ate", ate);
      const sufixo = parametros.toString() ? `?${parametros}` : "";
      setPainel(await api.get<Painel>(`/painel/indicadores${sufixo}`));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
      setPainel(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  React.useEffect(() => {
    void carregar("", "");
  }, [carregar]);

  const margens: ItemBarra[] = (painel?.margem_por_material ?? []).map((m) => ({
    rotulo: m.material_descricao,
    valor: Number(m.margem_contribuicao_por_kg),
    detalhe: `${percentual(m.margem_percentual)} sobre o preço estimado · ${peso(m.quantidade_kg)}`,
  }));

  const ociosidade: ItemBarra[] = (painel?.ociosidade_por_atividade ?? [])
    .map((o) => ({
      rotulo: o.atividade_nome,
      valor: Number(o.custo_ociosidade),
      detalhe: `ocupação de ${percentual(o.percentual_ocupacao, 2)} — ${numero(o.utilizacao_real, 1)} de ${numero(o.capacidade_pratica, 0)} ${o.unidade_direcionador}`,
    }))
    // Grafico de magnitude ordena por magnitude: a lista de medidores acima ja
    // responde "onde sobra capacidade"; aqui a pergunta e "onde custa mais".
    .sort((a, b) => b.valor - a.valor);

  return (
    <>
      <CabecalhoPagina
        titulo="Painel gerencial"
        descricao="Indicadores apurados a partir dos lotes do período. A ociosidade aparece separada do custo dos produtos, como a especificação exige."
      />

      {/* Filtros em uma linha, acima de tudo que eles delimitam. */}
      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(evento) => {
          evento.preventDefault();
          void carregar(periodo.de, periodo.ate);
        }}
      >
        <div className="w-40">
          <Campo rotulo="De">
            <Entrada
              type="date"
              value={periodo.de}
              onChange={(e) => setPeriodo((p) => ({ ...p, de: e.target.value }))}
            />
          </Campo>
        </div>
        <div className="w-40">
          <Campo rotulo="Até">
            <Entrada
              type="date"
              value={periodo.ate}
              onChange={(e) => setPeriodo((p) => ({ ...p, ate: e.target.value }))}
            />
          </Campo>
        </div>
        <Botao type="submit" variante="secundario" disabled={carregando}>
          Aplicar
        </Botao>
        {periodo.de || periodo.ate ? (
          <Botao
            type="button"
            variante="fantasma"
            onClick={() => {
              setPeriodo({ de: "", ate: "" });
              void carregar("", "");
            }}
          >
            Limpar
          </Botao>
        ) : null}
      </form>

      {erro ? (
        <Alerta severidade="critico" titulo="Não foi possível carregar o painel">
          {erro}
        </Alerta>
      ) : null}

      {painel ? (
        // Durante o recarregamento o painel anterior fica visivel a meia
        // opacidade: sem esqueleto, sem salto de layout.
        <div className={carregando ? "space-y-6 opacity-60" : "space-y-6"}>
          {painel.alertas.length ? (
            <Alerta
              severidade="atencao"
              titulo={`${painel.alertas.length} alerta(s) do período`}
            >
              <ul className="list-disc space-y-1 pl-4">
                {painel.alertas.map((alerta) => (
                  <li key={alerta}>{alerta}</li>
                ))}
              </ul>
            </Alerta>
          ) : null}

          <Cartao>
            <CartaoCorpo className="flex flex-wrap items-end justify-between gap-8">
              <FiguraHeroi
                rotulo="Custo por tonelada vendável"
                valor={moeda(painel.custo_por_tonelada_vendavel)}
                detalhe={`${painel.lotes_apurados} lote(s) apurado(s) · ${peso(painel.quantidade_vendavel_kg)} vendáveis`}
                alerta={
                  painel.lotes_com_erro > 0
                    ? `${painel.lotes_com_erro} lote(s) não apurado(s) e fora das somas`
                    : undefined
                }
              />
              <div className="flex flex-wrap gap-8">
                <div className="space-y-1">
                  <p className="text-xs font-medium tracking-wide text-texto-tenue uppercase">
                    Rendimento médio
                  </p>
                  <div className="pt-1">
                    <Rendimento valor={painel.rendimento_medio} />
                  </div>
                </div>
                <Indicador
                  rotulo="Preço médio de compra"
                  valor={precoUnitario(painel.preco_medio_compra_kg)}
                />
                <Indicador
                  rotulo="Ciclo financeiro"
                  valor={`${numero(painel.dias_ciclo_financeiro, 0)} dias`}
                  detalhe={`capital empregado ${moeda(painel.capital_empregado)}`}
                />
              </div>
            </CartaoCorpo>
          </Cartao>

          <div className="grid gap-6 lg:grid-cols-2">
            <Cartao>
              <CartaoCabecalho
                titulo="Composição do custo do período"
                descricao="Aquisição, transformação e capital — a ociosidade fica fora, por construção."
              />
              <CartaoCorpo className="space-y-4">
                <Indicador
                  rotulo="Aquisição"
                  valor={moeda(painel.custo_aquisicao_total)}
                />
                <Indicador
                  rotulo="Transformação (ABC)"
                  valor={moeda(painel.custo_transformacao_total)}
                />
                <Indicador
                  rotulo="Capital de giro"
                  valor={moeda(painel.custo_capital_total)}
                />
                <div className="border-t border-borda pt-4">
                  <Indicador
                    rotulo="Custo total"
                    valor={moeda(painel.custo_total)}
                    destaque
                  />
                </div>
              </CartaoCorpo>
            </Cartao>

            <Cartao>
              <CartaoCabecalho
                titulo="Massa e perdas"
                descricao="Perda normal integra o rendimento; perda anormal é desvio do período."
              />
              <CartaoCorpo className="space-y-4">
                <Indicador rotulo="Aceita" valor={peso(painel.quantidade_aceita_kg)} />
                <Indicador
                  rotulo="Vendável"
                  valor={peso(painel.quantidade_vendavel_kg)}
                />
                <Indicador rotulo="Rejeito" valor={peso(painel.rejeito_kg)} />
                <div className="grid grid-cols-2 gap-4 border-t border-borda pt-4">
                  <Indicador
                    rotulo="Perda normal"
                    valor={peso(painel.perda_normal_kg)}
                  />
                  <Indicador
                    rotulo="Perda anormal"
                    valor={peso(painel.perda_anormal_kg)}
                    detalhe={
                      Number(painel.perda_anormal_kg) > 0
                        ? "fora do custo-padrão"
                        : undefined
                    }
                  />
                </div>
              </CartaoCorpo>
            </Cartao>
          </div>

          <BarrasNominais
            titulo="Margem de contribuição por material"
            descricao="Preço estimado de venda menos o custo variável por quilograma. Enquanto não houver venda faturada, é margem esperada."
            itens={margens}
            formatarValor={(valor) => precoUnitario(valor)}
            rotuloColuna="MC por kg"
          />

          <Cartao>
            <CartaoCabecalho
              titulo="Ocupação por atividade"
              descricao="A capacidade paga e não utilizada é custo do período, nunca do produto."
              acao={
                <Distintivo tom="atencao">
                  ociosidade {moeda(painel.custo_ociosidade_total)}
                </Distintivo>
              }
            />
            <CartaoCorpo className="space-y-5">
              {painel.ociosidade_por_atividade.length === 0 ? (
                <p className="text-sm text-texto-suave">
                  Nenhuma atividade apontada no período.
                </p>
              ) : (
                painel.ociosidade_por_atividade.map((atividade) => (
                  <Medidor
                    key={atividade.atividade_codigo}
                    rotulo={atividade.atividade_nome}
                    fracao={Number(atividade.percentual_ocupacao)}
                    detalhe={`${numero(atividade.utilizacao_real, 1)} de ${numero(atividade.capacidade_pratica, 0)} ${atividade.unidade_direcionador} · ocioso ${moeda(atividade.custo_ociosidade)}`}
                  />
                ))
              )}
            </CartaoCorpo>
          </Cartao>

          <BarrasNominais
            titulo="Custo de ociosidade por atividade"
            descricao="Onde a capacidade não utilizada está custando mais."
            itens={ociosidade}
            formatarValor={(valor) => moeda(valor)}
            rotuloColuna="Custo ocioso"
          />

          <Cartao>
            <CartaoCabecalho
              titulo="Créditos tributários"
              descricao="Crédito condicionado não reduziu custo algum — está aqui para ser cobrado, não para ser comemorado."
            />
            <CartaoCorpo>
              <div className="grid gap-6 sm:grid-cols-2">
                <Indicador
                  rotulo="Confirmados e apropriados"
                  valor={moeda(painel.creditos_confirmados)}
                />
                <Indicador
                  rotulo="Condicionados, aguardando comprovação"
                  valor={moeda(painel.creditos_condicionados)}
                  detalhe="não reduziram o custo"
                />
              </div>
            </CartaoCorpo>
          </Cartao>

          {painel.indisponiveis.length ? (
            <Cartao>
              <CartaoCabecalho
                titulo="Indicadores que esta base ainda não sustenta"
                descricao="Declarados em vez de estimados: a especificação proíbe preencher lacuna com número inventado."
              />
              <CartaoCorpo>
                <dl className="space-y-4">
                  {painel.indisponiveis.map((item) => (
                    <div key={item.nome}>
                      <dt className="text-sm font-medium">{item.nome}</dt>
                      <dd className="mt-0.5 text-sm text-texto-suave">
                        {item.motivo}
                      </dd>
                    </div>
                  ))}
                </dl>
              </CartaoCorpo>
            </Cartao>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
