"use client";

/**
 * Graficos em SVG inline.
 *
 * Sem biblioteca de charts de proposito: as especificacoes de marca deste
 * sistema (barra de no maximo 24px, ponta arredondada so no lado do dado,
 * 2px de respiro entre barras vizinhas, grade em fio de cabelo) sao mais
 * simples de acertar desenhando do que de contornar em uma lib generica.
 *
 * Regras que valem para todos os graficos daqui:
 *
 * - toda cor de dado veio do validador de paleta, nao do gosto;
 * - texto nunca veste a cor da serie -- a identidade vem da marca colorida
 *   ao lado, e o texto usa os tokens de tinta;
 * - todo grafico tem gemeo em tabela, para quem nao le cor nem passa o mouse;
 * - rotulo que nao cabe dentro da barra vai para fora dela, nunca e cortado.
 */

import * as React from "react";

import { Botao } from "@/components/ui/primitivos";
import { moeda, numero, percentual, precoUnitario } from "@/lib/formato";
import { cx } from "@/lib/utilitarios";
import type { CamadaPreco } from "@/lib/tipos";

/* ------------------------------------------------------------ fundamentos */

const ALTURA_BARRA = 22; // <= 24px: a barra nunca preenche a faixa toda
const RESPIRO = 10; // espaco entre barras vizinhas, em superficie
const RAIO = 4; // ponta arredondada no lado do dado

/** Caminho de barra horizontal: quadrada na linha de base, arredondada na ponta. */
function barraHorizontal(x0: number, y: number, largura: number, altura: number) {
  const r = Math.min(RAIO, Math.max(0, largura));
  const x1 = x0 + largura;
  if (largura <= 0.5) return `M${x0},${y} L${x0},${y + altura}`;
  return [
    `M${x0},${y}`,
    `H${x1 - r}`,
    `A${r},${r} 0 0 1 ${x1},${y + r}`,
    `V${y + altura - r}`,
    `A${r},${r} 0 0 1 ${x1 - r},${y + altura}`,
    `H${x0}`,
    "Z",
  ].join(" ");
}

/** Casca comum: titulo, alternador de tabela e area do grafico. */
function Moldura({
  titulo,
  descricao,
  tabela,
  children,
}: {
  titulo: string;
  descricao?: string;
  tabela: React.ReactNode;
  children: React.ReactNode;
}) {
  const [verTabela, setVerTabela] = React.useState(false);

  return (
    <section className="rounded-xl border border-borda bg-fundo-elevado">
      <header className="flex items-start justify-between gap-4 border-b border-borda px-5 py-4">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold tracking-tight">{titulo}</h3>
          {descricao ? (
            <p className="mt-1 text-sm text-texto-suave">{descricao}</p>
          ) : null}
        </div>
        <Botao
          variante="fantasma"
          tamanho="sm"
          onClick={() => setVerTabela((v) => !v)}
          aria-pressed={verTabela}
        >
          {verTabela ? "Ver gráfico" : "Ver tabela"}
        </Botao>
      </header>
      <div className="px-5 py-4">{verTabela ? tabela : children}</div>
    </section>
  );
}

function TabelaSimples({
  colunas,
  linhas,
}: {
  colunas: string[];
  linhas: (string | number)[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr>
            {colunas.map((coluna, indice) => (
              <th
                key={coluna}
                className={cx(
                  "border-b border-borda px-3 py-2 text-xs font-medium tracking-wide text-texto-tenue uppercase",
                  indice === 0 ? "text-left" : "text-right",
                )}
              >
                {coluna}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {linhas.map((linha) => (
            <tr key={String(linha[0])}>
              {linha.map((celula, indice) => (
                <td
                  key={indice}
                  className={cx(
                    "border-b border-borda/60 px-3 py-2",
                    indice === 0 ? "text-left" : "numerico text-right",
                  )}
                >
                  {celula}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Dica flutuante: o valor lidera, o rotulo acompanha. */
function DicaAncorada({
  esquerdaPercentual,
  topoPercentual,
  titulo,
  valor,
  detalhe,
}: {
  esquerdaPercentual: number;
  topoPercentual: number;
  titulo: string;
  valor: string;
  detalhe?: string;
}) {
  return (
    <div
      className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-lg border border-borda bg-fundo-elevado px-3 py-2 shadow-lg"
      style={{ left: `${esquerdaPercentual}%`, top: `${topoPercentual}%` }}
      role="status"
    >
      <p className="numerico text-sm font-semibold">{valor}</p>
      <p className="text-xs text-texto-suave">{titulo}</p>
      {detalhe ? <p className="text-xs text-texto-tenue">{detalhe}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------- Escada de precos */

const COR_CAMADA: Record<CamadaPreco, string> = {
  CAIXA: "var(--camada-caixa)",
  CONTRIBUICAO: "var(--camada-contribuicao)",
  OPERACIONAL: "var(--camada-operacional)",
  SUSTENTAVEL: "var(--camada-sustentavel)",
  ALVO: "var(--camada-alvo)",
  MERCADO_COMPARAVEL: "var(--camada-mercado)",
};

const NOME_CAMADA: Record<CamadaPreco, string> = {
  CAIXA: "Caixa",
  CONTRIBUICAO: "Contribuição",
  OPERACIONAL: "Operacional",
  SUSTENTAVEL: "Sustentável",
  ALVO: "Alvo",
  MERCADO_COMPARAVEL: "Mercado",
};

export interface DegrauEscada {
  camada: CamadaPreco;
  preco: string;
  custo: string;
  margem: string;
  finalidade: string;
}

export function EscadaPrecos({
  degraus,
  precoProposto,
}: {
  degraus: DegrauEscada[];
  precoProposto?: string | null;
}) {
  const [ativo, setAtivo] = React.useState<number | null>(null);

  const larguraRotulo = 108;
  const larguraValor = 92;
  const alturaLinha = ALTURA_BARRA + RESPIRO;
  const altura = degraus.length * alturaLinha + 8;
  const largura = 640;
  const larguraPlot = largura - larguraRotulo - larguraValor;

  const valores = degraus.map((d) => Number(d.preco));
  const proposto = precoProposto ? Number(precoProposto) : null;
  const maximo = Math.max(...valores, proposto ?? 0) * 1.04 || 1;
  const escala = (valor: number) => (valor / maximo) * larguraPlot;

  return (
    <Moldura
      titulo="Escada de preços"
      descricao="Cada degrau tem finalidade própria. Um preço nunca circula sem dizer de qual camada de custo ele saiu."
      tabela={
        <TabelaSimples
          colunas={["Camada", "Custo unitário", "Preço", "Margem", "Finalidade"]}
          linhas={degraus.map((d) => [
            NOME_CAMADA[d.camada],
            precoUnitario(d.custo),
            precoUnitario(d.preco),
            percentual(d.margem),
            d.finalidade,
          ])}
        />
      }
    >
      <div className="relative">
        <svg
          viewBox={`0 0 ${largura} ${altura}`}
          className="w-full"
          role="img"
          aria-label={`Escada de preços com ${degraus.length} camadas, de ${precoUnitario(degraus[0]?.preco)} a ${precoUnitario(degraus[degraus.length - 1]?.preco)} por quilograma`}
        >
          {/* Grade em fio de cabelo, sempre solida e recessiva. */}
          {[0.25, 0.5, 0.75, 1].map((fracao) => (
            <line
              key={fracao}
              x1={larguraRotulo + larguraPlot * fracao}
              x2={larguraRotulo + larguraPlot * fracao}
              y1={0}
              y2={altura - 8}
              stroke="var(--grade)"
              strokeWidth={1}
            />
          ))}

          {degraus.map((degrau, indice) => {
            const y = indice * alturaLinha;
            const largurabarra = escala(Number(degrau.preco));
            return (
              <g
                key={degrau.camada}
                onPointerEnter={() => setAtivo(indice)}
                onPointerLeave={() => setAtivo(null)}
                onFocus={() => setAtivo(indice)}
                onBlur={() => setAtivo(null)}
                tabIndex={0}
                aria-label={`${NOME_CAMADA[degrau.camada]}: ${precoUnitario(degrau.preco)} por quilograma`}
                className="cursor-default focus:outline-none"
              >
                {/* Alvo de toque maior que a marca: a faixa inteira responde. */}
                <rect
                  x={0}
                  y={y - RESPIRO / 2}
                  width={largura}
                  height={alturaLinha}
                  fill="transparent"
                />
                <text
                  x={larguraRotulo - 10}
                  y={y + ALTURA_BARRA / 2 + 4}
                  textAnchor="end"
                  className="fill-texto-suave text-[11px]"
                >
                  {NOME_CAMADA[degrau.camada]}
                </text>
                <path
                  d={barraHorizontal(larguraRotulo, y, largurabarra, ALTURA_BARRA)}
                  fill={COR_CAMADA[degrau.camada]}
                  opacity={ativo === null || ativo === indice ? 1 : 0.55}
                />
                <text
                  x={larguraRotulo + largurabarra + 8}
                  y={y + ALTURA_BARRA / 2 + 4}
                  className="numerico fill-texto text-[11px] font-medium"
                >
                  {precoUnitario(degrau.preco)}
                </text>
              </g>
            );
          })}

          {/* Proposta como linha de referencia: o leitor ve onde ela cai. */}
          {proposto !== null ? (
            <g>
              <line
                x1={larguraRotulo + escala(proposto)}
                x2={larguraRotulo + escala(proposto)}
                y1={-2}
                y2={altura - 6}
                stroke="var(--critico)"
                strokeWidth={2}
              />
              <text
                x={larguraRotulo + escala(proposto)}
                y={altura - 0}
                textAnchor="middle"
                className="numerico fill-critico text-[10px] font-medium"
              >
                proposta {precoUnitario(proposto)}
              </text>
            </g>
          ) : null}
        </svg>

        {/* A dica e ancorada em porcentagem porque o SVG escala com a largura
            do contêiner; coordenadas do viewBox nao valem como pixels de tela. */}
        {ativo !== null ? (
          <DicaAncorada
            esquerdaPercentual={38}
            topoPercentual={
              ((ativo * (ALTURA_BARRA + RESPIRO) + ALTURA_BARRA / 2) / altura) * 100
            }
            titulo={NOME_CAMADA[degraus[ativo].camada]}
            valor={precoUnitario(degraus[ativo].preco)}
            detalhe={degraus[ativo].finalidade}
          />
        ) : null}
      </div>

      <p className="mt-3 text-xs text-texto-tenue">
        A cor acompanha a ordem da escada — mais escuro é mais alto na escada,
        não uma categoria diferente.
      </p>
    </Moldura>
  );
}

/* --------------------------------------------- Barras nominais (uma serie) */

export interface ItemBarra {
  rotulo: string;
  valor: number;
  detalhe?: string;
}

/**
 * Categorias nominais -- materiais, atividades -- recebem **a mesma cor**.
 * Colorir cada barra por tamanho gastaria o canal de identidade repetindo
 * o que o comprimento da barra ja diz.
 */
export function BarrasNominais({
  titulo,
  descricao,
  itens,
  formatarValor,
  rotuloColuna = "Valor",
}: {
  titulo: string;
  descricao?: string;
  itens: ItemBarra[];
  formatarValor: (valor: number) => string;
  rotuloColuna?: string;
}) {
  const [ativo, setAtivo] = React.useState<number | null>(null);

  const larguraRotulo = 170;
  const larguraValor = 96;
  const largura = 660;
  const alturaLinha = ALTURA_BARRA + RESPIRO;
  const altura = Math.max(itens.length * alturaLinha, alturaLinha);
  const larguraPlot = largura - larguraRotulo - larguraValor;
  const maximo = Math.max(...itens.map((i) => Math.abs(i.valor)), 0) * 1.04 || 1;

  return (
    <Moldura
      titulo={titulo}
      descricao={descricao}
      tabela={
        <TabelaSimples
          colunas={["Item", rotuloColuna]}
          linhas={itens.map((i) => [i.rotulo, formatarValor(i.valor)])}
        />
      }
    >
      {itens.length === 0 ? (
        <p className="py-8 text-center text-sm text-texto-suave">
          Sem dados no período selecionado.
        </p>
      ) : itens.length === 1 ? (
        // Uma barra so nao compara nada. Vira indicador, que e a forma certa
        // para um numero isolado.
        <div className="space-y-1 py-2">
          <p className="text-sm text-texto-suave">{itens[0].rotulo}</p>
          <p className="numerico text-3xl font-semibold tracking-tight">
            {formatarValor(itens[0].valor)}
          </p>
          {itens[0].detalhe ? (
            <p className="text-xs text-texto-tenue">{itens[0].detalhe}</p>
          ) : null}
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${largura} ${altura}`}
            className="w-full"
            role="img"
            aria-label={`${titulo}: ${itens.length} itens`}
          >
            {[0.5, 1].map((fracao) => (
              <line
                key={fracao}
                x1={larguraRotulo + larguraPlot * fracao}
                x2={larguraRotulo + larguraPlot * fracao}
                y1={0}
                y2={altura}
                stroke="var(--grade)"
                strokeWidth={1}
              />
            ))}

            {itens.map((item, indice) => {
              const y = indice * alturaLinha;
              const larguraBarra = (Math.abs(item.valor) / maximo) * larguraPlot;
              return (
                <g
                  key={item.rotulo}
                  tabIndex={0}
                  aria-label={`${item.rotulo}: ${formatarValor(item.valor)}`}
                  onPointerEnter={() => setAtivo(indice)}
                  onPointerLeave={() => setAtivo(null)}
                  onFocus={() => setAtivo(indice)}
                  onBlur={() => setAtivo(null)}
                  className="cursor-default focus:outline-none"
                >
                  <rect
                    x={0}
                    y={y - RESPIRO / 2}
                    width={largura}
                    height={alturaLinha}
                    fill="transparent"
                  />
                  <text
                    x={larguraRotulo - 10}
                    y={y + ALTURA_BARRA / 2 + 4}
                    textAnchor="end"
                    className="fill-texto-suave text-[11px]"
                  >
                    {item.rotulo.length > 26
                      ? `${item.rotulo.slice(0, 25)}…`
                      : item.rotulo}
                  </text>
                  <path
                    d={barraHorizontal(larguraRotulo, y, larguraBarra, ALTURA_BARRA)}
                    fill={item.valor < 0 ? "var(--dado-reducao)" : "var(--dado)"}
                    opacity={ativo === null || ativo === indice ? 1 : 0.55}
                  />
                  <text
                    x={larguraRotulo + larguraBarra + 8}
                    y={y + ALTURA_BARRA / 2 + 4}
                    className="numerico fill-texto text-[11px] font-medium"
                  >
                    {formatarValor(item.valor)}
                  </text>
                </g>
              );
            })}
          </svg>

          {ativo !== null && itens[ativo].detalhe ? (
            <DicaAncorada
              esquerdaPercentual={45}
              topoPercentual={
                ((ativo * alturaLinha + ALTURA_BARRA / 2) / altura) * 100
              }
              titulo={itens[ativo].rotulo}
              valor={formatarValor(itens[ativo].valor)}
              detalhe={itens[ativo].detalhe}
            />
          ) : null}
        </div>
      )}
    </Moldura>
  );
}

/* -------------------------------------------------------------- Medidor */

/**
 * Razao contra um limite. A trilha vazia e um passo mais claro da mesma
 * rampa -- o estado se le no comprimento e na cor, nunca so na cor.
 */
export function Medidor({
  rotulo,
  fracao,
  detalhe,
}: {
  rotulo: string;
  fracao: number;
  detalhe?: string;
}) {
  const preenchido = Math.max(0, Math.min(1, fracao));
  // A cor acompanha a severidade da ociosidade, com o numero sempre ao lado.
  const cor =
    preenchido >= 0.8
      ? "var(--ok)"
      : preenchido >= 0.5
        ? "var(--atencao)"
        : "var(--critico)";

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm">{rotulo}</span>
        <span className="numerico text-sm font-medium">
          {percentual(preenchido, 1)}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full"
        style={{ background: "color-mix(in oklch, var(--dado) 18%, transparent)" }}
        role="meter"
        aria-valuenow={Math.round(preenchido * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={rotulo}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${preenchido * 100}%`, background: cor }}
        />
      </div>
      {detalhe ? <p className="text-xs text-texto-tenue">{detalhe}</p> : null}
    </div>
  );
}

/* ---------------------------------------------------------- Figura heroi */

/**
 * O numero que a tela lidera. Um por visao, na mesma fonte de todo o resto,
 * com algarismos proporcionais -- tabulares deixam numeros grandes soltos.
 */
export function FiguraHeroi({
  rotulo,
  valor,
  detalhe,
  alerta,
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  alerta?: string;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium tracking-wide text-texto-tenue uppercase">
        {rotulo}
      </p>
      <p className="text-5xl font-semibold tracking-tight">{valor}</p>
      {detalhe ? <p className="text-sm text-texto-suave">{detalhe}</p> : null}
      {alerta ? <p className="text-sm text-critico">{alerta}</p> : null}
    </div>
  );
}

export { NOME_CAMADA, moeda, numero };

/* ------------------------------------------------- Composicao (parte-todo) */

export interface ParteComposicao {
  rotulo: string;
  valor: number;
  cor: string;
}

/**
 * Barra empilhada horizontal para parte-todo.
 *
 * O preco **e** a soma das suas partes, entao a forma certa e a barra
 * empilhada -- nao uma cascata, que existe para mostrar variacao entre dois
 * pontos. As partes seguem a mesma rampa ordinal da escada de precos: a
 * mesma cor significa a mesma camada nos dois graficos.
 */
export function BarraComposicao({
  titulo,
  descricao,
  partes,
  total,
  formatarValor = precoUnitario,
}: {
  titulo: string;
  descricao?: string;
  partes: ParteComposicao[];
  total: number;
  formatarValor?: (valor: number) => string;
}) {
  const [ativo, setAtivo] = React.useState<number | null>(null);

  const largura = 660;
  const alturaBarra = 24;
  const soma = partes.reduce((acumulado, parte) => acumulado + parte.valor, 0) || 1;

  // 2px de superficie separam segmentos vizinhos -- nunca um contorno.
  const gap = 2;
  const larguraUtil = largura - gap * (partes.length - 1);

  let deslocamento = 0;
  const segmentos = partes.map((parte) => {
    const larguraSegmento = (parte.valor / soma) * larguraUtil;
    const x = deslocamento;
    deslocamento += larguraSegmento + gap;
    return { ...parte, x, largura: larguraSegmento };
  });

  return (
    <Moldura
      titulo={titulo}
      descricao={descricao}
      tabela={
        <TabelaSimples
          colunas={["Componente", "Valor", "Participação"]}
          linhas={[
            ...partes.map((parte) => [
              parte.rotulo,
              formatarValor(parte.valor),
              percentual(parte.valor / soma),
            ]),
            ["Total", formatarValor(total), percentual(1)],
          ]}
        />
      }
    >
      <div className="relative">
        <svg
          viewBox={`0 0 ${largura} ${alturaBarra}`}
          className="w-full"
          style={{ height: alturaBarra }}
          preserveAspectRatio="none"
          role="img"
          aria-label={`${titulo}: ${partes.map((p) => `${p.rotulo} ${formatarValor(p.valor)}`).join(", ")}`}
        >
          {segmentos.map((segmento, indice) => (
            <rect
              key={segmento.rotulo}
              x={segmento.x}
              y={0}
              width={Math.max(segmento.largura, 1)}
              height={alturaBarra}
              rx={indice === 0 || indice === segmentos.length - 1 ? 4 : 0}
              fill={segmento.cor}
              opacity={ativo === null || ativo === indice ? 1 : 0.55}
              tabIndex={0}
              aria-label={`${segmento.rotulo}: ${formatarValor(segmento.valor)}`}
              onPointerEnter={() => setAtivo(indice)}
              onPointerLeave={() => setAtivo(null)}
              onFocus={() => setAtivo(indice)}
              onBlur={() => setAtivo(null)}
              className="cursor-default focus:outline-none"
            />
          ))}
        </svg>

        {ativo !== null ? (
          <DicaAncorada
            esquerdaPercentual={
              ((segmentos[ativo].x + segmentos[ativo].largura / 2) / largura) * 100
            }
            topoPercentual={0}
            titulo={segmentos[ativo].rotulo}
            valor={formatarValor(segmentos[ativo].valor)}
            detalhe={`${percentual(segmentos[ativo].valor / soma)} do preço`}
          />
        ) : null}
      </div>

      {/* Legenda sempre presente: a identidade nunca depende so da cor. */}
      <ul className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
        {partes.map((parte) => (
          <li key={parte.rotulo} className="flex items-baseline gap-2 text-xs">
            <span
              className="mt-0.5 size-2.5 shrink-0 rounded-sm"
              style={{ background: parte.cor }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-texto-suave">
              {parte.rotulo}
            </span>
            <span className="numerico font-medium">{formatarValor(parte.valor)}</span>
          </li>
        ))}
      </ul>

      <p className="mt-4 border-t border-borda pt-3 text-sm">
        <span className="text-texto-suave">Preço-alvo</span>{" "}
        <span className="numerico ml-2 font-semibold">{formatarValor(total)}</span>
      </p>
    </Moldura>
  );
}
