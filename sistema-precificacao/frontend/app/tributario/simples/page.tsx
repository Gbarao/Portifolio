"use client";

/**
 * Simulador de mudanca de faixa do Simples Nacional.
 *
 * E a tela que materializa o alerta critico da secao 7.7-C: uma venda volumosa
 * pode empurrar a RBT12 para a faixa seguinte e elevar a aliquota efetiva de
 * **todo o faturamento do mes**, nao apenas daquela venda.
 */

import * as React from "react";

import { Alerta, Indicador } from "@/components/dominio/indicadores";
import { CabecalhoPagina } from "@/components/layout/pagina";
import {
  Botao,
  Campo,
  Cartao,
  CartaoCabecalho,
  CartaoCorpo,
  Distintivo,
  Entrada,
  Selecao,
} from "@/components/ui/primitivos";
import { ErroApi, api } from "@/lib/api";
import { moeda, percentual } from "@/lib/formato";

interface Resposta {
  rbt12_antes: string;
  rbt12_depois: string;
  faixa_antes: number;
  faixa_depois: number;
  aliquota_antes: string;
  aliquota_depois: string;
  das_sem_a_venda: string;
  das_com_a_venda: string;
  das_adicional: string;
  das_adicional_atribuivel_a_venda: string;
  aliquota_marginal_da_venda: string;
  mudou_de_faixa: boolean;
  alerta: string | null;
}

export default function PaginaSimples() {
  const [formulario, setFormulario] = React.useState({
    rbt12_atual: "700000",
    receita_mes_sem_a_venda: "60000",
    receita_da_venda: "40000",
    anexo: "ANEXO_II",
  });
  const [resposta, setResposta] = React.useState<Resposta | null>(null);
  const [erro, setErro] = React.useState<string | null>(null);
  const [carregando, setCarregando] = React.useState(false);

  async function simular(evento: React.FormEvent) {
    evento.preventDefault();
    setCarregando(true);
    setErro(null);
    try {
      setResposta(
        await api.post<Resposta>("/tributario/simples/mudanca-faixa", formulario),
      );
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : String(e));
      setResposta(null);
    } finally {
      setCarregando(false);
    }
  }

  function campo(nome: keyof typeof formulario) {
    return {
      value: formulario[nome],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
        setFormulario((f) => ({ ...f, [nome]: e.target.value })),
    };
  }

  return (
    <>
      <CabecalhoPagina
        titulo="Simples Nacional — mudança de faixa"
        descricao="A alíquota efetiva não é a nominal, e uma venda que muda de faixa encarece todo o faturamento do mês. Este simulador mostra o custo tributário marginal real da venda."
      />

      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <Cartao className="h-fit">
          <CartaoCabecalho titulo="Cenário" />
          <CartaoCorpo>
            <form onSubmit={simular} className="space-y-4">
              <Campo
                rotulo="RBT12 atual"
                dica="Receita bruta acumulada nos últimos 12 meses"
              >
                <Entrada inputMode="decimal" {...campo("rbt12_atual")} />
              </Campo>

              <Campo
                rotulo="Faturamento do mês sem esta venda"
                dica="Base que também será atingida pela nova alíquota"
              >
                <Entrada inputMode="decimal" {...campo("receita_mes_sem_a_venda")} />
              </Campo>

              <Campo rotulo="Receita da venda analisada">
                <Entrada inputMode="decimal" {...campo("receita_da_venda")} />
              </Campo>

              <Campo rotulo="Anexo" dica="II para indústria, I para comércio">
                <Selecao {...campo("anexo")}>
                  <option value="ANEXO_I">Anexo I — comércio</option>
                  <option value="ANEXO_II">Anexo II — indústria</option>
                </Selecao>
              </Campo>

              <Botao type="submit" disabled={carregando} className="w-full">
                {carregando ? "Calculando…" : "Simular"}
              </Botao>
            </form>
          </CartaoCorpo>
        </Cartao>

        <div className="space-y-4">
          {erro ? (
            <Alerta severidade="critico" titulo="Não foi possível simular">
              {erro}
            </Alerta>
          ) : null}

          {resposta ? (
            <>
              {resposta.alerta ? (
                <Alerta severidade="critico" titulo="Esta venda muda a faixa">
                  {resposta.alerta}
                </Alerta>
              ) : (
                <Alerta severidade="info" titulo="A venda não muda de faixa">
                  A alíquota efetiva permanece em{" "}
                  {percentual(resposta.aliquota_antes, 4)}.
                </Alerta>
              )}

              <Cartao>
                <CartaoCabecalho
                  titulo="Efeito no DAS do mês"
                  acao={
                    resposta.mudou_de_faixa ? (
                      <Distintivo tom="critico">
                        Faixa {resposta.faixa_antes} → {resposta.faixa_depois}
                      </Distintivo>
                    ) : (
                      <Distintivo tom="ok">Faixa {resposta.faixa_antes}</Distintivo>
                    )
                  }
                />
                <CartaoCorpo>
                  <div className="grid gap-6 sm:grid-cols-2">
                    <Indicador
                      rotulo="Alíquota efetiva antes"
                      valor={percentual(resposta.aliquota_antes, 4)}
                    />
                    <Indicador
                      rotulo="Alíquota efetiva depois"
                      valor={percentual(resposta.aliquota_depois, 4)}
                    />
                    <Indicador
                      rotulo="DAS adicional do mês"
                      valor={moeda(resposta.das_adicional)}
                      detalhe="diferença entre o mês com e sem a venda"
                    />
                    <Indicador
                      rotulo="Alíquota marginal real"
                      valor={percentual(resposta.aliquota_marginal_da_venda, 4)}
                      detalhe="o que a venda custa de fato"
                      destaque
                    />
                  </div>

                  {resposta.mudou_de_faixa ? (
                    <p className="mt-5 rounded-lg border border-borda bg-fundo-sutil px-4 py-3 text-sm text-texto-suave">
                      Do DAS adicional,{" "}
                      <span className="numerico font-medium text-texto">
                        {moeda(resposta.das_adicional_atribuivel_a_venda)}
                      </span>{" "}
                      recai sobre o faturamento que já existia — é o custo
                      escondido que a mudança de faixa joga sobre as outras
                      vendas do mês.
                    </p>
                  ) : null}
                </CartaoCorpo>
              </Cartao>
            </>
          ) : (
            <Cartao>
              <CartaoCorpo className="py-14 text-center text-sm text-texto-suave">
                Informe o cenário e clique em simular.
              </CartaoCorpo>
            </Cartao>
          )}
        </div>
      </div>
    </>
  );
}
