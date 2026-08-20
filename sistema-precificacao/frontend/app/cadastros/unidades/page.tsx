"use client";

import * as React from "react";

import { CabecalhoPagina } from "@/components/layout/pagina";
import { ErroDeCarregamento } from "@/components/ui/estado-api";
import { Indicador } from "@/components/dominio/indicadores";
import {
  Cartao,
  CartaoCabecalho,
  CartaoCorpo,
  Distintivo,
  Vazio,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import { percentual, rotulo, vigencia } from "@/lib/formato";
import type { Parametro, Unidade } from "@/lib/tipos";

async function parametroDa(unidade: Unidade): Promise<Parametro | null> {
  try {
    return await api.get<Parametro>(`/unidades/${unidade.id}/parametros`);
  } catch (e) {
    // 404 aqui significa "sem parametro vigente hoje", nao falha: a unidade
    // aparece na lista com o aviso, em vez de derrubar a pagina inteira.
    if (e instanceof ErroApi && e.status === 404) return null;
    throw e;
  }
}

export default function PaginaUnidades() {
  const [unidades, setUnidades] = React.useState<Unidade[]>([]);
  const [parametros, setParametros] = React.useState<(Parametro | null)[]>([]);
  const [erro, setErro] = React.useState<unknown>(null);
  const [carregando, setCarregando] = React.useState(true);

  React.useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const pagina = await api.lista<Unidade>("/unidades?limite=50");
        const encontradas = pagina.itens;
        const params = await Promise.all(encontradas.map(parametroDa));
        if (!cancelado) {
          setUnidades(encontradas);
          setParametros(params);
        }
      } catch (e) {
        if (!cancelado) setErro(e);
      } finally {
        if (!cancelado) setCarregando(false);
      }
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  if (erro) {
    return (
      <>
        <CabecalhoPagina titulo="Unidades e parâmetros" />
        <ErroDeCarregamento erro={erro} />
      </>
    );
  }

  return (
    <>
      <CabecalhoPagina
        titulo="Unidades e parâmetros"
        descricao="Parâmetros são versionados por vigência: alterar uma meta encerra a vigência atual e abre nova, para que cotações antigas continuem reproduzíveis."
      />

      {unidades.length === 0 && !carregando ? (
        <Cartao>
          <Vazio titulo="Nenhuma unidade cadastrada" />
        </Cartao>
      ) : (
        <div className="space-y-4">
          {unidades.map((unidade, indice) => {
            const parametro = parametros[indice];
            return (
              <Cartao key={unidade.id}>
                <CartaoCabecalho
                  titulo={unidade.nome}
                  descricao={`${unidade.codigo} — ${unidade.municipio}/${unidade.uf}`}
                  acao={
                    parametro ? (
                      <Distintivo tom="marca">
                        {rotulo(parametro.regime_tributario)}
                        {parametro.anexo_simples
                          ? ` · ${rotulo(parametro.anexo_simples)}`
                          : ""}
                      </Distintivo>
                    ) : (
                      <Distintivo tom="critico">Sem parâmetro vigente</Distintivo>
                    )
                  }
                />
                {parametro ? (
                  <CartaoCorpo>
                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
                      <Indicador
                        rotulo="Margem-alvo"
                        valor={percentual(parametro.meta_margem_alvo)}
                      />
                      <Indicador
                        rotulo="Contribuição mínima"
                        valor={percentual(parametro.meta_margem_contribuicao_minima)}
                      />
                      <Indicador
                        rotulo="Taxa de capital (a.a.)"
                        valor={percentual(parametro.taxa_minima_atratividade_anual)}
                      />
                      <Indicador
                        rotulo="Tolerância de massa"
                        valor={percentual(parametro.tolerancia_balanco_massa)}
                        detalhe="Acima disso, o lote não encerra"
                      />
                    </div>
                    <p className="mt-4 text-xs text-texto-tenue">
                      Vigência:{" "}
                      {vigencia(parametro.vigencia_inicio, parametro.vigencia_fim)} ·
                      validade da cotação:{" "}
                      {parametro.horizonte_validade_cotacao_dias} dias
                    </p>
                  </CartaoCorpo>
                ) : (
                  <CartaoCorpo>
                    <p className="text-sm text-texto-suave">
                      Nenhum parâmetro vigente hoje. Sem ele, o cálculo do lote é
                      bloqueado: não há tolerância de massa nem taxa de capital
                      para aplicar.
                    </p>
                  </CartaoCorpo>
                )}
              </Cartao>
            );
          })}
        </div>
      )}
    </>
  );
}
