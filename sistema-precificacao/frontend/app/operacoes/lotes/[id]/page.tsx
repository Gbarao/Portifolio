import Link from "next/link";

import { MemoriaCalculo } from "@/components/dominio/memoria-calculo";
import {
  Alerta,
  Indicador,
  ListaAlertas,
  Rendimento,
} from "@/components/dominio/indicadores";
import { CabecalhoPagina } from "@/components/layout/pagina";
import { ErroDeCarregamento } from "@/components/ui/estado-api";
import {
  Cartao,
  CartaoCabecalho,
  CartaoCorpo,
  Distintivo,
  LinhaTabela,
  Tabela,
  Td,
  Th,
} from "@/components/ui/primitivos";
import { api } from "@/lib/api";
import { moeda, peso, percentual, precoUnitario } from "@/lib/formato";
import type { ResultadoLote } from "@/lib/tipos";

export const dynamic = "force-dynamic";

export default async function PaginaResultadoLote({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let resultado: ResultadoLote | null = null;
  let erro: unknown = null;

  try {
    resultado = await api.get<ResultadoLote>(`/lotes/${id}/resultado`);
  } catch (e) {
    erro = e;
  }

  if (erro || !resultado) {
    return (
      <>
        <CabecalhoPagina titulo="Resultado do lote" />
        <ErroDeCarregamento erro={erro} />
        <p className="mt-4 text-sm">
          <Link href="/operacoes/lotes" className="text-marca-700 hover:underline">
            ← Voltar para a lista de lotes
          </Link>
        </p>
      </>
    );
  }

  const { balanco } = resultado;
  const massaAberta = !balanco.dentro_da_tolerancia;

  return (
    <>
      <CabecalhoPagina
        titulo={`Lote ${resultado.codigo}`}
        descricao="Reconciliação entre compra, balanço de massa, atividades consumidas e custo final por quilograma vendável."
        acoes={
          <Link
            href="/operacoes/lotes"
            className="text-sm font-medium text-marca-700 hover:underline"
          >
            ← Lotes
          </Link>
        }
      />

      <div className="space-y-6">
        {massaAberta ? (
          <Alerta severidade="critico" titulo="Balanço de massa fora da tolerância">
            <p>
              Diferença não explicada de {peso(balanco.diferenca_nao_explicada)}. O
              encerramento do lote está bloqueado até que a divergência seja
              justificada e aprovada.
            </p>
            <p className="mt-1 text-xs text-texto-suave">
              A diferença fica visível de propósito: somá-la ao rendimento
              esconderia furto, erro de balança ou apontamento faltante.
            </p>
          </Alerta>
        ) : null}

        <ListaAlertas alertas={resultado.alertas} />

        {/* ------------------------------------------------ Balanço de massa */}
        <Cartao>
          <CartaoCabecalho
            titulo="Balanço de massa"
            descricao="Pesos são grandezas distintas e não intercambiáveis."
            acao={
              balanco.dentro_da_tolerancia ? (
                <Distintivo tom="ok">Fecha na tolerância</Distintivo>
              ) : (
                <Distintivo tom="critico">Fora da tolerância</Distintivo>
              )
            }
          />
          <CartaoCorpo>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <Indicador rotulo="Bruta" valor={peso(balanco.quantidade_bruta)} />
              <Indicador
                rotulo="Aceita"
                valor={peso(balanco.quantidade_aceita)}
                detalhe={`recusado: ${peso(balanco.quantidade_recusada)}`}
              />
              <Indicador
                rotulo="Vendável"
                valor={peso(balanco.quantidade_vendavel)}
                destaque
              />
              <div className="space-y-1">
                <p className="text-xs font-medium tracking-wide text-texto-tenue uppercase">
                  Rendimento
                </p>
                <div className="pt-1">
                  <Rendimento valor={balanco.rendimento} />
                </div>
                <p className="text-xs text-texto-suave">
                  rejeito: {percentual(balanco.taxa_rejeito)}
                </p>
              </div>
            </div>

            <div className="mt-6 grid gap-4 border-t border-borda pt-4 sm:grid-cols-3">
              <Indicador rotulo="Rejeito" valor={peso(balanco.quantidade_rejeito)} />
              <Indicador
                rotulo="Perda normal"
                valor={peso(balanco.perda_normal)}
                detalhe="integra o rendimento esperado"
              />
              <Indicador
                rotulo="Perda anormal"
                valor={peso(balanco.perda_anormal)}
                detalhe="desvio do período, fora do custo-padrão"
              />
            </div>
          </CartaoCorpo>
        </Cartao>

        {/* -------------------------------------------------------- Custos */}
        <Cartao>
          <CartaoCabecalho
            titulo="Composição do custo"
            descricao="O custo por quilograma vendável é maior que o por quilograma aceito sempre que houver perda — é assim que a perda é transferida ao produto."
          />
          <CartaoCorpo>
            <Tabela>
              <thead>
                <tr>
                  <Th>Componente</Th>
                  <Th numerica>Valor</Th>
                  <Th numerica>Por kg vendável</Th>
                </tr>
              </thead>
              <tbody>
                <LinhaTabela>
                  <Td>Aquisição líquida</Td>
                  <Td numerica>{moeda(resultado.custo_aquisicao_total)}</Td>
                  <Td numerica>
                    {precoUnitario(resultado.custo_aquisicao_por_kg_vendavel)}
                  </Td>
                </LinhaTabela>
                <LinhaTabela>
                  <Td>Transformação (ABC)</Td>
                  <Td numerica>{moeda(resultado.custo_transformacao)}</Td>
                  <Td numerica className="text-texto-tenue">
                    —
                  </Td>
                </LinhaTabela>
                <LinhaTabela>
                  <Td>Capital de giro</Td>
                  <Td numerica>{moeda(resultado.custo_capital)}</Td>
                  <Td numerica className="text-texto-tenue">
                    —
                  </Td>
                </LinhaTabela>
                <LinhaTabela className="bg-fundo-sutil font-medium">
                  <Td>Custo total do lote</Td>
                  <Td numerica>{moeda(resultado.custo_total)}</Td>
                  <Td numerica>{precoUnitario(resultado.custo_unitario_vendavel)}</Td>
                </LinhaTabela>
              </tbody>
            </Tabela>

            <div className="mt-5 grid gap-6 border-t border-borda pt-4 sm:grid-cols-2">
              <Indicador
                rotulo="Custo por kg aceito"
                valor={precoUnitario(resultado.custo_aquisicao_por_kg_aceito)}
                detalhe="o que foi pago pelo material que entrou"
              />
              <Indicador
                rotulo="Custo por kg vendável"
                valor={precoUnitario(resultado.custo_aquisicao_por_kg_vendavel)}
                detalhe="o mesmo custo distribuído no que sobrou para vender"
              />
            </div>

            {Number(resultado.creditos_pendentes) > 0 ? (
              <Alerta severidade="atencao" className="mt-5">
                Crédito condicionado de {moeda(resultado.creditos_pendentes)} não
                reduziu o custo: depende de confirmação documental antes de ser
                apropriado.
              </Alerta>
            ) : null}
          </CartaoCorpo>
        </Cartao>

        <MemoriaCalculo memoria={resultado.memoria} />
      </div>
    </>
  );
}
